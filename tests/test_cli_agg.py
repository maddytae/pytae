import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv


def test_order_agg_then_shape_uses_aggregated_frame(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y", "y"],
            "v1": [1, 2, 3, 4],
            "v2": [10, 20, 30, 40],
        }
    )
    path = _write_csv(tmp_path, df)

    # With -by: groups by grp, v1/v2 summed -> 2 rows x 3 cols
    exit_code = cli.main([path, "-by", "grp", "-agg", "-shape"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(2, 3)" in out

    # Without -by: whole-table summary across numeric columns -> 1 row x 2 cols
    exit_code = cli.main([path, "-agg", "-shape"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(1, 2)" in out


def test_order_agg_dropna_default_and_flags(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", None],
            "v1": [1, 2],
        }
    )
    path = _write_csv(tmp_path, df)

    # Default is dropna=false: keeps the NA grouping key, so both groups remain (2 rows).
    exit_code = cli.main([path, "-by", "grp", "-agg", "sum", "-shape"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(2, 2)" in out

    # Explicit -dropna true drops the NA grouping key (1 row).
    exit_code_drop = cli.main([path, "-by", "grp", "-agg", "sum", "-dropna", "true", "-shape"])
    out_drop = capsys.readouterr().out
    assert exit_code_drop == 0
    assert "(1, 2)" in out_drop


def test_group_by_agg_bare_aggfunc_keeps_source_column_name(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y", "y"],
            "v1": [1, 2, 3, 4],
            "v2": [10, 20, 30, 40],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-by", "grp", "-agg", "v1 = sum, v2 = mean"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "v1" in out and "v2" in out
    assert "3" in out and "15.0" in out
    assert "7" in out and "35.0" in out


def test_group_by_agg_named_output(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y", "y"],
            "v1": [1, 2, 3, 4],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-by", "grp", "-agg", "total = v1:sum"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "total" in out
    assert "v1" not in out.split("\n")[0]  # header uses the custom output name, not the source column


def test_agg_same_func_on_multiple_columns(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["x", "x"], "v1": [1, 2], "v2": [10, 20]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-by", "grp", "-agg", "sum"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "v1" in out and "v2" in out
    assert "3" in out and "30" in out


def test_agg_named_output_with_spaced_group(tmp_path, capsys):
    df = pd.DataFrame({"Scenario Name": ["A", "A", "B"], "value": [1, 2, 3]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main(
        [path, "-by", "Scenario Name", "-agg", "v = value:sum"]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    header = out.split("\n")[0]
    assert "v" in header and "value" not in header
    assert "3" in out


def test_agg_rejects_dict_literal(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit, match="use a name"):
        cli.main([path, "-by", "grp", "-agg", "{'v1':'sum'}"])


def test_agg_retired_syntax_raises_helpful_error(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit, match="syntax is retired"):
        cli.main([path, "-by", "grp", "-agg", "column=v1,aggfunc=sum"])


def test_by_requires_agg_or_mutate(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-by", "grp"])
    assert exc_info.value.code == 2
    assert "requires -agg or -mutate" in capsys.readouterr().err


def test_agg_then_sort_by_prints_only_final_table(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["b", "a", "a"],
            "val": [2, 1, 3],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-by", "grp", "-agg", "sum", "-sort_by", "grp"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # Header should appear once: only final sorted aggregated table is printed.
    assert out.count("grp") == 1


def test_parse_agg_name_list_and_mapping():
    from pytae.cli_parsing import parse_agg
    assert parse_agg("mean") == "mean"
    assert parse_agg("mean,sum,n") == ["mean", "sum", "n"]
    assert parse_agg("val = sum, n = n") == {"val": "sum", "n": "n"}
    assert parse_agg("'body mass' = mean") == {"body mass": "mean"}
    assert parse_agg("total = v1:sum") == {"total": "v1:sum"}
    with pytest.raises(SystemExit, match="syntax is retired"):
        parse_agg("column=v1,aggfunc=sum")
    with pytest.raises(SystemExit, match="use '='"):
        parse_agg("val: sum, n: n")
    with pytest.raises(SystemExit, match="use a name"):
        parse_agg("['mean', 'sum']")
    with pytest.raises(SystemExit, match="mix of names"):
        parse_agg("mean, val = sum")


def test_agg_comma_list(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3]}),
    )

    exit_code = cli.main([path, "-by", "grp", "-agg", "sum,n", "-cols"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "n", "val"]


def test_agg_python_literal_is_rejected(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "val": [1]}))
    with pytest.raises(SystemExit, match="use a name"):
        cli.main([path, "-agg", "{'val': 'sum'}"])


def test_agg_mapping_named_a_does_not_collide_with_kwargs(tmp_path, capsys):
    # CLI Issue 2: -agg "a = sum" passed positionally to agg_df
    df = pd.DataFrame({"grp": ["x", "x", "y"], "a": [1, 2, 3], "b": [10, 20, 30]})
    path = _write_csv(tmp_path, df)
    exit_code = cli.main([path, "-by", "grp", "-agg", "a = sum", "-cols"])
    assert exit_code == 0
    cols = capsys.readouterr().out.strip().splitlines()
    assert cols == ["grp", "a"]

