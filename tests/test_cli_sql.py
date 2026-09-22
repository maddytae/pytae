import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv, _write_two_csvs


def test_sql_query_via_data_alias(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1, 20, 3], "col b": ["x", "y", "z"]}))

    exit_code = cli.main([path, "-sql", 'select "col b" from data where "col a" > 10'])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "y" in out
    assert "x" not in out

def test_sql_spaced_column_name_needs_double_quotes(tmp_path, capsys):
    # Standard SQL identifier quoting: double quotes for names with spaces, not single quotes.
    path = _write_csv(tmp_path, pd.DataFrame({"bill length mm": [1, 20, 3], "species": ["a", "b", "c"]}))

    exit_code = cli.main([path, "-sql", 'select species from data where "bill length mm" > 10'])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines()[-1].strip() == "b"

def test_sql_only_data_is_registered_no_file_derived_alias(tmp_path, capsys):
    # The file is already named on the command line; -sql does not also register a
    # file-stem alias (e.g. "my_data" for my_data.csv) -- only `data` is queryable.
    path = tmp_path / "my_data.csv"
    pd.DataFrame({"a": [1, 2]}).to_csv(path, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(path), "-sql", "select * from my_data"])
    assert exc_info.value.code == 2
    assert "-sql" in capsys.readouterr().err

def test_sql_reserved_word_table_is_not_registered(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-sql", "select * from table"])
    assert exc_info.value.code == 2
    assert "-sql" in capsys.readouterr().err

def test_sql_chains_after_select(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    exit_code = cli.main(
        [path, "-select", "keep,flt", "-sql", 'select "keep" from data where "flt" = \'A\'', "-shape"]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"

def test_sql_invalid_query_errors(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-sql", "not valid sql"])
    assert exc_info.value.code == 2
    assert "-sql" in capsys.readouterr().err

def test_sql_first_op_scans_parquet_directly(tmp_path, capsys):
    # -sql as the very first op should give the same result whether duckdb scans the
    # source file directly (fast path) or pandas materializes it first (fallback).
    path = tmp_path / "data.parquet"
    pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}).to_parquet(path, index=False)

    exit_code = cli.main([str(path), "-sql", "select b from data where a > 1"])

    out = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 0
    assert out[1:] == ["y", "z"]

def test_sql_first_op_respects_nrows(tmp_path, capsys):
    path = tmp_path / "data.parquet"
    pd.DataFrame({"a": range(10)}).to_parquet(path, index=False)

    exit_code = cli.main([str(path), "-nrows", "3", "-sql", "select * from data"])

    out = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 0
    assert len(out) - 1 == 3  # header + 3 rows

def test_sql_first_op_with_progress_still_works(tmp_path, capsys):
    # -progress forces the pandas-materialize fallback instead of the direct duckdb scan.
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2, 3]}))

    exit_code = cli.main([path, "-progress", "-sql", "select * from data where a > 1"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "reading" in out  # progress line proves the pandas fallback path ran
    table_lines = [line for line in out.strip().splitlines() if "reading" not in line]
    assert len(table_lines) - 1 == 2

def test_sql_first_op_with_custom_encoding_still_works(tmp_path, capsys):
    # A non-utf8 encoding forces the pandas-materialize fallback (duckdb's CSV reader
    # doesn't support arbitrary encodings the way pandas does).
    path = tmp_path / "data.csv"
    pd.DataFrame({"a": [1, 2], "name": ["café", "naïve"]}).to_csv(path, index=False, encoding="latin-1")

    exit_code = cli.main([str(path), "-encoding", "latin-1", "-sql", "select * from data"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "café" in out

def test_sql_can_join_file_aliases_directly(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-sql", 'select * from df1 inner join df2 on df1."col a" = df2.cola',
    ])

    out = capsys.readouterr().out
    assert "val_l" in out and "val_r" in out

def test_sql_after_merge_can_query_data(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on=col a:cola",
        "-sql", "select count(*) as n from data",
    ])

    assert capsys.readouterr().out.strip().splitlines()[-1].strip() == "2"

def test_sql_as_first_op_satisfies_file_requirement(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    # no -merge at all — -sql alone should be accepted as the founding op
    exit_code = cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-sql", "select * from df1",
    ])
    assert exit_code == 0


def test_sql_load_from_file_cli(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [10, 20]}))
    qfile = tmp_path / "query.txt"
    qfile.write_text("select a, b from data where a > 1")

    exit_code = cli.main([str(path), "-sql", f"@{qfile}", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 2)"


def test_sql_load_from_quoted_file_cli(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [10, 20]}))
    sub = tmp_path / "subdir"
    sub.mkdir()
    qfile = sub / "query.txt"
    qfile.write_text("select a, b from data where a > 1")

    # Test with outer quotes around '@path'
    exit_code = cli.main([str(path), "-sql", f"'@{qfile}'", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 2)"

    # Test with quotes around the path itself '@"path"'
    exit_code = cli.main([str(path), "-sql", f'@"{qfile}"', "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 2)"


def test_sql_bracketed_identifiers_cli(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1, 2], "col b": [10, 20]}))

    exit_code = cli.main([str(path), "-sql", "select [col a], `col b` from data", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 2)"



