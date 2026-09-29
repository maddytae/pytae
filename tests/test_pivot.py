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
    res = df.pt.pivot(r="Island", c="Species", v="Sex", a="n", fill_value=np.nan)
    # When explicit NaN fill is requested, missing combinations are <NA> of Int64 dtype
    assert res["Adelie"].dtype == "Int64"
    assert res["Chinstrap"].dtype == "Int64"
    assert pd.isna(res.loc[res["Island"] == "Dream", "Adelie"].iloc[0])
    assert res.loc[res["Island"] == "Dream", "Chinstrap"].iloc[0] == 1


def test_pivot_fill_value(sales_df):
    res = sales_df.pt.pivot(r=["Region", "Store"], c="Year", v="Sales", a="sum", fill_value=0.0)
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


def test_pivot_aliases(sales_df):
    res = sales_df.pt.pivot(rows="Region", cols="Year", values="Sales", aggfunc="mean", fill=0.0)
    assert list(res.columns) == ["Region", "2023", "2024"]


def test_pivot_missing_v_error(sales_df):
    with pytest.raises(ValueError, match="value column 'v' is required"):
        sales_df.pt.pivot(r="Region", c="Year")


def test_pivot_unknown_column_error(sales_df):
    with pytest.raises(KeyError, match="not found in DataFrame"):
        sales_df.pt.pivot(r="NonExistent", c="Year", v="Sales")


def test_wide_accepts_r_alias(sales_df):
    # wide accepts r as alias for index/by
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
    out1 = df1.pt.pivot(r="r", c="c", v="v", a="sum")
    assert list(out1.columns) == ["r", "1", "1_1"]

    df2 = pd.DataFrame({"r": ["a", "a", "a"], "c": [np.nan, "nan", "ok"], "v": [1.0, 2.0, 3.0]})
    out2 = df2.pt.pivot(r="r", c="c", v="v", a="sum")
    assert "nan" in out2.columns
    assert "nan_1" in out2.columns


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
    out1 = df1.pt.pivot(r="island", v="island", a="n")
    assert "island" in out1.columns
    assert "n" in out1.columns
    assert list(out1["n"]) == [2, 1]

    df2 = pd.DataFrame({"count": ["a", "a", "b"], "Sales": [1, 2, 3], "Profit": [4, 5, 6]})
    out2 = df2.pt.pivot(r="count", v=["Sales", "Profit"], a="n")
    assert "count" in out2.columns
    assert "n" in out2.columns


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
    exit_code = cli.main([path, "-pivot", "r=Region,c=Store,v=Sales,a=sum,fill=0", "-round", "1"])
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


def test_wide_cols_and_values_aliases(tmp_path):
    df = pd.DataFrame({
        "id": ["a", "b"],
        "country": ["sg", "cn"],
        "balance": [10, 20],
    })
    w1 = df.pt.wide(cols="country", values="balance")
    assert "cn" in w1.columns and "sg" in w1.columns

    path = str(tmp_path / "data.csv")
    df.to_csv(path, index=False)
    exit_code = cli.main([path, "-wide", "cols=country,values=balance"])
    assert exit_code == 0


def test_cli_value_counts_with_existing_count_column(tmp_path, capsys):
    df = pd.DataFrame({"count": ["a", "a", "b"]})
    path = str(tmp_path / "counts.csv")
    df.to_csv(path, index=False)
    exit_code = cli.main([path, "-value_counts"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "count" in out
