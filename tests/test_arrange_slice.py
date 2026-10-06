import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae import cli
from tests.cli_helpers import _write_csv


def test_library_arrange_basic_and_directions():
    df = pd.DataFrame({
        "grp": ["b", "a", "b", "a"],
        "val": [10, 20, 30, 40],
        "cost": [100, 50, 200, 150],
    })

    # Default asc
    res1 = df.pt.arrange("grp", "val")
    assert list(res1["grp"]) == ["a", "a", "b", "b"]
    assert list(res1["val"]) == [20, 40, 10, 30]

    # Mixed directions
    res2 = df.pt.arrange("grp asc", "val desc")
    assert list(res2["grp"]) == ["a", "a", "b", "b"]
    assert list(res2["val"]) == [40, 20, 30, 10]

    # Leading '-'
    res3 = df.pt.arrange("-grp", "val")
    assert list(res3["grp"]) == ["b", "b", "a", "a"]
    assert list(res3["val"]) == [10, 30, 20, 40]

    # pt.arrange standalone function
    res4 = pt.arrange(df, "val desc")
    assert list(res4["val"]) == [40, 30, 20, 10]


def test_library_arrange_bracket_spaced_columns():
    df = pd.DataFrame({
        "first name": ["Charlie", "Alice", "Bob"],
        "annual salary": [50000, 70000, 60000],
    })

    res = df.pt.arrange("[annual salary] desc")
    assert list(res["first name"]) == ["Alice", "Bob", "Charlie"]
    assert list(res["annual salary"]) == [70000, 60000, 50000]

    # Comma string with brackets
    res2 = df.pt.arrange("[annual salary] asc, [first name]")
    assert list(res2["first name"]) == ["Charlie", "Bob", "Alice"]


def test_library_slice_max_and_slice_min():
    df = pd.DataFrame({
        "species": ["Adelie", "Adelie", "Adelie", "Gentoo", "Gentoo"],
        "body_mass_g": [3000, 4000, 3500, 5000, 5500],
    })

    # Global slice_max
    top1 = df.pt.slice_max("body_mass_g", n=1)
    assert len(top1) == 1
    assert top1["body_mass_g"].iloc[0] == 5500

    # Grouped slice_max
    top_per_grp = df.pt.slice_max("body_mass_g", n=1, by="species")
    assert len(top_per_grp) == 2
    assert set(top_per_grp["body_mass_g"]) == {4000, 5500}

    # Grouped slice_min
    bot_per_grp = df.pt.slice_min("body_mass_g", n=1, by="species")
    assert len(bot_per_grp) == 2
    assert set(bot_per_grp["body_mass_g"]) == {3000, 5000}

    # Standalone function pt.slice_max and pt.slice_min
    assert pt.slice_max(df, "body_mass_g", n=2).iloc[0]["body_mass_g"] == 5500
    assert pt.slice_min(df, "body_mass_g", n=2).iloc[0]["body_mass_g"] == 3000


def test_cli_arrange_and_slice(tmp_path, capsys):
    df = pd.DataFrame({
        "species": ["Adelie", "Adelie", "Adelie", "Gentoo", "Gentoo"],
        "body_mass_g": [3000, 4000, 3500, 5000, 5500],
    })
    path = _write_csv(tmp_path, df)

    # -arrange with direction
    exit_code = cli.main([path, "-arrange", "body_mass_g desc", "-head", "1"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "5500" in out

    # -slice_max with -by
    exit_code = cli.main([path, "-by", "species", "-slice_max", "body_mass_g,n=1", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(2, 2)" in out

    # -slice_min with -by
    exit_code = cli.main([path, "-by", "species", "-slice_min", "body_mass_g,n=1", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(2, 2)" in out


def test_cli_dedupe_and_dropna(tmp_path, capsys):
    df = pd.DataFrame({
        "a": [1, 1, 2, None],
        "b": [10, 20, 30, 40],
    })
    path = _write_csv(tmp_path, df)

    # Bare -dedupe drops duplicate rows
    exit_code = cli.main([path, "-dedupe", "a", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(3, 2)" in out

    # -dropna drops rows with missing values
    exit_code = cli.main([path, "-dropna", "a", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(3, 2)" in out
