import sqlite3

import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae._parsing import _parse_filter_string, _split_mutate_entries, parse_rename_spec
from pytae._text import _is_enclosed_pair as is_enclosed_pair
from pytae.readers import read_uri
from pytae.repl import PytaeRepl as InteractiveSession
from pytae.repl import _substitute_variables, _transpile_pipeline_tokens_to_python
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
    res = grouped.agg("total = value:sum").arrange("group")
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


def test_repl_transpile_extended_flags():
    tokens = [
        "-pivot",
        "r=region,c=year,v=sales,a=mean",
        "-long",
        "cols=y2020,id_vars=region",
        "-wide",
        "r=region,c=variable,v=value",
        "-assert",
        "sales > 0",
        "-explode",
        "tags",
        "-mask",
        "ssn:redact",
        "-unmask",
        "ssn",
    ]
    code = _transpile_pipeline_tokens_to_python(tokens)
    assert ".pivot(r='region', c='year', v='sales', a='mean')" in code
    assert ".long(cols='y2020', id_vars='region')" in code
    assert ".wide(r='region')" in code
    assert ".assert_('sales > 0')" in code
    assert ".explode('tags')" in code
    assert ".mask('ssn:redact')" in code
    assert ".unmask('ssn')" in code


def test_repl_substitute_variables_skips_quotes():
    variables = {"role": "admin"}
    assert _substitute_variables("role == @role", variables) == "role == 'admin'"
    assert _substitute_variables("role == '@role'", variables) == "role == '@role'"


def test_repl_fast_inspection_does_not_swallow_pipeline():
    pldf = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    sess = InteractiveSession(df=pldf)
    outputs: list[str] = []
    handled = sess._try_fast_inspection(pldf, ["-head", "2", "-select", "a"], outputs.append)
    assert handled is False


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
