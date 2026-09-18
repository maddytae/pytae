import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae  # noqa: F401


def test_to_clip_copies_and_does_not_shadow_pandas_clip(monkeypatch):
    df = pd.DataFrame({"a": [-1, 2]})
    copied = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["called"] = True
        copied["index"] = kwargs.get("index")

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)
    df.to_clip()
    assert copied["called"] is True
    assert copied["index"] is False

    clipped = df.clip(lower=0)
    pd.testing.assert_series_equal(clipped["a"], pd.Series([0, 2], name="a"))


def test_handle_missing_fills_object_and_numeric():
    df = pd.DataFrame({"grp": pd.Series(["x", None], dtype=object), "val": [1.0, None]})
    result = df.handle_missing()
    assert result["grp"].tolist() == ["x", "."]
    assert result["val"].tolist() == [1.0, 0.0]
    assert df["grp"].isna().any()


def test_cols_sort_orders():
    df = pd.DataFrame({"c": [1], "a": [2], "b": [3]})
    assert df.cols() == ["a", "b", "c"]
    assert df.cols(ascending=False) == ["c", "b", "a"]
    assert df.cols(ascending=None) == ["c", "a", "b"]
    with pytest.raises(ValueError, match="Invalid ascending"):
        df.cols(ascending="nope")


def test_group_x_count_and_value():
    df = pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3]})
    counted = df.group_x()
    assert counted["n"].tolist() == [2, 2, 1]
    averaged = df.group_x(group=["grp"], a="mean", v="val")
    assert averaged["x"].tolist() == [1.5, 1.5, 3.0]


def test_clean_columns_strip_fill_case():
    df = pd.DataFrame({"  Col A  ": [1], "col   b": [2]})
    result = df.clean_columns(strip=True, fill="_", case="lower")
    assert list(result.columns) == ["col_a", "col___b"]
    assert list(df.columns) == ["  Col A  ", "col   b"]  # original untouched


def test_clean_columns_squeeze_strip_special_dedupe():
    df = pd.DataFrame({"Col A": [1], "col  a": [2], "100% Match!": [3]})
    result = df.clean_columns(strip=True, squeeze=True, strip_special=True, fill="_", case="lower", dedupe=True)
    assert list(result.columns) == ["col_a", "col_a_1", "100_match"]


def test_clean_columns_no_fill_leaves_whitespace():
    df = pd.DataFrame({"col a": [1]})
    result = df.clean_columns(case="upper")
    assert list(result.columns) == ["COL A"]


def test_clean_columns_strip_special_removes_quotes():
    df = pd.DataFrame({"'col a'": [1], '"col b"': [2]})
    result = df.clean_columns(strip_special=True)
    assert list(result.columns) == ["col a", "col b"]


def test_clean_columns_strip_special_keeps_fill_character():
    df = pd.DataFrame({"co-op's data": [1]})
    result = df.clean_columns(strip_special=True, fill="-")
    assert list(result.columns) == ["co-ops-data"]


def test_replace_values_exact_whole_df():
    df = pd.DataFrame({"a": ["x", "not x exactly"], "b": ["x", "y"]})
    result = df.replace_values({"x": "z"})
    assert result["a"].tolist() == ["z", "not x exactly"]
    assert result["b"].tolist() == ["z", "y"]
    assert df["a"].tolist() == ["x", "not x exactly"]  # original untouched


def test_replace_values_scoped_to_columns():
    df = pd.DataFrame({"a": ["x"], "b": ["x"]})
    result = df.replace_values({"x": "z"}, c="a")
    assert result["a"].tolist() == ["z"]
    assert result["b"].tolist() == ["x"]


def test_replace_values_substring_match():
    df = pd.DataFrame({"a": ["not a magician exactly"]})
    result = df.replace_values({"a magician": "the magic"}, exact=False)
    assert result["a"].tolist() == ["not the magic exactly"]
