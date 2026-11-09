"""Tests for deterministic dead assignment and redundant command pruning during script export."""

import tempfile
from pathlib import Path

import polars as pl
import pytest

from pytae.repl import (
    PytaeRepl,
    _compile_history_to_pt,
    _compile_history_to_python,
    _extract_entry_def_and_uses,
    _prune_dead_assignments,
    run_cli_export,
)


def test_prune_dead_assignments_unit():
    # 1. Exact consecutive assignment
    e1 = ["df = test.csv", "df = test.csv"]
    assert _prune_dead_assignments(e1) == ["df = test.csv"]

    # 2. Re-assignment with different file before use
    e2 = ["df = test1.csv", "df = test2.csv"]
    assert _prune_dead_assignments(e2) == ["df = test2.csv"]

    # 3. Triple assignment before use
    e3 = ["df = 1.csv", "df = 2.csv", "df = 3.csv"]
    assert _prune_dead_assignments(e3) == ["df = 3.csv"]

    # 4. Sequential batch with side-effects (user's exact scenario)
    e4 = [
        "df = test1.csv",
        "k = df -head",
        "k -o tes1_sample.csv",
        "df = test12csv",
        "k = df -head",
        "k -o tes2_sample.csv",
    ]
    assert _prune_dead_assignments(e4) == e4

    # 5. Scratchpad overwrite: k changed before being exported
    e5 = [
        "df = test.csv",
        "k = df -head",
        "k = df -tail",
        "k -o out.csv",
    ]
    assert _prune_dead_assignments(e5) == [
        "df = test.csv",
        "k = df -tail",
        "k -o out.csv",
    ]

    # 6. Self-referential mutation
    e6 = [
        "df = test.csv",
        "df = df -head",
        "df = df -filter a > 1",
    ]
    assert _prune_dead_assignments(e6) == e6

    # 7. Shorthand flag mutation (e.g. df = -filter ...)
    e7 = [
        "df = test.csv",
        "df = -filter a > 1",
    ]
    assert _prune_dead_assignments(e7) == e7

    # 8. Multi-table joins
    e8 = [
        "df1 = a.csv",
        "df2 = b.csv",
        "res = df1 -join df2 -on id",
        "res -o out.csv",
    ]
    assert _prune_dead_assignments(e8) == e8


def test_compile_history_pruning_pt_and_py(tmp_path):
    entries = [
        "df = test.csv",
        "df = test.csv",
    ]
    pt_code = _compile_history_to_pt(entries, "out.pt")
    assert pt_code.count("df = test.csv") == 1

    py_code = _compile_history_to_python(entries)
    assert py_code.count("pt.read('test.csv')") == 1

    # With prune_dead=False
    pt_code_raw = _compile_history_to_pt(entries, "out.pt", prune_dead=False)
    assert pt_code_raw.count("df = test.csv") == 2

    py_code_raw = _compile_history_to_python(entries, prune_dead=False)
    assert py_code_raw.count("pt.read('test.csv')") == 2


def test_repl_export_duplicate_deduplication(tmp_path):
    outputs = []
    r = PytaeRepl()

    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    r.execute_line("df = sample:penguins", output_fn=outputs.append)

    pt_file = tmp_path / "dedup.pt"
    py_file = tmp_path / "dedup.py"

    r.execute_line(f"export {pt_file}", output_fn=outputs.append)
    r.execute_line(f"export {py_file}", output_fn=outputs.append)

    assert pt_file.exists()
    pt_text = pt_file.read_text(encoding="utf-8")
    assert pt_text.count("df = sample:penguins") == 1

    assert py_file.exists()
    py_text = py_file.read_text(encoding="utf-8")
    assert py_text.count("pt.sample('penguins')") == 1

    # Export with -no-prune preserves verbatim duplicates
    pt_raw_file = tmp_path / "dedup_raw.pt"
    r.execute_line(f"export {pt_raw_file} -no-prune", output_fn=outputs.append)
    assert pt_raw_file.exists()
    pt_raw_text = pt_raw_file.read_text(encoding="utf-8")
    assert pt_raw_text.count("df = sample:penguins") == 2


def test_repl_export_sequential_batch_preservation(tmp_path):
    outputs = []
    r = PytaeRepl()

    f1 = tmp_path / "test1.csv"
    f2 = tmp_path / "test2.csv"
    pl.DataFrame({"val": [1, 2, 3]}).write_csv(f1)
    pl.DataFrame({"val": [10, 20, 30]}).write_csv(f2)

    out1 = tmp_path / "s1.csv"
    out2 = tmp_path / "s2.csv"

    r.execute_line(f"df = {f1}", output_fn=outputs.append)
    r.execute_line("k = df -head 2", output_fn=outputs.append)
    r.execute_line(f"k -o {out1}", output_fn=outputs.append)

    r.execute_line(f"df = {f2}", output_fn=outputs.append)
    r.execute_line("k = df -head 2", output_fn=outputs.append)
    r.execute_line(f"k -o {out2}", output_fn=outputs.append)

    pt_file = tmp_path / "batch.pt"
    r.execute_line(f"export {pt_file}", output_fn=outputs.append)

    pt_text = pt_file.read_text(encoding="utf-8")
    # k = df -head 2 must be recorded twice!
    assert pt_text.count("k = df -head 2") == 2
    assert f"k -o {out1}" in pt_text
    assert f"k -o {out2}" in pt_text


def test_cli_export_no_prune_flag(tmp_path):
    hist_file = tmp_path / "test_hist.txt"
    hist_file.write_text("""
df = sample:penguins
df = sample:penguins
df -o final.csv
""", encoding="utf-8")

    out_pt = tmp_path / "pruned.pt"
    ret = run_cli_export([str(hist_file), "-o", str(out_pt)])
    assert ret == 0
    assert out_pt.read_text(encoding="utf-8").count("df = sample:penguins") == 1

    out_pt_raw = tmp_path / "raw.pt"
    ret2 = run_cli_export([str(hist_file), "-o", str(out_pt_raw), "-no-prune"])
    assert ret2 == 0
    assert out_pt_raw.read_text(encoding="utf-8").count("df = sample:penguins") == 2
