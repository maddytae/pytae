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


def test_cli_pivot_rich_metrics_1d(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "East", "West"],
        "Sales": [100.0, 200.0, 300.0],
    })
    p = _write_csv(tmp_path, df)
    exit_code = cli.main([p, "-pivot", "r=Region, v='avg_sales=Sales:mean, count=n'", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols == ["Region", "avg_sales", "count"]


def test_cli_pivot_rich_metrics_2d_unquoted(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "East", "West"],
        "Year": [2020, 2021, 2020],
        "Sales": [100.0, 200.0, 300.0],
    })
    p = _write_csv(tmp_path, df)
    exit_code = cli.main([p, "-pivot", "r=Region, c=Year, v=rev=Sales:sum, count=n", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols == ["Region", "rev_2020", "rev_2021", "orders_2020", "orders_2021"] or cols == ["Region", "rev_2020", "rev_2021", "count_2020", "count_2021"]


def test_cli_pivot_multi_func(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "East", "West"],
        "Sales": [100.0, 200.0, 300.0],
    })
    p = _write_csv(tmp_path, df)
    exit_code = cli.main([p, "-pivot", "r=Region, v=Sales:[mean, sum]", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols == ["Region", "Sales_mean", "Sales_sum"]


def test_cli_pivot_optional_v(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "East", "West"],
        "Year": [2020, 2021, 2020],
        "Store": ["S1", "S2", "S1"],
    })
    p = _write_csv(tmp_path, df)

    # 2D table without v
    exit_code = cli.main([p, "-pivot", "r=Region, c=Year", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols == ["Region", "2020", "2021"]

    # 1D row frequency table without v
    exit_code = cli.main([p, "-pivot", "r=Region,Store", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols == ["Region", "Store", "n"]


def test_cli_pivot_f_v(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "East", "West"],
        "Quarter": ["Q1", "Q1", "Q2"],
        "Sales": [100.0, 200.0, 300.0],
    })
    p = _write_csv(tmp_path, df)

    # f_v=0 works
    exit_code = cli.main([p, "-pivot", "r=Region, c=Quarter, v=Sales, a=sum, f_v=0", "-head"])
    assert exit_code == 0
    out_fv = capsys.readouterr().out
    assert "East" in out_fv

    # fill=0 is rejected
    with pytest.raises(SystemExit):
        cli.main([p, "-pivot", "r=Region, c=Quarter, v=Sales, fill=0"])

    # fill_value=0 is rejected
    with pytest.raises(SystemExit):
        cli.main([p, "-pivot", "r=Region, c=Quarter, v=Sales, fill_value=0"])


def test_cli_pivot_single_metric_2d_no_prefix(tmp_path, capsys):
    df = pd.DataFrame({
        "cola": ["A1", "A2"],
        "colb": ["B1", "B2"],
        "colc": ["C1", "C2"],
        "colv": [10.0, 20.0],
    })
    p = _write_csv(tmp_path, df)
    # pytae x.parquet -pivot "r=cola,colb,c=colc,v=colv:sum"
    exit_code = cli.main([p, "-pivot", "r=cola,colb,c=colc,v=colv:sum", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols == ["cola", "colb", "C1", "C2"]





