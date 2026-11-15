"""Unit tests for remote URL / Cloud URI ingestion in Pytae."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

import pytae as pt
from pytae.readers import is_db_or_cloud_uri, read_uri


def test_is_db_or_cloud_uri() -> None:
    assert is_db_or_cloud_uri("https://example.com/data.parquet")
    assert is_db_or_cloud_uri("http://example.com/data.csv")
    assert is_db_or_cloud_uri("s3://bucket/data.parquet")
    assert is_db_or_cloud_uri("gs://bucket/data.csv")
    assert is_db_or_cloud_uri("duckdb://mydb.duckdb:orders")
    assert not is_db_or_cloud_uri("local_file.parquet")
    assert not is_db_or_cloud_uri("/var/log/syslog")


def test_read_uri_http_parquet() -> None:
    # Create test parquet buffer
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    buf = io.BytesIO()
    df.write_parquet(buf)
    content = buf.getvalue()

    mock_resp = MagicMock()
    mock_resp.read.return_value = content
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        path, res_df = read_uri("https://test.corp.internal/lake/sample.parquet")
        assert path.name == "sample.parquet"
        assert res_df.shape == (3, 2)
        assert res_df["a"].to_list() == [1, 2, 3]


def test_read_uri_http_csv() -> None:
    csv_bytes = b"id,val\n10,foo\n20,bar\n"
    mock_resp = MagicMock()
    mock_resp.read.return_value = csv_bytes
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        path, res_df = read_uri("http://test.corp.internal/data.csv")
        assert path.name == "data.csv"
        assert res_df.shape == (2, 2)
        assert res_df["val"].to_list() == ["foo", "bar"]
