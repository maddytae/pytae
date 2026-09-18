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


def test_sample_with_seed_is_reproducible(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(100), "b": range(100, 200)}))

    cli.main([path, "-sample", "10", "-seed", "42"])
    first = capsys.readouterr().out

    cli.main([path, "-sample", "10", "-seed", "42"])
    second = capsys.readouterr().out

    assert first == second


def test_sample_frac_selects_expected_row_count(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(100), "b": range(100, 200)}))

    exit_code = cli.main([path, "-sample", "-frac", "0.1", "-seed", "1", "-shape"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip() == "(10, 2)"


def _penguins_frame():
    return pd.DataFrame({
        "species": ["Adelie", "Adelie", "Adelie", "Chinstrap", "Chinstrap", "Gentoo", "Gentoo", "Gentoo"],
        "island": ["Biscoe", "Dream", "Dream", "Dream", "Dream", "Biscoe", "Biscoe", "Biscoe"],
        "sex": ["Male", "Female", "Male", "Male", "Female", "Male", "Female", "Male"],
        "body_mass_g": [3750, 3800, 4000, 3700, 3400, 5700, 4500, 5600],
    })


def test_crosstab_counts(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    exit_code = cli.main([path, "-crosstab", "index='species',columns='island'"])

    out = capsys.readouterr().out
    assert exit_code == 0
    lines = out.strip().splitlines()
    assert lines[0].split() == ["island", "Biscoe", "Dream"]
    assert lines[2].split() == ["Adelie", "1", "2"]


def test_crosstab_margins_adds_totals(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    cli.main([path, "-crosstab", "index='species',columns='island',margins=true"])

    out = capsys.readouterr().out
    assert "All" in out.strip().splitlines()[0]


def test_crosstab_margins_name_renames_totals(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    cli.main([path, "-crosstab", "index='species',columns='island',margins=true,margins_name='Total'"])

    out = capsys.readouterr().out
    assert "Total" in out.strip().splitlines()[0]
    assert "All" not in out


def test_crosstab_margins_name_requires_margins(tmp_path):
    path = _write_csv(tmp_path, _penguins_frame())

    with pytest.raises(SystemExit, match="margins_name= requires margins=true"):
        cli.main([path, "-crosstab", "index='species',columns='island',margins_name='Total'"])


def test_crosstab_values_and_aggfunc(tmp_path, capsys):
    path = _write_csv(tmp_path, _penguins_frame())

    exit_code = cli.main([
        path, "-crosstab",
        "index='species',columns='sex',values='body_mass_g',aggfunc='mean'",
        "-round", "1",
    ])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "3875.0" in out


def test_crosstab_values_requires_aggfunc(tmp_path):
    path = _write_csv(tmp_path, _penguins_frame())

    with pytest.raises(SystemExit, match="values= and aggfunc= must be given together"):
        cli.main([path, "-crosstab", "index='species',columns='sex',values='body_mass_g'"])


def test_crosstab_unknown_column_errors(tmp_path):
    path = _write_csv(tmp_path, _penguins_frame())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-crosstab", "index='species',columns='nope'"])
    assert exc_info.value.code == 2


def test_frac_requires_sample(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(10), "b": range(10, 20)}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-frac", "0.5", "-head"])
    assert exc_info.value.code == 2


def test_shape_cannot_be_followed_by_another_flag(tmp_path):
    # -shape returns a tuple in pandas terms (not a DataFrame), so nothing may
    # chain after it except -to_clip.
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(10), "b": range(10, 20)}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-shape", "-head", "3"])
    assert exc_info.value.code == 2


@pytest.mark.parametrize("op", ["cols", "dtype", "nulls", "info"])
def test_non_df_ops_cannot_be_followed_by_another_flag(tmp_path, op):
    path = _write_csv(tmp_path, pd.DataFrame({"a": range(3), "b": range(3, 6)}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, f"-{op}", "-head", "1"])
    assert exc_info.value.code == 2


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

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "column='v1',aggfunc='sum'; column='v2',aggfunc='mean'"])

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

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "column='v1',aggfunc='sum',as='total'"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "total" in out
    assert "v1" not in out.split("\n")[0]  # header uses the custom output name, not the source column


def test_agg_same_func_on_multiple_columns(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["x", "x"], "v1": [1, 2], "v2": [10, 20]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-group_by", "grp", "-agg", "column='v1,v2',aggfunc='sum'"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "v1" in out and "v2" in out
    assert "3" in out and "30" in out


def test_agg_named_output_with_spaced_group(tmp_path, capsys):
    df = pd.DataFrame({"Scenario Name": ["A", "A", "B"], "value": [1, 2, 3]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main(
        [path, "-group_by", "Scenario Name", "-agg", "column='value',aggfunc='sum',as='v'"]
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
        cli.main([path, "-agg", "column='v1',aggfunc='sum'"])
    assert exc_info.value.code == 2


def test_agg_df_and_agg_cannot_combine(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["x"], "v1": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-agg_df", "-group_by", "grp", "-agg", "column='v1',aggfunc='sum'"])
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

    exit_code = cli.main([path, "-group_x", "group='grp',v='val',a='mean'"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1.5" in out and "3.5" in out


def test_group_x_still_accepts_group_by_flag(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["x", "x", "y", "y"], "val": [1, 2, 3, 4]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-group_by", "grp", "-group_x", "v='val',a='mean'"])

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

    exit_code = cli.main([path, "-long", "c='feature',v='amount'", "-cols"])

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

    exit_code = cli.main([path, "-wide", "c='country',v='balance'", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "ca", "cn", "sg"]


def test_long_quoted_names_with_spaces(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["a"], "n": [1], "x": [10]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-long", "c='feature name',v='amount col'", "-cols"])

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

    exit_code = cli.main([path, "-wide", "c='country name',v='body mass'", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "cn", "sg"]


def test_wide_aggfunc_mean(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "id": ["a", "a"],
            "country": ["sg", "sg"],
            "balance": [10, 20],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "c='country',v='balance',a='mean'", "-head", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert "15" in captured.out


def test_cli_long_short_aliases(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["a"], "n": [1], "x": [10]}))

    exit_code = cli.main([path, "-long", "c='feature',v='amount'", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "feature", "amount"]


def test_cli_wide_short_aliases(tmp_path, capsys):
    df = pd.DataFrame({"id": ["a", "b"], "country": ["sg", "cn"], "balance": [10, 20]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "c='country',v='balance',a='mean'", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "cn", "sg"]


def test_wide_unknown_column_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"id": ["a"], "balance": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-wide", "c='country',v='balance'"])
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
        [path, "-agg_df", "{'val': 'sum', 'n': 'n'}", "-select", "grp,n", "-cols"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "n"]


def test_agg_df_dict_without_braces_is_equivalent(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"grp": ["x", "x", "y"], "val": [1, 2, 3], "z": [9, 8, 7]}),
    )

    exit_code = cli.main(
        [path, "-agg_df", "'val': 'sum', 'n': 'n'", "-select", "grp,n", "-cols"]
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
        cli.main([path, "-select", "keep,val", "-qry", "{'flt':'A'}", "-shape"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "-qry" in err
    assert "flt" in err


def test_query_then_select_filters_like_pandas(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    exit_code = cli.main(
        [path, "-query", "flt == 'A'", "-select", "keep,val", "-shape"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 2)"


def test_qry_without_braces_is_equivalent(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    exit_code = cli.main([path, "-qry", "'flt': 'A'", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 3)"


def test_qry_column_key_quoting_is_optional(tmp_path, capsys):
    path = _write_csv(
        tmp_path,
        pd.DataFrame({"keep": [1, 2, 3], "flt": ["A", "B", "A"], "val": [10, 20, 30]}),
    )

    cli.main([path, "-qry", "flt:'A'", "-shape"])
    unquoted = capsys.readouterr().out.strip()

    cli.main([path, "-qry", "'flt':'A'", "-shape"])
    quoted = capsys.readouterr().out.strip()

    assert unquoted == quoted == "(2, 3)"


def test_qry_unquoted_string_value_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"flt": ["A", "B"]}))

    with pytest.raises(SystemExit, match="must be quoted"):
        cli.main([path, "-qry", "flt:A", "-shape"])


def test_describe_then_shape_is_describe_table(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}))

    exit_code = cli.main([path, "-describe", "-shape"])

    assert exit_code == 0
    # pandas describe() of two numeric columns is 8 stats × 2
    assert capsys.readouterr().out.strip() == "(8, 2)"


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


def test_sql_query_via_df_alias(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1, 20, 3], "col b": ["x", "y", "z"]}))

    exit_code = cli.main([path, "-sql", 'select "col b" from df where "col a" > 10'])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "y" in out
    assert "x" not in out


def test_sql_spaced_column_name_needs_double_quotes(tmp_path, capsys):
    # Standard SQL identifier quoting: double quotes for names with spaces, not single quotes.
    path = _write_csv(tmp_path, pd.DataFrame({"bill length mm": [1, 20, 3], "species": ["a", "b", "c"]}))

    exit_code = cli.main([path, "-sql", 'select species from df where "bill length mm" > 10'])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines()[-1].strip() == "b"


def test_sql_only_df_is_registered_no_file_derived_alias(tmp_path, capsys):
    # The file is already named on the command line; -sql does not also register a
    # file-stem alias (e.g. "data" for data.csv) -- only `df` is queryable.
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-sql", "select * from data"])
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
        [path, "-select", "keep,flt", "-sql", 'select "keep" from df where "flt" = \'A\'', "-shape"]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 1)"


def test_sql_invalid_query_errors(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-sql", "not valid sql"])
    assert exc_info.value.code == 2
    assert "-sql" in capsys.readouterr().err



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


def _replace_frame():
    return pd.DataFrame({
        "col a": ["a magician", "not a magician exactly", "analphabet"],
        "colb": ["alpha", "alpha team", "x"],
    })


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

    cli.main([path, "-replace_values", "c='col a',v='alpha:bravo'"])

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
        cli.main([path, "-replace_values", "c='missing',v='alpha:bravo'"])
    assert exc_info.value.code == 2
    assert "-replace_values" in capsys.readouterr().err


def test_replace_requires_v(tmp_path):
    path = _write_csv(tmp_path, _replace_frame())

    with pytest.raises(SystemExit):
        cli.main([path, "-replace_values", "c='col a'"])


def test_replace_values_mapping_quoting_is_optional(tmp_path, capsys):
    df = pd.DataFrame({"col a": ["alpha"], "colb": ["alpha"]})

    path = _write_csv(tmp_path, df)
    cli.main([path, "-replace_values", "v=alpha:bravo"])
    unquoted = capsys.readouterr().out.strip()

    path = _write_csv(tmp_path, df)
    cli.main([path, "-replace_values", "v='alpha':'bravo'"])
    quoted = capsys.readouterr().out.strip()

    assert unquoted == quoted
    assert "bravo" in unquoted


def _messy_headers_frame():
    return pd.DataFrame({
        "  Col A  ": [1],
        "col   b": [2],
        "Col A": [3],
        "100% Match!": [4],
    })


def test_rename_quoting_is_optional(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"old col": [1, 2], "b": [3, 4]}))
    out1 = tmp_path / "out1.csv"
    out2 = tmp_path / "out2.csv"

    cli.main([path, "-convert", "-rename", "old col:new col", "-o", str(out1)])
    cli.main([path, "-convert", "-rename", "'old col':'new col'", "-o", str(out2)])

    assert list(pd.read_csv(out1).columns) == ["new col", "b"]
    assert list(pd.read_csv(out2).columns) == ["new col", "b"]


def test_clean_columns_strip_fill_case(tmp_path, capsys):
    path = _write_csv(tmp_path, _messy_headers_frame())

    cli.main([path, "-clean_columns", "strip,fill,case=lower"])

    header = capsys.readouterr().out.strip().splitlines()[0].split()
    assert header == ["col_a", "col___b", "col_a", "100%_match!"]


def test_clean_columns_custom_fill_char(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"col a": [1]}))

    cli.main([path, "-clean_columns", "fill='$'"])

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

    cli.main([path, "-clean_columns", "strip_special,fill='-'", "-cols"])

    header = capsys.readouterr().out.strip()
    assert header == "co-ops-data"


def _write_two_csvs(tmp_path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    pd.DataFrame({"col a": [1, 2, 3], "val_l": ["a", "b", "c"]}).to_csv(left, index=False)
    pd.DataFrame({"cola": [1, 2, 4], "val_r": ["x", "y", "z"]}).to_csv(right, index=False)
    return str(left), str(right)


def test_merge_on_differing_column_names(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on='col a:cola'",
    ])

    out = capsys.readouterr().out.strip()
    assert "val_l" in out and "val_r" in out
    assert len(out.splitlines()) == 3  # header + 2 matching rows (inner join)


def test_merge_on_pair_quoting_is_optional(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on='col a':'cola'",
    ])

    out = capsys.readouterr().out.strip()
    assert "val_l" in out and "val_r" in out
    assert len(out.splitlines()) == 3


def test_merge_shared_column_name_outer_join(tmp_path, capsys):
    left = tmp_path / "a.csv"
    right = tmp_path / "b.csv"
    pd.DataFrame({"id": [1, 2, 3], "x": ["a", "b", "c"]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 2, 4], "y": ["p", "q", "r"]}).to_csv(right, index=False)

    cli.main([
        "-file", f"{left}=a;{right}=b",
        "-merge", "left=a,right=b,on='id',how=outer", "-shape",
    ])

    assert capsys.readouterr().out.strip() == "(4, 3)"


def test_merge_requires_file(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-merge", "left=df1,right=df2,on='id'"])
    assert exc_info.value.code == 2


def test_file_requires_merge(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{left}=df1;{right}=df2", "-shape"])
    assert exc_info.value.code == 2


def test_file_cannot_combine_with_positional_path(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([left, "-file", f"{left}=df1;{right}=df2", "-merge", "left=df1,right=df2,on='col a:cola'"])
    assert exc_info.value.code == 2


def test_merge_unknown_alias_errors(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{left}=df1;{right}=df2", "-merge", "left=df1,right=bogus,on='col a:cola'"])
    assert exc_info.value.code == 2


def test_merge_convert_requires_output(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{left}=df1;{right}=df2", "-merge", "left=df1,right=df2,on='col a:cola'", "-convert"])
    assert exc_info.value.code == 2


def test_merge_must_be_first_op_with_file(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([
            "-file", f"{left}=df1;{right}=df2",
            "-shape",
            "-merge", "left=df1,right=df2,on='col a:cola'",
        ])
    assert exc_info.value.code == 2


def test_sql_can_join_file_aliases_directly(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-sql", 'select * from df1 inner join df2 on df1."col a" = df2.cola',
    ])

    out = capsys.readouterr().out
    assert "val_l" in out and "val_r" in out


def test_sql_after_merge_can_query_df(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on='col a:cola'",
        "-sql", "select count(*) as n from df",
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


def _write_three_id_csvs(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    c = tmp_path / "c.csv"
    pd.DataFrame({"id": [1, 2, 3], "x": ["a", "b", "c"]}).to_csv(a, index=False)
    pd.DataFrame({"id": [1, 2, 4], "y": ["p", "q", "r"]}).to_csv(b, index=False)
    pd.DataFrame({"id": [1, 2], "z": ["m", "n"]}).to_csv(c, index=False)
    return str(a), str(b), str(c)


def test_merge_chained_via_df_alias(tmp_path, capsys):
    a, b, c = _write_three_id_csvs(tmp_path)

    cli.main([
        "-file", f"{a}=a;{b}=b;{c}=c",
        "-merge", "left=a,right=b,on='id'",
        "-merge", "left=df,right=c,on='id'",
    ])

    out = capsys.readouterr().out
    assert all(col in out for col in ("x", "y", "z"))


def test_merge_df_not_available_before_anything_produced(tmp_path, capsys):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=df,right=b,on='id'"])
    assert exc_info.value.code == 2
    assert "'df' isn't available yet" in capsys.readouterr().err


def test_concat_stacks_three_frames_with_reset_index(tmp_path, capsys):
    a, b, c = _write_three_id_csvs(tmp_path)

    cli.main(["-file", f"{a}=a;{b}=b;{c}=c", "-concat", "frames='a,b,c'"])

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 + 3 + 3 + 2  # header + 3 rows from each of a, b, c


def test_concat_resets_index(tmp_path, capsys, monkeypatch):
    a, b, _ = _write_three_id_csvs(tmp_path)
    copied = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["frame"] = self.copy()

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    cli.main(["-file", f"{a}=a;{b}=b", "-concat", "frames='a,b'", "-to_clip"])

    result = copied["frame"]
    assert list(result.index) == list(range(len(result)))


def test_concat_chained_via_df_alias(tmp_path, capsys):
    a, b, c = _write_three_id_csvs(tmp_path)

    cli.main([
        "-file", f"{a}=a;{b}=b;{c}=c",
        "-concat", "frames='a,b'",
        "-concat", "frames='df,c'",
        "-shape",
    ])

    assert capsys.readouterr().out.strip() == "(8, 4)"


def test_concat_requires_file(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-concat", "frames='a,b'"])
    assert exc_info.value.code == 2


def test_concat_unknown_alias_errors(tmp_path, capsys):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{a}=a;{b}=b", "-concat", "frames='a,bogus'"])
    assert exc_info.value.code == 2
    assert "unknown -file alias" in capsys.readouterr().err


def test_file_dlim_and_encoding_overrides_applied(tmp_path, capsys):
    pipe_path = tmp_path / "pipe.csv"
    pipe_path.write_bytes("id|name\n1|caf\xe9\n".encode("latin-1"))
    plain_path = tmp_path / "plain.csv"
    pd.DataFrame({"id": [2], "name": ["bravo"]}).to_csv(plain_path, index=False)

    cli.main([
        "-file", f"{pipe_path}=p,dlim='|',encoding='latin-1'; {plain_path}=q",
        "-concat", "frames='p,q'",
    ])

    out = capsys.readouterr().out
    assert "café" in out
    assert "bravo" in out


def test_file_requires_at_least_two_entries(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit, match="at least two"):
        cli.main(["-file", f"{path}=a", "-concat", "frames='a,a'"])


def test_concat_requires_at_least_two_frame_names(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="frames= needs at least two names"):
        cli.main(["-file", f"{a}=a;{b}=b", "-concat", "frames='a'"])


def test_file_duplicate_alias_errors(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="duplicate alias"):
        cli.main(["-file", f"{a}=x;{b}=x", "-concat", "frames='x,x'"])


def test_merge_on_mixed_style_errors(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="mixes plain columns and left:right pairs"):
        cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=a,right=b,on='id:id,x'"])


def test_merge_missing_required_keys_errors(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="missing required key"):
        cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=a"])


def test_merge_validate_failure_errors(tmp_path, capsys):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    pd.DataFrame({"id": [1, 1, 2], "x": ["a", "b", "c"]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 2], "y": ["p", "q"]}).to_csv(right, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([
            "-file", f"{left}=l;{right}=r",
            "-merge", "left=l,right=r,on='id',validate=one_to_one",
        ])
    assert exc_info.value.code == 2
    assert "-merge:" in capsys.readouterr().err


def test_convert_succeeds_after_merge(tmp_path):
    left, right = _write_two_csvs(tmp_path)
    dest = tmp_path / "merged.parquet"

    exit_code = cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on='col a:cola'",
        "-convert", "-o", str(dest),
    ])

    assert exit_code == 0
    assert dest.exists()
    result = pd.read_parquet(dest)
    assert list(result.columns) == ["col a", "val_l", "cola", "val_r"]
    assert len(result) == 2


def test_select_runs_after_merge(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on='col a:cola'",
        "-select", "val_l,val_r", "-shape",
    ])

    assert capsys.readouterr().out.strip() == "(2, 2)"


def test_file_nonexistent_path_errors(tmp_path, capsys):
    a, _, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{a}=a;{tmp_path / 'missing.csv'}=b", "-concat", "frames='a,b'"])
    assert exc_info.value.code == 2
    assert "file not found" in capsys.readouterr().err


def test_file_bad_encoding_errors(tmp_path, capsys):
    bad_path = tmp_path / "bad.csv"
    bad_path.write_bytes("id,name\n1,caf\xe9\n".encode("latin-1"))
    ok_path = tmp_path / "ok.csv"
    pd.DataFrame({"id": [2], "name": ["bravo"]}).to_csv(ok_path, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{bad_path}=a;{ok_path}=b", "-concat", "frames='a,b'"])
    assert exc_info.value.code == 2
    assert "try -encoding" in capsys.readouterr().err