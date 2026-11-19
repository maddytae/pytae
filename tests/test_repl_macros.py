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


def test_macro_definition_and_inspection(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    
    # 1. Initially no macros
    sample_repl.execute_line("macros", output_fn=output.append)
    assert any("No macros defined" in line for line in output)
    output.clear()

    # 2. Define a macro
    sample_repl.execute_line("macro clean = -dropna -filter 'sales > 0'", output_fn=output.append)
    assert any("Defined macro 'clean'" in line for line in output)
    assert "clean" in sample_repl.macros
    assert sample_repl.macros["clean"] == "-dropna -filter 'sales > 0'"
    output.clear()

    # 3. Inspect the macro
    sample_repl.execute_line("macro clean", output_fn=output.append)
    assert any("macro clean = -dropna -filter 'sales > 0'" in line for line in output)
    output.clear()

    # 4. List macros
    sample_repl.execute_line("macros", output_fn=output.append)
    assert any("Defined macros (1)" in line for line in output)
    assert any("clean = -dropna -filter 'sales > 0'" in line for line in output)
    output.clear()

    # 5. Status macro
    sample_repl.execute_line("status macro", output_fn=output.append)
    assert any("Defined macros (1)" in line for line in output)
    output.clear()


def test_macro_execution_piped_and_assigned(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("macro clean = -dropna -filter 'sales > 0'", output_fn=output.append)
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

    # Chained flag after macro: q2_top = q2 | clean -head 1
    sample_repl.execute_line("q2_top = q2 | clean -head 1", output_fn=output.append)
    assert "q2_top" in sample_repl.tables
    assert sample_repl.tables["q2_top"].shape == (1, 2)
    assert sample_repl.tables["q2_top"]["sales"].to_list() == [200]
    output.clear()


def test_macro_execution_on_active_table(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("macro clean = -dropna -filter 'sales > 0'", output_fn=output.append)
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


def test_macro_removal(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("macro m1 = -filter 'sales > 0'", output_fn=output.append)
    sample_repl.execute_line("macro m2 = -dropna", output_fn=output.append)
    assert len(sample_repl.macros) == 2
    output.clear()

    # Remove single macro
    sample_repl.execute_line("rm macro m1", output_fn=output.append)
    assert any("Removed macro 'm1'" in line for line in output)
    assert "m1" not in sample_repl.macros
    assert "m2" in sample_repl.macros
    output.clear()

    # Remove all macros
    sample_repl.execute_line("rm macro *", output_fn=output.append)
    assert any("Removed all macros" in line for line in output)
    assert len(sample_repl.macros) == 0
    output.clear()


def test_macro_checkpoints(sample_repl: PytaeRepl) -> None:
    output: list[str] = []
    sample_repl.execute_line("macro clean = -dropna -filter 'sales > 0'", output_fn=output.append)
    sample_repl.execute_line("checkpoint baseline", output_fn=output.append)
    output.clear()

    # Remove macro
    sample_repl.execute_line("rm macro clean", output_fn=output.append)
    assert "clean" not in sample_repl.macros
    output.clear()

    # Restore checkpoint
    sample_repl.execute_line("restore baseline", output_fn=output.append)
    assert "clean" in sample_repl.macros
    assert sample_repl.macros["clean"] == "-dropna -filter 'sales > 0'"


def test_macro_python_transpilation() -> None:
    history = [
        "load q1.parquet as q1",
        "load q2.parquet as q2",
        "macro clean_orders = -dropna -filter 'sales > 0' -mutate 'tax = sales * 0.08'",
        "q1_clean = q1 | clean_orders",
        "q2_clean = q2 | clean_orders -head 5",
    ]
    py_code = _compile_history_to_python(history, prune_dead=True)

    # 1. Macro compiled to a standalone helper function
    assert "def clean_orders(df: pt.DataFrame) -> pt.DataFrame:" in py_code
    assert ".dropna()" in py_code
    assert ".filter('sales > 0')" in py_code
    assert ".mutate('tax = sales * 0.08')" in py_code

    # 2. Macro call sites transpiled to function calls
    assert "q1_clean = clean_orders(q1)" in py_code
    assert "q2_clean = clean_orders(q2).head(5)" in py_code


def test_macro_dead_code_pruning() -> None:
    history = [
        "load q1.parquet as q1",
        "macro unused_macro = -filter 'sales > 1000'",
        "macro used_macro = -dropna",
        "q1_clean = q1 | used_macro",
    ]
    py_code = _compile_history_to_python(history, prune_dead=True)

    # used_macro is emitted
    assert "def used_macro(df: pt.DataFrame) -> pt.DataFrame:" in py_code
    assert "q1_clean = used_macro(q1)" in py_code

    # unused_macro was pruned!
    assert "unused_macro" not in py_code


def test_macro_pt_script_transpilation() -> None:
    history = [
        "load q1.parquet as q1",
        "macro clean = -dropna -filter 'sales > 0'",
        "q1_clean = q1 | clean",
    ]
    pt_code = _compile_history_to_pt(history, prune_dead=True)

    assert "macro clean = -dropna -filter 'sales > 0'" in pt_code
    assert "q1_clean = q1 | clean" in pt_code
