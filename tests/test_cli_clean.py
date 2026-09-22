import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _messy_headers_frame, _replace_frame, _write_csv


def test_handle_missing_default_fill(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", None],
            "val": [1.0, None],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-handle_missing"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # object/category NA becomes '.', numeric NA becomes 0.
    assert "." in out
    assert "0.0" in out

def test_replace_whole_df_exact_match(tmp_path, capsys):
    path = _write_csv(tmp_path, _replace_frame())

    cli.main([path, "-replace_values", "v='a magician:the magic,alpha:bravo'"])

    out = capsys.readouterr().out
    assert "the magic" in out
    assert "bravo" in out
    assert "not a magician exactly" in out  # untouched: not an exact whole-cell match
    assert "analphabet" in out              # untouched: not an exact whole-cell match

def test_replace_scoped_columns_only(tmp_path, capsys):
    df = pd.DataFrame({"col a": ["alpha"], "colb": ["alpha"]})
    path = _write_csv(tmp_path, df)

    cli.main([path, "-replace_values", "c=col a,v=alpha:bravo"])

    out = capsys.readouterr().out.strip().splitlines()
    assert out[1].split() == ["bravo", "alpha"]

def test_replace_exact_false_matches_substring(tmp_path, capsys):
    path = _write_csv(tmp_path, _replace_frame())

    cli.main([path, "-replace_values", "v='a magician:the magic,alpha:bravo',exact=false"])

    out = capsys.readouterr().out
    assert "not the magic exactly" in out
    assert "anbravobet" in out

def test_replace_unknown_column_errors(tmp_path, capsys):
    path = _write_csv(tmp_path, _replace_frame())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-replace_values", "c=missing,v=alpha:bravo"])
    assert exc_info.value.code == 2
    assert "-replace_values" in capsys.readouterr().err

def test_replace_requires_v(tmp_path):
    path = _write_csv(tmp_path, _replace_frame())

    with pytest.raises(SystemExit):
        cli.main([path, "-replace_values", "c=col a"])

def test_replace_values_mapping_quoting_is_optional(tmp_path, capsys):
    df = pd.DataFrame({"col a": ["alpha"], "colb": ["alpha"]})

    path = _write_csv(tmp_path, df)
    cli.main([path, "-replace_values", "v=alpha:bravo"])
    unquoted = capsys.readouterr().out.strip()

    path = _write_csv(tmp_path, df)
    cli.main([path, "-replace_values", "v=alpha:'bravo'"])
    quoted = capsys.readouterr().out.strip()

    assert unquoted == quoted
    assert "bravo" in unquoted

def test_rename_quoting_is_optional(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"old col": [1, 2], "b": [3, 4]}))
    out1 = tmp_path / "out1.csv"
    out2 = tmp_path / "out2.csv"

    cli.main([path, "-convert", "-rename", "old col:new col", "-o", str(out1)])
    cli.main([path, "-convert", "-rename", "'old col':'new col'", "-o", str(out2)])

    assert list(pd.read_csv(out1).columns) == ["new col", "b"]
    assert list(pd.read_csv(out2).columns) == ["new col", "b"]


def test_rename_with_equals_sign(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"old col": [1, 2], "b": [3, 4]}))
    out1 = tmp_path / "out1.csv"
    out2 = tmp_path / "out2.csv"

    cli.main([path, "-convert", "-rename", "old col=new col,b=beta", "-o", str(out1)])
    cli.main([path, "-convert", "-rename", "'old col'='new col','b'='beta'", "-o", str(out2)])

    assert list(pd.read_csv(out1).columns) == ["new col", "beta"]
    assert list(pd.read_csv(out2).columns) == ["new col", "beta"]

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

