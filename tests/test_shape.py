import os
import sys

import pandas as pd
import pytest

# Assuming the current working directory is where the project root is
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytae as pt
from pytae import sample


def test_long():

    penguins = sample("penguins")

    
    result = pt.long(penguins, c='features')
    

    numeric_cols = penguins.select_dtypes(include=['number']).columns.tolist()
    expected_df = pd.melt(penguins, id_vars=[col for col in penguins.columns if col not in numeric_cols],
                        value_vars=numeric_cols, var_name='features', 
                                                 value_name='value')
    
    pd.testing.assert_frame_equal(result, expected_df)


def test_wide_falls_back_to_sum_when_pivot_has_duplicate_keys():
    """Duplicate (id, country) makes DataFrame.pivot raise ValueError; wide() sums."""
    df = pd.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e", "", "f", "f"],
            "balance": [10, 20, 0, 21, 15, 10, 20, 25],
            "country": ["sg", "cn", "ca", "np", "in", "in", "in", "in"],
        }
    )

    result = pt.wide(df, c="country", v="balance")

    expected_df = df.pivot_table(
        index="id", columns="country", values="balance", aggfunc="sum"
    ).reset_index()
    expected_df.columns.name = None
    pd.testing.assert_frame_equal(result, expected_df)


def test_wide_uses_pivot_when_keys_are_unique():
    df = pd.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e", "", "f"],
            "balance": [10, 20, 0, 21, 15, 10, 20],
            "country": ["sg", "cn", "ca", "np", "in", "in", "in"],
        }
    )

    result = pt.wide(df, c="country", v="balance")

    expected_df = df.pivot(index="id", columns="country", values="balance").reset_index()
    expected_df.columns.name = None
    pd.testing.assert_frame_equal(result, expected_df)


def test_wide_a_n_is_alias_for_size():
    """a='n' matches agg_df's group-count convention; passes 'size' to pivot_table under the hood."""
    df = pd.DataFrame(
        {
            "id": ["a", "a", "b", "b", "b"],
            "balance": [10, 20, 0, 21, 15],
            "country": ["sg", "sg", "cn", "cn", "cn"],
        }
    )

    result = pt.wide(df, c="country", v="balance", a="n")

    expected_df = df.pivot_table(
        index="id", columns="country", values="balance", aggfunc="size"
    ).reset_index()
    expected_df.columns.name = None
    pd.testing.assert_frame_equal(result, expected_df)


def test_long_raises_when_no_numeric_columns():
    df = pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})
    with pytest.raises(ValueError, match="no numeric columns to melt"):
        pt.long(df)


def test_long_with_non_numeric_cols():
    df = pd.DataFrame({
        "id": ["1", "2"],
        "phone_home": ["123", "456"],
        "phone_work": ["789", "012"],
    })
    res = df.pt.long(cols=["phone_home", "phone_work"], c="phone_type", v="number")
    assert list(res.columns) == ["id", "phone_type", "number"]
    assert len(res) == 4
    assert set(res["phone_type"]) == {"phone_home", "phone_work"}


def test_long_with_id_vars():
    df = pd.DataFrame({
        "user": ["alice", "bob"],
        "color": ["red", "blue"],
        "size": ["M", "L"],
    })
    res = df.pt.long(id_vars=["user"])
    assert list(res.columns) == ["user", "variable", "value"]
    assert len(res) == 4
    assert set(res["variable"]) == {"color", "size"}


def test_long_unknown_col_raises_helpful_error():
    df = pd.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(KeyError, match=r"long\(\): cols column 'c' not found in DataFrame"):
        pt.long(df, cols=["c"])


def test_wide_with_explicit_index():
    df = pd.DataFrame({
        "region": ["East", "East", "West"],
        "rep": ["Alice", "Bob", "Charlie"],
        "quarter": ["Q1", "Q2", "Q1"],
        "sales": [100, 200, 300],
    })
    res = df.pt.wide(index="region", c="quarter", v="sales", a="sum")
    assert "region" in res.columns
    assert "Q1" in res.columns
    assert "Q2" in res.columns


def test_crosstab_basic():
    df = pd.DataFrame({
        "species": ["Adelie", "Adelie", "Gentoo"],
        "island": ["Biscoe", "Dream", "Biscoe"],
    })
    res = df.pt.crosstab("species", "island")
    assert res.loc["Adelie", "Biscoe"] == 1
    assert res.loc["Adelie", "Dream"] == 1
    assert res.loc["Gentoo", "Biscoe"] == 1


def test_crosstab_margins():
    df = pd.DataFrame({
        "species": ["Adelie", "Adelie", "Gentoo"],
        "island": ["Biscoe", "Dream", "Biscoe"],
    })
    res = df.pt.crosstab("species", "island", margins=True, margins_name="Total")
    assert "Total" in res.index
    assert "Total" in res.columns
    assert res.loc["Total", "Total"] == 3


def test_crosstab_normalize():
    df = pd.DataFrame({
        "a": ["x", "x", "y"],
        "b": ["1", "2", "1"],
    })
    res_idx = df.pt.crosstab("a", "b", normalize="index")
    assert res_idx.loc["x"].sum() == pytest.approx(1.0)
    assert res_idx.loc["y"].sum() == pytest.approx(1.0)

    res_all = df.pt.crosstab("a", "b", normalize="all")
    assert res_all.values.sum() == pytest.approx(1.0)


def test_crosstab_values_and_aggfunc():
    df = pd.DataFrame({
        "group": ["A", "A", "B"],
        "category": ["X", "X", "Y"],
        "val": [10.0, 20.0, 30.0],
    })
    res = df.pt.crosstab("group", "category", values="val", aggfunc="mean")
    assert res.loc["A", "X"] == 15.0
    assert res.loc["B", "Y"] == 30.0


def test_crosstab_with_bracketed_spaced_cols():
    df = pd.DataFrame({
        "smoker status": ["Yes", "Yes", "No"],
        "day of week": ["Sat", "Sun", "Sat"],
        "total bill": [10.0, 20.0, 30.0],
    })
    res = df.pt.crosstab(
        "[smoker status]",
        "[day of week]",
        values="[total bill]",
        aggfunc="mean",
        margins=True,
    )
    assert res.loc["Yes", "Sat"] == 10.0
    assert res.loc["Yes", "Sun"] == 20.0
    assert res.loc["No", "Sat"] == 30.0
    assert "All" in res.columns
    assert "All" in res.index


def test_crosstab_multi_index():
    df = pd.DataFrame({
        "species": ["Adelie", "Adelie", "Gentoo"],
        "island": ["Biscoe", "Dream", "Biscoe"],
        "sex": ["M", "F", "M"],
    })
    res = df.pt.crosstab(["species", "island"], "sex")
    assert ("Adelie", "Biscoe") in res.index
    assert res.loc[("Adelie", "Biscoe"), "M"] == 1


def test_crosstab_errors():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "v": [5, 6]})
    with pytest.raises(KeyError, match=r"crosstab\(\): column 'nope' not found"):
        df.pt.crosstab("a", "nope")
    with pytest.raises(ValueError, match="values' and 'aggfunc' must be specified together"):
        df.pt.crosstab("a", "b", values="v")
    with pytest.raises(ValueError, match="values' and 'aggfunc' must be specified together"):
        df.pt.crosstab("a", "b", aggfunc="mean")


if __name__ == '__main__':
    pytest.main()

