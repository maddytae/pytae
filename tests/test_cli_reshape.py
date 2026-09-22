import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _penguins_frame, _write_csv


def test_crosstab_counts(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    exit_code = cli.main([path, "-crosstab", "index=species,columns=island"])

    out = capsys.readouterr().out
    assert exit_code == 0
    lines = out.strip().splitlines()
    assert lines[0].split() == ["island", "Biscoe", "Dream"]
    assert lines[2].split() == ["Adelie", "1", "2"]

def test_crosstab_margins_adds_totals(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    cli.main([path, "-crosstab", "index=species,columns=island,margins=true"])

    out = capsys.readouterr().out
    assert "All" in out.strip().splitlines()[0]

def test_crosstab_margins_name_renames_totals(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    cli.main([path, "-crosstab", "index=species,columns=island,margins=true,margins_name=Total"])

    out = capsys.readouterr().out
    assert "Total" in out.strip().splitlines()[0]
    assert "All" not in out

def test_crosstab_margins_name_requires_margins(tmp_path):
    path = _write_csv(tmp_path, _penguins_frame())

    with pytest.raises(SystemExit, match="margins_name= requires margins=true"):
        cli.main([path, "-crosstab", "index=species,columns=island,margins_name=Total"])

def test_crosstab_values_and_aggfunc(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    exit_code = cli.main([
        path, "-crosstab",
        "index=species,columns=sex,values=body_mass_g,aggfunc=mean",
        "-round", "1",
    ])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "3875.0" in out

def test_crosstab_values_requires_aggfunc(tmp_path):
    path = _write_csv(tmp_path, _penguins_frame())

    with pytest.raises(SystemExit, match="values= and aggfunc= must be given together"):
        cli.main([path, "-crosstab", "index=species,columns=sex,values=body_mass_g"])

def test_crosstab_unknown_column_errors(tmp_path):
    path = _write_csv(tmp_path, _penguins_frame())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-crosstab", "index=species,columns=nope"])
    assert exc_info.value.code == 2

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

def test_wide_aggfunc_mean(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "id": ["a", "a"],
            "country": ["sg", "sg"],
            "balance": [10, 20],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "c=country,v=balance,a=mean", "-head", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert "15" in captured.out

def test_wide_unknown_column_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"id": ["a"], "balance": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-wide", "c=country,v=balance"])
    assert exc_info.value.code == 2

def test_wide_and_group_x_reject_dropna_kwarg(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["a"], "val": [1]}))
    with pytest.raises(SystemExit, match="unknown key 'dropna'"):
        cli.main([path, "-group_x", "group=grp,dropna=false"])
    path2 = _write_csv(
        tmp_path,
        pd.DataFrame({"country": ["a"], "variable": ["x"], "value": [1]}),
    )
    with pytest.raises(SystemExit, match="unknown key 'dropna'"):
        cli.main([path2, "-wide", "dropna=false"])

