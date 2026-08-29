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


def test_txt_reader_tab_delimited(tmp_path):
    path = tmp_path / "t.txt"
    df = _frame()
    df.to_csv(path, sep="\t", index=False)
    reader = get_reader(path)

    assert reader.columns() == ["a", "b"]
    pd.testing.assert_frame_equal(reader.to_dataframe(), df)


def test_write_dataframe_csv_and_parquet(tmp_path):
    df = _frame()
    csv_path = tmp_path / "out.csv"
    pq_path = tmp_path / "out.parquet"
    write_dataframe(df, csv_path)
    write_dataframe(df, pq_path)
    pd.testing.assert_frame_equal(pd.read_csv(csv_path), df)
    pd.testing.assert_frame_equal(pd.read_parquet(pq_path), df)


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


def test_get_reader_missing_suffix(tmp_path):
    path = Path(tmp_path / "noext")
    path.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="unsupported"):
        get_reader(path)
