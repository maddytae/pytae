import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv


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

def test_cli_long_short_aliases(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"grp": ["a"], "n": [1], "x": [10]}))

    exit_code = cli.main([path, "-long", "c=feature,v=amount", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["grp", "feature", "amount"]

def test_cli_wide_short_aliases(tmp_path, capsys):
    df = pd.DataFrame({"id": ["a", "b"], "country": ["sg", "cn"], "balance": [10, 20]})
    path = _write_csv(tmp_path, df)

    exit_code = cli.main([path, "-wide", "c=country,v=balance,a=mean", "-cols"])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.strip().splitlines() == ["id", "cn", "sg"]

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

    exit_code = cli.main([path, "-select", "grp,val", "-sort_by", "val desc", "-head", "1"])

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

    exit_code = cli.main([path, "-sort_by", "val asc", "-head", "1"])

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

def test_repeated_drop_subtracts_sequentially(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]}))

    exit_code = cli.main([path, "-drop", "b", "-drop", "d", "-cols"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == ["a", "c"]

def test_unquoted_spec_with_a_space_gets_a_quoting_hint(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"n": [1, 2]}))

    # simulates the shell splitting an unquoted "-select species,col name" into
    # separate argv tokens ("col" and "name" land as unrecognized leftovers)
    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-select", "n,col", "name"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments: col name" in err or "unrecognized arguments: name" in err
    assert "wrap the whole spec in quotes" in err

def test_typo_flag_does_not_get_the_quoting_hint(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"n": [1, 2]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-selecttypo", "n"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err
    assert "wrap the whole spec in quotes" not in err

def test_describe_then_shape_is_describe_table(tmp_path, capsys):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}))

    exit_code = cli.main([path, "-describe", "-shape"])

    assert exit_code == 0
    # pandas describe() of two numeric columns is 8 stats × 2
    assert capsys.readouterr().out.strip() == "(8, 2)"

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

def test_clip_shape_alone_succeeds(tmp_path, capsys, monkeypatch):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    copied = {}
    monkeypatch.setattr("pytae.cli_run._copy_to_clipboard", lambda s: copied.setdefault("text", s))

    exit_code = cli.main([path, "-shape", "-to_clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert copied["text"] == "(2, 2)"

def test_clip_shape_and_df_flag_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-head", "1", "-shape", "-to_clip"])
    assert exc_info.value.code == 2

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

