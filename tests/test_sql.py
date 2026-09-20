import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt

duckdb = pytest.importorskip("duckdb")


def test_sql_query_via_df_alias():
    df = pd.DataFrame({"col a": [1, 20, 3], "col b": ["x", "y", "z"]})
    out = pt.sql(df, 'select "col b" from df where "col a" > 10')
    assert list(out["col b"]) == ["y"]


def test_sql_via_accessor():
    penguins = pt.sample("penguins")
    out = penguins.pt.sql(
        "select species, avg(body_mass_g) as avg_mass from df group by species order by species"
    )
    assert list(out.columns) == ["species", "avg_mass"]
    assert set(out["species"]) == {"Adelie", "Chinstrap", "Gentoo"}


def test_sql_extra_frames():
    left = pd.DataFrame({"id": [1, 2], "x": ["a", "b"]})
    right = pd.DataFrame({"id": [1, 3], "y": ["p", "q"]})
    out = pt.sql(left, "select df.id, x, y from df inner join extra using (id)", extra=right)
    assert list(out["id"]) == [1]
    assert list(out["x"]) == ["a"]
    assert list(out["y"]) == ["p"]


def test_sql_rejects_df_as_extra_name():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="cannot be named 'df'"):
        pt.sql(df, "select * from df", df=df)


def test_sql_invalid_query_errors():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="sql:"):
        pt.sql(df, "not valid sql")


def test_sql_then_pandas_head():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    out = df.pt.sql("select b from df where a > 1").head(1)
    assert list(out["b"]) == ["y"]
