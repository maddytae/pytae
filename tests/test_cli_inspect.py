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
    # chain after it except -o clip.
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

    exit_code = cli.main([path, "-head", "2", "-o", "clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert copied["called"] is True

def test_clip_shape_alone_succeeds(tmp_path, capsys, monkeypatch):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    copied = {}
    monkeypatch.setattr("pytae.cli_run._copy_to_clipboard", lambda s: copied.setdefault("text", s))

    exit_code = cli.main([path, "-shape", "-o", "clip"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert copied["text"] == "(2, 2)"

def test_clip_shape_and_df_flag_errors(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-head", "1", "-shape", "-o", "clip"])
    assert exc_info.value.code == 2

def test_cli_convert_csv_to_parquet(tmp_path, capsys):
    src = tmp_path / "data.csv"
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_csv(src, index=False)
    dest = tmp_path / "data.parquet"

    exit_code = cli.main([str(src), "-o", str(dest)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert dest.exists()
    assert "Wrote 2 rows" in out
    result = pd.read_parquet(dest)
    assert list(result.columns) == ["a", "b"]
    assert len(result) == 2

def test_cli_output_bare_format(tmp_path, capsys):
    src = tmp_path / "input.csv"
    pd.DataFrame({"x": [10, 20]}).to_csv(src, index=False)

    exit_code = cli.main([str(src), "-o", "parquet"])
    assert exit_code == 0
    dest = tmp_path / "input.parquet"
    assert dest.exists()
    assert len(pd.read_parquet(dest)) == 2

def test_cli_output_shape_to_file_errors(tmp_path):
    src = tmp_path / "data.csv"
    pd.DataFrame({"a": [1]}).to_csv(src, index=False)
    dest = tmp_path / "out.parquet"

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(src), "-shape", "-o", str(dest)])
    assert exc_info.value.code == 2

def test_cli_removed_flags_migration_errors(tmp_path):
    src = tmp_path / "data.csv"
    pd.DataFrame({"a": [1]}).to_csv(src, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(src), "-to_clip"])
    assert exc_info.value.code == 2

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(src), "-convert"])
    assert exc_info.value.code == 2


def test_cli_multiple_positional_files_batch_convert(tmp_path, capsys):
    f1 = tmp_path / "data1.parquet"
    f2 = tmp_path / "data2.parquet"
    pd.DataFrame({"x": [1, 2]}).to_parquet(f1, index=False)
    pd.DataFrame({"y": [3, 4]}).to_parquet(f2, index=False)

    exit_code = cli.main([str(f1), str(f2), "-o", "csv"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert (tmp_path / "data1.csv").exists()
    assert (tmp_path / "data2.csv").exists()
    assert f"== {f1} ==" in out
    assert f"== {f2} ==" in out
    assert "Wrote 2 rows" in out


def test_cli_multiple_positional_files_inspect(tmp_path, capsys):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    pd.DataFrame({"col": [10, 20]}).to_csv(f1, index=False)
    pd.DataFrame({"col": [30, 40]}).to_csv(f2, index=False)

    exit_code = cli.main([str(f1), str(f2), "-head", "1"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert f"== {f1} ==" in out
    assert f"== {f2} ==" in out
    assert "10" in out
    assert "30" in out


def test_cli_multiple_files_single_destination_errors(tmp_path, capsys):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    pd.DataFrame({"col": [1]}).to_csv(f1, index=False)
    pd.DataFrame({"col": [2]}).to_csv(f2, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(f1), str(f2), "-o", str(tmp_path / "out.parquet")])
    assert exc_info.value.code == 2
    assert "requires a format" in capsys.readouterr().err


def test_cli_multiple_files_clip_errors(tmp_path, capsys):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    pd.DataFrame({"col": [1]}).to_csv(f1, index=False)
    pd.DataFrame({"col": [2]}).to_csv(f2, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(f1), str(f2), "-o", "clip"])
    assert exc_info.value.code == 2
    assert "-o clip cannot be used with multiple matched files" in capsys.readouterr().err


def test_cli_no_path_errors(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])
    assert exc_info.value.code == 2
    assert "the following arguments are required: path" in capsys.readouterr().err


def test_cli_positional_with_file_errors(tmp_path, capsys):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    pd.DataFrame({"id": [1]}).to_csv(f1, index=False)
    pd.DataFrame({"id": [2]}).to_csv(f2, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{f1}=a", str(f2), "-merge", "how=inner"])
    assert exc_info.value.code == 2
    assert "can't be combined with a positional path" in capsys.readouterr().err


def test_cli_progress_custom_chunk_size(tmp_path, capsys):
    src = tmp_path / "data.parquet"
    pd.DataFrame({"a": list(range(25))}).to_parquet(src, index=False)
    dest = tmp_path / "data.csv"

    exit_code = cli.main([str(src), "-o", str(dest), "-progress", "10"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert dest.exists()
    assert "reading... 10/25 rows (40%)" in out
    assert "writing... 10/25 rows (40%)" in out
    assert "Wrote 25 rows" in out


def test_cli_progress_bare_flag(tmp_path, capsys):
    src = tmp_path / "data.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(src, index=False)
    dest = tmp_path / "data.csv"

    exit_code = cli.main([str(src), "-o", str(dest), "-progress"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert dest.exists()
    assert "reading... 2/2 rows (100%)" in out
    assert "writing... 2/2 rows (100%)" in out
    assert "Wrote 2 rows" in out


def test_cli_invalid_progress_chunk_size_errors(tmp_path):
    src = tmp_path / "data.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(src, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(src), "-progress", "0"])
    assert exc_info.value.code == 2


def test_describe_and_crosstab_export_preserves_index(tmp_path):
    src = tmp_path / "data.parquet"
    df = pd.DataFrame({"sp": ["A", "B", "A"], "val": [10, 20, 30]})
    df.to_parquet(src, index=False)

    desc_csv = tmp_path / "desc.csv"
    assert cli.main([str(src), "-describe", "-o", str(desc_csv)]) == 0
    read_desc_csv = pd.read_csv(desc_csv, index_col=0)
    assert list(read_desc_csv.index) == ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]

    desc_pq = tmp_path / "desc.parquet"
    assert cli.main([str(src), "-describe", "-o", str(desc_pq)]) == 0
    read_desc_pq = pd.read_parquet(desc_pq)
    assert list(read_desc_pq.index) == ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]

    ct_csv = tmp_path / "ct.csv"
    assert cli.main([str(src), "-crosstab", "index=sp,columns=sp", "-o", str(ct_csv)]) == 0
    read_ct_csv = pd.read_csv(ct_csv, index_col=0)
    assert list(read_ct_csv.index) == ["A", "B"]

    reg_csv = tmp_path / "reg.csv"
    assert cli.main([str(src), "-head", "2", "-o", str(reg_csv)]) == 0
    read_reg = pd.read_csv(reg_csv)
    assert list(read_reg.columns) == ["sp", "val"]


def test_batch_export_colliding_stems_error(tmp_path, capsys):
    f1 = tmp_path / "stem.parquet"
    f2 = tmp_path / "stem.pq"
    pd.DataFrame({"x": [1]}).to_parquet(f1, index=False)
    pd.DataFrame({"y": [2]}).to_parquet(f2, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(f1), str(f2), "-o", "csv"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "multiple input files resolve to the same destination path" in err


def test_cli_progress_preceding_path(tmp_path):
    src = tmp_path / "data.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(src, index=False)
    dest1 = tmp_path / "out1.csv"
    dest2 = tmp_path / "out2.csv"
    dest3 = tmp_path / "out3.csv"

    assert cli.main(["-progress", str(src), "-o", str(dest1)]) == 0
    assert dest1.exists()

    assert cli.main(["-o", str(dest2), "-progress", str(src)]) == 0
    assert dest2.exists()

    assert cli.main(["-progress", "1000", str(src), "-o", str(dest3)]) == 0
    assert dest3.exists()


def test_cli_intermixed_positional_args(tmp_path):
    f1 = tmp_path / "a.parquet"
    f2 = tmp_path / "b.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(f1, index=False)
    pd.DataFrame({"b": [2]}).to_parquet(f2, index=False)

    exit_code = cli.main([str(f1), "-o", "csv", str(f2)])
    assert exit_code == 0
    assert (tmp_path / "a.csv").exists()
    assert (tmp_path / "b.csv").exists()


def test_in_place_overwrite_error_message(tmp_path, capsys):
    src = tmp_path / "file.csv"
    src.write_text("a,b\n1,2\n")

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(src), "-o", "csv"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "refusing to overwrite the source file" in err
    assert "specify a different format or an explicit path with -o/--output" in err


def test_non_df_terminal_op_error_message(tmp_path, capsys):
    src = tmp_path / "data.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(src, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(src), "-shape", "-head", "5"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "-shape does not return a DataFrame/Series, so no flag may follow it (except '-o clip'" in err


def test_cli_out_dir_single_and_batch(tmp_path):
    df1 = pd.DataFrame({"col1": [1, 2], "col2": ["x", "y"]})
    df2 = pd.DataFrame({"col1": [3, 4], "col2": ["z", "w"]})
    f1 = tmp_path / "file1.csv"
    f2 = tmp_path / "file2.csv"
    df1.to_csv(f1, index=False)
    df2.to_csv(f2, index=False)

    out_directory = tmp_path / "exported"
    # Single file
    exit_code = cli.main([str(f1), "-o", "parquet", "-out_dir", str(out_directory)])
    assert exit_code == 0
    assert (out_directory / "file1.parquet").exists()

    # Batch files with -od alias
    exit_code2 = cli.main([str(f1), str(f2), "-o", "parquet", "-od", str(out_directory)])
    assert exit_code2 == 0
    assert (out_directory / "file1.parquet").exists()
    assert (out_directory / "file2.parquet").exists()


def test_cli_out_dir_validations(tmp_path, capsys):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    out_directory = tmp_path / "exported"

    # Fails without -o
    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(f), "-out_dir", str(out_directory)])
    assert exc_info.value.code == 2
    assert "-out_dir requires -o/--output" in capsys.readouterr().err

    # Fails with -o clip
    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(f), "-o", "clip", "-out_dir", str(out_directory)])
    assert exc_info.value.code == 2
    assert "-out_dir cannot be used with '-o clip'" in capsys.readouterr().err


def test_cli_batch_out_dir_collision(tmp_path, capsys):
    sub1 = tmp_path / "sub1"
    sub2 = tmp_path / "sub2"
    sub1.mkdir()
    sub2.mkdir()
    f1 = sub1 / "data.csv"
    f2 = sub2 / "data.csv"
    f1.write_text("a,b\n1,2\n")
    f2.write_text("a,b\n3,4\n")

    out_directory = tmp_path / "exported"
    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(f1), str(f2), "-o", "parquet", "-out_dir", str(out_directory)])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "multiple input files resolve to the same destination path" in err


def test_cli_meta_parquet(tmp_path, capsys):
    p = tmp_path / "sample.parquet"
    pd.DataFrame({"id": range(10), "score": [float(i) * 1.5 for i in range(10)]}).to_parquet(p, index=False)

    exit_code = cli.main([str(p), "-meta"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Format: Parquet" in out
    assert "Rows: 10" in out
    assert "Columns: 2" in out
    assert "Row groups: 1" in out
    assert "Schema:" in out
    assert "id" in out
    assert "score" in out


def test_cli_meta_restrictions(tmp_path, capsys):
    p = tmp_path / "sample.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(p, index=False)

    # -meta cannot be chained before another flag
    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(p), "-meta", "-head", "5"])
    assert exc_info.value.code == 2
    assert "-meta does not return a DataFrame/Series, so no flag may follow it" in capsys.readouterr().err

    # -meta cannot export to file
    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(p), "-meta", "-o", "out.parquet"])
    assert exc_info.value.code == 2
    assert "-meta does not produce a tabular DataFrame, so it cannot be exported to a file" in capsys.readouterr().err


def test_cli_meta_clip(tmp_path, monkeypatch):
    p = tmp_path / "sample.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(p, index=False)

    copied = []
    monkeypatch.setattr(cli, "_process_path", cli._process_path)
    import pytae.cli_run as cli_run
    monkeypatch.setattr(cli_run, "_copy_to_clipboard", lambda text: copied.append(text))

    exit_code = cli.main([str(p), "-meta", "-o", "clip"])
    assert exit_code == 0
    assert len(copied) == 1
    assert "Format: Parquet" in copied[0]


def test_cli_diff_identical(tmp_path, capsys):
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    f1 = tmp_path / "f1.csv"
    f2 = tmp_path / "f2.csv"
    df.to_csv(f1, index=False)
    df.to_csv(f2, index=False)

    exit_code = cli.main([str(f1), "-diff", str(f2)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Comparing:" in out
    assert "Rows: 3 vs 3" in out
    assert "Cols: 2 vs 2" in out
    assert "Identical: all cell values match exactly." in out


def test_cli_diff_mismatches_and_drift(tmp_path, capsys):
    df1 = pd.DataFrame({"a": [1, 2, 3], "b": ["x", None, "z"], "c": [10, 20, 30]})
    df2 = pd.DataFrame({"a": [1, 2, 4], "b": ["x", "y", "z"], "d": [1.0, 2.0, 3.0]})
    f1 = tmp_path / "left.csv"
    f2 = tmp_path / "right.csv"
    df1.to_csv(f1, index=False)
    df2.to_csv(f2, index=False)

    exit_code = cli.main([str(f1), "-diff", str(f2)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "+ Added in left (1):   c" in out
    assert "- Removed in left (1): d" in out
    assert "Null Counts:" in out
    assert "Mismatches found" in out


def test_cli_diff_clip(tmp_path, monkeypatch):
    df = pd.DataFrame({"a": [1, 2]})
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    df.to_csv(f1, index=False)
    df.to_csv(f2, index=False)

    copied = []
    import pytae.cli_run as cli_run
    monkeypatch.setattr(cli_run, "_copy_to_clipboard", lambda text: copied.append(text))

    exit_code = cli.main([str(f1), "-diff", str(f2), "-o", "clip"])
    assert exit_code == 0
    assert len(copied) == 1
    assert "Comparing:" in copied[0]


def test_cli_diff_restrictions(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_text("a\n1\n")

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(f), "-diff", str(f), "-o", "out.csv"])
    assert exc_info.value.code == 2
    assert "-diff does not produce a tabular DataFrame, so it cannot be exported to a file" in capsys.readouterr().err


def test_cli_jsonl_inspect_and_conversion(tmp_path, capsys):
    df = pd.DataFrame({"id": [1, 2, 3], "city": ["NYC", "SFO", "LON"]})
    jpath = tmp_path / "data.jsonl"
    df.to_json(jpath, orient="records", lines=True)

    # Inspect
    exit_code = cli.main([str(jpath), "-shape"])
    assert exit_code == 0
    assert "(3, 2)" in capsys.readouterr().out

    exit_code = cli.main([str(jpath), "-cols"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "id" in out
    assert "city" in out

    # Convert to Parquet
    exit_code2 = cli.main([str(jpath), "-o", "parquet"])
    assert exit_code2 == 0
    pq_path = tmp_path / "data.parquet"
    assert pq_path.exists()
    assert len(pd.read_parquet(pq_path)) == 3

    # Convert Parquet to ndjson
    exit_code3 = cli.main([str(pq_path), "-o", "ndjson"])
    assert exit_code3 == 0
    assert (tmp_path / "data.ndjson").exists()


def test_cli_transparent_compression(tmp_path):
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": ["p", "q", "r", "s"]})
    csv_path = tmp_path / "data.csv"
    df.to_csv(csv_path, index=False)

    # Convert csv to csv.gz
    exit_code = cli.main([str(csv_path), "-o", "csv.gz"])
    assert exit_code == 0
    gz_path = tmp_path / "data.csv.gz"
    assert gz_path.exists()

    # Convert csv.gz to parquet
    exit_code2 = cli.main([str(gz_path), "-o", "parquet"])
    assert exit_code2 == 0
    pq_path = tmp_path / "data.parquet"
    assert pq_path.exists()
    pd.testing.assert_frame_equal(pd.read_parquet(pq_path), df)

    # Convert parquet to jsonl.gz
    exit_code3 = cli.main([str(pq_path), "-o", "jsonl.gz"])
    assert exit_code3 == 0
    j_gz = tmp_path / "data.jsonl.gz"
    assert j_gz.exists()
    pd.testing.assert_frame_equal(pd.read_json(j_gz, lines=True), df)


def test_cli_pager(tmp_path, monkeypatch):
    df = pd.DataFrame({"col": range(5)})
    p = tmp_path / "data.csv"
    df.to_csv(p, index=False)

    paged = []
    import pydoc
    monkeypatch.setattr(pydoc, "pager", lambda text: paged.append(text))

    exit_code = cli.main([str(p), "-head", "3", "-pager"])
    assert exit_code == 0
    assert len(paged) == 1
    assert "col" in paged[0]






