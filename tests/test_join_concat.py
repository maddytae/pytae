"""Tests for Pytae library join, concat, and transparent Polars method delegation."""

import os
import sys

import pandas as pd
import polars as pl

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def test_df_join_inner_and_chaining():
    df1 = pt.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"], "score": [80, 95, 70]})
    df2 = pt.DataFrame({"id": [2, 3, 4], "dept": ["Eng", "HR", "Sales"]})

    # Join and continue chaining Pytae fluent verbs
    res = (
        df1.join(df2, on="id", how="inner").filter("score >= 80").mutate(score_bonus="score + 10").arrange("score desc")
    )
    assert isinstance(res, pt.DataFrame)
    assert list(res.columns) == ["id", "name", "score", "dept", "score_bonus"]
    assert len(res) == 1
    assert res.iloc[0, "name"] == "Bob"
    assert res.iloc[0, "score_bonus"] == 105


def test_df_join_all_strategies():
    left = pt.DataFrame({"id": [1, 2, 3], "val": ["a", "b", "c"]})
    right = pt.DataFrame({"id": [2, 3, 4], "score": [20, 30, 40]})

    # left join
    lj = left.join(right, on="id", how="left")
    assert len(lj) == 3
    assert set(lj["id"].to_list()) == {1, 2, 3}

    # right join
    rj = left.join(right, on="id", how="right")
    assert len(rj) == 3
    assert set(rj["id"].to_list()) == {2, 3, 4}

    # full join
    fj = left.join(right, on="id", how="full")
    assert len(fj) == 4
    assert set(fj["id"].to_list()) == {1, 2, 3, 4}

    # semi join (filtering join - returns left rows that match right)
    sj = left.join(right, on="id", how="semi")
    assert len(sj) == 2
    assert list(sj.columns) == ["id", "val"]
    assert set(sj["id"].to_list()) == {2, 3}

    # anti join (returns left rows that do NOT match right)
    aj = left.join(right, on="id", how="anti")
    assert len(aj) == 1
    assert list(aj.columns) == ["id", "val"]
    assert aj.iloc[0, "id"] == 1

    # cross join
    cj = left.join(right, how="cross")
    assert len(cj) == 9  # 3 * 3


def test_df_join_colon_syntax():
    df1 = pt.DataFrame({"id": [1, 2, 3], "name": ["A", "B", "C"]})
    df2 = pt.DataFrame({"user_id": [2, 3, 4], "role": ["Dev", "PM", "QA"]})

    res = df1.join(df2, on="id:user_id", how="inner")
    assert len(res) == 2
    assert "id" in res.columns
    assert "user_id" in res.columns
    assert "role" in res.columns


def test_df_join_auto_detect_common_columns():
    df1 = pt.DataFrame({"user_id": [1, 2], "score": [90, 85]})
    df2 = pt.DataFrame({"user_id": [2, 3], "grade": ["A", "B"]})

    # Omit on parameter: automatically joins on user_id
    res = df1.join(df2)
    assert len(res) == 1
    assert res.iloc[0, "user_id"] == 2
    assert res.iloc[0, "score"] == 85
    assert res.iloc[0, "grade"] == "A"


def test_top_level_pt_join():
    df1 = pt.DataFrame({"id": [1, 2], "x": [10, 20]})
    df2 = pt.DataFrame({"id": [2, 3], "y": [200, 300]})

    res = pt.join(df1, df2, on="id", how="left")
    assert isinstance(res, pt.DataFrame)
    assert len(res) == 2


def test_pt_accessor_join_pandas_and_polars():
    pdf1 = pd.DataFrame({"id": [1, 2], "v": ["a", "b"]})
    pdf2 = pd.DataFrame({"id": [2, 3], "w": ["x", "y"]})

    # Pandas accessor .pt.join()
    res_pandas = pdf1.pt.join(pdf2, on="id", how="inner")
    assert isinstance(res_pandas, pt.DataFrame)
    assert len(res_pandas) == 1
    assert res_pandas.iloc[0, "id"] == 2

    # Polars accessor .pt.join()
    pldf1 = pl.DataFrame({"id": [1, 2], "v": ["a", "b"]})
    pldf2 = pl.DataFrame({"id": [2, 3], "w": ["x", "y"]})
    res_polars = pldf1.pt.join(pldf2, on="id", how="inner")
    assert isinstance(res_polars, pt.DataFrame)
    assert len(res_polars) == 1


def test_lazy_join_preserves_lazy_execution():
    lf1 = pl.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]}).lazy()
    lf2 = pl.DataFrame({"id": [2, 3, 4], "bonus": [100, 200, 300]}).lazy()

    df_lazy1 = pt.DataFrame(lf1)
    df_lazy2 = pt.DataFrame(lf2)

    joined_lazy = df_lazy1.join(df_lazy2, on="id", how="inner").filter("val > 10")
    assert joined_lazy.is_lazy

    collected = joined_lazy.collect()
    assert isinstance(collected, pt.DataFrame)
    assert not collected.is_lazy
    assert len(collected) == 2


def test_concat_vertical_and_fallback():
    df1 = pt.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    df2 = pt.DataFrame({"a": [3, 4], "b": ["w", "z"]})
    df3 = pt.DataFrame({"a": [5, 6], "c": [100, 200]})

    # Top-level concat with matching schemas
    res1 = pt.concat([df1, df2])
    assert len(res1) == 4
    assert list(res1.columns) == ["a", "b"]

    # Method chain concat
    res2 = df1.concat(df2)
    assert len(res2) == 4

    # Top-level concat with differing schemas (diagonal_relaxed fallback)
    res3 = pt.concat([df1, df3])
    assert len(res3) == 4
    assert list(res3.columns) == ["a", "b", "c"]
    assert res3.iloc[0, "c"] is None
    assert res3.iloc[2, "b"] is None


def test_concat_horizontal():
    df1 = pt.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    df2 = pt.DataFrame({"c": [10, 20], "d": [True, False]})

    res = pt.concat([df1, df2], how="horizontal")
    assert len(res) == 2
    assert list(res.columns) == ["a", "b", "c", "d"]


def test_dynamic_polars_forwarding_in_chain():
    df = pt.DataFrame({"id": [1, 2, 3, 4], "amt": [10, 25, 30, 45], "cat": ["a", "b", "a", "b"]})

    # with_columns is a native Polars method!
    # Because of transparent forwarding, it executes and wraps result back into pytae.DataFrame:
    res = (
        df.with_columns(tax=pl.col("amt") * 0.1)
        .filter("tax > 2")
        .by("cat")
        .mutate(total="sum(amt)")
        .arrange("total desc")
    )
    assert isinstance(res, pt.DataFrame)
    assert "tax" in res.columns
    assert "total" in res.columns

    # Native slice method
    sliced = df.slice(1, 2)
    assert isinstance(sliced, pt.DataFrame)
    assert len(sliced) == 2

    # Native describe method
    desc = df.describe()
    assert isinstance(desc, pt.DataFrame)
    assert "statistic" in desc.columns

    # Non-DataFrame return (scalar)
    n_unique = df.n_unique()
    assert isinstance(n_unique, int)
    assert n_unique == 4
