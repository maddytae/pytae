"""Unit tests for direct database and cloud storage URI ingestion in pytae."""

import sqlite3
from pathlib import Path

import pytest

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore[assignment]

import pytae as pt
from pytae.cli import main
from pytae.readers import is_db_or_cloud_uri, parse_db_uri
from pytae.repl import PytaeRepl


@pytest.fixture
def sqlite_db_path(tmp_path: Path) -> Path:
    db_file = tmp_path / "app.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE orders (order_id INT, customer_id INT, amount REAL)")
    conn.execute("INSERT INTO orders VALUES (1, 101, 45.5), (2, 102, 120.0), (3, 101, 75.25)")
    conn.commit()
    conn.close()
    return db_file


@pytest.fixture
def duckdb_file_path(tmp_path: Path) -> Path:
    if duckdb is None:
        pytest.skip("duckdb is not installed")
    duck_file = tmp_path / "analytics.duckdb"
    conn = duckdb.connect(str(duck_file))
    conn.execute("CREATE TABLE customers (cust_id INT, name VARCHAR, region VARCHAR)")
    conn.execute("INSERT INTO customers VALUES (101, 'Acme Corp', 'North'), (102, 'Beta LLC', 'South')")
    conn.close()
    return duck_file


def test_is_db_or_cloud_uri():
    assert is_db_or_cloud_uri("sqlite://app.db:orders")
    assert is_db_or_cloud_uri("sqlite:/app.db:orders")
    assert is_db_or_cloud_uri("duckdb://analytics.duckdb:customers")
    assert is_db_or_cloud_uri("s3://bucket/data.parquet")
    assert is_db_or_cloud_uri("gcs://bucket/data.parquet")
    assert is_db_or_cloud_uri("gs://bucket/data.parquet")
    assert not is_db_or_cloud_uri("data.parquet")
    assert not is_db_or_cloud_uri("sample:penguins")
    assert not is_db_or_cloud_uri("/path/to/data.csv")


def test_parse_db_uri():
    scheme, db_p, target = parse_db_uri("sqlite://app.db:orders")
    assert scheme == "sqlite"
    assert db_p == "app.db"
    assert target == "orders"

    scheme, db_p, target = parse_db_uri("duckdb:///data/app.duckdb:customers")
    assert scheme == "duckdb"
    assert db_p == "/data/app.duckdb"
    assert target == "customers"

    scheme, db_p, target = parse_db_uri("sqlite://app.db:SELECT * FROM orders WHERE amount > 50")
    assert scheme == "sqlite"
    assert db_p == "app.db"
    assert target == "SELECT * FROM orders WHERE amount > 50"


def test_pt_read_and_scan_sqlite(sqlite_db_path: Path):
    uri = f"sqlite://{sqlite_db_path}:orders"
    df = pt.read(uri)
    assert df.shape == (3, 3)
    assert set(df.columns) == {"order_id", "customer_id", "amount"}

    lf = pt.scan(uri)
    collected = lf.collect()
    assert collected.shape == (3, 3)


def test_pt_read_database_uri(sqlite_db_path: Path):
    uri = f"sqlite://{sqlite_db_path}:orders"
    df = pt.read_database(uri)
    assert df.shape == (3, 3)


def test_sqlite_query_uri(sqlite_db_path: Path):
    uri = f"sqlite://{sqlite_db_path}:SELECT order_id, amount FROM orders WHERE amount > 50"
    df = pt.read(uri)
    assert df.shape == (2, 2)
    assert set(df.columns) == {"order_id", "amount"}


def test_pt_read_and_scan_duckdb(duckdb_file_path: Path):
    uri = f"duckdb://{duckdb_file_path}:customers"
    df = pt.read(uri)
    assert df.shape == (2, 3)
    assert set(df.columns) == {"cust_id", "name", "region"}

    lf = pt.scan(uri)
    collected = lf.collect()
    assert collected.shape == (2, 3)


def test_duckdb_query_uri(duckdb_file_path: Path):
    uri = f"duckdb://{duckdb_file_path}:SELECT cust_id, name FROM customers WHERE region = 'North'"
    df = pt.read(uri)
    assert df.shape == (1, 2)
    assert df.to_dicts() == [{"cust_id": 101, "name": "Acme Corp"}]


def test_duckdb_in_memory_query():
    if duckdb is None:
        pytest.skip("duckdb is not installed")
    uri = "duckdb://:memory::SELECT 42 AS answer, 'hello' AS greeting"
    df = pt.read(uri)
    assert df.shape == (1, 2)
    assert df.to_dicts() == [{"answer": 42, "greeting": "hello"}]


def test_repl_sqlite_and_duckdb_ingest(sqlite_db_path: Path, duckdb_file_path: Path):
    repl = PytaeRepl()
    outputs: list[str] = []

    # Eager load sqlite
    repl.execute_line(f"orders = sqlite://{sqlite_db_path}:orders", output_fn=outputs.append)
    assert "orders" in repl.tables
    assert repl.tables["orders"].shape == (3, 3)
    assert "Loaded" in outputs[-1]

    # Lazy scan duckdb
    repl.execute_line(f"cust = scan duckdb://{duckdb_file_path}:customers", output_fn=outputs.append)
    assert "cust" in repl.tables
    assert "Scanned" in outputs[-1]

    # Query loaded tables using REPL pipeline
    repl.execute_line("orders -filter \"amount > 50\" -count", output_fn=outputs.append)
    assert any("2" in line for line in outputs)


def test_cli_sqlite_and_duckdb_ingest(sqlite_db_path: Path, duckdb_file_path: Path):
    # Single sqlite CLI table
    code = main([f"sqlite://{sqlite_db_path}:orders", "-head", "2"])
    assert code == 0

    # Single duckdb CLI table
    code = main([f"duckdb://{duckdb_file_path}:customers", "-select", "name", "-head"])
    assert code == 0

    # Cross-database relational join
    code = main([
        f"o=sqlite://{sqlite_db_path}:orders",
        f"c=duckdb://{duckdb_file_path}:customers",
        "-join", "right=c,on=customer_id:cust_id",
        "-head",
    ])
    assert code == 0
