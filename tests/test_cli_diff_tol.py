import pandas as pd
import pytest

import pytae as pt
from pytae import cli


def test_cli_diff_without_tol(tmp_path, capsys):
    f1 = tmp_path / "f1.csv"
    f2 = tmp_path / "f2.csv"

    # Differences within 0.01 tolerance
    df1 = pd.DataFrame({"id": [1, 2, 3], "val": [10.001, 20.004, 30.002]})
    df2 = pd.DataFrame({"id": [1, 2, 3], "val": [10.000, 20.000, 30.000]})
    df1.to_csv(f1, index=False)
    df2.to_csv(f2, index=False)

    # Without tolerance -> mismatches
    exit_code = cli.main([str(f1), "-diff", str(f2)])
    assert exit_code == 0
    out1 = capsys.readouterr().out
    assert "Mismatches found" in out1
    assert "val: 3 cell(s) differ" in out1


def test_cli_diff_with_tol_flag(tmp_path, capsys):
    f1 = tmp_path / "f1.csv"
    f2 = tmp_path / "f2.csv"

    df1 = pd.DataFrame({"metric": [1.0005, 2.0002]})
    df2 = pd.DataFrame({"metric": [1.0000, 2.0000]})
    df1.to_csv(f1, index=False)
    df2.to_csv(f2, index=False)

    # -tol flag
    exit_code = cli.main([str(f1), "-diff", str(f2), "-tol", "0.001"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Tolerance: threshold/atol=0.001" in out
    assert "Identical: all cell values match within tolerance" in out

    # -tolerance alias with scientific notation
    exit_code2 = cli.main([str(f1), "-diff", str(f2), "-tolerance", "1e-4"])
    assert exit_code2 == 0
    out2 = capsys.readouterr().out
    assert "Tolerance: threshold/atol=0.0001" in out2
    assert "Mismatches found in 2 cells exceeding tolerance" in out2
    assert "metric: 2 cell(s) differ (max diff: 0.0005)" in out2


def test_cli_diff_tol_requires_diff(tmp_path, capsys):
    f1 = tmp_path / "f1.csv"
    f1.write_text("a\n1\n")

    with pytest.raises(SystemExit) as exc:
        cli.main([str(f1), "-tol", "0.001"])
    assert exc.value.code == 2
    assert "-tol requires -diff" in capsys.readouterr().err


def test_python_dataframe_diff():
    df1 = pt.DataFrame({"id": [1, 2], "val": [10.05, 20.02]})
    df2 = pt.DataFrame({"id": [1, 2], "val": [10.00, 20.00]})

    # df.diff without tol
    res1 = df1.diff(df2)
    assert "Mismatches found in 2 cells" in res1
    assert "val: 2 cell(s) differ (max diff: 0.05)" in res1

    # df.diff with tol=0.1
    res2 = df1.diff(df2, tol=0.1)
    assert "Tolerance: threshold/atol=0.1" in res2
    assert "Identical: all cell values match within tolerance" in res2

    # pt.diff functional
    res3 = pt.diff(df1, df2, tol=0.1)
    assert "Identical: all cell values match within tolerance" in res3

    # Pandas accessor .pt.diff
    pd1 = df1.to_pandas()
    pd2 = df2.to_pandas()
    res4 = pd1.pt.diff(pd2, tol=0.1)
    assert "Identical: all cell values match within tolerance" in res4
