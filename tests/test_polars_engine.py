import pandas as pd
import polars as pl
import pytest

from pytae import cli
from pytae.polars_engine import (
    arrange_polars,
    clean_columns_polars,
    distinct_polars,
    dropna_polars,
    filter_polars,
    handle_missing_polars,
    long_polars,
    mutate_polars,
    pick_polars,
    pivot_polars,
    rename_polars,
    select_polars,
    value_counts_polars,
    wide_polars,
)


def test_filter_polars_operators():
    df = pl.DataFrame({
        "a": [1, 2, 3, 4, 5],
        "b": ["apple", "banana", "cherry", "date", "elderberry"],
        "c": [10.5, None, 20.5, None, 30.5],
    })

    # Numeric comparison
    res = filter_polars(df, [("a", (">", 2))])
    assert res["a"].to_list() == [3, 4, 5]

    # String string coercion with numeric column
    res_str_coerced = filter_polars(df, [("a", (">", "3"))])
    assert res_str_coerced["a"].to_list() == [4, 5]

    # In / Not In
    res_in = filter_polars(df, [("b", ("in", ["apple", "cherry"]))])
    assert res_in["b"].to_list() == ["apple", "cherry"]

    res_not_in = filter_polars(df, [("b", ("not in", ["apple", "cherry", "date"]))])
    assert res_not_in["b"].to_list() == ["banana", "elderberry"]

    # String operations
    res_sw = filter_polars(df, [("b", ("startswith", "ba"))])
    assert res_sw["b"].to_list() == ["banana"]

    res_ew = filter_polars(df, [("b", ("endswith", "ry"))])
    assert res_ew["b"].to_list() == ["cherry", "elderberry"]

    res_cont = filter_polars(df, [("b", ("contains", "an"))])
    assert res_cont["b"].to_list() == ["banana"]

    # Nulls
    res_null = filter_polars(df, [("c", ("isna",))])
    assert len(res_null) == 2

    res_notnull = filter_polars(df, [("c", ("notna",))])
    assert len(res_notnull) == 3

    # Intervals
    res_int = filter_polars(df, [("a", "[2, 4]")])
    assert res_int["a"].to_list() == [2, 3, 4]


def test_select_polars():
    df = pl.DataFrame({
        "x": [1, 2],
        "y": [3, 4],
        "z": [5, 6],
    })
    res = select_polars(df, ["z", "x"], {})
    assert res.columns == ["z", "x"]

    res_slice = select_polars(df, ["x:z"], {})
    assert res_slice.columns == ["x", "y", "z"]

    res_neg = select_polars(df, ["-y"], {})
    assert res_neg.columns == ["x", "z"]


def test_arrange_polars():
    df = pl.DataFrame({
        "grp": ["B", "A", "B", "A"],
        "val": [10, 20, 5, 15],
    })
    res = arrange_polars(df, "grp, val desc")
    assert res["grp"].to_list() == ["A", "A", "B", "B"]
    assert res["val"].to_list() == [20, 15, 10, 5]


def test_distinct_polars():
    df = pl.DataFrame({
        "k": [1, 1, 2, 2, 3],
        "v": ["a", "b", "c", "d", "e"],
    })
    res_first = distinct_polars(df, cols=["k"], keep="first")
    assert res_first["v"].to_list() == ["a", "c", "e"]

    res_last = distinct_polars(df, cols=["k"], keep="last")
    assert res_last["v"].to_list() == ["b", "d", "e"]

    res_none = distinct_polars(df, cols=["k"], keep="none")
    assert res_none["k"].to_list() == [3]


def test_dropna_and_rename_polars():
    df = pl.DataFrame({
        "a": [1, None, 3],
        "b": ["x", "y", None],
    })
    res_drop = dropna_polars(df, cols=["a"])
    assert res_drop["a"].to_list() == [1, 3]

    res_ren = rename_polars(df, {"a": "col_a", "b": "col_b"})
    assert res_ren.columns == ["col_a", "col_b"]


def test_pivot_polars():
    df = pl.DataFrame({
        "region": ["East", "East", "West", "West"],
        "year": [2020, 2021, 2020, 2021],
        "sales": [100, 200, 300, 400],
        "profit": [10, 20, 30, 40],
    })
    # Single value, sorted columns
    res = pivot_polars(df, r="region", c="year", v="sales", a="sum")
    assert res.columns == ["region", "2020", "2021"]
    assert res["region"].to_list() == ["East", "West"]
    assert res["2020"].to_list() == [100, 300]
    assert res["2021"].to_list() == [200, 400]

    # Multiple values
    res_multi = pivot_polars(df, r="region", c="year", v=["sales", "profit"], a="sum")
    assert "sales_2020" in res_multi.columns
    assert "profit_2020" in res_multi.columns

    # Count aggregation a="n" defaults missing to 0
    df_counts = pl.DataFrame({
        "item": ["apple", "apple", "banana"],
        "store": ["S1", "S2", "S1"],
    })
    res_cnt = pivot_polars(df_counts, r="item", c="store", a="n")
    assert res_cnt.columns == ["item", "S1", "S2"]
    assert res_cnt["S1"].to_list() == [1, 1]
    assert res_cnt["S2"].to_list() == [1, 0]


def test_mutate_polars():
    df = pl.DataFrame({
        "val": [100.0, 200.0, 300.0],
        "count with space": [1, 2, 3],
        "grp": ["G1", "G1", "G2"],
    })
    spec = {
        "x": "val / 1e6",
        "mult": "val * 2.0",
        "spaced": "[count with space] + 10",
        "cond": "if_else(val > 150, 1, 0)",
        "grp_sum": "sum(val)",
    }
    res = mutate_polars(df, spec, by=["grp"])
    assert res["x"].to_list() == pytest.approx([1e-4, 2e-4, 3e-4])
    assert res["mult"].to_list() == [200.0, 400.0, 600.0]
    assert res["spaced"].to_list() == [11, 12, 13]
    assert res["cond"].to_list() == [0, 1, 1]
    assert res["grp_sum"].to_list() == [300.0, 300.0, 300.0]


def test_cli_end_to_end_polars_pipeline(tmp_path, capsys):
    p = tmp_path / "test.parquet"
    df = pd.DataFrame({
        "category": ["A", "B", "A", "B", "A"],
        "region": ["East", "West", "East", "West", "North"],
        "val": [10.0, 20.0, 30.0, 40.0, 50.0],
        "flag": ["yes", "no", "yes", "yes", "no"],
    })
    df.to_parquet(p, index=False)

    # CLI chain: filter -> select -> mutate with 1e6 -> pivot
    code = cli.main([
        str(p),
        "-filter", "flag == 'yes'",
        "-select", "category,region,val",
        "-mutate", "v = val / 1e6",
        "-pivot", "r=category,c=region,v=v,a=sum",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "East" in out
    assert "West" in out


def test_pick_polars():
    df = pl.DataFrame({
        "grp": ["A", "A", "A", "B", "B", "B"],
        "val": [10, 30, 20, 5, 40, 15],
    })
    # Ungrouped max
    res_max = pick_polars(df, "val", n=2, order="max")
    assert res_max["val"].to_list() == [40, 30]

    # Ungrouped min
    res_min = pick_polars(df, "val", n=2, order="min")
    assert res_min["val"].to_list() == [5, 10]

    # Grouped max
    res_grp_max = pick_polars(df, "val", n=1, order="max", by=["grp"])
    assert res_grp_max["grp"].to_list() == ["A", "B"]
    assert res_grp_max["val"].to_list() == [30, 40]

    # Prop
    res_prop = pick_polars(df, "val", prop=0.5, order="max")
    assert len(res_prop) == 3


def test_value_counts_polars():
    df = pl.DataFrame({
        "item": ["apple", "banana", "apple", "cherry", None, "banana", "apple"],
        "count": [1, 2, 1, 3, 4, 2, 1],
    })
    # Single column
    res = value_counts_polars(df.select("item"), dropna=True)
    assert res.columns == ["item", "count"]
    assert res["item"].to_list() == ["apple", "banana", "cherry"]
    assert res["count"].to_list() == [3, 2, 1]

    # With existing 'count' column, count header becomes 'n'
    res_with_count = value_counts_polars(df, dropna=True)
    assert "n" in res_with_count.columns

    # Both count and n columns collision
    df_collision = pl.DataFrame({"count": [1], "n": [2]})
    with pytest.raises(ValueError, match="columns contain both 'count' and 'n'"):
        value_counts_polars(df_collision)


def test_long_and_wide_polars():
    df = pl.DataFrame({
        "id": [1, 2],
        "q1": [10, 20],
        "q2": [30, 40],
    })
    # Long (unpivot)
    long_res = long_polars(df, cols=["q1", "q2"], id_vars=["id"])
    assert long_res.columns == ["id", "variable", "value"]
    assert len(long_res) == 4

    # Wide (1-to-1 pivot)
    wide_res = wide_polars(long_res, r="id", c="variable", v="value")
    assert wide_res.columns == ["id", "q1", "q2"]
    assert wide_res["q1"].to_list() == [10, 20]
    assert wide_res["q2"].to_list() == [30, 40]

    with pytest.raises(TypeError, match="wide\\(\\) parameter 'index' has been removed; use 'r' instead"):
        wide_polars(long_res, c="variable", v="value", index="id")


def test_handle_missing_polars():
    df = pl.DataFrame({
        "s": [" hello ", None, "world "],
        "n": [10.0, None, 30.0],
        "b": [True, None, False],
    })
    res = handle_missing_polars(df, fillna=".")
    assert res["s"].to_list() == ["hello", ".", "world"]
    assert res["n"].to_list() == [10.0, 0.0, 30.0]
    # Boolean untouched
    assert res["b"].to_list() == [True, None, False]


def test_clean_columns_polars():
    df = pl.DataFrame({
        "  col a  ": [1],
        "col   b": [2],
    })
    res = clean_columns_polars(df, strip=True, squeeze=True, fill="_", case="lower")
    assert res.columns == ["col_a", "col_b"]


def test_mutate_polars_map_and_disallow_dot_map():
    df = pl.DataFrame({
        "island name": ["Biscoe", "Dream", "Torgersen"],
        "species": ["Adelie", "Gentoo", "Chinstrap"],
    })
    res = mutate_polars(df, {"island code": "map([island name], {'Biscoe': 'BIS', 'Dream': 'DRM'}, 'TOR')"})
    assert res["island code"].to_list() == ["BIS", "DRM", "TOR"]

    with pytest.raises(ValueError, match="'.map\\(\\)' method syntax is not supported"):
        mutate_polars(df, {"code": "species.map({'Adelie': 'AD'})"})


def test_format_table_tty_and_non_tty():
    from pytae.cli_run import _format_table

    pldf = pl.DataFrame({"name": ["alpha", "beta"], "val": [10, 20]})
    pddf = pd.DataFrame({"name": ["alpha", "beta"], "val": [10, 20]})

    # TTY mode: Polars boxed table
    tty_pl = _format_table(pldf, is_tty=True)
    assert "┌" in tty_pl
    assert "shape: (2, 2)" in tty_pl
    assert "name" in tty_pl and "val" in tty_pl

    tty_pd = _format_table(pddf, is_tty=True)
    assert "┌" in tty_pd
    assert "shape: (2, 2)" in tty_pd

    # Non-TTY mode: Bare table
    bare_pl = _format_table(pldf, is_tty=False)
    assert "┌" not in bare_pl
    assert "shape:" not in bare_pl
    assert "alpha" in bare_pl and "beta" in bare_pl

    bare_pd = _format_table(pddf, is_tty=False)
    assert "┌" not in bare_pd
    assert "shape:" not in bare_pd


def test_format_table_large_and_small_rows_tty():
    from pytae.cli_run import _format_table

    # Small table (25 rows): displays all rows in TTY
    df25 = pl.DataFrame({"a": list(range(25))})
    out25 = _format_table(df25, is_tty=True)
    assert "shape: (25, 1)" in out25
    assert "24" in out25  # all 25 rows shown, not truncated at 10

    # Huge table: Polars truncates cleanly
    df_huge = pl.DataFrame({"a": list(range(5000))})
    out_huge = _format_table(df_huge, is_tty=True)
    assert "shape: (5_000, 1)" in out_huge
    assert "…" in out_huge


def test_cli_pretty_deprecated_silent(tmp_path, capsys):
    p = tmp_path / "data.parquet"
    pl.DataFrame({"x": [1, 2]}).write_parquet(p)

    code = cli.main([str(p), "-pretty"])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.err == ""  # Zero deprecation warnings
    assert "1" in captured.out and "2" in captured.out


def test_cli_tty_boxed_output(tmp_path, monkeypatch, capsys):
    import sys

    p = tmp_path / "data.parquet"
    pl.DataFrame({"col1": [100, 200]}).write_parquet(p)

    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    code = cli.main([str(p)])
    assert code == 0
    out = capsys.readouterr().out
    assert "┌" in out
    assert "shape: (2, 1)" in out


def test_pivot_polars_rich_metrics_1d():
    df = pl.DataFrame({
        "region": ["East", "East", "West", "West", "East"],
        "sales": [100.0, 200.0, 300.0, 400.0, 150.0],
        "profit": [10.0, 25.0, 35.0, 50.0, 20.0],
    })
    res = pivot_polars(df, r="region", v="rev = sales:sum, avg_sales = sales:mean, orders = n")
    assert res.columns == ["region", "rev", "avg_sales", "orders"]
    assert res["region"].to_list() == ["East", "West"]
    assert res["rev"].to_list() == [450.0, 700.0]
    assert res["avg_sales"].to_list() == [150.0, 350.0]
    assert res["orders"].to_list() == [3, 2]


def test_pivot_polars_rich_metrics_2d():
    df = pl.DataFrame({
        "region": ["East", "East", "West", "West", "East"],
        "year": [2020, 2020, 2020, 2021, 2021],
        "sales": [100.0, 200.0, 300.0, 400.0, 150.0],
    })
    res = pivot_polars(df, r="region", c="year", v="rev = sales:sum, orders = n")
    assert res.columns == ["region", "rev_2020", "rev_2021", "orders_2020", "orders_2021"]
    assert res["region"].to_list() == ["East", "West"]
    assert res["rev_2020"].to_list() == [300.0, 300.0]
    assert res["rev_2021"].to_list() == [150.0, 400.0]
    assert res["orders_2020"].to_list() == [2, 1]
    assert res["orders_2021"].to_list() == [1, 1]


def test_pivot_polars_multi_func_single_col():
    df = pl.DataFrame({
        "region": ["East", "East", "West"],
        "sales": [100.0, 200.0, 300.0],
    })
    res = pivot_polars(df, r="region", v="sales:[mean, sum]")
    assert res.columns == ["region", "sales_mean", "sales_sum"]
    assert res["sales_mean"].to_list() == [150.0, 300.0]
    assert res["sales_sum"].to_list() == [300.0, 300.0]


def test_pivot_polars_whole_table_and_c_only():
    df = pl.DataFrame({
        "year": [2020, 2020, 2021],
        "sales": [100.0, 200.0, 300.0],
    })
    # Whole table
    res_whole = pivot_polars(df, v="total = sales:sum, count = n")
    assert res_whole.columns == ["total", "count"]
    assert res_whole["total"].to_list() == [600.0]
    assert res_whole["count"].to_list() == [3]

    # c only
    res_c = pivot_polars(df, c="year", v="sales", a="sum")
    assert res_c.columns == ["2020", "2021"]
    assert res_c["2020"].to_list() == [300.0]
    assert res_c["2021"].to_list() == [300.0]


def test_pivot_polars_optional_v_and_fill_aliases():
    df = pl.DataFrame({
        "region": ["East", "East", "West", "West", "East"],
        "year": [2020, 2021, 2020, 2020, 2020],
        "quarter": ["Q1", "Q1", "Q2", "Q2", "Q2"],
        "sales": [10.0, 20.0, 30.0, 40.0, 50.0],
    })

    # 2D contingency table with v omitted
    res_2d = pivot_polars(df, r="region", c="year")
    assert res_2d.columns == ["region", "2020", "2021"]
    assert res_2d["region"].to_list() == ["East", "West"]
    assert res_2d["2020"].to_list() == [2, 2]
    assert res_2d["2021"].to_list() == [1, 0]  # unobserved combination defaults to 0

    # 1D row frequency table with v omitted
    res_1d = pivot_polars(df, r="region,quarter")
    assert res_1d.columns == ["region", "quarter", "n"]
    assert res_1d["n"].to_list() == [2, 1, 2]

    # 1D col frequency table with v omitted
    res_c = pivot_polars(df, c="year")
    assert res_c.columns == ["2020", "2021"]
    assert res_c["2020"].to_list() == [4]
    assert res_c["2021"].to_list() == [1]

    # 0D scalar count
    res_0d = pivot_polars(df)
    assert res_0d.columns == ["n"]
    assert res_0d["n"].to_list() == [5]

    # Incompatible agg func without v
    with pytest.raises(ValueError, match="pivot\\(\\): value column 'v' is required when aggregation function is 'mean'. Omit 'v' for row counts."):
        pivot_polars(df, r="region", c="year", a="mean")

    # f_v parameter
    r = pivot_polars(df, r="region", c="quarter", v="sales", a="sum", f_v=0)
    assert "Q1" in r.columns
    assert "Q2" in r.columns

    # fill and fill_value are rejected
    with pytest.raises(TypeError, match="pivot_polars\\(\\) got unexpected keyword argument\\(s\\)"):
        pivot_polars(df, r="region", c="year", fill=0)
    with pytest.raises(TypeError, match="pivot_polars\\(\\) got unexpected keyword argument\\(s\\)"):
        pivot_polars(df, r="region", c="year", fill_value=0)


def test_pivot_polars_single_metric_in_2d_no_prefix():
    df = pl.DataFrame({
        "region": ["East", "East", "West"],
        "store": ["S1", "S2", "S1"],
        "year": [2020, 2021, 2020],
        "sales": [10.0, 20.0, 30.0],
    })
    res = pivot_polars(df, r="region,store", c="year", v="sales:sum")
    assert res.columns == ["region", "store", "2020", "2021"]


def test_write_dataframe_polars(tmp_path):
    from pytae.readers import write_dataframe

    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})

    # Parquet
    pq_path = tmp_path / "out.parquet"
    write_dataframe(df, pq_path)
    assert pq_path.exists()
    read_pq = pl.read_parquet(pq_path)
    assert read_pq["a"].to_list() == [1, 2, 3]

    # CSV
    csv_path = tmp_path / "out.csv"
    write_dataframe(df, csv_path)
    assert csv_path.exists()
    read_csv = pl.read_csv(csv_path)
    assert read_csv["a"].to_list() == [1, 2, 3]

    # NDJSON
    json_path = tmp_path / "out.jsonl"
    write_dataframe(df, json_path)
    assert json_path.exists()
    read_json = pl.read_ndjson(json_path)
    assert read_json["b"].to_list() == ["x", "y", "z"]




