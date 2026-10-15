import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def test_pt_accessor_select_then_agg():
    penguins = pt.sample("penguins")
    out = penguins.pt.by("species", "island").pt.agg(a=["mean", "n"])
    assert list(out.columns)[:3] == ["species", "island", "n"]


def test_pandas_rename_then_pt_agg():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 3]})
    out = df.rename(columns={"g": "grp", "v": "val"}).pt.by("grp").pt.agg(a=["sum", "n"])
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


def test_pt_accessor_dropna_pandas_and_polars():
    import polars as pl

    pdf = pd.DataFrame({"a": [1.0, None, 3.0], "b": [10.0, 20.0, 30.0]})
    pldf = pl.DataFrame({"a": [1.0, None, 3.0], "b": [10.0, 20.0, 30.0]})

    # Option B: bare dropna on partially null rows keeps all rows
    assert len(pdf.pt.dropna()) == 3
    assert len(pldf.pt.dropna()) == 3

    # Targeted dropna on column 'a' drops the null row
    assert len(pdf.pt.dropna("a")) == 2
    assert len(pldf.pt.dropna("a")) == 2

    # Aliases drop_nulls and drop_na
    assert len(pdf.pt.drop_nulls("a")) == 2
    assert len(pldf.pt.drop_nulls("a")) == 2
    assert len(pdf.pt.drop_na("a")) == 2
    assert len(pldf.pt.drop_na("a")) == 2


def test_pt_sample_datasets_and_row_sampling():
    import polars as pl

    # 1. Bundled dataset loading
    penguins = pt.sample("penguins")
    assert len(penguins) == 344
    assert len(pt.sample()) == 344
    assert len(pt.sample_data["tips"]) == 244

    # 2. DataFrame.sample()
    s1 = penguins.sample(5, seed=42)
    assert len(s1) == 5
    assert isinstance(s1, pt.DataFrame)

    # 3. df.pt.sample() on pytae DataFrame
    s2 = penguins.pt.sample(frac=0.1, seed=42)
    assert len(s2) == 34

    # 4. pt.sample(df, ...) top-level verb
    s3 = pt.sample(penguins, 10, seed=42)
    assert len(s3) == 10

    # 5. Pandas DataFrame with .pt.sample()
    pdf = pd.DataFrame({"x": range(100)})
    s4 = pdf.pt.sample(7, seed=42)
    assert len(s4) == 7

    # 6. Polars DataFrame with .pt.sample()
    pldf = pl.DataFrame({"x": range(100)})
    s5 = pldf.pt.sample(8, seed=42)
    assert len(s5) == 8

    # 7. Grouped sampling
    p_grouped = penguins.pt.by("species").sample(2, seed=42)
    assert len(p_grouped) == 6  # 3 species * 2 rows
