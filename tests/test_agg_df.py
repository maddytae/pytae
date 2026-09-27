import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def test_agg_df_sum():
    data = {
        "category": ["A", "A", "B", "B", "C"],
        "value": [10, 20, 30, 40, 50],
    }
    df = pd.DataFrame(data)

    result = pt.agg_df(df, "category", a=["sum"])
    expected_df = pd.DataFrame(data).groupby("category").sum().reset_index()
    pd.testing.assert_frame_equal(result, expected_df)


def test_all_agg():
    df = pd.DataFrame({
        "id": ["a", "b", "c", "d", "e", "", "f", "f"],
        "balance": [10, 20, 0, 21, 15, 10, 20, 25],
        "country": ["sg", "cn", "ca", "np", "in", "in", "in", "in"],
    })
    df["id"] = df["id"].replace("", np.nan)

    result = pt.agg_df(df, ["id", "country"], a=["sum", "min", "mean", "min", "max", "n"])

    expected_df = (
        df.groupby(["id", "country"])
        .agg(
            n=("id", "size"),
            balance_sum=("balance", "sum"),
            balance_min=("balance", "min"),
            balance_mean=("balance", "mean"),
            balance_max=("balance", "max"),
        )
        .reset_index()
    )
    expected_df = expected_df[["id", "country", "n", "balance_sum", "balance_min", "balance_mean", "balance_max"]]
    pd.testing.assert_frame_equal(result, expected_df)


def test_all_agg_drop_na():
    df = pd.DataFrame({
        "id": ["a", "b", "c", "d", "e", "", "f", "f"],
        "balance": [10, 20, 0, 21, 15, 10, 20, 25],
        "country": ["sg", "cn", "ca", "np", "in", "in", "in", "in"],
    })
    df["id"] = df["id"].replace("", np.nan)

    result = pt.agg_df(df, ["id", "country"], a=["sum", "min", "mean", "min", "max", "n"], dropna=False)

    expected_df = (
        df.groupby(["id", "country"], dropna=False)
        .agg(
            n=("id", "size"),
            balance_sum=("balance", "sum"),
            balance_min=("balance", "min"),
            balance_mean=("balance", "mean"),
            balance_max=("balance", "max"),
        )
        .reset_index()
    )
    expected_df = expected_df[["id", "country", "n", "balance_sum", "balance_min", "balance_mean", "balance_max"]]
    pd.testing.assert_frame_equal(result, expected_df)


def test_agg_df_raises_when_n_collides_with_real_column():
    df = pd.DataFrame({"g": ["x", "x", "y"], "n": [1, 2, 3], "v": [10, 20, 30]})
    with pytest.raises(ValueError, match="already has a numeric column named 'n'"):
        pt.agg_df(df, "g", ["sum", "n"])


def test_agg_df_column_kwargs():
    df = pd.DataFrame({"grp": ["A", "A", "B"], "v1": [10, 20, 30], "v2": [1, 2, 3]})
    res = df.pt.agg_df("grp", v1="mean", v2="max", count="n")
    assert list(res.columns) == ["grp", "v1", "v2", "count"]
    assert list(res["v1"]) == [15.0, 30.0]
    assert list(res["v2"]) == [2, 3]
    assert list(res["count"]) == [2, 1]


def test_agg_df_rejects_dictionary():
    df = pd.DataFrame({"grp": ["A", "A", "B"], "v1": [10, 20, 30]})
    with pytest.raises(TypeError, match=r"agg\(\) no longer accepts dictionaries"):
        pt.agg_df(df, "grp", {"v1": "mean"})
    with pytest.raises(TypeError, match=r"agg\(\) no longer accepts dictionaries"):
        df.pt.agg_df("grp", a={"v1": "mean"})
    with pytest.raises(TypeError, match=r"agg\(\) no longer accepts dictionaries"):
        pt.agg_df(df, {"grp": "mean"})


def test_agg_df_missing_by_raises():
    df = pd.DataFrame({"grp": ["A", "A", "B"], "v1": [10, 20, 30]})
    with pytest.raises(TypeError, match="missing required argument: 'by'"):
        df.pt.agg_df()


def test_agg_df_aggfunc_as_by_raises_helpful_error():
    df = pd.DataFrame({"grp": ["A", "A", "B"], "v1": [10, 20, 30]})
    with pytest.raises(ValueError, match="is a known aggregation function"):
        df.pt.agg_df("mean")
    with pytest.raises(ValueError, match="looks like an aggregation list"):
        df.pt.agg_df(["mean", "n"])


def test_agg_df_unknown_group_column_raises():
    df = pd.DataFrame({"species": ["A", "B"], "val": [1, 2]})
    with pytest.raises(KeyError, match=r"group column 'speceis' not found in DataFrame \(did you mean 'species'\?\)"):
        df.pt.agg_df("speceis", "mean")


def test_agg_df_numeric_group_by():
    df = pd.DataFrame({
        "year": [2023, 2023, 2024],
        "sales": [100.0, 200.0, 300.0],
        "units": [10, 20, 30],
    })
    res = df.pt.agg_df("year", a=["sum", "n"])
    assert list(res.columns) == ["year", "n", "sales", "units"]
    assert list(res["year"]) == [2023, 2024]
    assert list(res["sales"]) == [300.0, 300.0]
    assert list(res["units"]) == [30, 30]
    assert list(res["n"]) == [2, 1]


def test_agg_df_whole_table_summary():
    df = pd.DataFrame({
        "sales": [100.0, 200.0, 300.0],
        "units": [10, 20, 30],
    })
    res = df.pt.agg_df(None, a=["sum", "mean", "n"])
    assert len(res) == 1
    assert list(res.columns) == ["n", "sales_sum", "sales_mean", "units_sum", "units_mean"]
    assert res["n"].iloc[0] == 3
    assert res["sales_sum"].iloc[0] == 600.0
    assert res["sales_mean"].iloc[0] == 200.0


def test_agg_df_whole_table_kwargs():
    df = pd.DataFrame({
        "sales": [100.0, 200.0, 300.0],
        "units": [10, 20, 30],
    })
    res = df.pt.agg_df(None, sales="sum", orders="n")
    assert len(res) == 1
    assert list(res.columns) == ["sales", "orders"]
    assert res["sales"].iloc[0] == 600.0
    assert res["orders"].iloc[0] == 3


if __name__ == "__main__":
    pytest.main()
