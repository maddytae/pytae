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
    top_per_grp = df.pt.by("species").pt.slice_max("body_mass_g", n=1)
    assert len(top_per_grp) == 2
    assert set(top_per_grp["body_mass_g"]) == {4000, 5500}

    # Grouped slice_min
    bot_per_grp = df.pt.by("species").pt.slice_min("body_mass_g", n=1)
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


def test_cli_distinct_and_dropna(tmp_path, capsys):
    df = pd.DataFrame({
        "a": [1, 1, 2, None],
        "b": [10, 20, 30, 40],
    })
    path = _write_csv(tmp_path, df)

    # -distinct drops duplicate rows
    exit_code = cli.main([path, "-distinct", "a", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(3, 2)" in out

    # -dropna drops rows with missing values
    exit_code = cli.main([path, "-dropna", "a", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(3, 2)" in out


def test_slice_with_nan_by_keys():
    """Verify that rows with NaN in grouping keys are not dropped by slice_max/min."""
    df = pd.DataFrame({
        "group": ["A", "A", None, None],
        "val": [10, 20, 100, 200],
    })
    # slice_max with ties=False
    res_max = pt.slice_max(pt.by(df, "group"), "val", n=1)
    assert len(res_max) == 2
    assert set(res_max["val"]) == {20, 200}
    assert res_max["group"].isna().sum() == 1

    # slice_min with ties=False
    res_min = pt.slice_min(pt.by(df, "group"), "val", n=1)
    assert len(res_min) == 2
    assert set(res_min["val"]) == {10, 100}
    assert res_min["group"].isna().sum() == 1

    # slice_max with ties=True
    df_ties = pd.DataFrame({
        "group": ["A", "A", None, None],
        "val": [20, 20, 200, 200],
    })
    res_max_ties = pt.slice_max(pt.by(df_ties, "group"), "val", n=1, with_ties=True)
    assert len(res_max_ties) == 4


def test_slice_edge_cases():
    df = pd.DataFrame({
        "val": [10, 20, None],
    })
    # n <= 0 returns empty DataFrame
    res = pt.slice_max(df, "val", n=0)
    assert len(res) == 0
    assert list(res.columns) == ["val"]

    # na_last=False puts NaN at top for slice_max
    res_na_first = pt.slice_max(df, "val", n=1, na_last=False)
    assert pd.isna(res_na_first["val"].iloc[0])


def test_slice_prop():
    df = pd.DataFrame({
        "group": ["A"] * 10 + ["B"] * 20,
        "val": list(range(10)) + list(range(20)),
    })
    # Overall 10% of 30 is 3
    res_top = pt.slice_max(df, "val", prop=0.1)
    assert len(res_top) == 3
    assert list(res_top["val"]) == [19, 18, 17]

    # Grouped 10%: A gets 1 row (10 * 0.1), B gets 2 rows (20 * 0.1)
    res_grp = pt.slice_max(pt.by(df, "group"), "val", prop=0.1)
    assert len(res_grp) == 3
    assert list(res_grp[res_grp["group"] == "A"]["val"]) == [9]
    assert list(res_grp[res_grp["group"] == "B"]["val"]) == [19, 18]

    # slice_min with prop
    res_min_grp = pt.slice_min(pt.by(df, "group"), "val", prop=0.1)
    assert list(res_min_grp[res_min_grp["group"] == "A"]["val"]) == [0]
    assert list(res_min_grp[res_min_grp["group"] == "B"]["val"]) == [0, 1]

    # Error if both n and prop given
    import pytest
    with pytest.raises(ValueError, match="specify either 'n' or 'prop'"):
        pt.slice_max(df, "val", n=2, prop=0.1)


def test_cli_slice_syntax_and_prop(tmp_path, capsys):
    from pytae import cli
    df = pd.DataFrame({"x": list(range(100)), "grp": ["g1"] * 50 + ["g2"] * 50})
    path = str(tmp_path / "data.parquet")
    df.to_parquet(path)

    # col,n=N
    assert cli.main([path, "-slice_max", "x,n=5", "-shape"]) == 0
    assert "(5, 2)" in capsys.readouterr().out

    # col,prop=P
    assert cli.main([path, "-slice_max", "x,prop=0.1", "-shape"]) == 0
    assert "(10, 2)" in capsys.readouterr().out

    # bare col defaults to n=1
    assert cli.main([path, "-slice_max", "x", "-shape"]) == 0
    assert "(1, 2)" in capsys.readouterr().out


