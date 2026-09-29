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


def test_wide_raises_on_duplicate_keys():
    """Duplicate (id, country) raises ValueError directing user to pt.pivot()."""
    df = pd.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e", "", "f", "f"],
            "balance": [10, 20, 0, 21, 15, 10, 20, 25],
            "country": ["sg", "cn", "ca", "np", "in", "in", "in", "in"],
        }
    )

    with pytest.raises(ValueError, match=r"wide\(\) encountered duplicate entries.*Use pt\.pivot\(\)"):
        pt.wide(df, c="country", v="balance")


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


def test_wide_rejects_aggregation_arguments():
    """wide() is strictly for 1-to-1 reshaping and rejects aggregation 'a'."""
    df = pd.DataFrame(
        {
            "id": ["a", "b"],
            "balance": [10, 20],
            "country": ["sg", "cn"],
        }
    )

    with pytest.raises(ValueError, match=r"wide\(\) does not support 'a'.*Use pt\.pivot\(\)"):
        pt.wide(df, c="country", v="balance", a="sum")

    with pytest.raises(ValueError, match=r"wide\(\) does not support 'agg'.*Use pt\.pivot\(\)"):
        df.pt.wide(c="country", v="balance", agg="mean")


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
        "region": ["East", "West"],
        "rep": ["Alice", "Bob"],
        "quarter": ["Q1", "Q2"],
        "sales": [100, 200],
    })
    res = df.pt.wide(index="region", c="quarter", v="sales")
    assert "region" in res.columns
    assert "Q1" in res.columns
    assert "Q2" in res.columns


def test_wide_bracketed_names_and_column_validation():
    # Lib Issue 6: wide unquotes bracketed names and checks column existence
    df = pd.DataFrame({
        "region name": ["East", "West"],
        "quarter": ["Q1", "Q2"],
        "sales": [1, 2],
    })
    res = df.pt.wide(index="[region name]", c="quarter", v="sales")
    assert "region name" in res.columns
    assert "Q1" in res.columns
    assert "Q2" in res.columns

    with pytest.raises(KeyError, match=r"wide\(\): index column 'nope' not found in DataFrame"):
        df.pt.wide(index="nope", c="quarter", v="sales")

    with pytest.raises(KeyError, match=r"wide\(\): columns 'c' column 'nope' not found in DataFrame"):
        df.pt.wide(index="region name", c="nope", v="sales")


def test_safe_reset_index_name_collision():
    # Lib Issue 13: index name collision does not raise ValueError
    df = pd.DataFrame({"region": ["East", "West"], "c": ["Q1", "Q2"], "v": [1, 2]})
    df.index.name = "Q1"  # index name collides with pivoted column name "Q1"
    res = df.pt.wide(index="region", c="c", v="v")
    assert "region" in res.columns
    assert "Q1" in res.columns


def test_safe_reset_index_disambiguates_collision():
    # When pivoted column name matches index name, raise ValueError rather than magical renaming
    df = pd.DataFrame({"id": [1, 2], "k": ["id", "a"], "v": [10, 20]})
    with pytest.raises(ValueError, match="collide with existing column name"):
        df.pt.wide(index="id", c="k", v="v")


def test_long_cols_and_id_vars_overlap():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    with pytest.raises(ValueError, match="cannot appear in both 'cols' and 'id_vars'"):
        df.pt.long(cols=["a", "b"], id_vars=["b", "c"])


def test_wide_c_and_v_collisions():
    df = pd.DataFrame({"x": ["A", "B"], "y": [1, 2], "z": [3, 4]})
    with pytest.raises(ValueError, match="'c' and 'v' cannot be the same column"):
        df.pt.wide(index="x", c="y", v="y")

    with pytest.raises(ValueError, match="cannot also be in index columns"):
        df.pt.wide(index=["x", "y"], c="y", v="z")


if __name__ == '__main__':
    pytest.main()
