import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def test_pt_accessor_select_then_agg_df():
    penguins = pt.sample("penguins")
    out = (
        penguins
        .pt.select("species", "island", "bill_length_mm", "body_mass_g")
        .pt.agg_df(a=["mean", "n"])
    )
    assert list(out.columns)[:3] == ["species", "island", "n"]


def test_pandas_rename_then_pt_agg_df():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 3]})
    out = df.rename(columns={"g": "grp", "v": "val"}).pt.agg_df(a=["sum", "n"])
    assert list(out.columns) == ["grp", "n", "val"]
    assert out.loc[out["grp"] == "a", "val"].iloc[0] == 3


def test_pt_select_then_pandas_head():
    penguins = pt.sample("penguins")
    out = penguins.pt.select("species", "body_mass_g").head(3)
    assert list(out.columns) == ["species", "body_mass_g"]
    assert len(out) == 3
