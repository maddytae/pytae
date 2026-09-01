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
    assert out.strip() == "(3, 2)"


def test_order_shape_then_head(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(10), "b": range(10, 20)}))

    exit_code = cli.main([path, "-shape", "-head", "3"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "(10, 2)" not in out
    assert "0" in out and "10" in out


def test_head_then_cols_prints_only_names(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(8), "b": range(8)}))

    exit_code = cli.main([path, "-head", "5", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["a", "b"]


def test_empty_parquet_head_keeps_columns(tmp_path, capsys):
    path = tmp_path / "empty.parquet"
    pd.DataFrame({"a": pd.Series(dtype="int64"), "b": pd.Series(dtype="object")}).to_parquet(path, index=False)

    exit_code = cli.main([str(path), "-head", "5"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert "a" in captured.out and "b" in captured.out
    assert "Empty DataFrame" in captured.out


def test_info_prints_pandas_info(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}))

    exit_code = cli.main([path, "-info"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "DataFrame" in out
    assert "a" in out and "b" in out
    assert "2 entries" in out or "2 rows" in out or "RangeIndex: 2" in out


def test_head_then_info_prints_only_info(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(10), "b": range(10)}))

    exit_code = cli.main([path, "-head", "3", "-info"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "RangeIndex: 3" in out
    assert "DataFrame" in out


def test_describe_prints_pandas_summary(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2, 3]}))

    exit_code = cli.main([path, "-describe"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "count" in out and "mean" in out


def test_stats_flag_removed(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-stats"])
    assert exc_info.value.code == 2


def test_nonpositive_head_is_usage_error(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2, 3]}))

    for n in ("0", "-5"):
        with pytest.raises(SystemExit) as exc_info:
            cli.main([path, "-head", n])
        assert exc_info.value.code == 2


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

    exit_code = cli.main([path, "-group_by", "grp", "-group_x", "val:mean"])

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


def test_long_melts_numeric_columns(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["a", "b"], "n": [1, 2], "x": [10, 20]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-long", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["grp", "variable", "value"]


def test_long_renames_melt_columns(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["a"], "n": [1], "x": [10]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-long", "feature:amount", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "feature", "amount"]


def test_wide_pivots_long_frame(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "country": ["sg", "cn", "ca"],
            "balance": [10, 20, 0],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "country:balance", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "ca", "cn", "sg"]


def test_long_quoted_names_with_spaces(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["a"], "n": [1], "x": [10]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-long", "feature name:amount col", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "feature name", "amount col"]


def test_wide_quoted_names_with_spaces(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "id": ["a", "b"],
            "country name": ["sg", "cn"],
            "body mass": [10, 20],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "country name:body mass", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "cn", "sg"]


def test_wide_unknown_column_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"id": ["a"], "balance": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-wide", "country:balance"])
    assert exc_info.value.code == 2


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

    exit_code = cli.main([path, "-select", "grp,val", "-sort_by", "val", "desc", "-head", "1"])

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

    exit_code = cli.main([path, "-select", "grp", "-value_counts", "-sort_by", "count"])

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

    exit_code = cli.main([path, "-agg_df", "sum", "-sort_by", "grp"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # Header should appear once: only final sorted aggregated table is printed.
    assert out.count("grp") == 1


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


def test_cols_default_is_file_order(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"c": [1], "a": [2], "b": [3]}))

    exit_code = cli.main([path, "-cols"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines() == ["c", "a", "b"]


def test_cols_asc_and_desc(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"c": [1], "a": [2], "b": [3]}))

    assert cli.main([path, "-cols", "asc"]) == 0
    assert capsys.readouterr().out.strip().splitlines() == ["a", "b", "c"]

    assert cli.main([path, "-cols", "desc"]) == 0
    assert capsys.readouterr().out.strip().splitlines() == ["c", "b", "a"]


def test_dtype_optional_name_order(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"c": [1], "a": ["x"]}))

    assert cli.main([path, "-dtype"]) == 0
    file_order = capsys.readouterr().out
    assert file_order.splitlines()[0].startswith("c")

    assert cli.main([path, "-dtype", "asc"]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("a")


def test_sort_by_default_is_ascending(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["b", "a", "c"], "val": [2, 1, 3]}))

    exit_code = cli.main([path, "-sort_by", "val", "-head", "1"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "a" in out
    assert "1" in out


def test_sort_by_explicit_asc(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["b", "a"], "val": [2, 1]}))

    exit_code = cli.main([path, "-sort_by", "val", "asc", "-head", "1"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "a" in out
    assert "1" in out


def test_sort_flag_removed(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-sort", "desc"])
    assert exc_info.value.code == 2


def test_cols_rejects_invalid_order(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-cols", "foo"])
    assert exc_info.value.code == 2


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

    exit_code = cli.main([path, "-head", "2", "-to_clip"])

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

    exit_code = cli.main([path, "-qry", "{'month': 202607}", "-to_clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    pd.testing.assert_frame_equal(
        copied["frame"].reset_index(drop=True),
        pd.DataFrame({"month": [202607, 202607], "value": [2, 3]}),
    )


def test_clip_shape_alone_succeeds(tmp_path, capsys, monkeypatch):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    copied = {}
    monkeypatch.setattr(cli, "_copy_to_clipboard", lambda s: copied.setdefault("text", s))

    exit_code = cli.main([path, "-shape", "-to_clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert copied["text"] == "(2, 2)"


def test_cli_convert_csv_to_parquet(tmp_path, capsys):
    src = tmp_path / "data.csv"
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_csv(src, index=False)
    dest = tmp_path / "data.parquet"

    exit_code = cli.main([str(src), "-convert", "-o", str(dest)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert dest.exists()
    assert "Wrote 2 rows" in out
    result = pd.read_parquet(dest)
    assert list(result.columns) == ["a", "b"]
    assert len(result) == 2