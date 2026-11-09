"""Tests for universal pt.read(), pt.scan(), and df.to() / df.write()."""

import warnings
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae.dataframe import DataFrame


def test_universal_read_formats(tmp_path):
    # Parquet
    p_pq = tmp_path / "test.parquet"
    pl.DataFrame({"a": [1, 2, 3]}).write_parquet(p_pq)
    df_pq = pt.read(p_pq)
    assert isinstance(df_pq, DataFrame)
    assert df_pq["a"].to_list() == [1, 2, 3]

    # CSV
    p_csv = tmp_path / "test.csv"
    pl.DataFrame({"b": ["x", "y"]}).write_csv(p_csv)
    df_csv = pt.read(p_csv)
    assert isinstance(df_csv, DataFrame)
    assert df_csv["b"].to_list() == ["x", "y"]

    # IPC
    p_ipc = tmp_path / "test.ipc"
    pl.DataFrame({"c": [10.5, 20.5]}).write_ipc(p_ipc)
    df_ipc = pt.read(p_ipc)
    assert isinstance(df_ipc, DataFrame)
    assert df_ipc["c"].to_list() == [10.5, 20.5]

    # NDJSON
    p_nd = tmp_path / "test.ndjson"
    pl.DataFrame({"d": [True, False]}).write_ndjson(p_nd)
    df_nd = pt.read(p_nd)
    assert isinstance(df_nd, DataFrame)
    assert df_nd["d"].to_list() == [True, False]

    # Excel
    p_xlsx = tmp_path / "test.xlsx"
    pd.DataFrame({"e": [100, 200]}).to_excel(p_xlsx, index=False)
    df_xlsx = pt.read(p_xlsx)
    assert isinstance(df_xlsx, DataFrame)
    assert df_xlsx["e"].to_list() == [100, 200]


def test_universal_scan_formats(tmp_path):
    p_pq = tmp_path / "test_lazy.parquet"
    pl.DataFrame({"val": [1, 2]}).write_parquet(p_pq)
    lazy_df = pt.scan(p_pq)
    assert isinstance(lazy_df, DataFrame)
    assert lazy_df.is_lazy
    collected = lazy_df.collect()
    assert collected["val"].to_list() == [1, 2]


def test_universal_to_file_and_return_self(tmp_path):
    df = pt.DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]})

    # 1. Output to parquet and check return self
    out_pq = tmp_path / "out.parquet"
    res = df.to(out_pq)
    assert res is df  # Returns self for chaining!
    assert out_pq.exists()
    assert pt.read(out_pq)["name"].to_list() == ["Alice", "Bob"]

    # 2. Output to csv
    out_csv = tmp_path / "out.csv"
    res_csv = df.to(out_csv)
    assert res_csv is df
    assert out_csv.exists()
    assert pt.read(out_csv)["age"].to_list() == [25, 30]

    # 3. Output to ipc
    out_ipc = tmp_path / "out.ipc"
    assert df.to(out_ipc) is df
    assert out_ipc.exists()

    # 4. Output to excel
    out_xlsx = tmp_path / "out.xlsx"
    assert df.to(out_xlsx) is df
    assert out_xlsx.exists()

    # 5. write() alias works identically
    out_pq2 = tmp_path / "out2.parquet"
    assert df.write(out_pq2) is df
    assert out_pq2.exists()


def test_universal_to_in_memory_and_clipboard(monkeypatch):
    df = pt.DataFrame({"id": [1, 2], "score": [95.0, 88.5]})

    # to("pandas")
    pdf = df.to("pandas")
    assert isinstance(pdf, pd.DataFrame)
    assert list(pdf["id"]) == [1, 2]

    # to("polars")
    pldf = df.to("polars")
    assert isinstance(pldf, pl.DataFrame)
    assert pldf["score"].to_list() == [95.0, 88.5]

    # to("pytae")
    pytae_df = df.to("pytae")
    assert pytae_df is df

    # to("clip") returns self
    clip_called = []
    monkeypatch.setattr(df, "to_clip", lambda: clip_called.append(True))
    assert df.to("clip") is df
    assert len(clip_called) == 1


def test_accessor_to_bridge():
    pdf = pd.DataFrame({"x": [10, 20]})
    # Bridge from pandas to pytae
    pt_df = pdf.pt.to("pytae")
    assert isinstance(pt_df, DataFrame)
    assert pt_df["x"].to_list() == [10, 20]

    # Bridge back to pandas
    assert isinstance(pt_df.to("pandas"), pd.DataFrame)

    pldf = pl.DataFrame({"y": ["a", "b"]})
    # Bridge from polars to pytae
    pt_df2 = pldf.pt.to("pytae")
    assert isinstance(pt_df2, DataFrame)
    assert pt_df2["y"].to_list() == ["a", "b"]


def test_deprecated_readers_and_writers_warn(tmp_path):
    p_pq = tmp_path / "legacy.parquet"
    pl.DataFrame({"num": [1]}).write_parquet(p_pq)

    with pytest.deprecated_call():
        df = pt.read_parquet(p_pq)
    assert df["num"].to_list() == [1]

    with pytest.deprecated_call():
        lazy = pt.scan_parquet(p_pq)
    assert lazy.collect()["num"].to_list() == [1]

    out_p = tmp_path / "legacy_out.parquet"
    with pytest.deprecated_call():
        df.to_parquet(out_p)
    assert out_p.exists()
