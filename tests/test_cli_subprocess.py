"""Subprocess-level tests for pytae CLI.

Verifies true Unix CLI behavior:
- Subprocess execution via `python -m pytae.cli`
- Standard input (STDIN) stream piping (`- -fmt csv`)
- Shell exit codes (0 for success, 2 for CLI argument errors)
- File format conversions (-o parquet, -o csv)
- Pipeline chaining (-filter, -mutate, -select, -arrange)
- Cold-start invocation latency benchmark
- Special character column names in CLI filter/mutate
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


def _run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Execute pytae CLI in a clean subprocess."""
    cmd = [sys.executable, "-m", "pytae.cli", *args]
    return subprocess.run(
        cmd,
        input=stdin,
        text=True,
        capture_output=True,
    )


# =============================================================================
# 1. Version and Help
# =============================================================================


def test_cli_version():
    proc = _run_cli("-version")
    assert proc.returncode == 0
    assert "pytae" in proc.stdout


def test_cli_help():
    proc = _run_cli("--help")
    assert proc.returncode == 0
    assert "usage: pytae" in proc.stdout
    assert "-filter" in proc.stdout
    assert "-mutate" in proc.stdout
    assert "-cheatsheet" in proc.stdout


def test_cli_cheatsheet():
    proc = _run_cli("-cheatsheet")
    assert proc.returncode == 0
    assert "PYTAE CLI CHEAT SHEET & COOKBOOK" in proc.stdout
    assert "-filter" in proc.stdout
    assert "-mutate" in proc.stdout


def test_cli_examples():
    proc = _run_cli("-examples")
    assert proc.returncode == 0
    assert "PYTAE CLI CHEAT SHEET & COOKBOOK" in proc.stdout


# =============================================================================
# 2. STDIN Stream Piping
# =============================================================================


def test_cli_stdin_shape():
    csv_data = "col1,col2,col3\n1,2,3\n4,5,6\n7,8,9\n"
    proc = _run_cli("-", "-fmt", "csv", "-shape", stdin=csv_data)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "(3, 3)"


def test_cli_stdin_pipeline_filter_mutate_select():
    csv_data = (
        "species,bill_length_mm,body_mass_g\n"
        "Adelie,39.1,3750\n"
        "Gentoo,46.1,4500\n"
        "Gentoo,50.0,5700\n"
        "Chinstrap,46.5,3800\n"
    )
    proc = _run_cli(
        "-",
        "-fmt",
        "csv",
        "-filter",
        "species == 'Gentoo'",
        "-mutate",
        "mass_kg = body_mass_g / 1000.0",
        "-select",
        "species,mass_kg",
        "-arrange",
        "mass_kg desc",
        stdin=csv_data,
    )
    assert proc.returncode == 0
    out = proc.stdout.strip()
    assert "Gentoo" in out
    assert "5.7" in out
    assert "4.5" in out
    assert "Adelie" not in out
    assert "Chinstrap" not in out


def test_cli_select_negation_exclamation():
    csv_data = "cola,colb,sex,year\n1,2,F,2020\n3,4,M,2021\n"
    proc = _run_cli("-", "-fmt", "csv", "-select", "!sex,!year", "-cols", stdin=csv_data)
    assert proc.returncode == 0
    assert "cola" in proc.stdout
    assert "colb" in proc.stdout
    assert "sex" not in proc.stdout
    assert "year" not in proc.stdout


# =============================================================================
# 3. Exit Codes
# =============================================================================


def test_cli_exit_code_invalid_flag():
    proc = _run_cli("--this-flag-does-not-exist")
    assert proc.returncode == 2
    assert "unrecognized arguments" in proc.stderr


def test_cli_exit_code_invalid_flag_combination():
    proc = _run_cli("dummy.csv", "-frac", "0.5")
    assert proc.returncode == 2
    assert "-frac requires -sample" in proc.stderr


def test_cli_exit_code_nonexistent_file():
    proc = _run_cli("this_file_does_not_exist_at_all.parquet", "-shape")
    assert proc.returncode == 2


# =============================================================================
# 4. File Format Conversions
# =============================================================================


def test_cli_convert_csv_to_parquet(tmp_path: Path):
    csv_file = tmp_path / "input.csv"
    pq_file = tmp_path / "output.parquet"
    df = pd.DataFrame({"id": [1, 2, 3], "value": ["a", "b", "c"]})
    df.to_csv(csv_file, index=False)

    proc = _run_cli(str(csv_file), "-o", str(pq_file))
    assert proc.returncode == 0
    assert pq_file.exists()

    # Verify output parquet can be inspected
    proc_inspect = _run_cli(str(pq_file), "-shape")
    assert proc_inspect.returncode == 0
    assert proc_inspect.stdout.strip() == "(3, 2)"


def test_cli_convert_parquet_to_csv(tmp_path: Path):
    pq_file = tmp_path / "data.parquet"
    csv_file = tmp_path / "data.csv"
    df = pd.DataFrame({"x": [10.5, 20.5], "y": [1, 2]})
    df.to_parquet(pq_file)

    proc = _run_cli(str(pq_file), "-o", str(csv_file))
    assert proc.returncode == 0
    assert csv_file.exists()

    read_back = pd.read_csv(csv_file)
    assert len(read_back) == 2
    assert list(read_back.columns) == ["x", "y"]


# =============================================================================
# 5. Dataset Diff & Drift Detection
# =============================================================================


def test_cli_diff_in_subprocess(tmp_path: Path):
    f1 = tmp_path / "day1.csv"
    f2 = tmp_path / "day2.csv"
    pd.DataFrame({"id": [1, 2], "val": [10.0, 20.0]}).to_csv(f1, index=False)
    pd.DataFrame({"id": [1, 2], "val": [10.0, 20.0001]}).to_csv(f2, index=False)

    # Without tolerance: should report differences
    proc_no_tol = _run_cli(str(f1), "-diff", str(f2))
    assert proc_no_tol.returncode == 0
    assert "Mismatches" in proc_no_tol.stdout

    # With tolerance: should match
    proc_tol = _run_cli(str(f1), "-diff", str(f2), "-tol", "1e-3")
    assert proc_tol.returncode == 0
    assert "Identical" in proc_tol.stdout or "within tolerance" in proc_tol.stdout


# =============================================================================
# 6. Cold-Start Latency Benchmark
# =============================================================================


def test_cli_cold_start_speed():
    """Verify that launching pytae has low cold-start latency."""
    t0 = time.perf_counter()
    proc = _run_cli("-version")
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0
    # Process startup + python import should complete comfortably under 1.5 seconds even on cold cache
    assert elapsed < 1.5, f"Cold start took too long: {elapsed:.2f}s"


# =============================================================================
# 7. Special Character Columns in CLI Pipeline
# =============================================================================


def test_cli_special_columns_filter_and_mutate(tmp_path: Path):
    csv_file = tmp_path / "risk.csv"
    df = pd.DataFrame(
        {
            "counterparty_class_(irb)": ["Sovereign", None, "Corporate"],
            "irba_unsecured_lgd_(1g00)": [0.20, 0.45, 0.70],
        }
    )
    df.to_csv(csv_file, index=False)

    # Null check predicate on special column
    proc_null = _run_cli(
        str(csv_file),
        "-filter",
        "counterparty_class_(irb).notna()",
        "-shape",
    )
    assert proc_null.returncode == 0
    assert proc_null.stdout.strip() == "(2, 2)"

    # Numeric comparison + arithmetic on special column
    proc_mutate = _run_cli(
        str(csv_file),
        "-filter",
        "irba_unsecured_lgd_(1g00) > 0.30",
        "-mutate",
        "pct = irba_unsecured_lgd_(1g00) * 100",
        "-select",
        "pct",
        "-head",
        "1",
    )
    assert proc_mutate.returncode == 0
    assert "45.0" in proc_mutate.stdout
