import numpy as np
import pandas as pd
import pytest

import pytae as pt
from pytae import cli


@pytest.fixture
def sales_df():
    return pd.DataFrame({
        "Region": ["East", "East", "West", "West", "East"],
        "Store": ["S1", "S2", "S1", "S2", "S1"],
        "Year": [2023, 2023, 2023, 2024, 2024],
        "Quarter": ["Q1", "Q2", "Q1", "Q1", "Q2"],
        "Sales": [100.0, 200.0, 300.0, 400.0, 150.0],
        "Profit": [10.0, 25.0, 35.0, 50.0, 20.0],
    })


def test_pivot_both_r_and_c(sales_df):
    res = sales_df.pt.pivot(r="Region", c="Year", v="Sales", a="sum")
    assert isinstance(res, pd.DataFrame)
    assert list(res.columns) == ["Region", "2023", "2024"]
    assert res.columns.name is None
    assert list(res.index) == [0, 1]

    east_row = res[res["Region"] == "East"].iloc[0]
    assert east_row["2023"] == 300.0  # 100 + 200
    assert east_row["2024"] == 150.0

    west_row = res[res["Region"] == "West"].iloc[0]
    assert west_row["2023"] == 300.0
    assert west_row["2024"] == 400.0


def test_pivot_r_only(sales_df):
    res = pt.pivot(sales_df, r="Region", v="Sales", a="sum")
    assert list(res.columns) == ["Region", "Sales"]
    assert res.columns.name is None
    assert len(res) == 2
    assert res.loc[res["Region"] == "East", "Sales"].iloc[0] == 450.0
    assert res.loc[res["Region"] == "West", "Sales"].iloc[0] == 700.0


def test_pivot_c_only(sales_df):
    res = sales_df.pt.pivot(c="Year", v="Sales", a="sum")
    assert list(res.columns) == ["2023", "2024"]
    assert len(res) == 1
    assert res["2023"].iloc[0] == 600.0
    assert res["2024"].iloc[0] == 550.0


def test_pivot_neither_r_nor_c(sales_df):
    res = sales_df.pt.pivot(v="Sales", a="sum")
    assert list(res.columns) == ["Sales"]
    assert len(res) == 1
    assert res["Sales"].iloc[0] == 1150.0


def test_pivot_multiple_rows(sales_df):
    res = sales_df.pt.pivot(r=["Region", "Store"], c="Year", v="Sales", a="sum")
    assert list(res.columns[:2]) == ["Region", "Store"]
    assert "2023" in res.columns
    assert "2024" in res.columns
    assert len(res) == 4  # East-S1, East-S2, West-S1, West-S2 -> 4 combinations
    assert res.columns.name is None


def test_pivot_multiple_values(sales_df):
    res = sales_df.pt.pivot(r="Region", c="Year", v=["Sales", "Profit"], a="sum")
    assert res.columns[0] == "Region"
    assert "Sales_2023" in res.columns
    assert "Profit_2023" in res.columns
    assert "Sales_2024" in res.columns
    assert "Profit_2024" in res.columns
    assert not isinstance(res.columns, pd.MultiIndex)


def test_pivot_multiple_columns(sales_df):
    res = sales_df.pt.pivot(r="Region", c=["Year", "Quarter"], v="Sales", a="sum")
    assert res.columns[0] == "Region"
    # Column names are flattened with underscore
    assert any("2023_Q1" in col for col in res.columns)
    assert not isinstance(res.columns, pd.MultiIndex)


def test_pivot_agg_n_alias(sales_df):
    res = sales_df.pt.pivot(r="Region", c="Year", v="Sales", a="n")
    assert list(res.columns) == ["Region", "2023", "2024"]
    assert res["2023"].dtype == "int64"
    assert res["2024"].dtype == "int64"
    east_row = res[res["Region"] == "East"].iloc[0]
    assert east_row["2023"] == 2  # two rows for East in 2023
    assert east_row["2024"] == 1


def test_pivot_agg_n_fill_zero_by_default():
    # If a combination has 0 occurrences, it should be 0 and int64
    df = pd.DataFrame({
        "Island": ["Biscoe", "Biscoe", "Dream"],
        "Species": ["Adelie", "Gentoo", "Chinstrap"],
        "Sex": ["M", "F", "M"],
    })
    res = df.pt.pivot(r="Island", c="Species", v="Sex", a="n")
    assert list(res.columns) == ["Island", "Adelie", "Chinstrap", "Gentoo"]
    assert res["Adelie"].dtype == "int64"
    assert res["Chinstrap"].dtype == "int64"
    assert res["Gentoo"].dtype == "int64"

    biscoe = res[res["Island"] == "Biscoe"].iloc[0]
    assert biscoe["Adelie"] == 1
    assert biscoe["Chinstrap"] == 0
    assert biscoe["Gentoo"] == 1

    dream = res[res["Island"] == "Dream"].iloc[0]
    assert dream["Adelie"] == 0
    assert dream["Chinstrap"] == 1
    assert dream["Gentoo"] == 0


def test_pivot_agg_n_r_only(sales_df):
    res = sales_df.pt.pivot(r="Region", v="Sales", a="n")
    assert list(res.columns) == ["Region", "Sales"]
    assert res["Sales"].dtype == "int64"
    assert res.loc[res["Region"] == "East", "Sales"].iloc[0] == 3
    assert res.loc[res["Region"] == "West", "Sales"].iloc[0] == 2


def test_pivot_agg_n_c_only(sales_df):
    res = sales_df.pt.pivot(c="Year", v="Sales", a="n")
    assert list(res.columns) == ["2023", "2024"]
    assert res["2023"].dtype == "int64"
    assert res["2024"].dtype == "int64"
    assert res["2023"].iloc[0] == 3
    assert res["2024"].iloc[0] == 2


def test_pivot_agg_n_neither_r_nor_c(sales_df):
    res = sales_df.pt.pivot(v="Sales", a="n")
    assert list(res.columns) == ["Sales"]
    assert res["Sales"].dtype == "int64"
    assert res["Sales"].iloc[0] == 5


def test_pivot_agg_n_explicit_nan_fill():
    df = pd.DataFrame({
        "Island": ["Biscoe", "Dream"],
        "Species": ["Adelie", "Chinstrap"],
        "Sex": ["M", "F"],
    })
    res = df.pt.pivot(r="Island", c="Species", v="Sex", a="n", f_v=np.nan)
    # When explicit NaN fill is requested, missing combinations are <NA> of Int64 dtype
    assert res["Adelie"].dtype == "Int64"
    assert res["Chinstrap"].dtype == "Int64"
    assert pd.isna(res.loc[res["Island"] == "Dream", "Adelie"].iloc[0])
    assert res.loc[res["Island"] == "Dream", "Chinstrap"].iloc[0] == 1


def test_pivot_f_v_explicit(sales_df):
    res = sales_df.pt.pivot(r=["Region", "Store"], c="Year", v="Sales", a="sum", f_v=0.0)
    # Check that missing combinations have 0.0 instead of NaN
    assert not res.isna().any().any()


def test_pivot_dropna_false_default():
    df_na = pd.DataFrame({
        "Region": ["East", np.nan, "West"],
        "Year": [2023, 2023, np.nan],
        "Sales": [10.0, 20.0, 30.0],
    })
    res = df_na.pt.pivot(r="Region", c="Year", v="Sales", a="sum")
    # Region has NaN, so there should be a row with NaN in Region
    assert res["Region"].isna().any()
    # Year has NaN, so there should be a column representing nan
    col_names = [str(c) for c in res.columns]
    assert any("nan" in c.lower() for c in col_names)


def test_pivot_aliases_rejected(sales_df):
    for bad_kw in ({"rows": "Region"}, {"cols": "Year"}, {"values": "Sales"}, {"aggfunc": "mean"}, {"index": "Region"}, {"columns": "Year"}, {"fill": 0.0}, {"fill_value": 0.0}):
        with pytest.raises(TypeError, match="pivot\\(\\) got unexpected keyword argument\\(s\\)"):
            sales_df.pt.pivot(r="Region", c="Year", v="Sales", **bad_kw)


def test_pivot_optional_v(sales_df):
    # 2D cross-tabulation count matrix with v omitted
    res = sales_df.pt.pivot(r="Region", c="Year")
    assert list(res.columns) == ["Region", "2023", "2024"]
    assert res.loc[res["Region"] == "East", "2023"].iloc[0] == 2
    assert res.loc[res["Region"] == "East", "2024"].iloc[0] == 1
    assert res.loc[res["Region"] == "West", "2023"].iloc[0] == 1
    assert res.loc[res["Region"] == "West", "2024"].iloc[0] == 1

    # 1D row frequency table with v omitted
    res_1d = sales_df.pt.pivot(r="Region,Store")
    assert list(res_1d.columns) == ["Region", "Store", "n"]
    assert len(res_1d) == 4
    assert res_1d["n"].sum() == 5

    # 1D column frequency table with v omitted
    res_col = sales_df.pt.pivot(c="Year")
    assert list(res_col.columns) == ["2023", "2024"]
    assert res_col["2023"].iloc[0] == 3
    assert res_col["2024"].iloc[0] == 2

    # 0D total count with v omitted
    res_0d = sales_df.pt.pivot()
    assert list(res_0d.columns) == ["n"]
    assert res_0d["n"].iloc[0] == 5

    # v omitted but incompatible agg function requested
    with pytest.raises(ValueError, match="pivot\\(\\): value column 'v' is required when aggregation function is 'mean'. Omit 'v' for row counts."):
        sales_df.pt.pivot(r="Region", c="Year", a="mean")

    with pytest.raises(ValueError, match="pivot\\(\\): value column 'v' is required when aggregation function is 'median'. Omit 'v' for row counts."):
        sales_df.pt.pivot(r="Region", c="Year", a="median")


def test_pivot_f_v(sales_df):
    res = sales_df.pt.pivot(r="Region", c="Quarter", v="Sales", a="sum", f_v=0)
    assert not res.isna().any().any()
    assert (res["Q1"] >= 0).all()


def test_pivot_unknown_column_error(sales_df):
    with pytest.raises(KeyError, match="not found in DataFrame"):
        sales_df.pt.pivot(r="NonExistent", c="Year", v="Sales")


def test_wide_r_spec(sales_df):
    tall = sales_df.pt.long(cols=["Sales", "Profit"], id_vars=["Region", "Store", "Year"])
    back = tall.pt.wide(r=["Region", "Store", "Year"], c="variable", v="value")
    assert "Sales" in back.columns
    assert "Profit" in back.columns


# ---------------- CLI Tests ----------------


def test_cli_pivot_basic(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "East", "West"],
        "Year": [2023, 2024, 2023],
        "Sales": [100, 150, 200],
    })
    path = str(tmp_path / "data.csv")
    df.to_csv(path, index=False)

    exit_code = cli.main([path, "-pivot", "r=Region,c=Year,v=Sales,a=sum"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "East" in captured.out
    assert "West" in captured.out
    assert "2023" in captured.out
    assert "2024" in captured.out


def test_cli_pivot_r_only(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "East", "West"],
        "Sales": [100, 150, 200],
    })
    path = str(tmp_path / "data.csv")
    df.to_csv(path, index=False)

    exit_code = cli.main([path, "-pivot", "r=Region,v=Sales,a=sum"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "East" in captured.out
    assert "250" in captured.out
    assert "200" in captured.out


def test_cli_pivot_c_only(tmp_path, capsys):
    df = pd.DataFrame({
        "Year": [2023, 2024, 2023],
        "Sales": [100, 150, 200],
    })
    path = str(tmp_path / "data.csv")
    df.to_csv(path, index=False)

    exit_code = cli.main([path, "-pivot", "c=Year,v=Sales,a=sum"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "300" in captured.out
    assert "150" in captured.out


def test_cli_pivot_unknown_column(tmp_path):
    df = pd.DataFrame({"Region": ["East"], "Sales": [100]})
    path = str(tmp_path / "data.csv")
    df.to_csv(path, index=False)

    with pytest.raises(SystemExit) as exc:
        cli.main([path, "-pivot", "r=NoSuchCol,v=Sales"])
    assert exc.value.code == 2


def test_cli_pivot_export_parquet(tmp_path):
    df = pd.DataFrame({
        "Region": ["East", "West"],
        "Year": [2023, 2024],
        "Sales": [100, 200],
    })
    in_path = str(tmp_path / "in.csv")
    out_path = str(tmp_path / "out.parquet")
    df.to_csv(in_path, index=False)

    exit_code = cli.main([in_path, "-pivot", "r=Region,c=Year,v=Sales", "-o", out_path])
    assert exit_code == 0

    pivoted_df = pd.read_parquet(out_path)
    assert "Region" in pivoted_df.columns
    assert "2023" in pivoted_df.columns
    assert "2024" in pivoted_df.columns


def test_pivot_no_cartesian_product_unobserved_combinations():
    doc = pd.DataFrame({
        "Region": ["East", "East", "East", "East", "West", "West"],
        "Store": ["Store A", "Store A", "Store B", "Store B", "Store C", "Store C"],
        "Year": [2023, 2024, 2023, 2024, 2023, 2024],
        "Sales": [700.0, 850.0, 800.0, 950.0, 900.0, 1100.0],
    })
    res_sum = doc.pt.pivot(r=["Region", "Store"], c="Year", v="Sales", a="sum")
    # Only observed Region-Store pairs should exist (3 rows), not 6
    assert len(res_sum) == 3
    assert set(res_sum["Store"]) == {"Store A", "Store B", "Store C"}

    res_n = doc.pt.pivot(r=["Region", "Store"], c="Year", v="Sales", a="n")
    assert len(res_n) == 3


def test_pivot_multi_c_cols_a_n_preserves_outer_keys():
    df = pd.DataFrame({
        "Region": ["East", "East", "East", "East"],
        "Year": [2023, 2023, 2023, 2024],
        "Quarter": ["Q1", "Q1", "Q2", "Q1"],
        "Sales": [1, 1, 1, 1],
    })
    out = df.pt.pivot(r="Region", c=["Year", "Quarter"], v="Sales", a="n")
    assert "2023_Q1" in out.columns
    assert "2023_Q2" in out.columns
    assert "2024_Q1" in out.columns
    assert out["2023_Q1"].iloc[0] == 2
    assert out["2023_Q2"].iloc[0] == 1
    assert out["2024_Q1"].iloc[0] == 1


def test_pivot_header_deduplication():
    df1 = pd.DataFrame({"r": ["a", "a"], "c": [1, "1"], "v": [10.0, 20.0]})
    with pytest.raises(ValueError, match="contain duplicate names"):
        df1.pt.pivot(r="r", c="c", v="v", a="sum")

    df2 = pd.DataFrame({"r": ["a", "a", "a"], "c": [np.nan, "nan", "ok"], "v": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="contain duplicate names"):
        df2.pt.pivot(r="r", c="c", v="v", a="sum")


def test_pivot_c_only_multi_values_keeps_metric_index():
    df = pd.DataFrame({
        "Year": [2023, 2024, 2023],
        "Sales": [100.0, 150.0, 200.0],
        "Profit": [10.0, 15.0, 20.0],
    })
    out = df.pt.pivot(c="Year", v=["Sales", "Profit"], a="sum")
    assert "metric" in out.columns
    assert set(out["metric"]) == {"Sales", "Profit"}


def test_pivot_row_only_a_n_count_key_collision():
    df1 = pd.DataFrame({"island": ["A", "A", "B"]})
    out1 = df1.pt.pivot(r="island", a="n")
    assert "island" in out1.columns
    assert "n" in out1.columns
    assert list(out1["n"]) == [2, 1]

    # If v is specified and overlaps with r, raise ValueError
    with pytest.raises(ValueError, match="cannot also be in grouping dimensions"):
        df1.pt.pivot(r="island", v="island", a="n")

    # If row grouping column is named "n", omitting v will default to "n" which collides
    df_colliding = pd.DataFrame({"n": ["a", "a", "b"], "val": [1, 2, 3]})
    with pytest.raises(ValueError, match="collides with row grouping column"):
        df_colliding.pt.pivot(r="n", a="n")

    # Providing a non-colliding column for v works
    out_custom = df_colliding.pt.pivot(r="n", v="val", a="n")
    assert list(out_custom.columns) == ["n", "val"]


def test_pivot_v_in_dimensions_validation():
    df = pd.DataFrame({"Region": ["East", "West"], "Year": [2023, 2024], "Sales": [10, 20]})
    with pytest.raises(ValueError, match="cannot also be in grouping dimensions"):
        df.pt.pivot(r="Region", c="Year", v="Region", a="sum")


def test_cli_pivot_fill_numeric(tmp_path, capsys):
    df = pd.DataFrame({
        "Region": ["East", "West"],
        "Store": ["A", "B"],
        "Sales": [4.0, 2.0],
    })
    path = str(tmp_path / "sales.csv")
    df.to_csv(path, index=False)
    exit_code = cli.main([path, "-pivot", "r=Region,c=Store,v=Sales,a=sum,f_v=0", "-round", "1"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "0" in out


def test_cli_pivot_unknown_agg_fails_cleanly(tmp_path):
    df = pd.DataFrame({"Region": ["East"], "Sales": [100]})
    path = str(tmp_path / "sales.csv")
    df.to_csv(path, index=False)
    with pytest.raises(SystemExit) as exc:
        cli.main([path, "-pivot", "r=Region,v=Sales,a=nope"])
    assert exc.value.code == 2


def test_wide_cols_and_values_aliases_rejected(tmp_path):
    df = pd.DataFrame({
        "id": ["a", "b"],
        "country": ["sg", "cn"],
        "balance": [10, 20],
    })
    with pytest.raises(TypeError, match="wide\\(\\) got unexpected keyword argument\\(s\\)"):
        df.pt.wide(cols="country", values="balance")

    path = str(tmp_path / "data.csv")
    df.to_csv(path, index=False)
    with pytest.raises(SystemExit) as exc:
        cli.main([path, "-wide", "cols=country,values=balance"])
    assert "unknown key 'cols'" in str(exc.value)


def test_cli_group_by_rejected(tmp_path, capsys):
    df = pd.DataFrame({"Region": ["East", "West"], "Sales": [10, 20]})
    path = str(tmp_path / "data.csv")
    df.to_csv(path, index=False)

    with pytest.raises(SystemExit) as exc:
        cli.main([path, "-group_by", "Region"])
    assert exc.value.code == 2
    assert "'-group_by' has been removed; use '-by' instead" in capsys.readouterr().err


def test_cli_value_counts_with_existing_count_column(tmp_path, capsys):
    df = pd.DataFrame({"count": ["a", "a", "b"]})
    path = str(tmp_path / "counts.csv")
    df.to_csv(path, index=False)
    exit_code = cli.main([path, "-value_counts"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "count" in out


def test_pivot_multi_key_empty_string_component():
    # Issue 3: multi-key pivot keeps empty string level rather than dropping it
    df = pd.DataFrame({
        "r": ["r1", "r1", "r1"],
        "y": [2023, 2023, 2024],
        "q": ["", "Q1", "Q2"],
        "v": [15, 10, 20],
    })
    piv = df.pt.pivot(r="r", c=["y", "q"], v="v", a="sum")
    assert "2023_" in piv.columns
    assert "2023_Q1" in piv.columns
    assert piv.loc[piv["r"] == "r1", "2023_"].iloc[0] == 15


def test_pivot_repeated_columns_in_dimensions_and_values():
    # Issue 3: Repeated column in pivot dimensions or values
    df = pd.DataFrame({
        "Region": ["East", "West"],
        "Year": [2023, 2024],
        "Sales": [100, 200],
    })
    with pytest.raises(ValueError, match="cannot appear multiple times in grouping dimensions"):
        df.pt.pivot(r="Region", c="Region", v="Sales")

    with pytest.raises(ValueError, match="cannot appear multiple times in grouping dimensions"):
        df.pt.pivot(r=["Region", "Region"], v="Sales")

    with pytest.raises(ValueError, match="cannot appear multiple times in grouping dimensions"):
        df.pt.pivot(c=["Year", "Year"], v="Sales")

    with pytest.raises(ValueError, match="cannot appear multiple times in 'v'"):
        df.pt.pivot(r="Region", v=["Sales", "Sales"])


def test_pivot_rich_metric_1d_aliases_and_counts(sales_df):
    # 1D: new_col = col:aggfunc and count = n
    res = sales_df.pt.pivot(r="Region", v="rev = Sales:sum, avg_sales = Sales:mean, orders = n")
    assert list(res.columns) == ["Region", "rev", "avg_sales", "orders"]
    assert res["orders"].dtype == "int64"
    east = res[res["Region"] == "East"].iloc[0]
    assert east["rev"] == 450.0
    assert east["avg_sales"] == 150.0
    assert east["orders"] == 3
    west = res[res["Region"] == "West"].iloc[0]
    assert west["rev"] == 700.0
    assert west["avg_sales"] == 350.0
    assert west["orders"] == 2


def test_pivot_rich_metric_2d_aliases_and_counts(sales_df):
    # 2D cross-tabulation with multi-metric prefixes
    res = sales_df.pt.pivot(r="Region", c="Year", v="rev = Sales:sum, orders = n")
    assert list(res.columns) == ["Region", "rev_2023", "rev_2024", "orders_2023", "orders_2024"]
    assert res["orders_2023"].dtype == "int64"
    assert res["orders_2024"].dtype == "int64"
    east = res[res["Region"] == "East"].iloc[0]
    assert east["rev_2023"] == 300.0
    assert east["rev_2024"] == 150.0
    assert east["orders_2023"] == 2
    assert east["orders_2024"] == 1


def test_pivot_multi_func_single_col(sales_df):
    # Multi-func syntax col:[f1, f2]
    res_1d = sales_df.pt.pivot(r="Region", v="Sales:[mean, sum]")
    assert list(res_1d.columns) == ["Region", "Sales_mean", "Sales_sum"]
    east = res_1d[res_1d["Region"] == "East"].iloc[0]
    assert east["Sales_mean"] == 150.0
    assert east["Sales_sum"] == 450.0

    # With alias: prefix_[f]
    res_alias = sales_df.pt.pivot(r="Region", v="rev = Sales:[mean, sum]")
    assert list(res_alias.columns) == ["Region", "rev_mean", "rev_sum"]


def test_pivot_bracketed_column_spaced():
    df = pd.DataFrame({
        "Store Region": ["East", "East", "West"],
        "gross sales": [100.0, 200.0, 300.0],
    })
    res = df.pt.pivot(r="[Store Region]", v="total = [gross sales]:sum, count = n")
    assert list(res.columns) == ["Store Region", "total", "count"]
    assert res.loc[res["Store Region"] == "East", "total"].iloc[0] == 300.0
    assert res.loc[res["Store Region"] == "East", "count"].iloc[0] == 2


def test_pivot_dict_spec(sales_df):
    # Dict with col->func and alias->expr
    res1 = sales_df.pt.pivot(r="Region", v={"Sales": "mean", "Profit": "sum"})
    assert list(res1.columns) == ["Region", "Sales", "Profit"]
    assert res1.loc[res1["Region"] == "East", "Sales"].iloc[0] == 150.0
    assert res1.loc[res1["Region"] == "East", "Profit"].iloc[0] == 55.0

    res2 = sales_df.pt.pivot(r="Region", v={"rev": "Sales:sum", "orders": "n"})
    assert list(res2.columns) == ["Region", "rev", "orders"]
    assert res2.loc[res2["Region"] == "East", "rev"].iloc[0] == 450.0
    assert res2.loc[res2["Region"] == "East", "orders"].iloc[0] == 3


def test_pivot_whole_table_rich_metrics(sales_df):
    res = sales_df.pt.pivot(v="total_sales = Sales:sum, avg_profit = Profit:mean, count = n")
    assert list(res.columns) == ["total_sales", "avg_profit", "count"]
    assert len(res) == 1
    assert res["total_sales"].iloc[0] == 1150.0
    assert res["avg_profit"].iloc[0] == 28.0
    assert res["count"].iloc[0] == 5


def test_pivot_single_metric_in_2d_no_prefix(sales_df):
    # Single value metric with explicit func should NOT prefix column headers in 2D
    res = sales_df.pt.pivot(r=["Region", "Store"], c="Year", v="Sales:sum")
    assert list(res.columns) == ["Region", "Store", "2023", "2024"]

    # In contrast, multiple values DO prefix column headers
    res_multi = sales_df.pt.pivot(r="Region", c="Year", v="Sales:sum, Profit:mean")
    assert list(res_multi.columns) == ["Region", "Sales_sum_2023", "Sales_sum_2024", "Profit_mean_2023", "Profit_mean_2024"]


