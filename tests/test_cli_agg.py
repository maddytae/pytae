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

    exit_code = cli.main([path, "-agg_df", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # grp is the grouping key, and v1/v2 are summed -> 2 rows x 3 cols.
    assert "(2, 3)" in out

def test_order_agg_dropna_false_keeps_na_group(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", None],
            "v1": [1, 2],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-agg_df", "sum", "-dropna", "false", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # dropna=false keeps the NA grouping key, so both groups remain.
    assert "(2, 2)" in out

def test_group_by_agg_bare_aggfunc_keeps_source_column_name(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y", "y"],
            "v1": [1, 2, 3, 4],
            "v2": [10, 20, 30, 40],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "column=v1,aggfunc=sum; column=v2,aggfunc=mean"])

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

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "column=v1,aggfunc=sum,as=total"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "total" in out
    assert "v1" not in out.split("\n")[0]  # header uses the custom output name, not the source column

def test_agg_same_func_on_multiple_columns(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["x", "x"], "v1": [1, 2], "v2": [10, 20]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "column='v1,v2',aggfunc=sum"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "v1" in out and "v2" in out
    assert "3" in out and "30" in out

def test_agg_named_output_with_spaced_group(tmp_path, capsys):
    df = pd.DataFrame({"Scenario Name": ["A", "A", "B"], "value": [1, 2, 3]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main(
        [path, "-group_by", "Scenario Name", "-agg", "column=value,aggfunc=sum,as=v"]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    header = out.split("\n")[0]
    assert "v" in header and "value" not in header
    assert "3" in out

def test_agg_rejects_dict_literal(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit, match="key=value"):
        cli.main([path, "-group_by", "grp", "-agg", "{'v1':'sum'}"])

def test_agg_requires_group_by(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-agg", "column=v1,aggfunc=sum"])
    assert exc_info.value.code == 2

def test_agg_df_and_agg_cannot_combine(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-agg_df", "-group_by", "grp", "-agg", "column=v1,aggfunc=sum"])
    assert exc_info.value.code == 2

def test_group_x_default_counts_auto_detected_group(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y"],
            "val": [1, 2, 3],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-group_x"])

    out = capsys.readouterr().out
    assert exit_code == 0
    lines = out.strip().split("\n")
    assert "n" in lines[0]
    # both 'x' rows see group size 2, the 'y' row sees group size 1.
    assert "2" in lines[1] and "2" in lines[2] and "1" in lines[3]

def test_group_x_with_explicit_group_by_and_value(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y", "y"],
            "val": [1, 2, 3, 4],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-group_x", "group=grp,v=val,a=mean"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1.5" in out and "3.5" in out

def test_group_x_still_accepts_group_by_flag(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["x", "x", "y", "y"], "val": [1, 2, 3, 4]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-group_by", "grp", "-group_x", "v=val,a=mean"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1.5" in out and "3.5" in out

def test_group_by_requires_agg_or_group_x(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-group_by", "grp"])
    assert exc_info.value.code == 2

def test_agg_then_sort_by_prints_only_final_table(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["b", "a", "a"],
            "val": [2, 1, 3],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-agg_df", "sum", "-sort_by", "grp"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # Header should appear once: only final sorted aggregated table is printed.
    assert out.count("grp") == 1

def test_parse_agg_name_list_and_mapping():
    from pytae.cli_parsing import parse_agg
    assert parse_agg("mean") == "mean"
    assert parse_agg("mean,sum,n") == ["mean", "sum", "n"]
    assert parse_agg("val: sum, n: n") == {"val": "sum", "n": "n"}
    assert parse_agg("'body mass': mean") == {"body mass": "mean"}
    with pytest.raises(SystemExit, match="use a name"):
        parse_agg("['mean', 'sum']")
    with pytest.raises(SystemExit, match="mix of names"):
        parse_agg("mean, val: sum")

def test_agg_df_comma_list(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3]}),
    )

    exit_code = cli.main([path, "-agg_df", "sum,n", "-cols"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "n", "val"]

def test_agg_df_python_literal_is_rejected(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "val": [1]}))
    with pytest.raises(SystemExit, match="use a name"):
        cli.main([path, "-agg_df", "{'val': 'sum'}"])

