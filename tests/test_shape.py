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


if __name__ == '__main__':
    pytest.main()
