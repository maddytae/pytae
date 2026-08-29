import os
import sys

import pandas as pd
import pytest


# Keep test imports consistent with existing test files.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli


def _write_csv(tmp_path, df: pd.DataFrame) -> str:
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_order_head_then_shape(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(10), "b": range(10, 20)}))

    exit_code = cli.main([path, "-head", "3", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(3, 2)" in out


def test_order_shape_then_head(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(10), "b": range(10, 20)}))

    exit_code = cli.main([path, "-shape", "-head", "3"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(10, 2)" in out


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

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "{'v1':'sum','v2':'mean'}"])

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

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "{'v1':('total','sum')}"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "total" in out
    assert "v1" not in out.split("\n")[0]  # header uses the custom output name, not the source column


def test_agg_requires_group_by(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-agg", "{'v1':'sum'}"])
    assert exc_info.value.code == 2


def test_group_by_requires_agg(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-group_by", "grp"])
    assert exc_info.value.code == 2


def test_agg_df_and_agg_cannot_combine(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-agg_df", "-group_by", "grp", "-agg", "{'v1':'sum'}"])
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

    exit_code = cli.main([path, "-group_by", "grp", "-group_x", "mean:val"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1.5" in out and "3.5" in out


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


def test_group_by_requires_agg_or_group_x(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-group_by", "grp"])
    assert exc_info.value.code == 2


def test_order_unique_then_shape_uses_deduplicated_frame(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y"],
            "val": [1, 1, 2],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-unique", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # One duplicated row is removed by -unique, then -shape reflects the reduced frame.
    assert "(2, 2)" in out


def test_order_value_counts_then_shape_uses_count_table(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y"],
            "val": [1, 2, 3],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "grp", "-value_counts", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # value_counts result has two columns: key + count.
    assert "(2, 2)" in out


def test_value_counts_dropna_false_keeps_na_key(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", None, "x"],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "grp", "-value_counts", "-dropna", "false", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # dropna=false includes NA as its own key, yielding x + NA.
    assert "(2, 2)" in out


def test_value_counts_uses_selected_multiple_columns(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "num_legs": [2, 4, 4, 6],
            "num_wings": [2, 0, 0, 0],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "num_legs,num_wings", "-value_counts", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # Two key columns + count, three unique key combinations.
    assert "(3, 3)" in out


def test_value_counts_without_argument_uses_selected_columns(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "num_legs": [2, 4, 4, 6],
            "num_wings": [2, 0, 0, 0],
            "animal": ["falcon", "dog", "cat", "ant"],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "num_legs,num_wings", "-value_counts", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # -select narrows working columns, so no-arg -value_counts uses those two.
    assert "(3, 3)" in out


def test_order_sort_by_then_shape_uses_sorted_frame(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["b", "a", "c"],
            "val": [2, 1, 3],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-sort_by", "grp", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(3, 2)" in out


def test_sort_by_respects_select_and_descending(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["a", "b", "c"],
            "val": [1, 3, 2],
            "other": [10, 20, 30],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "grp,val", "-sort", "desc", "-sort_by", "val", "-head", "1"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # After sorting by val desc, the first row should be grp=b, val=3.
    assert "b" in out
    assert "3" in out


def test_value_counts_then_sort_by_prints_only_final_table(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["x", "x", "y"],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-select", "grp", "-value_counts", "-sort", "asc", "-sort_by", "count"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # Header should appear once: only final sorted value_counts table is printed.
    assert out.count("grp") == 1


def test_agg_then_sort_by_prints_only_final_table(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["b", "a", "a"],
            "val": [2, 1, 3],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-agg_df", "sum", "-sort", "asc", "-sort_by", "grp"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # Header should appear once: only final sorted aggregated table is printed.
    assert out.count("grp") == 1


def test_qry_column_not_in_select_still_filters(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "keep": [1, 2, 3],
            "flt": ["A", "B", "A"],
            "val": [10, 20, 30],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main(
        [
            path,
            "-qry",
            "{'flt':'A'}",
            "-select",
            "'keep','val'",
            "-shape",
        ]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(2, 2)" in out


def test_clip_suppresses_stdout_for_dataframe_ops(tmp_path, capsys, monkeypatch):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [3, 4]}))

    copied = {"called": False}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["called"] = True

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    exit_code = cli.main([path, "-head", "2", "-clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert copied["called"] is True


def test_qry_clip_copies_filtered_frame_without_output_op(tmp_path, capsys, monkeypatch):
    path = _write_csv(tmp_path, pd.DataFrame({"month": [202606, 202607, 202607], "value": [1, 2, 3]}))

    copied = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["frame"] = self.copy()

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    exit_code = cli.main([path, "-qry", "{'month': 202607}", "-clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    pd.testing.assert_frame_equal(
        copied["frame"].reset_index(drop=True),
        pd.DataFrame({"month": [202607, 202607], "value": [2, 3]}),
    )