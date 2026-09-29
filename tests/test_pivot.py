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
    east_row = res[res["Region"] == "East"].iloc[0]
    assert east_row["2023"] == 2  # two rows for East in 2023
    assert east_row["2024"] == 1


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
