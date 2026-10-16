import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _messy_headers_frame, _replace_frame, _write_csv


def test_handle_missing_redirect_error_and_fillna(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", None],
            "val": [1.0, None],
        }
    )
    path = _write_csv(tmp_path, df)

    # -handle_missing raises informative redirect error
    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-handle_missing"])
    assert exc_info.value.code == 2
    assert "'-handle_missing' has been removed; use '-fillna' instead" in capsys.readouterr().err

    # -fillna works
    exit_code = cli.main([path, "-fillna", "grp:., val:0.0"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "." in out
    assert "0.0" in out


def test_replace_values_redirect_error_and_mutate_map(tmp_path, capsys):
    path = _write_csv(tmp_path, _replace_frame())

    # -replace_values raises informative redirect error
    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-replace_values", "v='a magician:the magic'"])
    assert exc_info.value.code == 2
    assert (
        "'-replace_values' has been removed; use '-mutate' with map() or .str.replace() instead"
        in capsys.readouterr().err
    )

    # -mutate with map() works for replacing cell values
    exit_code = cli.main([path, "-mutate", "col a = map([col a], {'a magician': 'the magic'})"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "the magic" in out


def test_rename_quoting_is_optional(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"old col": [1, 2], "b": [3, 4]}))
    out1 = tmp_path / "out1.csv"
    out2 = tmp_path / "out2.csv"

    cli.main([path, "-rename", "old col:new col", "-o", str(out1)])
    cli.main([path, "-rename", "'old col':'new col'", "-o", str(out2)])

    assert list(pd.read_csv(out1).columns) == ["new col", "b"]
    assert list(pd.read_csv(out2).columns) == ["new col", "b"]


def test_rename_equals_raises_error(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"old col": [1, 2], "b": [3, 4]}))
    with pytest.raises(SystemExit, match="use ':'"):
        cli.main([path, "-rename", "old col=new col"])


def test_rename_multiple_pairs(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"old col": [1, 2], "b": [3, 4]}))
    out1 = tmp_path / "out1.csv"
    out2 = tmp_path / "out2.csv"

    cli.main([path, "-rename", "old col:new col,b:beta", "-o", str(out1)])
    cli.main([path, "-rename", "'old col':'new col','b':'beta'", "-o", str(out2)])

    assert list(pd.read_csv(out1).columns) == ["new col", "beta"]
    assert list(pd.read_csv(out2).columns) == ["new col", "beta"]


def test_rename_pipeline_head(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"island": ["Torgersen"], "species": ["Adelie"]}))
    cli.main([path, "-rename", "island:kailand", "-head"])
    out = capsys.readouterr().out
    assert "kailand" in out
    assert "island" not in out


def test_rename_pipeline_show_all(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"island": ["Torgersen"], "species": ["Adelie"]}))
    cli.main([path, "-rename", "island:kailand"])
    out = capsys.readouterr().out
    assert "kailand" in out
    assert "island" not in out


def test_rename_pipeline_chained_with_select(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))
    cli.main([path, "-rename", "a:alpha", "-select", "alpha,b", "-head"])
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "b" in out
    assert "c" not in out


def test_rename_repeated_flags(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2]}))
    cli.main([path, "-rename", "a:alpha", "-rename", "b:beta", "-head"])
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_rename_unknown_column_raises_error(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2]}))
    with pytest.raises(SystemExit):
        cli.main([path, "-rename", "unknown_col:x", "-head"])


def test_clean_columns_strip_fill_case(tmp_path, capsys):
    path = _write_csv(tmp_path, _messy_headers_frame())

    cli.main([path, "-clean_columns", "strip,fill,case=lower"])

    header = capsys.readouterr().out.strip().splitlines()[0].split()
    assert header == ["col_a", "col___b", "col_a", "100%_match!"]


def test_clean_columns_custom_fill_char(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1]}))

    cli.main([path, "-clean_columns", "fill=$"])

    header = capsys.readouterr().out.strip().splitlines()[0].split()
    assert header == ["col$a"]


def test_clean_columns_proper_case(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1]}))

    cli.main([path, "-clean_columns", "case=proper"])

    header = capsys.readouterr().out.strip().splitlines()[0]
    assert header == "Col A"


def test_clean_columns_squeeze_and_strip_special_and_dedupe(tmp_path, capsys):
    path = _write_csv(tmp_path, _messy_headers_frame())

    cli.main([path, "-clean_columns", "strip,squeeze,strip_special,fill,case=lower,dedupe=true"])

    header = capsys.readouterr().out.strip().splitlines()[0].split()
    assert header == ["col_a", "col_b", "col_a_1", "100_match"]


def test_clean_columns_no_fill_leaves_whitespace(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1]}))

    cli.main([path, "-clean_columns", "case=upper"])

    header = capsys.readouterr().out.strip().splitlines()[0]
    assert header == "COL A"


def test_clean_columns_unknown_key_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1]}))

    with pytest.raises(SystemExit, match="unknown key"):
        cli.main([path, "-clean_columns", "bogus=true"])


def test_clean_columns_case_without_value_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1]}))

    with pytest.raises(SystemExit):
        cli.main([path, "-clean_columns", "case"])


def test_clean_columns_strip_special_removes_quotes(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"'col a'": [1], '"col b"': [2]}))

    cli.main([path, "-clean_columns", "strip_special", "-cols"])

    header = capsys.readouterr().out.strip().splitlines()
    assert header == ["col a", "col b"]


def test_clean_columns_strip_special_keeps_fill_character(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"co-op's data": [1]}))

    cli.main([path, "-clean_columns", "strip_special,fill=-", "-cols"])

    header = capsys.readouterr().out.strip()
    assert header == "co-ops-data"
