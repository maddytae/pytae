import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv, _write_two_csvs


def test_select_regex_matches_column_names(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "species": ["A", "B"],
            "bill_length_mm": [1, 2],
            "bill_depth_mm": [3, 4],
            "body_mass_g": [5, 6],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "regex=^bill", "-cols"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines() == ["bill_length_mm", "bill_depth_mm"]

def test_select_regex_combines_with_explicit_select(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "species": ["A"],
            "island": ["Torgersen"],
            "bill_length_mm": [1],
            "body_mass_g": [2],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "species,regex=bill|body", "-cols"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines() == ["species", "bill_length_mm", "body_mass_g"]

def test_parse_select_spec_names_and_kwargs():
    names, kwargs = cli.parse_select_spec("species,contains=bill,dtype=numeric")
    assert names == ["species"]
    assert kwargs == {"contains": "bill", "dtype": "numeric"}

def test_parse_select_spec_quoted_name_and_repeated_key():
    names, kwargs = cli.parse_select_spec("'bill length mm',contains=bill,contains=body")
    assert names == ["bill length mm"]
    assert kwargs == {"contains": ["bill", "body"]}

def test_select_dtype_unions_with_explicit_names(tmp_path, capsys):
    df = pd.DataFrame({"cola": ["a"], "colb": [1], "n": [2.0], "label": ["x"]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "cola,colb,dtype=numeric", "-cols"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines() == ["cola", "colb", "n"]

def test_select_exclude_dtype_standalone(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"name": ["a"], "n": [1]}))

    exit_code = cli.main([path, "-select", "exclude_dtype=numeric", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["name"]

def test_select_exclude_dtype_non_numeric_keeps_numbers(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"name": ["a"], "n": [1], "x": [2.0]}))

    exit_code = cli.main([path, "-select", "exclude_dtype=non_numeric", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["n", "x"]

def test_select_exclude_dtype_cannot_combine(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"name": ["a"], "n": [1]}))

    with pytest.raises(SystemExit, match="exclude_dtype cannot be combined"):
        cli.main([path, "-select", "name,exclude_dtype=numeric", "-cols"])

def test_select_slice(tmp_path, capsys):
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "a:c", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["a", "b", "c"]

def test_second_select_filters_remaining_names(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]}))

    exit_code = cli.main([path, "-select", "a,b,c", "-select", "a,c", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["a", "c"]

def test_second_select_rejects_name_not_kept_by_first(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))

    # last-wins would yield b,c; chaining rejects c because the first spec dropped it
    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-select", "a,b", "-select", "b,c", "-cols"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown column" in err
    assert "'c'" in err

def test_select_only_prints_selected_table(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))

    exit_code = cli.main([path, "-select", "a,b"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "a" in out and "b" in out
    assert "c" not in out.split()

def test_select_unknown_exact_name_errors(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-select", "d,a,b", "-cols"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown column" in err
    assert "'d'" in err

def test_select_after_agg_df_sees_agg_columns(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3], "z": [9, 8, 7]}),
    )

    # n is created by agg_df; a starting-view -select would reject it
    exit_code = cli.main(
        [path, "-agg_df", "val = sum, n = n", "-select", "grp,n", "-cols"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "n"]

def test_select_agg_df_select_shape_chains(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3], "z": [9, 8, 7]}),
    )

    # starting-view chaining would collapse to val-only before agg → (1, 1)
    exit_code = cli.main(
        [path, "-select", "grp,val", "-agg_df", "sum", "-select", "val", "-shape"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"

def test_second_select_intersects_dtype_and_contains(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "species": ["A"],
            "bill_length_mm": [1],
            "bill_depth_mm": [2],
            "body_mass_g": [3],
            "island": ["Torgersen"],
        }
    )
    path = _write_csv(tmp_path, df)

    # last-wins of dtype=numeric would keep body_mass_g too
    exit_code = cli.main([path, "-select", "contains=bill", "-select", "dtype=numeric", "-cols"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["bill_length_mm", "bill_depth_mm"]

    exit_code = cli.main([path, "-select", "dtype=numeric", "-select", "contains=bill", "-cols"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["bill_length_mm", "bill_depth_mm"]

def test_removed_select_star_flags_are_unknown(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-select-regex", "^a", "-cols"])
    assert exc_info.value.code == 2

def test_select_caret_pattern_is_not_implicit_regex(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"bill_length_mm": [1], "species": ["A"]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-select", "^bill", "-cols"])
    assert exc_info.value.code == 2

def test_select_then_qry_on_dropped_column_errors(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2], "flt": ["A", "B"], "val": [10, 20]}),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-select", "keep,val", "-qry", "flt = 'A'", "-shape"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "-qry" in err
    assert "flt" in err

def test_select_runs_after_merge(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on=col a:cola",
        "-select", "val_l,val_r", "-shape",
    ])

    assert capsys.readouterr().out.strip() == "(2, 2)"

