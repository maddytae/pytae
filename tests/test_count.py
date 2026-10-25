"""Tests for the count verb and counting enhancements across library and CLI."""

from __future__ import annotations

import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae import cli


@pytest.fixture
def df():
    return pt.DataFrame(
        {
            "species": ["Adelie", "Adelie", "Chinstrap", "Adelie", "Gentoo", "Gentoo"],
            "island": ["Torgersen", "Biscoe", "Dream", "Torgersen", "Biscoe", "Biscoe"],
            "mass": [3750.0, 3800.0, 3250.0, 3450.0, 4850.0, 5000.0],
        }
    )


def test_count_single_column(df):
    res = df.count("species")
    assert list(res.columns) == ["species", "n"]
    assert res["species"].to_list() == ["Adelie", "Gentoo", "Chinstrap"]
    assert res["n"].to_list() == [3, 2, 1]


def test_count_multiple_columns(df):
    res = df.count("species", "island")
    assert list(res.columns) == ["species", "island", "n"]
    assert len(res) == 4
    # Top count is Adelie-Torgersen with 2 and Gentoo-Biscoe with 2
    assert res["n"].to_list()[:2] == [2, 2]


def test_count_comma_separated_string(df):
    res = df.count("species, island")
    assert list(res.columns) == ["species", "island", "n"]
    assert len(res) == 4


def test_count_sort_false(df):
    res = df.count("species", sort=False)
    assert res["species"].to_list() == ["Adelie", "Chinstrap", "Gentoo"]
    assert res["n"].to_list() == [3, 1, 2]


def test_count_custom_name(df):
    res = df.count("species", name="total")
    assert list(res.columns) == ["species", "total"]
    assert res["total"].to_list() == [3, 2, 1]


def test_count_whole_table(df):
    res = df.count()
    assert list(res.columns) == ["n"]
    assert res["n"].to_list() == [6]


def test_count_grouped_dataframe(df):
    res = df.by("species").count()
    assert list(res.columns) == ["species", "n"]
    assert res["species"].to_list() == ["Adelie", "Gentoo", "Chinstrap"]
    assert res["n"].to_list() == [3, 2, 1]


def test_count_grouped_dataframe_custom_name_sort_false(df):
    res = df.by("species").count(sort=False, name="total")
    assert list(res.columns) == ["species", "total"]
    assert res["species"].to_list() == ["Adelie", "Chinstrap", "Gentoo"]
    assert res["total"].to_list() == [3, 1, 2]


def test_count_functional_api(df):
    res = pt.count(df, "species")
    assert res["n"].to_list() == [3, 2, 1]

    # Passing pandas DataFrame to pt.count
    pdf = pd.DataFrame({"cat": ["x", "x", "y"]})
    res_pdf = pt.count(pdf, "cat")
    assert res_pdf["cat"].to_list() == ["x", "y"]
    assert res_pdf["n"].to_list() == [2, 1]

    # Passing polars DataFrame to pt.count
    pldf = pl.DataFrame({"cat": ["x", "x", "y"]})
    res_pldf = pt.count(pldf, "cat")
    assert res_pldf["n"].to_list() == [2, 1]


def test_count_accessors(df):
    pdf = pd.DataFrame({"species": ["A", "A", "B"]})
    res = pdf.pt.count("species")
    assert res["species"].to_list() == ["A", "B"]
    assert res["n"].to_list() == [2, 1]

    pldf = pl.DataFrame({"species": ["A", "A", "B"]})
    res_pl = pldf.pt.count("species")
    assert res_pl["species"].to_list() == ["A", "B"]
    assert res_pl["n"].to_list() == [2, 1]


def test_count_collision_error():
    collision_df = pt.DataFrame({"n": [1, 1, 2]})
    with pytest.raises(ValueError, match="collides with group column 'n'"):
        collision_df.count("n")

    with pytest.raises(ValueError, match="collides with group column 'n'"):
        collision_df.by("n").count()


def test_count_unknown_column(df):
    with pytest.raises(KeyError, match="unknown column 'unknown'"):
        df.count("unknown")


def test_count_list_arg_error(df):
    with pytest.raises(TypeError, match="count\\(\\) takes column names as positional arguments"):
        df.count(["species", "island"])


def test_lazy_count():
    lazy = pt.scan_parquet("src/pytae/datasets/penguins.parquet")
    res = lazy.count("species").collect()
    assert list(res.columns) == ["species", "n"]
    assert len(res) == 3


def test_agg_count_canonical(df):
    # agg(total="count")
    res1 = df.by("species").agg(total="count", avg_mass="mass:mean")
    assert list(res1.columns) == ["species", "total", "avg_mass"]
    assert res1["total"].to_list() == [3, 1, 2]

    # agg(n="count()")
    res2 = df.by("species").agg(n="count()")
    assert list(res2.columns) == ["species", "n"]
    assert res2["n"].to_list() == [3, 1, 2]

    # agg string expression with func(col) syntax
    res3 = df.by("species").agg("total = count(), avg_mass = mean(mass)")
    assert list(res3.columns) == ["species", "total", "avg_mass"]
    assert res3["total"].to_list() == [3, 1, 2]

    # unground whole-table agg
    res4 = df.agg("count")
    assert list(res4.columns) == ["n"]
    assert res4["n"].to_list() == [6]

    res5 = df.agg("count()")
    assert list(res5.columns) == ["n"]
    assert res5["n"].to_list() == [6]


def test_cli_count(capsys):
    ret = cli.main(["src/pytae/datasets/penguins.parquet", "-count", "species"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Adelie" in out
    assert "152" in out


def test_cli_count_multiple(capsys):
    ret = cli.main(["src/pytae/datasets/penguins.parquet", "-count", "species,island"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Biscoe" in out
    assert "124" in out


def test_cli_count_sort_false(capsys):
    ret = cli.main(["src/pytae/datasets/penguins.parquet", "-count", "species,sort=false"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Adelie" in out


def test_cli_count_name_total(capsys):
    ret = cli.main(["src/pytae/datasets/penguins.parquet", "-count", "species,name=total"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "total" in out


def test_cli_by_count(capsys):
    ret = cli.main(["src/pytae/datasets/penguins.parquet", "-by", "species", "-count"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Adelie" in out
    assert "152" in out


def test_cli_count_whole_table(capsys):
    ret = cli.main(["src/pytae/datasets/penguins.parquet", "-count"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "344" in out


def test_cli_count_unknown_column(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["src/pytae/datasets/penguins.parquet", "-count", "unknown_col"])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "unknown column" in err or "unknown" in err
