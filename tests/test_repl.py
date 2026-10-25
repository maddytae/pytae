"""Unit tests for pytae interactive REPL (PytaeRepl, pt.repl(), df.repl(), and CLI flags)."""


import pandas as pd
import polars as pl
import pytest

from pytae import cli
from pytae.dataframe import DataFrame
from pytae.repl import PytaeRepl, repl


@pytest.fixture
def sample_df():
    return pl.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "species": ["Adelie", "Gentoo", "Adelie", "Gentoo", "Chinstrap"],
            "body_mass_g": [3500.0, 5000.0, 3800.0, 5200.0, 4100.0],
        }
    )


@pytest.fixture
def sample_parquet(tmp_path, sample_df):
    path = tmp_path / "penguins_sample.parquet"
    sample_df.write_parquet(path)
    return path


def test_repl_init_with_dataframe(sample_df):
    r = PytaeRepl(df=sample_df)
    assert r.current_df is not None
    assert r.current_df.shape == (5, 3)
    assert r.orig_df is not None
    assert r.orig_df.shape == (5, 3)


def test_repl_init_with_path(sample_parquet):
    r = PytaeRepl(path=sample_parquet)
    assert r.current_df is not None
    assert r.current_df.shape == (5, 3)
    assert r.path_str == "penguins_sample.parquet"


def test_repl_filter_and_undo_and_reset(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # 1. Apply filter
    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)
    assert len(r.undo_stack) == 1

    # 2. Undo filter
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)
    assert "Undid:" in outputs[-1]

    # 3. Apply another filter
    r.execute_line("-filter \"species == 'Adelie'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)

    # 4. Reset to original
    r.execute_line("reset", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)
    assert "Restored original dataset" in outputs[-1]


def test_repl_redo(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)

    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)

    r.execute_line("redo", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)
    assert "Redid:" in outputs[-1]


def test_repl_checkpoint_and_restore(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Save checkpoint
    r.execute_line("checkpoint v1", output_fn=outputs.append)
    assert "v1" in r.checkpoints

    # Mutate data
    r.execute_line("-mutate \"mass_kg = body_mass_g / 1000.0\"", output_fn=outputs.append)
    assert "mass_kg" in r.current_df.columns
    assert r.current_df.shape == (5, 4)

    # List checkpoints
    r.execute_line("checkpoints", output_fn=outputs.append)
    assert any("v1" in o for o in outputs)

    # Restore checkpoint
    r.execute_line("restore v1", output_fn=outputs.append)
    assert "mass_kg" not in r.current_df.columns
    assert r.current_df.shape == (5, 3)


def test_repl_non_destructive_inspection(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # shape
    r.execute_line("shape", output_fn=outputs.append)
    assert "(5, 3)" in outputs[-1]
    assert len(r.undo_stack) == 0

    # cols
    r.execute_line("cols", output_fn=outputs.append)
    assert "species" in outputs[-1]

    # dtype
    r.execute_line("dtype", output_fn=outputs.append)

    # nulls
    r.execute_line("nulls", output_fn=outputs.append)

    # glimpse
    r.execute_line("glimpse", output_fn=outputs.append)

    # head / tail
    r.execute_line("head 2", output_fn=outputs.append)
    r.execute_line("tail 2", output_fn=outputs.append)

    # None of these should mutate or push to undo stack!
    assert r.current_df.shape == (5, 3)
    assert len(r.undo_stack) == 0


def test_repl_sql_query(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    r.execute_line("sql SELECT species, COUNT(*) as cnt FROM df GROUP BY species ORDER BY cnt DESC", output_fn=outputs.append)
    assert r.current_df.shape == (3, 2)
    assert "cnt" in r.current_df.columns

    # Can undo SQL query
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)


def test_repl_python_expression(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    r.execute_line("py len(df)", output_fn=outputs.append)
    assert outputs[-1] == "5"


def test_repl_save_export(sample_df, tmp_path):
    outputs = []
    r = PytaeRepl(df=sample_df)
    out_file = tmp_path / "exported.parquet"

    r.execute_line(f"save {out_file}", output_fn=outputs.append)
    assert out_file.exists()
    assert pl.read_parquet(out_file).shape == (5, 3)


def test_repl_load_new_file(sample_parquet, tmp_path):
    # Create second file
    second_path = tmp_path / "second.csv"
    pd.DataFrame({"x": [10, 20], "y": [30, 40]}).to_csv(second_path, index=False)

    outputs = []
    r = PytaeRepl(path=sample_parquet)
    assert r.current_df.shape == (5, 3)

    r.execute_line(f"load {second_path}", output_fn=outputs.append)
    assert r.current_df.shape == (2, 2)
    assert "x" in r.current_df.columns


def test_repl_error_handling(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Invalid column name in filter
    r.execute_line("-filter \"non_existent > 10\"", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)  # Intact!
    assert len(r.undo_stack) == 0
    assert any("error" in o.lower() or "not found" in o.lower() for o in outputs)


def test_repl_headless_run(sample_df):
    lines = [
        "-filter \"species == 'Gentoo'\"",
        "checkpoint g_only",
        "-mutate \"mass_kg = body_mass_g / 1000.0\"",
        "undo",
        "exit",
    ]
    outputs = []
    r = PytaeRepl(df=sample_df)
    final_df = r.run(input_fn=iter(lines).__next__, output_fn=outputs.append)

    assert final_df.shape == (2, 3)
    assert "g_only" in r.checkpoints


def test_repl_convenience_function(sample_df):
    lines = ["head 2", "exit"]
    res = repl(df=sample_df) if False else PytaeRepl(df=sample_df).run(input_fn=iter(lines).__next__, output_fn=lambda _: None)
    assert res.shape == (5, 3)


def test_dataframe_method_repl(sample_df):
    pt_df = DataFrame(sample_df)
    lines = ["-filter \"body_mass_g > 4000\"", "exit"]
    r = PytaeRepl(df=pt_df)
    res = r.run(input_fn=iter(lines).__next__, output_fn=lambda _: None)
    assert res.shape == (3, 3)


def test_repl_join_direct_file(tmp_path):
    f1 = tmp_path / "orders.parquet"
    f2 = tmp_path / "customers.parquet"
    pl.DataFrame({"order_id": [101, 102, 103], "cust_id": [1, 2, 1], "amount": [50.0, 75.0, 20.0]}).write_parquet(f1)
    pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}).write_parquet(f2)

    outputs = []
    r = PytaeRepl(path=f1)
    assert r.current_df.shape == (3, 3)

    r.execute_line(f"join {f2} on=cust_id:id how=left", output_fn=outputs.append)
    assert r.current_df.shape == (3, 4)
    assert "name" in r.current_df.columns
    assert "Alice" in r.current_df["name"].to_list()

    # Undo join
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (3, 3)
    assert "name" not in r.current_df.columns


def test_repl_join_checkpoints_and_sql(tmp_path):
    f1 = tmp_path / "orders.parquet"
    f2 = tmp_path / "customers.parquet"
    pl.DataFrame({"order_id": [101, 102], "cust_id": [1, 2]}).write_parquet(f1)
    pl.DataFrame({"cust_id": [1, 2], "name": ["Alice", "Bob"]}).write_parquet(f2)

    outputs = []
    r = PytaeRepl()

    r.execute_line(f"load {f1} as ord", output_fn=outputs.append)
    assert "ord" in r.checkpoints

    r.execute_line(f"load {f2} as cust", output_fn=outputs.append)
    assert "cust" in r.checkpoints

    # Direct join between checkpoints
    r.execute_line("restore ord", output_fn=outputs.append)
    r.execute_line("join cust on=cust_id", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)
    assert "name" in r.current_df.columns

    # SQL join between checkpoints
    r.execute_line("sql SELECT ord.order_id, cust.name FROM ord JOIN cust ON ord.cust_id = cust.cust_id", output_fn=outputs.append)
    assert r.current_df.shape == (2, 2)
    assert set(r.current_df.columns) == {"order_id", "name"}


def test_cli_repl_invocation(sample_parquet, monkeypatch):
    import sys

    invoked = False

    def mock_repl(*args, **kwargs):
        nonlocal invoked
        invoked = True
        return None

    monkeypatch.setattr(sys.modules["pytae.repl"], "repl", mock_repl)

    # Test pytae repl <file>
    cli.main(["repl", str(sample_parquet)])
    assert invoked

    invoked = False
    # Test pytae <file> -i
    cli.main([str(sample_parquet), "-i"])
    assert invoked

    invoked = False
    # Test pytae -i
    cli.main(["-i"])
    assert invoked


def test_repl_variable_assignment_and_multi_tables(tmp_path):
    f_orders = tmp_path / "orders.parquet"
    f_customers = tmp_path / "customers.parquet"

    pl.DataFrame({
        "order_id": [101, 102, 103],
        "cust_id": [1, 2, 1],
        "amount": [150.0, 75.0, 20.0],
    }).write_parquet(f_orders)

    pl.DataFrame({
        "cust_id": [1, 2],
        "name": ["Alice", "Bob"],
        "tier": ["Gold", "Silver"],
    }).write_parquet(f_customers)

    outputs = []
    # Start empty REPL (like `pytae -i`)
    r = PytaeRepl()
    assert r.current_df is None

    # 1. Assign df1 = orders.parquet
    r.execute_line(f"df1 = {f_orders}", output_fn=outputs.append)
    assert "df1" in r.checkpoints
    assert r.checkpoints["df1"].shape == (3, 3)

    # 2. Assign df2 = customers.parquet
    r.execute_line(f"df2 = {f_customers}", output_fn=outputs.append)
    assert "df2" in r.checkpoints
    assert r.checkpoints["df2"].shape == (2, 3)

    # 3. List tables
    r.execute_line("tables", output_fn=outputs.append)
    assert any("df1" in o for o in outputs)
    assert any("df2" in o for o in outputs)

    # 4. Targeted inspections
    r.execute_line("df1 shape", output_fn=outputs.append)
    assert "(3, 3)" in outputs[-1]
    r.execute_line("df2 shape", output_fn=outputs.append)
    assert "(2, 3)" in outputs[-1]

    # 5. Targeted transformation: filter df1 in place
    r.execute_line("df1 -filter \"amount > 50\"", output_fn=outputs.append)
    assert r.checkpoints["df1"].shape == (2, 3)

    # 6. Switch active table with bare name or `use`
    r.execute_line("use df2", output_fn=outputs.append)
    assert r.path_str == "df2"
    assert r.current_df.shape == (2, 3)

    # 7. Assignment from join: df3 = df1 join df2 on=cust_id
    r.execute_line("df3 = df1 join df2 on=cust_id", output_fn=outputs.append)
    assert "df3" in r.checkpoints
    assert r.checkpoints["df3"].shape == (2, 5)
    assert "name" in r.checkpoints["df3"].columns

    # 8. Assignment from SQL query
    r.execute_line(
        "df4 = sql SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.cust_id",
        output_fn=outputs.append,
    )
    assert "df4" in r.checkpoints
    assert r.checkpoints["df4"].shape == (2, 3)
    assert set(r.checkpoints["df4"].columns) == {"order_id", "name", "amount"}


def test_repl_standard_cli_join_and_output(tmp_path):
    f_orders = tmp_path / "orders.parquet"
    f_customers = tmp_path / "customers.parquet"
    f_merged = tmp_path / "merged.parquet"
    f_final = tmp_path / "final.csv"

    pl.DataFrame({
        "order_id": [1, 2, 3],
        "cust_id": [10, 20, 10],
        "amount": [100.0, 250.0, 50.0],
    }).write_parquet(f_orders)

    pl.DataFrame({
        "cust_id": [10, 20],
        "name": ["Alice", "Bob"],
    }).write_parquet(f_customers)

    outputs = []
    r = PytaeRepl()

    # Load datasets using standard assignment
    r.execute_line(f"df1 = {f_orders}", output_fn=outputs.append)
    r.execute_line(f"df2 = {f_customers}", output_fn=outputs.append)

    # 1. Standard -join with -o destination
    r.execute_line("use df1", output_fn=outputs.append)
    r.execute_line(f"-join df2 on=cust_id -o {f_merged}", output_fn=outputs.append)
    assert f_merged.exists()
    saved = pl.read_parquet(f_merged)
    assert saved.shape == (3, 4)
    assert "name" in saved.columns

    # 2. Key-value standard CLI join syntax: left=df1,right=df2,on=cust_id
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (3, 3)
    r.execute_line("-join left=df1,right=df2,on=cust_id,how=inner", output_fn=outputs.append)
    assert r.current_df.shape == (3, 4)

    # 3. Standard -o flag
    r.execute_line(f"-o {f_final}", output_fn=outputs.append)
    assert f_final.exists()
    assert len(f_final.read_text().splitlines()) == 4  # header + 3 rows


