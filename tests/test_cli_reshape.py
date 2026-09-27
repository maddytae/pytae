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

def test_wide_rejects_dropna_kwarg(tmp_path):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"country": ["a"], "variable": ["x"], "value": [1]}),
    )
    with pytest.raises(SystemExit, match="unknown key 'dropna'"):
        cli.main([path, "-wide", "dropna=false"])


def test_crosstab_sort_and_export_preserves_row_key(tmp_path):
    # CLI Issue 5: -crosstab row index preserved across sort and file export
    df = pd.DataFrame({"species": ["Adelie", "Gentoo"], "island": ["Biscoe", "Dream"]})
    p = _write_csv(tmp_path, df)
    out_csv = tmp_path / "out.csv"
    exit_code = cli.main([p, "-crosstab", "index=species,columns=island", "-sort_by", "Biscoe", "-o", str(out_csv)])
    assert exit_code == 0
    res = pd.read_csv(out_csv)
    assert "species" in res.columns


def test_crosstab_jsonl_export_preserves_row_index(tmp_path):
    # CLI Issue 6: -crosstab -o ct.jsonl preserves row index
    df = pd.DataFrame({"species": ["Adelie", "Gentoo"], "island": ["Biscoe", "Dream"]})
    p = _write_csv(tmp_path, df)
    out_jsonl = tmp_path / "ct.jsonl"
    exit_code = cli.main([p, "-crosstab", "index=species,columns=island", "-o", str(out_jsonl)])
    assert exit_code == 0
    res = pd.read_json(out_jsonl, lines=True)
    assert "species" in res.columns


def test_long_unknown_column_validation(tmp_path):
    # CLI Issue 11: -long validates columns
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    p = _write_csv(tmp_path, df)
    with pytest.raises(SystemExit) as exc_info:
        cli.main([p, "-long", "cols=nope"])
    assert exc_info.value.code == 2


def test_crosstab_collision_sort_and_jsonl_export(tmp_path):
    # CLI Issue 1 (Review 2ec5bbba): index name colliding with category or margins column
    df = pd.DataFrame({"question": ["question", "other", "question"], "answer": ["question", "yes", "no"]})
    p = _write_csv(tmp_path, df)
    exit_code = cli.main([p, "-crosstab", "index=question,columns=answer", "-sort_by", "yes"])
    assert exit_code == 0

    df2 = pd.DataFrame({"species": ["A", "B"], "island": ["X", "Y"]})
    p2 = _write_csv(tmp_path, df2)
    out_jsonl = tmp_path / "ct.jsonl"
    exit_code2 = cli.main([p2, "-crosstab", "index=species,columns=island,margins=true,margins_name=species", "-o", str(out_jsonl)])
    assert exit_code2 == 0
    res = pd.read_json(out_jsonl, lines=True)
    assert "species" in res.columns
    assert "species_1" in res.columns


def test_crosstab_round_clip(tmp_path, monkeypatch):
    # CLI Issue 2 (Review 2ec5bbba): -crosstab -round -o clip copies rounded values
    df = pd.DataFrame({"species": ["A", "A"], "sex": ["M", "M"], "body_mass_g": [1.26, 1.26]})
    p = _write_csv(tmp_path, df)
    copied = []
    monkeypatch.setattr(pd.DataFrame, "to_clipboard", lambda self, *a, **kw: copied.append((self.copy(), kw)))
    exit_code = cli.main([p, "-crosstab", "index=species,columns=sex,values=body_mass_g,aggfunc=mean", "-round", "1", "-o", "clip"])
    assert exit_code == 0
    assert len(copied) == 1
    clip_df, clip_kwargs = copied[0]
    assert clip_df.iloc[0, 0] == 1.3
    assert clip_kwargs.get("index") is True


def test_crosstab_follow_on_ops_on_row_index(tmp_path, capsys):
    # CLI Issue 3 (Review 2ec5bbba): -sort_by, -qry, and -select can reference crosstab row key
    df = pd.DataFrame({"species": ["Adelie", "Gentoo"], "island": ["Biscoe", "Dream"]})
    p = _write_csv(tmp_path, df)
    exit_sort = cli.main([p, "-crosstab", "index=species,columns=island", "-sort_by", "species"])
    assert exit_sort == 0
    out_sort = capsys.readouterr().out
    assert "species" in out_sort

    exit_qry = cli.main([p, "-crosstab", "index=species,columns=island", "-qry", "species = 'Adelie'"])
    assert exit_qry == 0
    out_qry = capsys.readouterr().out
    assert "Adelie" in out_qry
    assert "Gentoo" not in out_qry

    exit_sel = cli.main([p, "-crosstab", "index=species,columns=island", "-select", "species,Biscoe"])
    assert exit_sel == 0
    out_sel = capsys.readouterr().out
    assert "species" in out_sel


def test_crosstab_head_clip_includes_row_key(tmp_path, monkeypatch):
    # CLI Issue 4 (Review 2ec5bbba): -head -o clip after crosstab preserves row key
    df = pd.DataFrame({"species": ["Adelie", "Gentoo"], "island": ["Biscoe", "Dream"]})
    p = _write_csv(tmp_path, df)
    copied = []
    monkeypatch.setattr(pd.DataFrame, "to_clipboard", lambda self, *a, **kw: copied.append((self.copy(), kw)))
    exit_code = cli.main([p, "-crosstab", "index=species,columns=island", "-head", "1", "-o", "clip"])
    assert exit_code == 0
    assert len(copied) == 1
    clip_df, _ = copied[0]
    assert "species" in clip_df.columns or clip_df.index.name == "species"




