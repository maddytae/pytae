import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae import cli
from tests.cli_helpers import _write_csv


def test_library_arrange_basic_and_directions():
    df = pd.DataFrame(
        {
            "grp": ["b", "a", "b", "a"],
            "val": [10, 20, 30, 40],
            "cost": [100, 50, 200, 150],
        }
    )

    # Default asc
    res1 = df.pt.arrange("grp", "val")
    assert list(res1["grp"]) == ["a", "a", "b", "b"]
    assert list(res1["val"]) == [20, 40, 10, 30]

    # Mixed directions
    res2 = df.pt.arrange("grp asc", "val desc")
    assert list(res2["grp"]) == ["a", "a", "b", "b"]
    assert list(res2["val"]) == [40, 20, 30, 10]

    # Leading '-' is rejected in line with 'one and only one obvious way'
    with pytest.raises(ValueError, match=r"leading '-' is not supported"):
        df.pt.arrange("-grp", "val")

    # pt.arrange standalone function
    res4 = pt.arrange(df, "val desc")
    assert list(res4["val"]) == [40, 30, 20, 10]


def test_library_arrange_bracket_spaced_columns():
    df = pd.DataFrame(
        {
            "first name": ["Charlie", "Alice", "Bob"],
            "annual salary": [50000, 70000, 60000],
        }
    )

    res = df.pt.arrange("[annual salary] desc")
    assert list(res["first name"]) == ["Alice", "Bob", "Charlie"]
    assert list(res["annual salary"]) == [70000, 60000, 50000]

    # Comma string with brackets
    res2 = df.pt.arrange("[annual salary] asc, [first name]")
    assert list(res2["first name"]) == ["Charlie", "Bob", "Alice"]


def test_library_arrange_and_head_canonical():
    df = pd.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Adelie", "Gentoo", "Gentoo"],
            "body_mass_g": [3000, 4000, 3500, 5000, 5500],
        }
    )

    # Global top 1
    top1 = df.pt.arrange("body_mass_g desc").head(1)
    assert len(top1) == 1
    assert top1["body_mass_g"].iloc[0] == 5500

    # Grouped top 1 per group
    top_per_grp = df.pt.by("species").arrange("body_mass_g desc").head(1)
    assert len(top_per_grp) == 2
    assert set(top_per_grp["body_mass_g"]) == {4000, 5500}

    # Grouped bottom 1 per group via arrange asc
    bot_per_grp = df.pt.by("species").arrange("body_mass_g").head(1)
    assert len(bot_per_grp) == 2
    assert set(bot_per_grp["body_mass_g"]) == {3000, 5000}

    # Grouped bottom 1 per group via tail
    bot_per_grp_tail = df.pt.by("species").arrange("body_mass_g desc").tail(1)
    assert len(bot_per_grp_tail) == 2
    assert set(bot_per_grp_tail["body_mass_g"]) == {3000, 5000}

    # Standalone function pt.head
    sorted_df = pt.arrange(df, "body_mass_g desc")
    assert pt.head(sorted_df, 2).iloc[0]["body_mass_g"] == 5500
    assert pt.tail(sorted_df, 2).iloc[-1]["body_mass_g"] == 3000


def test_library_pick_and_slice_max_min_removed():
    df = pd.DataFrame({"x": [1, 2, 3]})
    with pytest.raises(AttributeError, match=r"pick\(\) has been removed"):
        df.pt.pick("x")
    with pytest.raises(AttributeError, match=r"pick\(\) has been removed"):
        pt.pick(df, "x")
    with pytest.raises(AttributeError, match=r"GroupedDataFrame\.pick\(\) has been removed"):
        df.pt.by("x").pick("x")
    with pytest.raises(AttributeError, match=r"slice_max\(\) has been removed"):
        df.pt.slice_max("x")
    with pytest.raises(AttributeError, match=r"slice_min\(\) has been removed"):
        df.pt.slice_min("x")
    with pytest.raises(AttributeError, match=r"slice_max\(\) has been removed"):
        pt.slice_max(df, "x")
    with pytest.raises(AttributeError, match=r"slice_min\(\) has been removed"):
        pt.slice_min(df, "x")


def test_cli_arrange_and_head(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Adelie", "Gentoo", "Gentoo"],
            "body_mass_g": [3000, 4000, 3500, 5000, 5500],
        }
    )
    path = _write_csv(tmp_path, df)

    # -arrange with direction and -head
    exit_code = cli.main([path, "-arrange", "body_mass_g desc", "-head", "1"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "5500" in out

    # -by with -arrange and -head
    exit_code = cli.main([path, "-by", "species", "-arrange", "body_mass_g desc", "-head", "1", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(2, 2)" in out

    # -by with -arrange and -tail
    exit_code = cli.main([path, "-by", "species", "-arrange", "body_mass_g desc", "-tail", "1", "-shape"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "(2, 2)" in out


def test_cli_pick_and_slice_fatal_error(tmp_path, capsys):
    df = pd.DataFrame({"x": [1, 2, 3]})
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit):
        cli.main([path, "-pick", "x"])
    err = capsys.readouterr().err
    assert "'-pick' has been removed; use '-arrange ... -head N'" in err

    with pytest.raises(SystemExit):
        cli.main([path, "-slice_max", "x"])
    err = capsys.readouterr().err
    assert "'-slice_max' has been removed; use '-arrange ... -head N' instead" in err

    with pytest.raises(SystemExit):
        cli.main([path, "-slice_min", "x"])
    err = capsys.readouterr().err
    assert "'-slice_min' has been removed" in err


def test_cli_distinct_and_dropna(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "a": [1, 1, 2, None],
            "b": [10, 20, 30, 40],
        }
    )
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


def test_head_with_nan_by_keys():
    """Verify that rows with NaN in grouping keys are not dropped by head/tail."""
    df = pd.DataFrame(
        {
            "group": ["A", "A", None, None],
            "val": [10, 20, 100, 200],
        }
    )
    # top 1 per group
    res_max = df.pt.by("group").arrange("val desc").head(1)
    assert len(res_max) == 2
    assert set(res_max["val"]) == {20, 200}
    assert res_max["group"].isna().sum() == 1

    # bottom 1 per group
    res_min = df.pt.by("group").arrange("val").head(1)
    assert len(res_min) == 2
    assert set(res_min["val"]) == {10, 100}
    assert res_min["group"].isna().sum() == 1

    # with ties
    df_ties = pd.DataFrame(
        {
            "group": ["A", "A", None, None],
            "val": [20, 20, 200, 200],
        }
    )
    res_max_ties = df_ties.pt.by("group").arrange("val desc").head(1, with_ties=True)
    assert len(res_max_ties) == 4


def test_head_edge_cases():
    df = pd.DataFrame(
        {
            "val": [10, 20, None],
        }
    )
    # n <= 0 returns empty DataFrame
    res = df.pt.head(0)
    assert len(res) == 0
    assert list(res.columns) == ["val"]

    # na_last=False puts NaN at top
    res_na_first = df.pt.arrange("val desc", na_last=False).head(1)
    assert pd.isna(res_na_first["val"].iloc[0])

    # with_ties requires arrange
    with pytest.raises(ValueError, match="with_ties=True requires calling df.arrange"):
        df.pt.head(1, with_ties=True)


def test_head_tail_prop():
    df = pd.DataFrame(
        {
            "group": ["A"] * 10 + ["B"] * 20,
            "val": list(range(10)) + list(range(20)),
        }
    )
    # Overall 10% of 30 is 3
    res_top = df.pt.arrange("val desc").head(prop=0.1)
    assert len(res_top) == 3
    assert list(res_top["val"]) == [19, 18, 17]

    # Grouped 10%: A gets 1 row (10 * 0.1), B gets 2 rows (20 * 0.1)
    res_grp = df.pt.by("group").arrange("val desc").head(prop=0.1)
    assert len(res_grp) == 3
    assert list(res_grp[res_grp["group"] == "A"]["val"]) == [9]
    assert list(res_grp[res_grp["group"] == "B"]["val"]) == [19, 18]

    # bottom 10% per group
    res_min_grp = df.pt.by("group").arrange("val").head(prop=0.1)
    assert list(res_min_grp[res_min_grp["group"] == "A"]["val"]) == [0]
    assert list(res_min_grp[res_min_grp["group"] == "B"]["val"]) == [0, 1]

    # Error if both n and prop given
    with pytest.raises(ValueError, match="specify either 'n' or 'prop'"):
        df.pt.head(n=2, prop=0.1)


def test_cli_head_syntax_and_prop(tmp_path, capsys):
    df = pd.DataFrame({"x": list(range(100)), "grp": ["g1"] * 50 + ["g2"] * 50})
    path = str(tmp_path / "data.parquet")
    df.to_parquet(path)

    # -head N
    assert cli.main([path, "-head", "5", "-shape"]) == 0
    assert "(5, 2)" in capsys.readouterr().out

    # -head P%
    assert cli.main([path, "-head", "10%", "-shape"]) == 0
    assert "(10, 2)" in capsys.readouterr().out

    # -head float
    assert cli.main([path, "-head", "0.1", "-shape"]) == 0
    assert "(10, 2)" in capsys.readouterr().out

    # -head default 5
    assert cli.main([path, "-head", "-shape"]) == 0
    assert "(5, 2)" in capsys.readouterr().out

    # -by with -arrange and -head
    assert cli.main([path, "-by", "grp", "-arrange", "x desc", "-head", "2", "-shape"]) == 0
    assert "(4, 2)" in capsys.readouterr().out
