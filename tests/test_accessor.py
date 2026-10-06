import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def test_pt_accessor_select_then_agg():
    penguins = pt.sample("penguins")
    out = (
        penguins
        .pt.agg(["species", "island"], a=["mean", "n"])
    )
    assert list(out.columns)[:3] == ["species", "island", "n"]


def test_pandas_rename_then_pt_agg():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 3]})
    out = df.rename(columns={"g": "grp", "v": "val"}).pt.agg("grp", a=["sum", "n"])
    assert list(out.columns) == ["grp", "n", "val"]
    assert out.loc[out["grp"] == "a", "val"].iloc[0] == 3


def test_pt_accessor_agg_df_deprecated():
    import pytest
    df = pd.DataFrame({"g": ["a", "b"], "v": [1, 2]})
    with pytest.raises(AttributeError, match="df.pt.agg_df.*removed; use df.pt.agg"):
        df.pt.agg_df("g")


def test_pt_select_then_pandas_head():
    penguins = pt.sample("penguins")
    out = penguins.pt.select("species", "body_mass_g").head(3)
    assert list(out.columns) == ["species", "body_mass_g"]
    assert len(out) == 3


def test_pt_accessor_safe_reset_index():
    df = pd.DataFrame({"a": [1, 2]}, index=pd.Index(["x", "y"], name="idx"))
    res = df.pt.safe_reset_index()
    assert list(res.columns) == ["idx", "a"]
    assert list(res["idx"]) == ["x", "y"]


def test_pt_accessor_to_clip(monkeypatch):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    clip_called = []

    def mock_to_clipboard(self, *args, **kwargs):
        clip_called.append((args, kwargs))

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", mock_to_clipboard)
    df.pt.to_clip()
    assert len(clip_called) == 1
    assert clip_called[0][1].get("index") is False

