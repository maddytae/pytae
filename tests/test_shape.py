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


def test_long_output_name_collisions():
    # Issue 2: long() output names colliding with id_vars, cols, or each other
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    with pytest.raises(ValueError, match="cannot have the same name"):
        df.pt.long(cols=["a"], id_vars=["b"], c="val", v="val")

    with pytest.raises(ValueError, match="collides with kept id column"):
        df.pt.long(cols=["a"], id_vars=["b"], c="b", v="val")

    with pytest.raises(ValueError, match="collides with kept id column"):
        df.pt.long(cols=["a"], id_vars=["b"], c="var", v="b")

def test_wide_no_id_columns():
    # Issue 4: wide() where index_cols is empty
    df = pd.DataFrame({"metric": ["Sales", "Profit"], "val": [100, 20]})
    res = df.pt.wide(c="metric", v="val")
    assert list(res.columns) == ["Profit", "Sales"]
    assert len(res) == 1
    assert res.iloc[0]["Sales"] == 100
    assert res.iloc[0]["Profit"] == 20

    # Duplicates should raise clean ValueError
    df_dup = pd.DataFrame({"metric": ["Sales", "Sales"], "val": [100, 200]})
    with pytest.raises(ValueError, match="encountered duplicate entries"):
        df_dup.pt.wide(c="metric", v="val")


def test_long_bracketed_column_names():
    # Issue 11: long() bracket tokenization for cols and id_vars
    df = pd.DataFrame({
        "order id": [1, 2],
        "total bill": [10.5, 20.0],
        "tip amount": [2.0, 3.5],
    })
    res = df.pt.long(id_vars="[order id]", cols="[total bill], [tip amount]")
    assert list(res.columns) == ["order id", "variable", "value"]
    assert len(res) == 4


if __name__ == '__main__':
    pytest.main()
