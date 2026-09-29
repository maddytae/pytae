import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv


def test_long_melts_numeric_columns(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["a", "b"], "n": [1, 2], "x": [10, 20]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-long", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["grp", "variable", "value"]

def test_long_renames_melt_columns(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["a"], "n": [1], "x": [10]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-long", "c=feature,v=amount", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "feature", "amount"]

def test_wide_pivots_long_frame(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "country": ["sg", "cn", "ca"],
            "balance": [10, 20, 0],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "c=country,v=balance", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "ca", "cn", "sg"]

def test_long_quoted_names_with_spaces(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["a"], "n": [1], "x": [10]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-long", "c=feature name,v=amount col", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "feature name", "amount col"]

def test_wide_quoted_names_with_spaces(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "id": ["a", "b"],
            "country name": ["sg", "cn"],
            "body mass": [10, 20],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "c=country name,v=body mass", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "cn", "sg"]

def test_wide_rejects_a_arg(tmp_path):
    df = pd.DataFrame(
        {
            "id": ["a", "b"],
            "country": ["sg", "cn"],
            "balance": [10, 20],
        }
    )
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit, match=r"-wide: -wide is strictly for 1-to-1 reshaping without aggregation"):
        cli.main([path, "-wide", "c=country,v=balance,a=mean"])


def test_wide_duplicate_keys_fail_cleanly(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "id": ["a", "a"],
            "country": ["sg", "sg"],
            "balance": [10, 20],
        }
    )
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-wide", "c=country,v=balance"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "duplicate entries" in captured.err.lower()
    assert "-pivot" in captured.err

def test_wide_unknown_column_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"id": ["a"], "balance": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-wide", "c=country,v=balance"])
    assert exc_info.value.code == 2

def test_wide_rejects_dropna_kwarg(tmp_path):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"country": ["a"], "variable": ["x"], "value": [1]}),
    )
    with pytest.raises(SystemExit, match="unknown key 'dropna'"):
        cli.main([path, "-wide", "dropna=false"])


def test_long_unknown_column_validation(tmp_path):
    # CLI Issue 11: -long validates columns
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    p = _write_csv(tmp_path, df)
    with pytest.raises(SystemExit) as exc_info:
        cli.main([p, "-long", "cols=nope"])
    assert exc_info.value.code == 2


def test_crosstab_unrecognized_argument(tmp_path):
    df = pd.DataFrame({"species": ["Adelie", "Gentoo"], "island": ["Biscoe", "Dream"]})
    p = _write_csv(tmp_path, df)
    with pytest.raises(SystemExit) as exc_info:
        cli.main([p, "-crosstab", "index=species,columns=island"])
    assert exc_info.value.code == 2




