import polars as pl
import pytest
from pathlib import Path

from pytae.repl import PytaeRepl
from pytae.transpiler import _compile_history_to_python, _compile_history_to_pt


@pytest.fixture
def sample_repl(tmp_path: Path) -> PytaeRepl:
    df1 = pl.DataFrame({
        "sales": [100, -10, 50, None],
        "category": ["A", "B", "A", "B"],
    })
    df2 = pl.DataFrame({
        "sales": [200, 30, -5, 80],
        "category": ["C", "C", "D", "D"],
    })
    repl = PytaeRepl()
    repl.tables["q1"] = df1
    repl.tables["q2"] = df2
    repl.current_df = df1
    repl.path_str = "q1"
    return repl


def test_def_definition_and_inspection(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    
    # 1. Initially no defs
    sample_repl.execute_line("defs", output_fn=output.append)
    assert any("No definitions defined" in line for line in output)
    output.clear()

    # 2. Define a recipe with `def`
    sample_repl.execute_line("def clean = -dropna -filter 'sales > 0'", output_fn=output.append)
    assert any("Defined recipe 'clean'" in line for line in output)
    assert "clean" in sample_repl.defs
    assert sample_repl.defs["clean"] == "-dropna -filter 'sales > 0'"
    output.clear()

    # 3. Inspect the def
    sample_repl.execute_line("def clean", output_fn=output.append)
    assert any("def clean = -dropna -filter 'sales > 0'" in line for line in output)
    output.clear()

    # 4. List defs
    sample_repl.execute_line("defs", output_fn=output.append)
    assert any("Defined recipes (1)" in line for line in output)
    assert any("clean = -dropna -filter 'sales > 0'" in line for line in output)
    output.clear()

    # 5. Status def
    sample_repl.execute_line("status def", output_fn=output.append)
    assert any("Defined recipes (1)" in line for line in output)
    output.clear()

    # 6. Retired macro keyword redirects to def
    sample_repl.execute_line("macro", output_fn=output.append)
    assert any("replaced by 'def'" in line for line in output)
    output.clear()


def test_def_execution_piped_and_assigned(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("def clean = -dropna -filter 'sales > 0'", output_fn=output.append)
    output.clear()

    # Piped assignment: q1_clean = q1 | clean
    sample_repl.execute_line("q1_clean = q1 | clean", output_fn=output.append)
    assert "q1_clean" in sample_repl.tables
    res = sample_repl.tables["q1_clean"]
    assert res.shape == (2, 2)
    assert res["sales"].to_list() == [100, 50]
    output.clear()

    # Piped assignment on another table: q2_clean = q2 | clean
    sample_repl.execute_line("q2_clean = q2 | clean", output_fn=output.append)
    assert "q2_clean" in sample_repl.tables
    res2 = sample_repl.tables["q2_clean"]
    assert res2.shape == (3, 2)
    assert res2["sales"].to_list() == [200, 30, 80]
    output.clear()

    # Chained flag after def: q2_top = q2 | clean -head 1
    sample_repl.execute_line("q2_top = q2 | clean -head 1", output_fn=output.append)
    assert "q2_top" in sample_repl.tables
    assert sample_repl.tables["q2_top"].shape == (1, 2)
    assert sample_repl.tables["q2_top"]["sales"].to_list() == [200]
    output.clear()


def test_def_execution_on_active_table(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("def clean = -dropna -filter 'sales > 0'", output_fn=output.append)
    output.clear()

    # Active table is q1
    sample_repl.execute_line("clean", output_fn=output.append)
    # Prints formatted table preview (non-destructive)
    combined = "\n".join(output)
    assert "100" in combined
    assert "50" in combined
    assert "-10" not in combined
    output.clear()

    # Assign from active table: out = clean
    sample_repl.execute_line("out = clean", output_fn=output.append)
    assert "out" in sample_repl.tables
    assert sample_repl.tables["out"].shape == (2, 2)
    output.clear()


def test_def_removal(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("def m1 = -filter 'sales > 0'", output_fn=output.append)
    sample_repl.execute_line("def m2 = -dropna", output_fn=output.append)
    assert len(sample_repl.defs) == 2
    output.clear()

    # Remove single def
    sample_repl.execute_line("rm def m1", output_fn=output.append)
    assert any("Removed def 'm1'" in line for line in output)
    assert "m1" not in sample_repl.defs
    assert "m2" in sample_repl.defs
    output.clear()

    # Remove all defs
    sample_repl.execute_line("rm def *", output_fn=output.append)
    assert any("Removed all definitions" in line for line in output)
    assert len(sample_repl.defs) == 0
    output.clear()

    # Friendly redirect on rm macro
    sample_repl.execute_line("rm macro m1", output_fn=output.append)
    assert any("replaced by 'def'" in line for line in output)
    output.clear()


def test_def_checkpoints(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("def clean = -dropna -filter 'sales > 0'", output_fn=output.append)
    sample_repl.execute_line("checkpoint baseline", output_fn=output.append)
    output.clear()

    # Remove def
    sample_repl.execute_line("rm def clean", output_fn=output.append)
    assert "clean" not in sample_repl.defs
    output.clear()

    # Restore checkpoint
    sample_repl.execute_line("restore baseline", output_fn=output.append)
    assert "clean" in sample_repl.defs
    assert sample_repl.defs["clean"] == "-dropna -filter 'sales > 0'"


def test_def_python_transpilation() -> None:
    history = [
        "load q1.parquet as q1",
        "load q2.parquet as q2",
        "def clean_orders = -dropna -filter 'sales > 0' -mutate 'tax = sales * 0.08'",
        "q1_clean = q1 | clean_orders",
        "q2_clean = q2 | clean_orders -head 5",
    ]
    py_code = _compile_history_to_python(history, prune_dead=True)

    # 1. Def compiled to a standalone helper function
    assert "def clean_orders(df: pt.DataFrame) -> pt.DataFrame:" in py_code
    assert ".dropna()" in py_code
    assert ".filter('sales > 0')" in py_code
    assert ".mutate('tax = sales * 0.08')" in py_code

    # 2. Call sites transpiled to function calls
    assert "q1_clean = clean_orders(q1)" in py_code
    assert "q2_clean = clean_orders(q2).head(5)" in py_code


def test_def_dead_code_pruning() -> None:
    history = [
        "load q1.parquet as q1",
        "def unused_recipe = -filter 'sales > 1000'",
        "def used_recipe = -dropna",
        "q1_clean = q1 | used_recipe",
    ]
    py_code = _compile_history_to_python(history, prune_dead=True)

    # used_recipe is emitted
    assert "def used_recipe(df: pt.DataFrame) -> pt.DataFrame:" in py_code
    assert "q1_clean = used_recipe(q1)" in py_code

    # unused_recipe was pruned!
    assert "unused_recipe" not in py_code


def test_def_pt_script_transpilation() -> None:
    history = [
        "load q1.parquet as q1",
        "def clean = -dropna -filter 'sales > 0'",
        "q1_clean = q1 | clean",
    ]
    pt_code = _compile_history_to_pt(history, prune_dead=True)

    assert "def clean = -dropna -filter 'sales > 0'" in pt_code
    assert "q1_clean = q1 | clean" in pt_code


def test_parameterized_def_definition_and_inspection(sample_repl: PytaeRepl) -> None:
    output: list[str] = []

    # 1. Define parameterized recipe
    sample_repl.execute_line(
        "def winsorize(col, min_val=0, max_val=1000) = -filter '$col >= $min_val' -mutate '$col = if_else($col > $max_val, $max_val, $col)'",
        output_fn=output.append,
    )
    assert any("Defined recipe 'winsorize(col, min_val=0, max_val=1000)'" in line for line in output)
    assert "winsorize" in sample_repl.defs
    assert sample_repl.def_signatures["winsorize"] == "(col, min_val=0, max_val=1000)"
    output.clear()

    # 2. Inspect definition
    sample_repl.execute_line("def winsorize", output_fn=output.append)
    assert any("def winsorize(col, min_val=0, max_val=1000) = " in line for line in output)
    output.clear()

    # 3. List in defs
    sample_repl.execute_line("defs", output_fn=output.append)
    assert any("winsorize(col, min_val=0, max_val=1000) = " in line for line in output)
    output.clear()

    # 4. Status def
    sample_repl.execute_line("status def", output_fn=output.append)
    assert any("winsorize(col, min_val=0, max_val=1000) = " in line for line in output)
    output.clear()


def test_parameterized_def_execution_piped_and_assigned(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    # q1 has sales: [100, -10, 50, None]
    # q2 has sales: [200, 30, -5, 80]
    sample_repl.execute_line(
        "def threshold(col, val=0) = -dropna '$col' -filter '$col > $val'",
        output_fn=output.append,
    )
    output.clear()

    # 1. Piped positional argument
    sample_repl.execute_line("q1_clean = q1 | threshold(sales, 20)", output_fn=output.append)
    assert "q1_clean" in sample_repl.tables
    res = sample_repl.tables["q1_clean"]
    assert res["sales"].to_list() == [100, 50]
    output.clear()

    # 2. Piped with default value (val=0)
    sample_repl.execute_line("q1_default = q1 | threshold(sales)", output_fn=output.append)
    assert "q1_default" in sample_repl.tables
    assert sample_repl.tables["q1_default"]["sales"].to_list() == [100, 50]
    output.clear()

    # 3. Piped with keyword argument
    sample_repl.execute_line("q2_clean = q2 | threshold(col=sales, val=50)", output_fn=output.append)
    assert "q2_clean" in sample_repl.tables
    assert sample_repl.tables["q2_clean"]["sales"].to_list() == [200, 80]
    output.clear()

    # 4. Piped with chained verbs: -head 1
    sample_repl.execute_line("q2_top = q2 | threshold(sales, 20) -head 1", output_fn=output.append)
    assert "q2_top" in sample_repl.tables
    assert sample_repl.tables["q2_top"].shape == (1, 2)
    assert sample_repl.tables["q2_top"]["sales"].to_list() == [200]
    output.clear()


def test_parameterized_def_on_active_and_targeted_table(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line(
        "def winsorize(col, min_val=0, max_val=100) = -dropna '$col' -filter '$col >= $min_val' -mutate '$col = if_else($col > $max_val, $max_val, $col)'",
        output_fn=output.append,
    )
    output.clear()

    # 1. Bare invocation on active table (q1)
    sample_repl.execute_line("winsorize(sales, min_val=10, max_val=80)", output_fn=output.append)
    combined = "\n".join(output)
    assert "80" in combined  # 100 clamped to 80
    assert "50" in combined
    assert "-10" not in combined
    output.clear()

    # 2. Assignment from active table
    sample_repl.execute_line("out = winsorize(sales, min_val=10, max_val=75)", output_fn=output.append)
    assert "out" in sample_repl.tables
    assert sample_repl.tables["out"]["sales"].to_list() == [75, 50]
    output.clear()

    # 3. Targeted invocation on specific table (q2)
    sample_repl.execute_line("q2_win = q2 winsorize(sales, min_val=0, max_val=100)", output_fn=output.append)
    assert "q2_win" in sample_repl.tables
    assert sample_repl.tables["q2_win"]["sales"].to_list() == [100, 30, 80]
    output.clear()


def test_parameterized_def_error_handling(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line(
        "def test_func(a, b=10) = -filter '$a > $b'",
        output_fn=output.append,
    )
    output.clear()

    # Missing required argument
    sample_repl.execute_line("q1 | test_func()", output_fn=output.append)
    assert any("missing required argument 'a'" in line for line in output)
    output.clear()

    # Unexpected keyword argument
    sample_repl.execute_line("q1 | test_func(sales, foo=123)", output_fn=output.append)
    assert any("got unexpected keyword argument 'foo'" in line for line in output)
    output.clear()

    # Too many positional arguments
    sample_repl.execute_line("q1 | test_func(sales, 10, 20, 30)", output_fn=output.append)
    assert any("takes 2 arguments but 4 were given" in line for line in output)
    output.clear()

    # Invalid parameter ordering in definition (non-default follows default)
    sample_repl.execute_line("def bad(a=1, b) = -filter 'sales > 0'", output_fn=output.append)
    assert any("non-default parameter 'b' follows default parameter" in line for line in output)
    assert "bad" not in sample_repl.defs
    output.clear()


def test_parameterized_def_checkpoints(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line(
        "def winsorize(col, max_val=100) = -mutate '$col = if_else($col > $max_val, $max_val, $col)'",
        output_fn=output.append,
    )
    sample_repl.execute_line("checkpoint snap_sig", output_fn=output.append)
    output.clear()

    # Remove def
    sample_repl.execute_line("rm def winsorize", output_fn=output.append)
    assert "winsorize" not in sample_repl.defs
    assert "winsorize" not in sample_repl.def_signatures
    output.clear()

    # Restore checkpoint
    sample_repl.execute_line("restore snap_sig", output_fn=output.append)
    assert "winsorize" in sample_repl.defs
    assert sample_repl.def_signatures["winsorize"] == "(col, max_val=100)"


def test_parameterized_def_python_transpilation() -> None:
    history = [
        "load q1.parquet as q1",
        "load q2.parquet as q2",
        "def winsorize(col, min_val=0, max_val=1000) = -filter '$col >= $min_val' -mutate '$col = if_else($col > $max_val, $max_val, $col)'",
        "q1_clean = q1 | winsorize(sales, 10)",
        "q2_clean = q2 | winsorize(sales, min_val=0, max_val=500) -head 5",
    ]
    py_code = _compile_history_to_python(history, prune_dead=True)

    # 1. Parameterized def function signature
    assert "def winsorize(df: pt.DataFrame, col, min_val=0, max_val=1000) -> pt.DataFrame:" in py_code
    assert ".filter(f\"{col} >= {min_val}\")" in py_code
    assert ".mutate(f\"{col} = if_else({col} > {max_val}, {max_val}, {col})\")" in py_code

    # 2. Call sites transpiled with Python arguments
    assert "q1_clean = winsorize(q1, 'sales', 10)" in py_code
    assert "q2_clean = winsorize(q2, 'sales', min_val=0, max_val=500).head(5)" in py_code

