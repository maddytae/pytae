import sqlite3

import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae._parsing import _parse_filter_string, _split_mutate_entries, parse_rename_spec
from pytae._text import _is_enclosed_pair as is_enclosed_pair
from pytae.readers import read_uri
from pytae.validation import check_dsl_string


def test_is_enclosed_pair_escaped_quotes_and_brackets():
    assert is_enclosed_pair(r'"hello \"world\""', '"', '"') is True
    assert is_enclosed_pair(r'"a\" + \"b"', '"', '"') is True
    assert is_enclosed_pair('"a" + "b"', '"', '"') is False
    assert is_enclosed_pair("[1, ']', 2]", "[", "]") is True
    assert is_enclosed_pair("[1] + [2]", "[", "]") is False


def test_grouped_dataframe_rename_string_spec():
    df = pt.DataFrame({"grp": ["a", "a", "b"], "val": [1, 2, 3]})
    grouped = df.by("grp").rename("grp:group, val:value")
    res = grouped.agg("total = sum(value)").arrange("group")
    assert res.columns == ["group", "total"]
    assert res["group"].to_list() == ["a", "b"]
    assert res["total"].to_list() == [3, 3]


def test_parse_rename_spec_validation():
    assert parse_rename_spec("a:b, c:d") == {"a": "b", "c": "d"}
    with pytest.raises(ValueError, match="expected 'old:new'"):
        parse_rename_spec("a=b")
    with pytest.raises(ValueError, match="conflicting rename mappings"):
        parse_rename_spec("a:b, a:c")


def test_at_param_backslash_and_quote_safety():
    win_path = r"C:\Users\admin\node"
    df = pt.DataFrame({"path": [win_path, "other"], "tag": ["@win_path", "ok"]})

    # Backslashes in @var should not trigger re.sub escape errors in filter or mutate
    filtered = df.filter("path == @win_path", params={"win_path": win_path})
    assert len(filtered) == 1
    assert filtered["path"].to_list() == [win_path]

    mutated = df.mutate("norm = @win_path", params={"win_path": win_path})
    assert mutated["norm"].to_list() == [win_path, win_path]

    # @var inside string literal should not be expanded
    literal_filtered = df.filter("tag == '@win_path'", params={"win_path": win_path})
    assert len(literal_filtered) == 1
    assert literal_filtered["tag"].to_list() == ["@win_path"]


def test_filter_bracketed_column_with_colon():
    df = pt.DataFrame({"a:b": [1, 2, 3], "x": [10, 20, 30]})
    res = df.filter("[a:b] >= 2")
    assert res["x"].to_list() == [20, 30]

    node = _parse_filter_string("`a:b` == 1")
    assert node.col == "a:b"
    assert node.cond == ("==", 1)


def test_split_mutate_entries_nested_parens_on_lhs():
    entries = _split_mutate_entries("x = 1, y = (a + b) == 2")
    assert entries == [("x", "1"), ("y", "(a + b) == 2")]


def test_check_dsl_string_filter():
    assert check_dsl_string("filter", "age >= 18 and status in ['A', 'B']") == []
    assert check_dsl_string("filter", "score >= 10 and score <= 20 and name.is_not_null()") == []
    assert check_dsl_string("filter", "val == @threshold") == []

    errs = check_dsl_string("filter", "age >= (18")
    assert len(errs) > 0

    errs_eq = check_dsl_string("filter", "age = 18")
    assert len(errs_eq) > 0






def test_read_uri_sqlite_cte_and_quoted_table(tmp_path):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute('CREATE TABLE "my""tbl" (id INTEGER, val TEXT)')
    conn.execute('INSERT INTO "my""tbl" VALUES (1, "a"), (2, "b")')
    conn.commit()
    conn.close()

    _, df_tbl = read_uri(f'sqlite://{db_file}:my"tbl')
    assert df_tbl.shape == (2, 2)

    _, df_cte = read_uri(f'sqlite://{db_file}:WITH cte AS (SELECT id FROM "my""tbl" WHERE id = 2) SELECT * FROM cte')
    assert df_cte["id"].to_list() == [2]


def test_dataframe_default_range_index_not_materialized():
    pdf = pd.DataFrame({"a": [1, 2, 3]})
    df = pt.DataFrame(pdf)
    assert df._orig_index is None
    assert list(df.index) == [0, 1, 2]


def test_schema_only_diff_cli_repl_and_api(tmp_path, capsys):
    from pytae.cli import main

    jan_df = pl.DataFrame(
        {
            "id": pl.Series([1, 2, 3], dtype=pl.Int32),
            "name": ["Alice", "Bob", "Charlie"],
            "amount": [10.5, 20.0, 30.0],
            "legacy_code": ["A", "B", "C"],
        }
    )
    feb_df = pl.DataFrame(
        {
            "id": pl.Series([1, 2, 3, 4], dtype=pl.Int64),
            "name": ["Alice_changed", "Bob", None, "Diana"],
            "amount": [999.0, None, 30.0, 40.0],
            "discount_pct": [0.1, 0.2, 0.0, 0.05],
        }
    )
    jan_path = tmp_path / "jan.parquet"
    feb_path = tmp_path / "feb.parquet"
    jan_df.write_parquet(jan_path)
    feb_df.write_parquet(feb_path)

    # 1. CLI: pytae jan.parquet -diff "feb.parquet,schema"
    rc = main([str(jan_path), "-diff", f"{feb_path},schema"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Rows: 3 vs 4 (-1)" in out
    assert "+ Added in left (1):   legacy_code" in out
    assert "- Removed in left (1): discount_pct" in out
    assert "* id: Int64 (right) -> Int32 (left)" in out
    assert "* amount: 0 vs 1 nulls (-1)" in out
    assert "Skipped (schema-only diff)" in out
    assert "cell(s) differ" not in out

    # 2. Competing flag -diff_schema is rejected with canonical guidance
    with pytest.raises(SystemExit):
        main([str(jan_path), "-diff_schema", str(feb_path)])
    err = capsys.readouterr().err
    assert "use '-diff \"<target>,schema\"' instead" in err

    # 3. Python API: pt.diff(..., schema=True)
    api_out = pt.diff(jan_path, feb_path, schema=True)
    assert "* id: Int64 (right) -> Int32 (left)" in api_out
    assert "Skipped (schema-only diff)" in api_out


def test_schema_ddl_and_code_generation(tmp_path, capsys, monkeypatch):
    import json

    from pytae.cli import main

    df = pl.DataFrame(
        {
            "id": pl.Series([1, 2], dtype=pl.Int64),
            "customer_name": ["Alice", None],
            "amount": pl.Series([10.5, 20.0], dtype=pl.Float64),
            "is_active": [True, False],
        }
    )
    pq_path = tmp_path / "orders.parquet"
    df.write_parquet(pq_path)

    # 1. Default -schema summary table
    rc = main([str(pq_path), "-schema"])
    assert rc == 0
    out_table = capsys.readouterr().out
    assert "Columns: 4 | Rows: 2" in out_table
    assert "customer_name" in out_table

    # 2. -schema sql
    rc = main([str(pq_path), "-schema", "sql"])
    assert rc == 0
    out_sql = capsys.readouterr().out
    assert "CREATE TABLE orders (" in out_sql
    assert "id BIGINT NOT NULL" in out_sql
    assert "customer_name VARCHAR," in out_sql
    assert "amount DOUBLE PRECISION NOT NULL" in out_sql
    assert "is_active BOOLEAN NOT NULL" in out_sql

    # 3. -schema bq
    rc = main([str(pq_path), "-schema", "bq"])
    assert rc == 0
    out_bq = capsys.readouterr().out
    bq_fields = json.loads(out_bq)
    assert bq_fields == [
        {"name": "id", "type": "INT64", "mode": "REQUIRED"},
        {"name": "customer_name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "amount", "type": "FLOAT64", "mode": "REQUIRED"},
        {"name": "is_active", "type": "BOOL", "mode": "REQUIRED"},
    ]

    # 4. -schema pydantic
    rc = main([str(pq_path), "-schema", "pydantic"])
    assert rc == 0
    out_pyd = capsys.readouterr().out
    assert "from pydantic import BaseModel" in out_pyd
    assert "class OrdersRecord(BaseModel):" in out_pyd
    assert "id: int" in out_pyd
    assert "customer_name: Optional[str] = None" in out_pyd
    assert "amount: float" in out_pyd
    assert "is_active: bool" in out_pyd

    # 5. -schema json
    rc = main([str(pq_path), "-schema", "json"])
    assert rc == 0
    out_json = capsys.readouterr().out
    js_obj = json.loads(out_json)
    assert js_obj["type"] == "object"
    assert js_obj["properties"]["id"]["type"] == "integer"
    assert js_obj["properties"]["customer_name"]["type"] == ["string", "null"]
    assert set(js_obj["required"]) == {"id", "amount", "is_active"}

    # 6. -schema sql -o clip
    copied: list[str] = []
    monkeypatch.setattr("pytae.cli_run._copy_to_clipboard", lambda text: copied.append(text))
    rc = main([str(pq_path), "-schema", "sql", "-o", "clip"])
    assert rc == 0
    capsys.readouterr()
    assert len(copied) == 1
    assert "CREATE TABLE orders (" in copied[0]

    # 7. Python API pt.schema(df, "sql")
    assert "CREATE TABLE data (" in pt.schema(df, "sql")
