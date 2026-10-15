from __future__ import annotations

import math

import pandas as pd
import polars as pl
import pytest

import pytae as pt


def test_df_fillna_scalar_default_nans_true():
    # Both NaN and null are filled by default
    df = pt.DataFrame({
        "flt": [1.0, float("nan"), None],
        "txt": ["a", None, "c"],
        "num": [10, None, 30],
    })
    res = df.fillna(0.0)
    assert res["flt"].to_list() == [1.0, 0.0, 0.0]
    # String column untouched because 0.0 is float
    assert res["txt"].to_list() == ["a", None, "c"]
    assert res["num"].to_list() == [10.0, 0.0, 30.0]


def test_df_fillna_scalar_nans_false():
    # Only null is filled; NaN remains intact
    df = pt.DataFrame({
        "flt": [1.0, float("nan"), None],
        "txt": ["a", None, "c"],
    })
    res = df.fillna(0.0, nans=False)
    flt_vals = res["flt"].to_list()
    assert flt_vals[0] == 1.0
    assert math.isnan(flt_vals[1])
    assert flt_vals[2] == 0.0


def test_df_fillna_dict():
    df = pt.DataFrame({
        "flt": [1.0, float("nan"), None],
        "txt": ["a", None, "c"],
        "num": [10, None, 30],
    })
    res = df.fillna({"flt": -1.0, "txt": "MISSING", "num": 0})
    assert res["flt"].to_list() == [1.0, -1.0, -1.0]
    assert res["txt"].to_list() == ["a", "MISSING", "c"]
    assert res["num"].to_list() == [10, 0, 30]


def test_df_fillna_subset_and_cols():
    df = pt.DataFrame({
        "flt1": [1.0, float("nan"), None],
        "flt2": [2.0, float("nan"), None],
    })
    # Target flt1 only via *cols
    r1 = df.fillna(0.0, "flt1")
    assert r1["flt1"].to_list() == [1.0, 0.0, 0.0]
    assert math.isnan(r1["flt2"].to_list()[1])
    assert r1["flt2"].to_list()[2] is None

    # Target flt2 only via subset=
    r2 = df.fillna(99.0, subset=["flt2"])
    assert r2["flt2"].to_list() == [2.0, 99.0, 99.0]
    assert math.isnan(r2["flt1"].to_list()[1])


def test_df_fillna_missing_column_raises_key_error():
    df = pt.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(KeyError, match="fillna: column\\(s\\) \\['non_existent'\\] not found"):
        df.fillna(0, "non_existent")


def test_df_fillna_missing_value_raises_type_error():
    df = pt.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(TypeError, match="fillna\\(\\) missing required argument: 'value'"):
        df.fillna()


def test_df_fill_null_and_fill_nan():
    df = pt.DataFrame({
        "flt": [1.0, float("nan"), None],
    })
    # fill_null fills null only (nans=False)
    r_null = df.fill_null(0.0)
    assert math.isnan(r_null["flt"].to_list()[1])
    assert r_null["flt"].to_list()[2] == 0.0

    # fill_nan fills NaN only, leaving null intact
    r_nan = df.fill_nan(0.0)
    assert r_nan["flt"].to_list()[0] == 1.0
    assert r_nan["flt"].to_list()[1] == 0.0
    assert r_nan["flt"].to_list()[2] is None


def test_functional_and_accessor_fillna():
    # 1. Polars accessor
    pldf = pl.DataFrame({"x": [1.0, float("nan"), None]})
    res_pl = pldf.pt.fillna(0.0)
    assert isinstance(res_pl, pt.DataFrame)
    assert res_pl["x"].to_list() == [1.0, 0.0, 0.0]

    # 2. Pandas accessor
    pddf = pd.DataFrame({"x": [1.0, float("nan"), None]})
    res_pd = pddf.pt.fillna(0.0)
    assert isinstance(res_pd, pt.DataFrame)
    assert res_pd["x"].to_list() == [1.0, 0.0, 0.0]

    # 3. Top-level pt.fillna
    res_fn = pt.fillna(pldf, 5.0)
    assert res_fn["x"].to_list() == [1.0, 5.0, 5.0]


def test_grouped_dataframe_fillna():
    df = pt.DataFrame({
        "grp": ["A", "A", "B", "B"],
        "val": [1.0, float("nan"), None, 4.0],
    })
    res = df.by("grp").fillna(0.0)
    assert res["val"].to_list() == [1.0, 0.0, 0.0, 4.0]
