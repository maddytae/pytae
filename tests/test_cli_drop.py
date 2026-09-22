import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv


def test_parse_drop_spec_names_and_quoted():
    assert cli.parse_drop_spec("sex,year") == ["sex", "year"]
    assert cli.parse_drop_spec("'bill length mm',body_mass_g") == ["bill length mm", "body_mass_g"]
    assert cli.parse_drop_spec("a:b") == ["a:b"]  # exact name, not a slice

def test_parse_drop_spec_rejects_select_kwargs_and_empty():
    with pytest.raises(SystemExit, match="only column names"):
        cli.parse_drop_spec("dtype=numeric")
    with pytest.raises(SystemExit, match="only column names"):
        cli.parse_drop_spec("sex,contains=bill")
    with pytest.raises(SystemExit, match="expected column names"):
        cli.parse_drop_spec("")

def test_drop_does_not_collide_with_dropna():
    parser = cli.build_parser()
    args, extras = parser.parse_known_args(["file.csv", "-drop", "sex", "-dropna", "false"])
    assert extras == []
    assert args.drop == ["sex"]
    assert args.dropna is False

def test_drop_removes_names_and_keeps_order(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "c": [2], "b": [3], "d": [4]}))

    exit_code = cli.main([path, "-drop", "c,d", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["a", "b"]

def test_drop_quoted_name_with_space(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"bill length mm": [1], "body mass g": [2], "keep": [3]}))

    exit_code = cli.main([path, "-drop", "bill length mm", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["body mass g", "keep"]

def test_drop_after_select_subtracts_from_kept(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]}))

    exit_code = cli.main([path, "-select", "a,b,c", "-drop", "b", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["a", "c"]

def test_drop_rejects_name_not_kept_by_select(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-select", "a,b", "-drop", "c", "-cols"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown column" in err
    assert "'c'" in err

def test_select_then_drop_from_dtype_union(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"species": ["A"], "n": [1], "x": [2.0], "label": ["z"]}),
    )

    exit_code = cli.main([path, "-select", "dtype=numeric,species", "-drop", "x", "-cols"])

    assert exit_code == 0
    # -select puts explicit names first, then dtype matches; -drop leaves that order
    assert capsys.readouterr().out.strip().splitlines() == ["species", "n"]

def test_drop_unknown_name_errors_with_typo_hint(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"species": [1], "island": [2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-drop", "speces", "-cols"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown column" in err
    assert "'speces'" in err
    assert "species" in err

def test_drop_slice_token_is_not_a_slice(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-drop", "a:c", "-cols"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown column" in err
    assert "does not accept slices" in err

def test_drop_colon_column_name_is_exact(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a:b": [1], "c": [2]}))

    exit_code = cli.main([path, "-drop", "a:b", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["c"]

def test_drop_rejects_select_kwargs(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2]}))

    with pytest.raises(SystemExit, match="only column names"):
        cli.main([path, "-drop", "dtype=numeric", "-cols"])
    with pytest.raises(SystemExit, match="only column names"):
        cli.main([path, "-drop", "contains=a", "-cols"])

def test_drop_all_columns_errors(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-drop", "a,b", "-cols"])
    assert exc_info.value.code == 2
    assert "no columns left" in capsys.readouterr().err

def test_drop_only_prints_remaining_table(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))

    exit_code = cli.main([path, "-drop", "c"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "a" in out and "b" in out
    assert "c" not in out.split()

def test_drop_after_agg_df_sees_agg_columns(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3], "z": [9, 8, 7]}),
    )

    exit_code = cli.main(
        [path, "-agg_df", "val = sum, n = n", "-drop", "val", "-cols"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "n"]

def test_qry_then_drop_filter_column(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2], "flt": ["A", "B"], "val": [10, 20]}),
    )

    exit_code = cli.main([path, "-qry", "flt = 'A'", "-drop", "flt", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["keep", "val"]

