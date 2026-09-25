import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae.other_utilities import clean_column_names


def test_snip_copies_as_property_and_does_not_shadow_pandas_clip(monkeypatch):
    df = pd.DataFrame({"a": [-1, 2]})
    copied: dict[str, Any] = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["called"] = True
        copied["index"] = kwargs.get("index")

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    # 1. df.snip property without ()
    res = df.snip
    assert res is None
    assert copied["called"] is True
    assert copied["index"] is False

    # 2. pt.snip(df) top-level function
    copied["called"] = False
    pt.snip(df)
    assert copied["called"] is True

    # 3. df.pt.snip accessor property
    copied["called"] = False
    res3 = df.pt.snip
    assert res3 is None
    assert copied["called"] is True

    # 4. Series snip property
    copied_series: dict[str, Any] = {}
    monkeypatch.setattr(pd.Series, "to_clipboard", lambda self, *args, **kwargs: copied_series.setdefault("called", True))
    df["a"].snip
    assert copied_series.get("called") is True

    # 5. verify pandas df.clip is preserved and not shadowed
    clipped = df.clip(lower=0)
    pd.testing.assert_series_equal(clipped["a"], pd.Series([0, 2], name="a"))


def test_handle_missing_fills_object_and_numeric():
    df = pd.DataFrame({"grp": pd.Series(["x", None], dtype=object), "val": [1.0, None]})
    result = pt.handle_missing(df)
    assert result["grp"].tolist() == ["x", "."]
    assert result["val"].tolist() == [1.0, 0.0]
    assert df["grp"].isna().any()


def test_cols_sort_orders():
    df = pd.DataFrame({"c": [1], "a": [2], "b": [3]})
    assert pt.cols(df) == ["a", "b", "c"]
    assert pt.cols(df, ascending=False) == ["c", "b", "a"]
    assert pt.cols(df, ascending=None) == ["c", "a", "b"]
    with pytest.raises(ValueError, match="Invalid ascending"):
        pt.cols(df, ascending="nope")


def test_group_x_count_and_value():
    df = pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3]})
    counted = pt.group_x(df)
    assert counted["n"].tolist() == [2, 2, 1]
    averaged = pt.group_x(df, group=["grp"], a="mean", v="val")
    assert averaged["x"].tolist() == [1.5, 1.5, 3.0]


def test_clean_columns_strip_fill_case():
    df = pd.DataFrame({"  Col A  ": [1], "col   b": [2]})
    result = pt.clean_columns(df, strip=True, fill="_", case="lower")
    assert list(result.columns) == ["col_a", "col___b"]
    assert list(df.columns) == ["  Col A  ", "col   b"]  # original untouched


def test_clean_columns_squeeze_strip_special_dedupe():
    df = pd.DataFrame({"Col A": [1], "col  a": [2], "100% Match!": [3]})
    result = pt.clean_columns(df, strip=True, squeeze=True, strip_special=True, fill="_", case="lower", dedupe=True)
    assert list(result.columns) == ["col_a", "col_a_1", "100_match"]


def test_clean_columns_no_fill_leaves_whitespace():
    df = pd.DataFrame({"col a": [1]})
    result = pt.clean_columns(df, case="upper")
    assert list(result.columns) == ["COL A"]


def test_clean_columns_strip_special_removes_quotes():
    df = pd.DataFrame({"'col a'": [1], '"col b"': [2]})
    result = pt.clean_columns(df, strip_special=True)
    assert list(result.columns) == ["col a", "col b"]


def test_clean_columns_strip_special_keeps_fill_character():
    df = pd.DataFrame({"co-op's data": [1]})
    result = pt.clean_columns(df, strip_special=True, fill="-")
    assert list(result.columns) == ["co-ops-data"]


def test_replace_values_exact_whole_df():
    df = pd.DataFrame({"a": ["x", "not x exactly"], "b": ["x", "y"]})
    result = pt.replace_values(df, {"x": "z"})
    assert result["a"].tolist() == ["z", "not x exactly"]
    assert result["b"].tolist() == ["z", "y"]
    assert df["a"].tolist() == ["x", "not x exactly"]  # original untouched


def test_replace_values_scoped_to_columns():
    df = pd.DataFrame({"a": ["x"], "b": ["x"]})
    result = pt.replace_values(df, {"x": "z"}, c="a")
    assert result["a"].tolist() == ["z"]
    assert result["b"].tolist() == ["x"]


def test_replace_values_substring_match():
    df = pd.DataFrame({"a": ["not a magician exactly"]})
    result = pt.replace_values(df, {"a magician": "the magic"}, exact=False)
    assert result["a"].tolist() == ["not the magic exactly"]


def test_replace_values_substring_match_on_numeric_column_raises():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(ValueError, match="only works on string/object columns"):
        pt.replace_values(df, {1: 9}, exact=False)


def test_handle_missing_leaves_bool_column_untouched():
    df = pd.DataFrame({"b": [True, None]})
    result = pt.handle_missing(df)
    assert result["b"].iloc[0] is True
    assert pd.isna(result["b"].iloc[1])


def test_clean_columns_int_names_are_stringified():
    df = pd.DataFrame({0: [1, 2], "b": [3, 4]})
    result = pt.clean_columns(df, strip=True)
    assert list(result.columns) == ["0", "b"]


def test_clean_columns_dedupe_avoids_new_collisions():
    result = clean_column_names(["revenue", "revenue", "revenue_1"], dedupe=True)
    assert result == ["revenue", "revenue_2", "revenue_1"]
    assert len(set(result)) == len(result)


def test_group_x_raises_if_n_column_already_exists():
    df = pd.DataFrame({"grp": ["x", "x", "y"], "n": [10, 20, 30]})
    with pytest.raises(ValueError, match="column 'n' already exists"):
        pt.group_x(df)


def test_group_x_raises_if_x_column_already_exists():
    df = pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3], "x": [1, 1, 1]})
    with pytest.raises(ValueError, match="column 'x' already exists"):
        pt.group_x(df, group=["grp"], a="mean", v="val")


def test_group_x_raises_on_all_numeric_frame():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    with pytest.raises(ValueError, match="no non-numeric columns to group by"):
        pt.group_x(df)
