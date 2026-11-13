"""Unit tests for Python and SQL autocompletion inside REPL blocks."""

import polars as pl
import pytest

from pytae.repl import PytaeRepl


@pytest.fixture
def populated_repl() -> PytaeRepl:
    repl = PytaeRepl()
    repl.tables["orders"] = pl.DataFrame({
        "order_id": [1, 2, 3],
        "customer_id": [101, 102, 101],
        "amount": [50.0, 100.0, 75.0],
    })
    repl.tables["customers"] = pl.DataFrame({
        "customer_id": [101, 102],
        "name": ["Alice", "Bob"],
        "region": ["North", "South"],
    })
    repl.current_df = repl.tables["orders"]
    repl.path_str = "orders"
    return repl


def test_sql_block_keyword_completion(populated_repl: PytaeRepl):
    # Lowercase text completes lowercase SQL keywords
    comp_sel = populated_repl._get_completions("sel", "sql { sel")
    assert "select" in comp_sel

    # Uppercase text completes uppercase SQL keywords
    comp_sel_upper = populated_repl._get_completions("SEL", "sql { SEL")
    assert "SELECT" in comp_sel_upper

    comp_where = populated_repl._get_completions("whe", "sql { whe")
    assert "where" in comp_where


def test_sql_block_table_and_column_completion(populated_repl: PytaeRepl):
    # Table name completion
    comp_table = populated_repl._get_completions("cust", "sql { select * from cust")
    assert "customers" in comp_table

    # Column name completion across loaded tables
    comp_col = populated_repl._get_completions("amo", "sql { select amo")
    assert "amount" in comp_col

    # Table-qualified column completion: 'orders.'
    comp_orders_dot = populated_repl._get_completions("orders.", "sql { select orders.")
    assert "orders.order_id" in comp_orders_dot
    assert "orders.customer_id" in comp_orders_dot
    assert "orders.amount" in comp_orders_dot


def test_sql_block_multiline_completion(populated_repl: PytaeRepl):
    # Simulate being on line 2 of a multiline SQL block
    populated_repl._active_multiline_buffer = ["res = sql {", "  select"]
    comp = populated_repl._get_completions("ord", "    ord")
    assert "orders" in comp
    assert "order_id" in comp
    assert "ORDER BY" in comp or "order by" in comp


def test_python_block_attribute_completion(populated_repl: PytaeRepl):
    # df.h -> df.head(), df.hist()
    comp_df_h = populated_repl._get_completions("df.h", "py { df.h")
    assert "df.head()" in comp_df_h

    # pl.c -> pl.col(), etc.
    comp_pl_c = populated_repl._get_completions("pl.c", "py { pl.c")
    assert "pl.col()" in comp_pl_c


def test_python_block_identifier_completion(populated_repl: PytaeRepl):
    # Top-level identifiers
    comp_p = populated_repl._get_completions("p", "py { p")
    assert "pl" in comp_p
    assert "pt" in comp_p

    # Table names in scope
    comp_o = populated_repl._get_completions("ord", "py { ord")
    assert "orders" in comp_o


def test_python_block_multiline_completion(populated_repl: PytaeRepl):
    # Simulate being inside a multiline py { ... } block
    populated_repl._active_multiline_buffer = ["py {", "    x = 10"]
    comp = populated_repl._get_completions("df.h", "    df.h")
    assert "df.head()" in comp
