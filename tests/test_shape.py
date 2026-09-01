import pytest
import numpy as np
import pandas as pd

import sys
import os

# Assuming the current working directory is where the project root is
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pytae import long, wide, sample

def test_long():

    penguins = sample("penguins")

    
    result = penguins.long(col='features')
    

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

    result = df.wide(col="country", value="balance")

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

    result = df.wide(col="country", value="balance")

    expected_df = df.pivot(index="id", columns="country", values="balance").reset_index()
    expected_df.columns.name = None
    pd.testing.assert_frame_equal(result, expected_df)


def test_long_and_wide_accept_short_aliases():
    df = pd.DataFrame({"grp": ["a", "b"], "n": [1, 2], "x": [10, 20]})
    via_full = df.long(column="metric", value="reading")
    via_short = df.long(c="metric", v="reading")
    pd.testing.assert_frame_equal(via_full, via_short)
    pd.testing.assert_frame_equal(via_full, df.long(col="metric", val="reading"))

    long_df = pd.DataFrame(
        {"id": ["a", "b"], "country": ["sg", "cn"], "balance": [10, 20]}
    )
    pd.testing.assert_frame_equal(
        long_df.wide(column="country", value="balance"),
        long_df.wide(c="country", v="balance"),
    )
    pd.testing.assert_frame_equal(
        long_df.wide(column="country", value="balance", aggfunc="mean"),
        long_df.wide(col="country", v="balance", a="mean"),
    )


def test_reshape_rejects_duplicate_aliases():
    df = pd.DataFrame({"grp": ["a"], "n": [1]})
    with pytest.raises(ValueError, match="column given more than once"):
        df.long(col="metric", c="other")
    
if __name__ == '__main__':
    pytest.main()
