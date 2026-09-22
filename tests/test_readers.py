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


def test_sas_reader_defaults_to_utf8():
    path = Path("dummy.sas7bdat")
    assert get_reader(path).encoding == "utf-8"
    assert get_reader(path, encoding="latin-1").encoding == "latin-1"


def test_get_reader_missing_suffix(tmp_path):
    path = Path(tmp_path / "noext")
    path.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="unsupported"):
        get_reader(path)
