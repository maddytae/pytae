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
    monkeypatch.setattr(df, "_to_clip_internal", lambda: clip_called.append(True))
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


def test_deprecated_readers_and_writers_warn(tmp_path, monkeypatch):
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

    # Deprecated to_pandas(), to_polars(), to_clip(), to_pytae()
    with pytest.deprecated_call():
        assert isinstance(df.to_pandas(), pd.DataFrame)

    with pytest.deprecated_call():
        assert isinstance(df.to_polars(), pl.DataFrame)

    monkeypatch.setattr(df, "_to_clip_internal", lambda: None)
    with pytest.deprecated_call():
        df.to_clip()

    with pytest.deprecated_call():
        assert df.to_pytae() is df


def test_multi_file_and_glob_read_and_scan(tmp_path):
    # Prepare 2 Parquet files
    p1 = tmp_path / "part1.parquet"
    p2 = tmp_path / "part2.parquet"
    pl.DataFrame({"id": [1, 2], "val": ["a", "b"]}).write_parquet(p1)
    pl.DataFrame({"id": [3, 4], "val": ["c", "d"]}).write_parquet(p2)

    # Read list of files
    df_list = pt.read([p1, p2])
    assert df_list.shape == (4, 2)
    assert df_list["id"].to_list() == [1, 2, 3, 4]

    # Scan list of files
    lazy_list = pt.scan([p1, p2])
    assert lazy_list.is_lazy
    assert lazy_list.collect().shape == (4, 2)

    # Glob scan
    glob_str = str(tmp_path / "part*.parquet")
    lazy_glob = pt.scan(glob_str)
    assert lazy_glob.collect().shape == (4, 2)

    # Multi-file CSV
    c1 = tmp_path / "c1.csv"
    c2 = tmp_path / "c2.csv"
    pl.DataFrame({"x": [10], "y": [20]}).write_csv(c1)
    pl.DataFrame({"x": [30], "y": [40]}).write_csv(c2)

    df_csv_list = pt.read([c1, c2])
    assert df_csv_list.shape == (2, 2)
    assert df_csv_list["x"].to_list() == [10, 30]

    lazy_csv_list = pt.scan([c1, c2])
    assert lazy_csv_list.collect().shape == (2, 2)


def test_partitioned_lake_writes_and_reads(tmp_path):
    df = pt.DataFrame({
        "year": [2024, 2024, 2025],
        "region": ["North", "South", "North"],
        "sales": [100.0, 250.0, 300.0],
    })

    lake_dir = tmp_path / "orders_lake"
    # Write partitioned lake
    res = df.to(lake_dir, partition_by=["year", "region"])
    assert res is df
    assert lake_dir.exists()

    # Read back partitioned lake with pt.read()
    read_lake = pt.read(lake_dir)
    assert read_lake.shape == (3, 3)
    assert set(read_lake["region"].to_list()) == {"North", "South"}

    # Read back with pt.scan()
    lazy_lake = pt.scan(lake_dir)
    assert lazy_lake.is_lazy
    assert lazy_lake.collect().shape == (3, 3)


def test_extra_in_memory_export_targets():
    df = pt.DataFrame({"col_a": [1, 2], "col_b": ["apple", "banana"]})

    # to("records") / to("rows")
    records = df.to("records")
    assert records == [
        {"col_a": 1, "col_b": "apple"},
        {"col_a": 2, "col_b": "banana"},
    ]
    assert df.to("rows") == records

    # to("dict") / to("columns")
    col_dict = df.to("dict")
    assert col_dict == {"col_a": [1, 2], "col_b": ["apple", "banana"]}
    assert df.to("columns") == col_dict

    # to("arrow")
    table = df.to("arrow")
    import pyarrow as pa
    assert isinstance(table, pa.Table)
    assert table.num_rows == 2

    # to("numpy") / to("np")
    arr = df.select("col_a").to("numpy")
    import numpy as np
    assert isinstance(arr, np.ndarray)


def test_cli_shell_completion(tmp_path, monkeypatch):
    from pytae.completion import run_completion, run_install_completion

    # Test scripts generation
    for sh in ("zsh", "bash", "fish"):
        assert run_completion([sh]) == 0

    # Test installation
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    # Install zsh completion
    res_zsh = run_install_completion(["zsh"])
    assert res_zsh == 0
    assert (fake_home / ".pytae" / "completion" / "_pytae.zsh").exists()
    assert "source" in (fake_home / ".zshrc").read_text()

    # Install bash completion
    res_bash = run_install_completion(["bash"])
    assert res_bash == 0
    assert (fake_home / ".pytae" / "completion" / "pytae.bash").exists()
    assert "source" in (fake_home / ".bashrc").read_text()

    # Install fish completion
    res_fish = run_install_completion(["fish"])
    assert res_fish == 0
    assert (fake_home / ".config" / "fish" / "completions" / "pytae.fish").exists()
