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
    averaged = df.group_x(group=["grp"], aggfunc="mean", value="val")
    assert averaged["x"].tolist() == [1.5, 1.5, 3.0]
    via_alias = df.group_x(g="grp", v="val", a="mean")
    assert via_alias["x"].tolist() == [1.5, 1.5, 3.0]
    via_grp = df.group_x(grp="grp", val="val", agg="mean")
    assert via_grp["x"].tolist() == [1.5, 1.5, 3.0]
