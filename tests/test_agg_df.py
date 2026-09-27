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


def test_agg_df_string_spec_with_brackets():
    df = pd.DataFrame({
        "smoker status": ["Yes", "Yes", "No"],
        "tip amount": [2.0, 4.0, 3.0],
        "total bill": [10.0, 20.0, 30.0],
    })
    # 1. Single string spec with brackets
    res1 = df.pt.agg_df("[smoker status]", "[tip amount] = mean, [total bill] = mean, n = n")
    assert list(res1.columns) == ["smoker status", "tip amount", "total bill", "n"]
    assert list(res1["smoker status"]) == ["No", "Yes"]
    assert list(res1["tip amount"]) == [3.0, 3.0]
    assert list(res1["total bill"]) == [30.0, 15.0]
    assert list(res1["n"]) == [1, 2]

    # 2. Multiple positional string specs
    res2 = df.pt.agg_df("[smoker status]", "[tip amount] = mean", "[total bill] = mean", "n = n")
    pd.testing.assert_frame_equal(res1, res2)

    # 3. Passed via keyword a=
    res3 = df.pt.agg_df("[smoker status]", a="[tip amount] = mean, [total bill] = mean, n = n")
    pd.testing.assert_frame_equal(res1, res3)

    # 4. Mixed string spec and kwargs
    res4 = df.pt.agg_df("[smoker status]", "[total bill] = mean", **{"tip amount": "mean", "n": "n"})
    assert list(res4.columns) == ["smoker status", "total bill", "tip amount", "n"]
    assert list(res4["total bill"]) == [30.0, 15.0]

    # 5. Named aggregation with brackets in output and source
    res5 = df.pt.agg_df("[smoker status]", "[avg bill] = [total bill]:mean, [bill sum] = [total bill]:sum, [count] = n")
    assert list(res5.columns) == ["smoker status", "avg bill", "bill sum", "count"]
    assert list(res5["avg bill"]) == [30.0, 15.0]
    assert list(res5["bill sum"]) == [30.0, 30.0]
    assert list(res5["count"]) == [1, 2]

    # 6. Whole-table summary with string mapping
    res6 = df.pt.agg_df(None, "[avg bill] = [total bill]:mean, [count] = n")
    assert len(res6) == 1
    assert list(res6.columns) == ["avg bill", "count"]
    assert res6["avg bill"].iloc[0] == 20.0
    assert res6["count"].iloc[0] == 3


def test_agg_df_whole_frame_string_spec():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v1": [1.0, 3.0, 5.0], "v2": [2.0, 4.0, 6.0]})
    res = df.pt.agg_df("g", "mean, n")
    assert list(res.columns) == ["g", "n", "v1", "v2"]
    assert list(res["n"]) == [2, 1]
    assert list(res["v1"]) == [2.0, 5.0]

    res_multi = df.pt.agg_df("g", "mean", "n")
    pd.testing.assert_frame_equal(res, res_multi)


def test_agg_df_user_pipeline_tips():
    tips = pt.sample("tips")
    res = (
        tips
        .pt.qry(day=["Sat", "Sun"], time="Dinner", size=">= 2", total_bill="> 10")
        .pt.select("smoker", "tip", "total_bill")
        .rename(columns={"total_bill": "total bill"})
        .pt.agg_df("smoker", "tip = mean, [total bill] = mean, n = n")
    )
    assert list(res.columns) == ["smoker", "tip", "total bill", "n"]
    assert len(res) == 2
    assert list(res["smoker"]) == ["Yes", "No"]
    assert list(res["n"]) == [57, 97]


def test_agg_df_string_spec_errors():
    df = pd.DataFrame({"g": ["a", "b"], "v": [1, 2]})
    with pytest.raises(ValueError, match="agg\\(\\):"):
        df.pt.agg_df("g", "invalid syntax without equals and not known agg")
    with pytest.raises(ValueError, match="cannot mix whole-frame aggregation"):
        df.pt.agg_df("g", "mean", v="sum")
    with pytest.raises(TypeError, match="multiple values for aggregation spec"):
        df.pt.agg_df("g", "mean", a="sum")


def test_agg_df_multi_agg_column_flattening_preserves_underscores():
    # Lib Issue 1: multi-agg flattening preserves leading/trailing underscores
    df = pd.DataFrame({"g": ["a", "b"], "_x": [1, 2], "y_": [3, 4]})
    res = df.pt.agg_df("g", ["mean", "sum"])
    assert "_x_mean" in res.columns
    assert "_x_sum" in res.columns
    assert "y__mean" in res.columns
    assert "y__sum" in res.columns


def test_agg_df_group_by_n_with_count_n_raises():
    # Lib Issue 2: grouping by 'n' and requesting 'n' raises collision error
    df = pd.DataFrame({"n": ["a", "a", "b"], "v": [1.0, 2.0, 4.0]})
    with pytest.raises(ValueError, match="collides with group column 'n'|already has a group column named 'n'"):
        df.pt.agg_df("n", ["mean", "n"])

    with pytest.raises(ValueError, match="collides with group column 'n'|already has a group column named 'n'"):
        df.pt.agg_df("n", v="mean", n="n")


if __name__ == "__main__":
    pytest.main()

