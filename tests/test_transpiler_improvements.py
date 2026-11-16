"""Comprehensive tests for Pytae transpiler, history compilation, and round-trip execution."""

from __future__ import annotations

import ast

import polars as pl

from pytae.repl import PytaeRepl
from pytae.transpiler import (
    _compile_history_to_pt,
    _compile_history_to_python,
    _extract_entry_def_and_uses,
    _prune_rolled_back_entries,
    _transpile_pipeline_tokens_to_python,
)


def test_transpile_shorthand_inplace_flag_assignment():
    """Verify `df = -filter ...` or `df = -mutate ...` transpiles to valid Python chaining."""
    entries = [
        "df = test.csv",
        "df = -filter \"x > 1\"",
        "df = -mutate \"y = x * 2\"",
    ]
    py_code = _compile_history_to_python(entries)
    ast.parse(py_code)
    assert "df = pt.read('test.csv')" in py_code
    assert "df = df.filter('x > 1')" in py_code
    assert "df = df.mutate('y = x * 2')" in py_code


def test_transpile_output_command_preserves_pipeline():
    """Verify intermediate operations before -o are not dropped."""
    entries = [
        "df = test.csv",
        "df -filter \"x > 1\" -select a,b -o out.parquet",
    ]
    py_code = _compile_history_to_python(entries)
    ast.parse(py_code)
    assert "df = pt.read('test.csv')" in py_code
    assert "df.filter('x > 1').select('a', 'b').to('out.parquet')" in py_code


def test_transpile_bare_output_command_defaults_to_df():
    """Verify `-filter ... -o ...` without explicit table defaults to df."""
    entries = [
        "df = test.csv",
        "-filter \"x > 1\" -o out.parquet",
    ]
    py_code = _compile_history_to_python(entries)
    ast.parse(py_code)
    assert "df.filter('x > 1').to('out.parquet')" in py_code


def test_transpile_concat():
    """Verify -concat flag is correctly transpiled."""
    tokens = ["-concat", "t1,t2"]
    res = _transpile_pipeline_tokens_to_python(tokens)
    assert res == ".concat(t1, t2)"

    entries = [
        "t1 = a.csv",
        "t2 = b.csv",
        "res = t1 -concat t2",
    ]
    py_code = _compile_history_to_python(entries)
    ast.parse(py_code)
    assert "res = t1.concat(t2)" in py_code


def test_transpile_join_with_full_arguments():
    """Verify -join transpiles with on, left_on, right_on, how, validate, fuzzy, score."""
    tokens = [
        "-join", "users",
        "-on", "id",
        "how=left",
        "validate=1:1",
        "fuzzy=0.85",
        "score=sim_score",
        "suffix=_user",
    ]
    res = _transpile_pipeline_tokens_to_python(tokens)
    assert "on='id'" in res
    assert "how='left'" in res
    assert "validate='1:1'" in res
    assert "fuzzy=0.85" in res
    assert "score='sim_score'" in res
    assert "suffix='_user'" in res


def test_transpile_distinct_and_dropna_with_arguments():
    """Verify -distinct and -dropna transpile column specs and options."""
    tokens = ["-distinct", "a,b,keep=last"]
    res = _transpile_pipeline_tokens_to_python(tokens)
    assert res == ".distinct('a', 'b', keep='last')"

    tokens_drop = ["-dropna", "colA,colB,how=all"]
    res_drop = _transpile_pipeline_tokens_to_python(tokens_drop)
    assert res_drop == ".dropna('colA', 'colB', how='all')"


def test_transpile_clean_columns_with_spec():
    """Verify -clean_columns transpiles with parsed keyword arguments."""
    tokens = ["-clean_columns", "case=lower,strip"]
    res = _transpile_pipeline_tokens_to_python(tokens)
    assert "case='lower'" in res
    assert "strip=True" in res


def test_table_sources_preloaded_when_not_in_history():
    """Verify table_sources loads pre-existing session tables in Python and PT exports."""
    entries = [
        "df = -filter \"status == 'active'\"",
        "df -o active.parquet",
    ]
    sources = {"df": "data/users.csv"}
    py_code = _compile_history_to_python(entries, table_sources=sources)
    ast.parse(py_code)
    assert "df = pt.read('data/users.csv')" in py_code
    assert "df = df.filter(\"status == 'active'\")" in py_code

    pt_code = _compile_history_to_pt(entries, "out.pt", table_sources=sources)
    assert "load data/users.csv" in pt_code


def test_checkpoint_quotes_in_pruning():
    """Verify checkpoint and restore with quotes are properly pruned."""
    entries = [
        "df = test.csv",
        "checkpoint 'snap1'",
        "df = -filter bad",
        "restore 'snap1'",
        "df = -filter good",
    ]
    pruned = _prune_rolled_back_entries(entries)
    assert "df = -filter bad" not in pruned
    assert "df = -filter good" in pruned


def test_concat_comma_in_def_and_uses():
    """Verify -concat t1,t2 tracks both t1 and t2 in uses."""
    defs, uses, side, barrier = _extract_entry_def_and_uses("res = -concat t1,t2")
    assert "res" in defs
    assert "t1" in uses
    assert "t2" in uses


def test_roundtrip_execution_repl_to_python(tmp_path):
    """End-to-end verification: execute in REPL -> export to .py -> execute .py with exec() -> assert identical data."""
    data_file = tmp_path / "raw_data.csv"
    pl.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "David"],
        "age": [25, 30, 35, 40],
        "score": [88.5, 92.0, 79.5, 95.0],
    }).write_csv(data_file)

    out_file = tmp_path / "filtered.parquet"

    r = PytaeRepl()
    outputs: list[str] = []
    # 1. Ingest
    r.execute_line(f"df = {data_file}", output_fn=outputs.append)
    # 2. In-place filter with shorthand flag
    r.execute_line("df = -filter \"age >= 30\"", output_fn=outputs.append)
    # 3. In-place mutate with shorthand flag
    r.execute_line("df = -mutate \"bonus = score * 1.1\"", output_fn=outputs.append)
    # 4. Pipeline with output
    r.execute_line(f"df -arrange \"bonus desc\" -o {out_file}", output_fn=outputs.append)

    repl_result = r.current_df.to_dict(as_series=False)

    # Export to standalone Python script
    py_file = tmp_path / "pipeline.py"
    r.execute_line(f"export {py_file}", output_fn=outputs.append)
    assert py_file.exists()

    py_code = py_file.read_text(encoding="utf-8")
    ast.parse(py_code)

    # Execute generated python code directly
    ns: dict = {}
    exec(compile(py_code, str(py_file), "exec"), ns)

    assert "df" in ns
    py_df = ns["df"]
    if hasattr(py_df, "to_polars"):
        py_df = py_df.to_polars()
    elif hasattr(py_df, "_df"):
        py_df = py_df._df

    assert py_df.to_dict(as_series=False) == repl_result
    assert out_file.exists()
    saved_df = pl.read_parquet(out_file)
    assert len(saved_df) == 3


def test_roundtrip_preloaded_repl_to_python(tmp_path):
    """Verify that launching REPL with an initial file correctly exports and executes standalone without NameError."""
    data_file = tmp_path / "accounts.csv"
    pl.DataFrame({
        "account_id": [101, 102, 103],
        "balance": [5000, 15000, 25000],
    }).write_csv(data_file)

    # Initialize REPL with pre-loaded file path (no `load` line in session history)
    r = PytaeRepl(path=data_file)
    outputs: list[str] = []

    r.execute_line("df = -filter \"balance > 10000\"", output_fn=outputs.append)
    r.execute_line("df = -mutate \"tier = 'VIP'\"", output_fn=outputs.append)

    py_file = tmp_path / "accounts_pipeline.py"
    r.execute_line(f"export {py_file}", output_fn=outputs.append)
    assert py_file.exists()

    py_code = py_file.read_text(encoding="utf-8")
    ast.parse(py_code)

    # Executing the script MUST NOT raise NameError: name 'df' is not defined
    ns: dict = {}
    exec(compile(py_code, str(py_file), "exec"), ns)
    assert "df" in ns
    assert len(ns["df"]) == 2


def test_roundtrip_multi_table_join_and_concat(tmp_path):
    """Verify multi-table workflows with -join and -concat compile and execute faithfully."""
    f1 = tmp_path / "emp.csv"
    f2 = tmp_path / "dept.csv"
    pl.DataFrame({"emp_id": [1, 2, 3], "dept_id": [10, 20, 10]}).write_csv(f1)
    pl.DataFrame({"dept_id": [10, 20], "dept_name": ["Engineering", "Product"]}).write_csv(f2)

    entries = [
        f"emp = {f1}",
        f"dept = {f2}",
        "joined = emp -join dept -on dept_id how=inner",
    ]
    py_code = _compile_history_to_python(entries)
    ast.parse(py_code)
    ns: dict = {}
    exec(compile(py_code, "<test_join>", "exec"), ns)
    assert "joined" in ns
    assert len(ns["joined"]) == 3
    assert "dept_name" in ns["joined"].columns


def test_transpile_windows_unquoted_paths_preserved():
    """Verify that unquoted Windows backslash paths are not mangled by shlex during transpilation."""
    entries = [
        r"df = C:\Users\user\data\sales.csv",
        r"df -filter 'amount > 100' -o C:\Users\user\out\summary.parquet",
    ]
    py_code = _compile_history_to_python(entries)
    ast.parse(py_code)
    assert "pt.read('C:/Users/user/data/sales.csv')" in py_code
    assert ".to('C:/Users/user/out/summary.parquet')" in py_code

    pt_code = _compile_history_to_pt(entries, "pipeline.pt")
    assert "df = C:/Users/user/data/sales.csv" in pt_code
    assert "-o C:/Users/user/out/summary.parquet" in pt_code
