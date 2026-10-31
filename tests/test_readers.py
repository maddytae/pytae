import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


import pytae.readers as readers
from pytae.readers import get_reader, write_dataframe


def _frame():
    return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


def test_csv_reader_shape_head_tail_and_load(tmp_path):
    path = tmp_path / "t.csv"
    df = _frame()
    df.to_csv(path, index=False)
    reader = get_reader(path)

    assert reader.shape() == (3, 2)
    assert reader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(reader.head(2), df.head(2))
    pd.testing.assert_frame_equal(reader.tail(1).reset_index(drop=True), df.tail(1).reset_index(drop=True))
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)


def test_parquet_reader_roundtrip(tmp_path):
    path = tmp_path / "t.parquet"
    df = _frame()
    df.to_parquet(path, index=False)
    reader = get_reader(path)

    assert reader.shape() == (3, 2)
    assert reader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(reader.head(1), df.head(1))
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)


def test_parquet_head_and_tail_keep_schema_when_empty(tmp_path):
    path = tmp_path / "empty.parquet"
    pd.DataFrame({"a": pd.Series(dtype="int64"), "b": pd.Series(dtype="object")}).to_parquet(path, index=False)
    reader = get_reader(path)

    for frame in (reader.head(5), reader.tail(5)):
        assert list(frame.columns) == ["a", "b"]
        assert len(frame) == 0


def test_txt_reader_tab_delimited(tmp_path):
    path = tmp_path / "t.txt"
    df = _frame()
    df.to_csv(path, sep="\t", index=False)
    reader = get_reader(path)

    assert reader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)


def test_dat_reader_pipe_delimited(tmp_path):
    path = tmp_path / "t.dat"
    df = _frame()
    df.to_csv(path, sep="|", index=False)
    reader = get_reader(path)

    assert reader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)


def test_dat_reader_defaults_to_latin1_encoding(tmp_path):
    path = tmp_path / "t.dat"
    df = pd.DataFrame({"name": ["café", "naïve"]})
    df.to_csv(path, sep="|", index=False, encoding="latin-1")

    reader = get_reader(path)
    assert reader.encoding == "latin-1"
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)


def test_dat_reader_encoding_override():
    path = Path("dummy.dat")
    assert get_reader(path).encoding == "latin-1"
    assert get_reader(path, encoding="utf-8").encoding == "utf-8"


def test_txt_reader_encoding_defaults_to_none(tmp_path):
    path = tmp_path / "t.txt"
    df = _frame()
    df.to_csv(path, sep="\t", index=False)
    reader = get_reader(path)
    assert reader.encoding is None


def test_write_dataframe_csv_and_parquet(tmp_path):
    df = _frame()
    csv_path = tmp_path / "out.csv"
    pq_path = tmp_path / "out.parquet"
    write_dataframe(df, csv_path)
    write_dataframe(df, pq_path)
    pd.testing.assert_frame_equal(pd.read_csv(csv_path), df)
    pd.testing.assert_frame_equal(pd.read_parquet(pq_path), df)


def test_parquet_to_dataframe_keeps_schema_when_empty_with_nrows_or_progress(tmp_path):
    path = tmp_path / "empty.parquet"
    pd.DataFrame({"a": pd.Series(dtype="int64"), "b": pd.Series(dtype="int64")}).to_parquet(path)
    reader = get_reader(path)

    assert list(reader.to_dataframe().columns) == ["a", "b"]
    assert list(reader.to_dataframe(nrows=5).columns) == ["a", "b"]
    assert list(reader.to_dataframe(progress=True).columns) == ["a", "b"]


def test_csv_shape_counts_quoted_newline_as_one_row(tmp_path):
    path = tmp_path / "q.csv"
    path.write_text('a,b\n"hello\nworld",2\nfoo,3\n')
    reader = get_reader(path)

    assert reader.shape() == (2, 2)
    pd.testing.assert_frame_equal(reader.to_dataframe(), pd.read_csv(path))


def test_csv_tail_correct_after_quoted_newline(tmp_path):
    path = tmp_path / "q.csv"
    path.write_text('a,b\n"hello\nworld",2\nfoo,3\n')
    reader = get_reader(path)

    tail = reader.tail(1)
    assert tail["a"].tolist() == ["foo"]


def test_empty_csv_raises_friendly_error(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")
    reader = get_reader(path)

    with pytest.raises(ValueError, match="empty or not a valid"):
        reader.shape()


def test_nrows_caps_head_and_tail(tmp_path):
    from pytae.cli_pipeline import _Pipeline

    path = tmp_path / "x.csv"
    pd.DataFrame({"a": range(20), "b": range(20)}).to_csv(path, index=False)

    pipe = _Pipeline(get_reader(path), nrows=5)
    assert len(pipe.head(15)) == 5

    pipe2 = _Pipeline(get_reader(path), nrows=5)
    assert pipe2.tail(3)["a"].tolist() == [2, 3, 4]


def test_write_dataframe_dat_uses_pipe_delimiter(tmp_path):
    df = _frame()
    dat_path = tmp_path / "out.dat"
    write_dataframe(df, dat_path)
    pd.testing.assert_frame_equal(pd.read_csv(dat_path, sep="|"), df)


def test_write_dataframe_dat_defaults_to_latin1(tmp_path):
    df = pd.DataFrame({"name": ["café", "naïve"]})
    dat_path = tmp_path / "out.dat"
    write_dataframe(df, dat_path)
    pd.testing.assert_frame_equal(pd.read_csv(dat_path, sep="|", encoding="latin-1"), df)
    pd.testing.assert_frame_equal(get_reader(dat_path).to_dataframe(), df)


def test_unsupported_reader_and_writer(tmp_path):
    bad = tmp_path / "x.xlsx"
    bad.write_text("nope")
    with pytest.raises(ValueError, match="unsupported"):
        get_reader(bad)
    with pytest.raises(ValueError, match="unsupported"):
        write_dataframe(_frame(), tmp_path / "x.sas7bdat")


def test_csv_and_txt_dtypes_sample_not_full_file(tmp_path, monkeypatch):
    monkeypatch.setattr(readers, "DTYPE_SAMPLE_ROWS", 3)
    rows = ["n,label"] + [f"{i},a" for i in range(3)] + ["not_a_number,z"]
    csv_path = tmp_path / "t.csv"
    txt_path = tmp_path / "t.txt"
    csv_path.write_text("\n".join(rows) + "\n")
    txt_path.write_text("\n".join(row.replace(",", "\t") for row in rows) + "\n")

    csv_dtypes = get_reader(csv_path).dtypes()
    txt_dtypes = get_reader(txt_path).dtypes()
    assert pd.api.types.is_integer_dtype(csv_dtypes["n"])
    assert pd.api.types.is_integer_dtype(txt_dtypes["n"])
    full = pd.read_csv(csv_path)
    assert not pd.api.types.is_integer_dtype(full["n"])


def test_sas_reader_defaults_to_latin1():
    path = Path("dummy.sas7bdat")
    assert get_reader(path).encoding == "latin-1"
    assert get_reader(path, encoding="utf-8").encoding == "utf-8"


def test_get_reader_missing_suffix(tmp_path):
    path = Path(tmp_path / "noext")
    path.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="unsupported"):
        get_reader(path)


def test_jsonl_reader_and_writer(tmp_path):
    df = _frame()
    jsonl_path = tmp_path / "test.jsonl"
    write_dataframe(df, jsonl_path)
    assert jsonl_path.exists()

    reader = get_reader(jsonl_path)
    assert reader.shape() == (3, 2)
    assert reader.columns() == ["a", "b"]
    assert len(reader.dtypes()) == 2
    pd.testing.assert_frame_equal(reader.head(2), df.head(2))
    pd.testing.assert_frame_equal(reader.tail(1).reset_index(drop=True), df.tail(1).reset_index(drop=True))
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)
    pd.testing.assert_frame_equal(reader.to_dataframe(columns=["a"]), df[["a"]])

    # Test ndjson alias
    ndjson_path = tmp_path / "test.ndjson"
    write_dataframe(df, ndjson_path)
    nd_reader = get_reader(ndjson_path)
    assert nd_reader.shape() == (3, 2)
    pd.testing.assert_frame_equal(nd_reader.to_dataframe(), df)


def test_jsonl_reader_empty_error(tmp_path):
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("")
    reader = get_reader(empty_file)
    with pytest.raises(ValueError, match="is empty or not a valid JSON Lines file"):
        reader.columns()


def test_jsonl_chunked_progress(tmp_path):
    df = pd.DataFrame({"x": range(15), "y": [f"val_{i}" for i in range(15)]})
    path = tmp_path / "chunked.jsonl"
    write_dataframe(df, path, progress=True, chunk_size=5)

    reader = get_reader(path, chunk_size=5)
    read_df = reader.to_dataframe(progress=True, chunk_size=5)
    pd.testing.assert_frame_equal(read_df, df)


def test_compressed_csv_and_jsonl(tmp_path):
    df = _frame()
    csv_gz = tmp_path / "data.csv.gz"
    write_dataframe(df, csv_gz, progress=True, chunk_size=2)
    assert csv_gz.exists()

    reader = get_reader(csv_gz)
    assert reader.shape() == (3, 2)
    assert reader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)

    jsonl_gz = tmp_path / "data.jsonl.gz"
    write_dataframe(df, jsonl_gz, progress=True, chunk_size=2)
    assert jsonl_gz.exists()

    jreader = get_reader(jsonl_gz)
    assert jreader.shape() == (3, 2)
    assert jreader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(jreader.to_dataframe(), df)


def test_compressed_txt_and_dat(tmp_path):
    df = _frame()
    txt_gz = tmp_path / "data.txt.gz"
    write_dataframe(df, txt_gz)
    assert txt_gz.exists()
    reader = get_reader(txt_gz)
    assert reader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)

    dat_gz = tmp_path / "data.dat.gz"
    write_dataframe(df, dat_gz)
    assert dat_gz.exists()
    dreader = get_reader(dat_gz)
    assert dreader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(dreader.to_dataframe(), df)


def test_dedicated_readers_and_scanners(tmp_path):
    import polars as pl

    import pytae as pt

    raw = pl.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})

    # 1. Parquet
    pq_path = tmp_path / "test.parquet"
    raw.write_parquet(pq_path)
    df_pq = pt.read_parquet(pq_path)
    assert isinstance(df_pq, pt.DataFrame)
    assert not df_pq.is_lazy
    assert df_pq["x"].to_list() == [1, 2, 3]

    lazy_pq = pt.scan_parquet(pq_path)
    assert lazy_pq.is_lazy
    assert lazy_pq.collect()["x"].to_list() == [1, 2, 3]

    # 2. CSV
    csv_path = tmp_path / "test.csv"
    raw.write_csv(csv_path)
    df_csv = pt.read_csv(csv_path)
    assert isinstance(df_csv, pt.DataFrame)
    assert not df_csv.is_lazy
    assert df_csv["y"].to_list() == ["a", "b", "c"]

    lazy_csv = pt.scan_csv(csv_path)
    assert lazy_csv.is_lazy
    assert lazy_csv.collect()["y"].to_list() == ["a", "b", "c"]

    # 3. NDJSON
    ndjson_path = tmp_path / "test.ndjson"
    raw.write_ndjson(ndjson_path)
    df_nd = pt.read_ndjson(ndjson_path)
    assert isinstance(df_nd, pt.DataFrame)
    assert df_nd["x"].to_list() == [1, 2, 3]

    lazy_nd = pt.scan_ndjson(ndjson_path)
    assert lazy_nd.is_lazy
    assert lazy_nd.collect()["x"].to_list() == [1, 2, 3]

    # 4. JSON
    json_path = tmp_path / "test.json"
    raw.write_json(json_path)
    df_json = pt.read_json(json_path)
    assert isinstance(df_json, pt.DataFrame)
    assert df_json["x"].to_list() == [1, 2, 3]

    # 5. IPC
    ipc_path = tmp_path / "test.arrow"
    raw.write_ipc(ipc_path)
    df_ipc = pt.read_ipc(ipc_path)
    assert isinstance(df_ipc, pt.DataFrame)
    assert df_ipc["x"].to_list() == [1, 2, 3]

    lazy_ipc = pt.scan_ipc(ipc_path)
    assert lazy_ipc.is_lazy
    assert lazy_ipc.collect()["x"].to_list() == [1, 2, 3]


def test_csv_reader_late_decimals_infer_schema(tmp_path):
    import polars as pl

    import pytae as pt

    path = tmp_path / "late_decimals.csv"
    lines = ["id,Adjusted_Collateral_Value (Es)"]
    for i in range(150):
        lines.append(f"{i},{i}")
    lines.append("150,2021792.076885")
    path.write_text("\n".join(lines) + "\n")

    reader = get_reader(path)
    # Eager to_polars
    pldf = reader.to_polars()
    assert pldf["Adjusted_Collateral_Value (Es)"].dtype == pl.Float64
    assert len(pldf) == 151

    # Lazy to_polars_lazy
    lazy_df = reader.to_polars_lazy().collect()
    assert lazy_df["Adjusted_Collateral_Value (Es)"].dtype == pl.Float64
    assert len(lazy_df) == 151

    # pt.read_csv and pt.scan_csv
    assert pt.read_csv(path)["Adjusted_Collateral_Value (Es)"].dtype == pl.Float64
    assert pt.scan_csv(path).collect()["Adjusted_Collateral_Value (Es)"].dtype == pl.Float64


def test_ipc_reader_writer_and_cli_roundtrip(tmp_path):
    import polars as pl

    from pytae import cli

    df = _frame()
    for ext in (".ipc", ".arrow", ".feather"):
        p = tmp_path / f"sample{ext}"
        write_dataframe(df, p)
        assert p.exists()
        reader = get_reader(p)
        assert reader.shape() == (3, 2)
        assert reader.columns() == ["a", "b"]
        pd.testing.assert_frame_equal(reader.head(2), df.head(2))
        pd.testing.assert_frame_equal(reader.tail(1).reset_index(drop=True), df.tail(1).reset_index(drop=True))
        pd.testing.assert_frame_equal(reader.to_dataframe(), df)
        assert reader.to_polars_lazy(columns=["a"]).collect().columns == ["a"]

    # LazyFrame sink_ipc via write_dataframe
    lf = pl.DataFrame(df).lazy()
    lazy_ipc_path = tmp_path / "lazy_out.ipc"
    write_dataframe(lf, lazy_ipc_path)
    assert get_reader(lazy_ipc_path).shape() == (3, 2)

    # CLI -o ipc format shorthand
    src_pq = tmp_path / "src.parquet"
    df.to_parquet(src_pq, index=False)
    rc = cli.main([str(src_pq), "-o", "ipc"])
    assert rc == 0
    assert (tmp_path / "src.ipc").exists()
    assert get_reader(tmp_path / "src.ipc").shape() == (3, 2)


def test_lazy_dataframe_methods_and_accessors(tmp_path):
    import warnings

    import polars as pl

    import pytae as pt
    from pytae.select import select

    pq_path = tmp_path / "lazy_methods.parquet"
    raw_pl = pl.DataFrame({"id": [1, 2], "a": [10, 20], "b": [30.0, 40.0]})
    raw_pl.write_parquet(pq_path)

    ldf = pt.scan_parquet(pq_path)
    edf = pt.read_parquet(pq_path)

    # .equals(), .to_numpy(), .values, .iloc on Lazy DataFrame
    assert ldf.equals(edf)
    assert edf.equals(ldf)
    assert ldf.to_numpy().shape == (2, 3)
    assert ldf.values.shape == (2, 3)
    assert ldf.iloc[0]["a"] == 10
    assert ldf.iloc[1, 2] == 40.0

    # .select_dtypes() and select() on LazyFrame without PerformanceWarning
    with warnings.catch_warnings():
        warnings.simplefilter("error", pl.exceptions.PerformanceWarning)
        num_df = ldf.select_dtypes(include="float")
        assert list(num_df.columns) == ["b"]
        sel_lf = select(raw_pl.lazy(), "id, a")
        assert sel_lf.collect().columns == ["id", "a"]

    # pt.long and .pt.long with r= parameter
    long_pt = pt.long(edf, cols="a,b", r="id")
    assert set(long_pt.columns) == {"id", "variable", "value"}
    long_pl = raw_pl.pt.long(cols="a,b", r="id")
    assert set(long_pl.columns) == {"id", "variable", "value"}
    long_pd = raw_pl.to_pandas().pt.long(cols="a,b", r="id")
    assert set(long_pd.columns) == {"id", "variable", "value"}

    # pt.DataFrame.glimpse() returns pytae.DataFrame for chaining, while .pt.glimpse() returns self._obj
    chained_pt = edf.glimpse().mutate("c = a + 1")
    assert isinstance(chained_pt, pt.DataFrame)
    assert "c" in chained_pt.columns
    assert raw_pl.pt.glimpse() is raw_pl


def test_read_database_and_connections_yaml_and_lazy_sinks(tmp_path, monkeypatch):
    import sqlite3

    import polars as pl

    import pytae as pt

    # 1. pt.read_database with SQLite connection
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    conn.executemany("INSERT INTO items VALUES (?, ?)", [(1, "alpha"), (2, "beta")])
    conn.commit()
    df_db = pt.read_database("SELECT * FROM items ORDER BY id", conn)
    conn.close()
    assert isinstance(df_db, pt.DataFrame)
    assert df_db["name"].to_list() == ["alpha", "beta"]

    # 2. Retired pt.read() and pt.scan() stubs raise informative AttributeError
    with pytest.raises(AttributeError, match="pt.read\\(\\) has been removed"):
        pt.read("foo.parquet")
    with pytest.raises(AttributeError, match="pt.scan\\(\\) has been removed"):
        pt.scan("foo.parquet")

    # 3. YAML connection error paths when PYTAE_CONNECTIONS_PATH is unset or missing
    monkeypatch.setattr(readers, "_EXTERNAL_CONNECTIONS_MODULE", None)
    monkeypatch.delenv("PYTAE_CONNECTIONS_PATH", raising=False)
    with pytest.raises(FileNotFoundError, match="PYTAE_CONNECTIONS_PATH"):
        get_reader(tmp_path / "conn.yaml")

    monkeypatch.setenv("PYTAE_CONNECTIONS_PATH", str(tmp_path / "missing_conn.py"))
    with pytest.raises(FileNotFoundError, match="connection reader not found"):
        get_reader(tmp_path / "conn.yaml")

    # Valid mock connections module
    conn_mod = tmp_path / "mock_conn.py"
    conn_mod.write_text(
        "import pandas as pd\n"
        "from pytae.readers import DataFrameReader\n"
        "def build_yaml_reader(path):\n"
        "    return DataFrameReader(pd.DataFrame({'k': [42]}), path=path)\n"
    )
    monkeypatch.setenv("PYTAE_CONNECTIONS_PATH", str(conn_mod))
    yaml_reader = get_reader(tmp_path / "conn.yaml")
    assert yaml_reader.shape() == (1, 1)
    assert yaml_reader.to_polars()["k"].to_list() == [42]

    # 4. LazyFrame write_dataframe sink_parquet, sink_csv, sink_ndjson
    lf = pl.DataFrame({"a": [1, 2], "b": ["u", "v"]}).lazy()
    for ext in (".parquet", ".csv", ".ndjson", ".txt"):
        out_p = tmp_path / f"lazy_sink{ext}"
        write_dataframe(lf, out_p)
        assert get_reader(out_p).shape() == (2, 2)

    # 5. StdinReader and DataFrameReader coverage
    from pytae.readers import DataFrameReader, StdinReader

    s_csv = StdinReader(b"a,b\n1,x\n2,y\n")
    assert s_csv.shape() == (2, 2)
    assert s_csv.columns() == ["a", "b"]
    assert len(s_csv.head(1)) == 1
    assert len(s_csv.tail(1)) == 1
    assert s_csv.to_polars(columns=["a"], nrows=1).shape == (1, 1)
    assert s_csv.to_polars_lazy(columns=["b"]).collect().columns == ["b"]

    s_tsv = StdinReader(b"a\tb\n1\tx\n")
    assert s_tsv.shape() == (1, 2)
    s_pipe = StdinReader(b"a|b\n1|x\n")
    assert s_pipe.shape() == (1, 2)
    s_json = StdinReader(b'{"a": 1, "b": "x"}\n')
    assert s_json.shape() == (1, 2)
    s_empty = StdinReader(b"")
    assert s_empty.shape() == (0, 0)

    dfr = DataFrameReader(pt.DataFrame({"a": [1, 2], "b": [3, 4]}))
    assert dfr.shape() == (2, 2)
    assert dfr.columns() == ["a", "b"]
    assert len(dfr.dtypes()) == 2
    assert len(dfr.head(1)) == 1
    assert len(dfr.tail(1)) == 1
    assert dfr.to_dataframe(columns=["a"], nrows=1).shape == (1, 1)
    assert dfr.to_polars_lazy(columns=["b"]).collect().columns == ["b"]

