import os
import sys
from typing import Any

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae.other_utilities import clean_column_names


def test_to_clip_copies_as_method_and_does_not_shadow_pandas_clip(monkeypatch):
    df = pd.DataFrame({"a": [-1, 2]})
    copied: dict[str, Any] = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["called"] = True
        copied["index"] = kwargs.get("index")

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    # hasattr does not trigger clipboard copy
    assert hasattr(df, "to_clip") is True
    assert copied.get("called") is None

    df.to_clip()
    assert copied["called"] is True
    assert copied["index"] is False

    assert not hasattr(pt, "to_clip")
    assert hasattr(df.pt, "to_clip")

    copied_series: dict[str, Any] = {}
    monkeypatch.setattr(pd.Series, "to_clipboard", lambda self, *args, **kwargs: copied_series.setdefault("called", True))
    df["a"].to_clip()
    assert copied_series.get("called") is True

    clipped = df.clip(lower=0)
    pd.testing.assert_series_equal(clipped["a"], pd.Series([0, 2], name="a"))


def test_handle_missing_fills_object_and_numeric():
    df = pd.DataFrame({"grp": pd.Series(["x", None], dtype=object), "val": [1.0, None]})
    result = pt.handle_missing(df)
    assert result["grp"].tolist() == ["x", "."]
    assert result["val"].tolist() == [1.0, 0.0]
    assert df["grp"].isna().any()


def test_handle_missing_preserves_categorical():
    s = pd.Series(pd.Categorical(["A", None, "B"]))
    df = pd.DataFrame({"cat": s, "val": [1.0, None, 3.0]})
    result = pt.handle_missing(df, fillna="Missing")
    assert isinstance(result["cat"].dtype, pd.CategoricalDtype)
    assert result["cat"].tolist() == ["A", "Missing", "B"]
    assert "Missing" in result["cat"].cat.categories


def test_handle_missing_custom_numeric_fill_and_cols():
    df = pd.DataFrame({"a": [10.0, None], "b": [100.0, None], "txt": ["hello", None]})
    # Only fill 'a' with mean, leave 'b' and 'txt' untouched
    result = pt.handle_missing(df, numeric_fill="mean", cols=["a"])
    assert result["a"].tolist() == [10.0, 10.0]
    assert pd.isna(result["b"].iloc[1])
    assert pd.isna(result["txt"].iloc[1])

    # numeric_fill=None leaves numerics alone
    result2 = pt.handle_missing(df, fillna="N/A", numeric_fill=None)
    assert pd.isna(result2["a"].iloc[1])
    assert result2["txt"].tolist() == ["hello", "N/A"]



def test_cols_sort_orders():
    df = pd.DataFrame({"c": [1], "a": [2], "b": [3]})
    assert pt.cols(df) == ["a", "b", "c"]
    assert pt.cols(df, ascending=False) == ["c", "b", "a"]
    assert pt.cols(df, ascending=None) == ["c", "a", "b"]
    with pytest.raises(ValueError, match="Invalid ascending"):
        pt.cols(df, ascending="nope")



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


def test_handle_missing_all_null_object_column():
    # Lib Issue 15: all-null object column is filled by handle_missing
    df = pd.DataFrame({"a": [None, None]}, dtype=object)
    result = pt.handle_missing(df)
    assert list(result["a"]) == [".", "."]


def test_glimpse_formatting_and_chaining(capsys):
    df = pd.DataFrame({
        "species": ["Adelie", "Gentoo", None],
        "mass": [3700.0, 5200.0, 4100.0],
    })
    out_str = pt.format_glimpse(df, width=80)
    assert "Rows: 3" in out_str
    assert "Columns: 2" in out_str
    assert "$ species" in out_str
    assert "$ mass" in out_str
    assert "'Adelie'" in out_str
    assert "NA" in out_str

    # Method chaining: df.pt.glimpse() returns df
    chained = df.pt.glimpse(width=80)
    assert chained is df
    captured = capsys.readouterr()
    assert "Rows: 3" in captured.out
    assert "Columns: 2" in captured.out


def test_glimpse_empty_dataframe():
    df = pd.DataFrame()
    out_str = pt.format_glimpse(df)
    assert "Rows: 0" in out_str
    assert "Columns: 0" in out_str


def test_dedupe_all_columns():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    res_func = pt.dedupe(df)
    res_acc = df.pt.dedupe()
    expected = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    pd.testing.assert_frame_equal(res_func, expected)
    pd.testing.assert_frame_equal(res_acc, expected)


def test_dedupe_subset_columns():
    df = pd.DataFrame({"id": [1, 1, 2], "val": [10, 20, 30]})
    res = df.pt.dedupe("id")
    expected = pd.DataFrame({"id": [1, 2], "val": [10, 30]})
    pd.testing.assert_frame_equal(res, expected)

    res_last = df.pt.dedupe("id", keep="last")
    expected_last = pd.DataFrame({"id": [1, 2], "val": [20, 30]})
    pd.testing.assert_frame_equal(res_last, expected_last)


def test_dedupe_unknown_column_raises():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(KeyError, match="dedupe: column\\(s\\) \\['nonexistent'\\] not found"):
        df.pt.dedupe("nonexistent")



