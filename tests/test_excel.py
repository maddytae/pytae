import os
import sys

import pandas as pd
import polars as pl
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae import cli
from pytae.readers import ExcelReader, get_reader
from pytae.repl import PytaeRepl


@pytest.fixture
def multi_sheet_excel(tmp_path):
    path = tmp_path / "sales_2024.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_jan = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "product": ["Widget", "Gadget", "Doohickey"],
                "sales": [100, 200, 300],
            }
        )
        df_jan.to_excel(writer, sheet_name="Jan", index=False)

        df_feb = pd.DataFrame(
            {
                "id": [4, 5, 6],
                "product": ["Widget", "Gadget", "Thingamajig"],
                "sales": [150, 250, 350],
            }
        )
        df_feb.to_excel(writer, sheet_name="Feb", index=False)

        # Sheet with header comments / offset
        df_notes = pd.DataFrame(
            [
                ["Notes for Q1", "", ""],
                ["Confidential", "", ""],
                ["id", "code", "amount"],
                [10, "A", 999],
                [20, "B", 888],
            ]
        )
        df_notes.to_excel(writer, sheet_name="CustomNotes", header=False, index=False)

    return path


def test_python_api_read_excel(multi_sheet_excel):
    # Test pytae.read with Excel files
    df = pt.read(multi_sheet_excel, sheet_name="Jan")
    assert isinstance(df, pt.DataFrame)
    assert df.shape == (3, 3)
    assert list(df.columns) == ["id", "product", "sales"]

    # Test kwargs forwarding: skiprows
    df_custom = pt.read(multi_sheet_excel, sheet_name="CustomNotes", skiprows=2, header=0)
    assert df_custom.shape == (2, 3)
    assert list(df_custom.columns) == ["id", "code", "amount"]


def test_excel_reader_methods(multi_sheet_excel):
    reader = get_reader(multi_sheet_excel, sheet_name="Jan")
    assert isinstance(reader, ExcelReader)
    assert reader.shape() == (3, 3)
    assert reader.columns() == ["id", "product", "sales"]
    assert len(reader.dtypes()) == 3
    assert len(reader.head(2)) == 2
    assert len(reader.tail(2)) == 2
    assert reader.sheet_names() == ["Jan", "Feb", "CustomNotes"]

    pldf = reader.to_polars()
    assert isinstance(pldf, pl.DataFrame)
    assert pldf.shape == (3, 3)

    lf = reader.to_polars_lazy()
    assert isinstance(lf, pl.LazyFrame)
    assert lf.collect().shape == (3, 3)


def test_cli_single_excel_head(multi_sheet_excel, capsys):
    exit_code = cli.main([str(multi_sheet_excel), "-head", "2"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Widget" in out
    assert "Gadget" in out


def test_cli_excel_sheet_colon_syntax_rejected(multi_sheet_excel, capsys):
    target = f"{multi_sheet_excel}:Feb"
    with pytest.raises(SystemExit) as exc_info:
        cli.main([target, "-head", "3"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "colon sheet syntax" in err
    assert "specify sheet via -opts" in err


def test_cli_excel_opts_flag(multi_sheet_excel, capsys):
    exit_code = cli.main([str(multi_sheet_excel), "-opts", "sheet=CustomNotes, skiprows=2, header=0", "-head"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "code" in out
    assert "amount" in out


def test_cli_opt_singular_rejected(multi_sheet_excel, capsys):
    target = str(multi_sheet_excel)
    with pytest.raises(SystemExit) as exc_info:
        cli.main([target, "-opt", "skiprows=1"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err or "not recognized" in err


def test_cli_excel_concat_multiple_sheets(multi_sheet_excel, capsys):
    jan_target = f"Jan={multi_sheet_excel}"
    feb_target = f"Feb={multi_sheet_excel}"
    exit_code = cli.main([jan_target, feb_target, "-concat", "-opts", "Jan:sheet=Jan, Feb:sheet=Feb", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(6, 3)"


def test_cli_excel_join_with_csv(multi_sheet_excel, tmp_path, capsys):
    csv_file = tmp_path / "customers.csv"
    pd.DataFrame({"product": ["Widget", "Gadget"], "category": ["CatA", "CatB"]}).to_csv(csv_file, index=False)

    exit_code = cli.main(
        [
            f"sales={multi_sheet_excel}",
            f"cust={csv_file}",
            "-join",
            "on=product",
            "-opts",
            "sales:sheet=Jan",
            "-shape",
        ]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 4)"


def test_cli_excel_targeted_opts(multi_sheet_excel, tmp_path, capsys):
    csv_file = tmp_path / "extra.csv"
    with open(csv_file, "w") as f:
        f.write("# comment line 1\n# comment line 2\nid,name\n1,one\n2,two\n")

    exit_code = cli.main(
        [
            f"jan={multi_sheet_excel}",
            f"extra={csv_file}",
            "-join",
            "on=id",
            "-opts",
            "jan:sheet=Jan, extra:skiprows=2",
            "-shape",
        ]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 4)"


def test_repl_load_excel_default_sheet(multi_sheet_excel):
    r = PytaeRepl()
    outputs = []
    r.execute_line(f"df = {multi_sheet_excel}", output_fn=outputs.append)
    assert r.current_df is not None
    assert r.current_df.shape == (3, 3)
    assert "Widget" in str(r.current_df)


def test_repl_excel_colon_syntax_rejected(multi_sheet_excel):
    r = PytaeRepl()
    outputs = []
    r.execute_line(f"df = {multi_sheet_excel}:Feb", output_fn=outputs.append)
    assert any("colon sheet syntax" in o for o in outputs)
    assert any("specify sheet via -opts" in o for o in outputs)


def test_repl_load_excel_with_opts(multi_sheet_excel):
    r = PytaeRepl()
    outputs = []
    r.execute_line(f'df = {multi_sheet_excel} -opts "sheet=CustomNotes, skiprows=2, header=0"', output_fn=outputs.append)
    assert r.current_df is not None
    assert r.current_df.shape == (2, 3)
    assert list(r.current_df.columns) == ["id", "code", "amount"]


def test_repl_load_excel_sheet_in_opts(multi_sheet_excel):
    r = PytaeRepl()
    outputs = []
    # sheet as part of -opts directly
    r.execute_line(f'df = {multi_sheet_excel} -opts "sheet=Feb"', output_fn=outputs.append)
    assert r.current_df is not None
    assert r.current_df.shape == (3, 3)
    assert "Thingamajig" in str(r.current_df)

    # sheet_name as part of -opts directly
    r.execute_line(f'df2 = {multi_sheet_excel} -opts "sheet_name=CustomNotes, skiprows=2, header=0"', output_fn=outputs.append)
    assert r.tables["df2"].shape == (2, 3)
    assert list(r.tables["df2"].columns) == ["id", "code", "amount"]


def test_repl_no_opts_persistency(multi_sheet_excel):
    r = PytaeRepl()
    outputs = []
    # 1. 'set opts' should NOT be a valid persistent setting
    r.execute_line('set opts = "skiprows=2, header=0"', output_fn=outputs.append)
    assert "unknown setting 'opts'" in outputs[-1]

    # 2. Loading with -opts applies only to that assignment
    r.execute_line(f'df1 = {multi_sheet_excel} -opts "sheet=CustomNotes, skiprows=2, header=0"', output_fn=outputs.append)
    assert r.tables["df1"].shape == (2, 3)

    # 3. Subsequent assignment without -opts must NOT retain df1's opts
    r.execute_line(f'df2 = {multi_sheet_excel} -opts "sheet=Feb"', output_fn=outputs.append)
    assert r.tables["df2"].shape == (3, 3)  # normal 3 rows, not skipped rows!


def test_dataframe_to_excel_defaults_index_false(tmp_path):
    out_file = tmp_path / "single_export.xlsx"
    df = pt.DataFrame({"id": [1, 2, None], "score": [98.5, float("nan"), 75.0]})
    df.to(out_file)

    loaded = pt.read(out_file)
    assert list(loaded.columns) == ["id", "score"]
    assert "Unnamed: 0" not in loaded.columns
    assert loaded.shape == (3, 2)
    # Verify missing value normalization
    assert loaded["score"].to_list()[1] is None
    assert loaded["id"].to_list()[2] is None


def test_multi_sheet_dict_write_excel(tmp_path):
    multi_file = tmp_path / "multi_export.xlsx"
    df1 = pt.DataFrame({"dept": ["HR", "Eng"], "headcount": [10, 50]})
    df2 = pt.DataFrame({"sku": ["A1", "B2", "C3"], "price": [9.99, 19.99, 29.99]})

    with pytest.raises(ValueError, match=r"write\(\): 'pt\.write\(\)' is retired"):
        pt.write({"Departments": df1, "Products": df2}, multi_file)

    pt.to({"Departments": df1, "Products": df2}, multi_file)

    sheet_dept = pt.read(multi_file, sheet_name="Departments")
    sheet_prod = pt.read(multi_file, sheet_name="Products")

    assert sheet_dept.shape == (2, 2)
    assert list(sheet_dept.columns) == ["dept", "headcount"]
    assert "Unnamed: 0" not in sheet_dept.columns

    assert sheet_prod.shape == (3, 2)
    assert list(sheet_prod.columns) == ["sku", "price"]
    assert "Unnamed: 0" not in sheet_prod.columns

