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

    result = pt.agg(pt.by(df, "category"), a=["sum"])
    expected_df = pd.DataFrame(data).groupby("category").sum().reset_index()
    pd.testing.assert_frame_equal(result, expected_df)


def test_all_agg():
    df = pd.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e", "", "f", "f"],
            "balance": [10, 20, 0, 21, 15, 10, 20, 25],
            "country": ["sg", "cn", "ca", "np", "in", "in", "in", "in"],
        }
    )
    df["id"] = df["id"].replace("", np.nan)

    # Multi-metric aggregations require explicit Paradigm 2 aliases (zero on-the-fly columns)
    result = pt.agg(
        pt.by(df, "id", "country"),
        n="count",
        balance_sum="balance:sum",
        balance_min="balance:min",
        balance_mean="balance:mean",
        balance_max="balance:max",
    )

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


def test_all_agg_drop_na():
    df = pd.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e", "", "f", "f"],
            "balance": [10, 20, 0, 21, 15, 10, 20, 25],
            "country": ["sg", "cn", "ca", "np", "in", "in", "in", "in"],
        }
    )
    df["id"] = df["id"].replace("", np.nan)

    result = pt.agg(
        pt.by(df, "id", "country"),
        n="count",
        balance_sum="balance:sum",
        balance_min="balance:min",
        balance_mean="balance:mean",
        balance_max="balance:max",
        dropna=True,
    )

    expected_df = (
        df.groupby(["id", "country"], dropna=True)
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


def test_agg_df_multi_metric_without_aliases_raises():
    df = pd.DataFrame({"g": ["a", "b"], "v": [1, 2]})
    with pytest.raises(
        ValueError, match="multiple metric functions .* cannot be applied across columns without explicit aliases"
    ):
        df.pt.by("g").pt.agg(a=["mean", "sum"])
    with pytest.raises(
        ValueError, match="multiple aggregation functions in .* cannot be applied without explicit aliases"
    ):
        df.pt.by("g").pt.agg(v="mean,sum")
    with pytest.raises(
        ValueError, match="list of aggregation functions in .* cannot be applied without explicit aliases"
    ):
        df.pt.by("g").pt.agg(v=["mean", "sum"])


def test_agg_df_raises_when_n_collides_with_real_column():
    df = pd.DataFrame({"g": ["x", "x", "y"], "n": [1, 2, 3], "v": [10, 20, 30]})
    with pytest.raises(ValueError, match="already has a numeric column named 'n'"):
        pt.agg(pt.by(df, "g"), ["sum", "n"])


def test_agg_df_column_kwargs():
    df = pd.DataFrame({"grp": ["A", "A", "B"], "v1": [10, 20, 30], "v2": [1, 2, 3]})
    res = df.pt.by("grp").pt.agg(v1="mean", v2="max", count="n")
    assert list(res.columns) == ["grp", "v1", "v2", "count"]
    assert list(res["v1"]) == [15.0, 30.0]
    assert list(res["v2"]) == [2, 3]
    assert list(res["count"]) == [2, 1]


def test_agg_df_rejects_by_argument():
    df = pd.DataFrame({"grp": ["A", "A", "B"], "v1": [10, 20, 30]})
    with pytest.raises(TypeError, match="agg\\(\\) does not accept 'by'"):
        pt.agg(df, by="grp")
    with pytest.raises(TypeError, match="df.pt.agg\\(\\) does not accept 'by'"):
        df.pt.agg(by="grp")


def test_agg_df_rejects_dictionary():
    df = pd.DataFrame({"grp": ["A", "A", "B"], "v1": [10, 20, 30]})
    with pytest.raises(TypeError, match=r"agg\(\) no longer accepts dictionaries"):
        pt.agg(df, {"v1": "mean"})
    with pytest.raises(TypeError, match=r"agg\(\) no longer accepts dictionaries"):
        df.pt.by("grp").pt.agg(a={"v1": "mean"})


def test_agg_df_numeric_group_by():
    df = pd.DataFrame(
        {
            "year": [2023, 2023, 2024],
            "sales": [100.0, 200.0, 300.0],
            "units": [10, 20, 30],
        }
    )
    res = df.pt.by("year").pt.agg(a=["sum", "n"])
    assert list(res.columns) == ["year", "n", "sales", "units"]
    assert list(res["year"]) == [2023, 2024]
    assert list(res["sales"]) == [300.0, 300.0]
    assert list(res["units"]) == [30, 30]
    assert list(res["n"]) == [2, 1]


def test_agg_df_whole_table_summary():
    df = pd.DataFrame(
        {
            "sales": [100.0, 200.0, 300.0],
            "units": [10, 20, 30],
        }
    )
    # Whole-table single metric + count: 1-to-1 column preservation
    res = df.pt.agg(a=["sum", "n"])
    assert len(res) == 1
    assert list(res.columns) == ["n", "sales", "units"]
    assert res["n"].iloc[0] == 3
    assert res["sales"].iloc[0] == 600.0
    assert res["units"].iloc[0] == 60

    # Whole-table multiple metrics require explicit aliases (Paradigm 2)
    res_multi = df.pt.agg(
        n="count",
        sales_sum="sales:sum",
        sales_mean="sales:mean",
        units_sum="units:sum",
        units_mean="units:mean",
    )
    assert len(res_multi) == 1
    assert list(res_multi.columns) == ["n", "sales_sum", "sales_mean", "units_sum", "units_mean"]
    assert res_multi["sales_sum"].iloc[0] == 600.0
    assert res_multi["sales_mean"].iloc[0] == 200.0


def test_agg_df_string_spec_with_brackets():
    df = pd.DataFrame(
        {
            "smoker status": ["Yes", "Yes", "No"],
            "tip amount": [2.0, 4.0, 3.0],
            "total bill": [10.0, 20.0, 30.0],
        }
    )
    # 1. Single string spec with brackets
    res1 = df.pt.by("[smoker status]").pt.agg("[tip amount] = mean, [total bill] = mean, n = n")
    assert list(res1.columns) == ["smoker status", "tip amount", "total bill", "n"]
    assert list(res1["smoker status"]) == ["No", "Yes"]
    assert list(res1["tip amount"]) == [3.0, 3.0]
    assert list(res1["total bill"]) == [30.0, 15.0]
    assert list(res1["n"]) == [1, 2]

    # 2. Multiple positional string specs
    res2 = df.pt.by("[smoker status]").pt.agg("[tip amount] = mean", "[total bill] = mean", "n = n")
    pd.testing.assert_frame_equal(res1, res2)

    # 3. Passed via keyword a=
    res3 = df.pt.by("[smoker status]").pt.agg(a="[tip amount] = mean, [total bill] = mean, n = n")
    pd.testing.assert_frame_equal(res1, res3)

    # 4. Mixed string spec and kwargs
    res4 = df.pt.by("[smoker status]").pt.agg("[total bill] = mean", **{"tip amount": "mean", "n": "n"})
    assert list(res4.columns) == ["smoker status", "total bill", "tip amount", "n"]
    assert list(res4["total bill"]) == [30.0, 15.0]

    # 5. Named aggregation with brackets in output and source
    res5 = df.pt.by("[smoker status]").pt.agg(
        "[avg bill] = [total bill]:mean, [bill sum] = [total bill]:sum, [count] = n"
    )
    assert list(res5.columns) == ["smoker status", "avg bill", "bill sum", "count"]
    assert list(res5["avg bill"]) == [30.0, 15.0]
    assert list(res5["bill sum"]) == [30.0, 30.0]
    assert list(res5["count"]) == [1, 2]

    # 6. Whole-table summary with string mapping
    res6 = df.pt.agg("[avg bill] = [total bill]:mean, [count] = n")
    assert len(res6) == 1
    assert list(res6.columns) == ["avg bill", "count"]
    assert res6["avg bill"].iloc[0] == 20.0
    assert res6["count"].iloc[0] == 3


def test_agg_df_whole_frame_string_spec():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v1": [1.0, 3.0, 5.0], "v2": [2.0, 4.0, 6.0]})
    res = df.pt.by("g").pt.agg("mean, n")
    assert list(res.columns) == ["g", "n", "v1", "v2"]
    assert list(res["n"]) == [2, 1]
    assert list(res["v1"]) == [2.0, 5.0]

    res_multi = df.pt.by("g").pt.agg("mean", "n")
    pd.testing.assert_frame_equal(res, res_multi)


def test_agg_df_user_pipeline_tips():
    from pytae import c

    tips = pt.sample("tips")
    res = (
        tips.pt.filter(c.day.is_in(["Sat", "Sun"]), c.time == "Dinner", c.size >= 2, c.total_bill > 10)
        .pt.select(c.smoker, c.tip, c.total_bill)
        .rename(columns={"total_bill": "total bill"})
        .pt.by("smoker")
        .pt.agg("tip = mean, [total bill] = mean, n = n")
    )
    assert list(res.columns) == ["smoker", "tip", "total bill", "n"]
    assert len(res) == 2
    assert set(res["smoker"]) == {"Yes", "No"}
    assert dict(zip(res["smoker"], res["n"])) == {"Yes": 57, "No": 97}


def test_agg_df_string_spec_errors():
    df = pd.DataFrame({"g": ["a", "b"], "v": [1, 2]})
    with pytest.raises(ValueError, match="agg\\(\\):"):
        df.pt.by("g").pt.agg("invalid syntax without equals and not known agg")
    with pytest.raises(ValueError, match="cannot mix whole-frame aggregation"):
        df.pt.by("g").pt.agg("mean", v="sum")
    with pytest.raises(TypeError, match="multiple values for aggregation spec"):
        df.pt.by("g").pt.agg("mean", a="sum")


def test_agg_df_multi_metric_without_aliases_raises_on_the_fly():
    # Multi-metric without explicit alias is rejected because columns cannot be created on the fly
    df = pd.DataFrame({"g": ["a", "b"], "_x": [1, 2], "y_": [3, 4]})
    with pytest.raises(
        ValueError, match="multiple metric functions .* cannot be applied across columns without explicit aliases"
    ):
        df.pt.by("g").pt.agg(["mean", "sum"])


def test_agg_df_group_by_n_with_count_n_raises():
    # Lib Issue 2: grouping by 'n' and requesting 'n' raises collision error
    df = pd.DataFrame({"n": ["a", "a", "b"], "v": [1.0, 2.0, 4.0]})
    with pytest.raises(ValueError, match="collides with group column 'n'|already has a group column named 'n'"):
        df.pt.by("n").pt.agg(["mean", "n"])

    with pytest.raises(ValueError, match="collides with group column 'n'|already has a group column named 'n'"):
        df.pt.by("n").pt.agg(v="mean", n="n")


def test_agg_df_output_name_collides_with_group_col():
    # Issue 1: named agg output matching a group column raises ValueError
    df = pd.DataFrame({"Region": ["East", "East", "West"], "Sales": [10, 30, 5], "Profit": [1, 2, 3]})
    with pytest.raises(ValueError, match="collides with group column"):
        df.pt.by("Region").pt.agg(Region="Sales:sum")

    with pytest.raises(ValueError, match="collides with group column"):
        df.pt.by("Region").pt.agg("Region = Sales:sum")


def test_agg_df_duplicate_output_cols():
    # Issue 1: duplicate output column name in named_aggs / output_cols
    df = pd.DataFrame({"Region": ["East", "East", "West"], "Sales": [10, 30, 5], "Profit": [1, 2, 3]})
    with pytest.raises(ValueError, match="is duplicated in aggregation specification"):
        df.pt.by("Region").pt.agg("Sales_sum = Profit:sum, Sales_sum = Sales:sum")


def test_agg_df_list_collision_with_group_col():
    # Collision check: explicit alias colliding with group column raises
    df = pd.DataFrame({"Sales_sum": ["A", "B"], "Sales": [10, 20]})
    with pytest.raises(ValueError, match="collides with group column 'Sales_sum'"):
        df.pt.by("Sales_sum").pt.agg(Sales_sum="Sales:sum")


def test_agg_df_comma_separated_by_string():
    df = pd.DataFrame(
        {
            "day": ["Thur", "Thur", "Fri"],
            "sex": ["Male", "Female", "Male"],
            "total_bill": [10.0, 20.0, 30.0],
        }
    )
    res = df.pt.by("day", "sex").pt.agg(total_bill="mean")
    assert list(res.columns) == ["day", "sex", "total_bill"]
    assert len(res) == 3


def test_agg_shorthand_syntax():
    import pytae as pt
    from pytae import c, count

    df = pt.DataFrame({
        "species": ["A", "A", "B"],
        "body_mass_g": [100.0, 200.0, 300.0],
        "flipper_length_mm": [10.0, 20.0, 30.0],
    })

    # 1. Shorthand in-place: body_mass_g = sum()
    res1 = df.by("species").agg("body_mass_g = sum(), flipper_length_mm = mean(), n = count()")
    assert list(res1.columns) == ["species", "body_mass_g", "flipper_length_mm", "n"]
    assert res1.filter(c.species == "A")["body_mass_g"].to_list() == [300.0]
    assert res1.filter(c.species == "A")["flipper_length_mm"].to_list() == [15.0]
    assert res1.filter(c.species == "A")["n"].to_list() == [2]

    # 2. Method call in string: avg_mass = body_mass_g.mean()
    res2 = df.by("species").agg("avg_mass = body_mass_g.mean(), max_mass = body_mass_g.max()")
    assert list(res2.columns) == ["species", "avg_mass", "max_mass"]
    assert res2.filter(c.species == "A")["avg_mass"].to_list() == [150.0]
    assert res2.filter(c.species == "A")["max_mass"].to_list() == [200.0]

    # 3. Python API with count() and c
    res3 = df.by(c.species).agg(n=count(), total_mass=c.body_mass_g.sum())
    assert res3.filter(c.species == "A")["n"].to_list() == [2]
    assert res3.filter(c.species == "A")["total_mass"].to_list() == [300.0]


def test_agg_shorthand_missing_col_error():
    import pytae as pt

    df = pt.DataFrame({
        "species": ["A", "A", "B"],
        "body_mass_g": [100.0, 200.0, 300.0],
    })
    with pytest.raises(KeyError, match="cannot apply 'sum\\(\\)' to new alias 'total_mass'"):
        df.by("species").agg("total_mass = sum()")


def test_c_call_deprecation_and_count_expr():
    import warnings
    from pytae import c, count

    # c() emits DeprecationWarning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        expr = c()
        assert len(w) == 1
        assert issubclass(w[-1].category, DeprecationWarning)
        assert "c() is deprecated for row counting" in str(w[-1].message)

    # count() works cleanly without warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cnt_expr = count()
        assert len(w) == 0


if __name__ == "__main__":
    pytest.main()
