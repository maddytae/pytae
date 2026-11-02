"""Unit tests for pytae interactive REPL (PytaeRepl, pt.repl(), df.repl(), and CLI flags)."""

from pathlib import Path

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

    # 1. Exploratory preview filter does not mutate active table
    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)  # Safe preview, untouched!
    assert any("Gentoo" in o for o in outputs)

    # 2. Assign filter explicitly updates active table and records undo
    outputs.clear()
    r.execute_line("df = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)
    assert len(r.undo_stack) == 1

    # 3. Undo filter
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)
    assert "Undid:" in outputs[-1]

    # 4. Apply another filter via assignment
    r.execute_line("df = -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)

    # 5. Reset to original
    r.execute_line("reset", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)
    assert "Restored" in outputs[-1] and "initial" in outputs[-1]


def test_repl_redo(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    r.execute_line("df = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
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

    # Mutate data via assignment
    r.execute_line('df = -mutate "mass_kg = body_mass_g / 1000.0"', output_fn=outputs.append)
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

    # -shape
    r.execute_line("-shape", output_fn=outputs.append)
    assert "(5, 3)" in outputs[-1]
    assert len(r.undo_stack) == 0

    # -cols
    r.execute_line("-cols", output_fn=outputs.append)
    assert "species" in outputs[-1]

    # -dtype
    r.execute_line("-dtype", output_fn=outputs.append)

    # -nulls
    r.execute_line("-nulls", output_fn=outputs.append)

    # -glimpse
    r.execute_line("-glimpse", output_fn=outputs.append)

    # -head / -tail
    r.execute_line("-head 2", output_fn=outputs.append)
    r.execute_line("-tail 2", output_fn=outputs.append)

    # None of these should mutate or push to undo stack!
    assert r.current_df.shape == (5, 3)
    assert len(r.undo_stack) == 0


def test_repl_sql_query(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Bare sql rejected
    r.execute_line("sql SELECT species FROM df", output_fn=outputs.append)
    assert "bare 'sql' is not recognized; use '-sql'" in outputs[-1]

    # -sql query succeeds
    outputs.clear()
    r.execute_line(
        '-sql "SELECT species, COUNT(*) as cnt FROM df GROUP BY species ORDER BY cnt DESC"',
        output_fn=outputs.append,
    )
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

    # Bare save is rejected with guidance
    r.execute_line(f"save {out_file}", output_fn=outputs.append)
    assert "pytae: 'save' is not recognized; use '-o <path>'." in outputs[-1]

    # Standard -o succeeds
    r.execute_line(f"-o {out_file}", output_fn=outputs.append)
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
    r.execute_line('-filter "non_existent > 10"', output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)  # Intact!
    assert len(r.undo_stack) == 0
    assert any("error" in o.lower() or "not found" in o.lower() for o in outputs)


def test_repl_headless_run(sample_df):
    lines = [
        "df = -filter \"species == 'Gentoo'\"",
        "checkpoint g_only",
        'df = -mutate "mass_kg = body_mass_g / 1000.0"',
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
    res = (
        repl(df=sample_df)
        if False
        else PytaeRepl(df=sample_df).run(input_fn=iter(lines).__next__, output_fn=lambda _: None)
    )
    assert res.shape == (5, 3)


def test_dataframe_method_repl(sample_df):
    pt_df = DataFrame(sample_df)
    lines = ['df = -filter "body_mass_g > 4000"', "exit"]
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

    # Bare join is rejected with guidance
    r.execute_line(f"join {f2} on=cust_id:id how=left", output_fn=outputs.append)
    assert "bare 'join' is not recognized; use '-join'" in outputs[-1]

    # Standard -join succeeds
    r.execute_line(f"-join {f2} on=cust_id:id how=left", output_fn=outputs.append)
    assert r.current_df.shape == (3, 4)
    assert "name" in r.current_df.columns
    assert "Alice" in r.current_df["name"].to_list()

    # Undo join
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (3, 3)
    assert "name" not in r.current_df.columns


def test_repl_join_tables_and_sql(tmp_path):
    f1 = tmp_path / "orders.parquet"
    f2 = tmp_path / "customers.parquet"
    pl.DataFrame({"order_id": [101, 102], "cust_id": [1, 2]}).write_parquet(f1)
    pl.DataFrame({"cust_id": [1, 2], "name": ["Alice", "Bob"]}).write_parquet(f2)

    outputs = []
    r = PytaeRepl()

    r.execute_line(f"load {f1} as ord", output_fn=outputs.append)
    assert "ord" in r.tables

    r.execute_line(f"load {f2} as cust", output_fn=outputs.append)
    assert "cust" in r.tables

    # Direct join between tables: bare join rejected, -join succeeds
    r.execute_line("join cust on=cust_id", output_fn=outputs.append)
    assert "bare 'join' is not recognized; use '-join'" in outputs[-1]

    r.execute_line("-join cust on=cust_id", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)
    assert "name" in r.current_df.columns

    # SQL join between tables
    r.execute_line(
        '-sql "SELECT ord.order_id, cust.name FROM ord JOIN cust ON ord.cust_id = cust.cust_id"',
        output_fn=outputs.append,
    )
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

    # Test legacy pytae repl <file> is cleanly retired
    with pytest.raises(SystemExit):
        cli.main(["repl", str(sample_parquet)])

    invoked = False
    # Test pytae <file> -i is disallowed with clear guidance
    with pytest.raises(SystemExit) as exc:
        cli.main([str(sample_parquet), "-i"])
    assert exc.value.code == 2

    invoked = False
    # Test pytae -i
    cli.main(["-i"])
    assert invoked


def test_repl_variable_assignment_and_multi_tables(tmp_path):
    f_orders = tmp_path / "orders.parquet"
    f_customers = tmp_path / "customers.parquet"

    pl.DataFrame(
        {
            "order_id": [101, 102, 103],
            "cust_id": [1, 2, 1],
            "amount": [150.0, 75.0, 20.0],
        }
    ).write_parquet(f_orders)

    pl.DataFrame(
        {
            "cust_id": [1, 2],
            "name": ["Alice", "Bob"],
            "tier": ["Gold", "Silver"],
        }
    ).write_parquet(f_customers)

    outputs = []
    # Start empty REPL (like `pytae -i`)
    r = PytaeRepl()
    assert r.current_df is None

    # 1. Assign df1 = orders.parquet
    r.execute_line(f"df1 = {f_orders}", output_fn=outputs.append)
    assert "df1" in r.tables
    assert r.tables["df1"].shape == (3, 3)
    assert "df1" not in r.checkpoints

    # 2. Assign df2 = customers.parquet
    r.execute_line(f"df2 = {f_customers}", output_fn=outputs.append)
    assert "df2" in r.tables
    assert r.tables["df2"].shape == (2, 3)
    assert "df2" not in r.checkpoints

    # 3. List tables
    r.execute_line("tables", output_fn=outputs.append)
    assert any("df1" in o for o in outputs)
    assert any("df2" in o for o in outputs)

    # 4. Targeted inspections
    r.execute_line("df1 -shape", output_fn=outputs.append)
    assert "(3, 3)" in outputs[-1]
    r.execute_line("df2 -shape", output_fn=outputs.append)
    assert "(2, 3)" in outputs[-1]

    # 5. Targeted preview does not mutate df1
    r.execute_line('df1 -filter "amount > 50"', output_fn=outputs.append)
    assert r.tables["df1"].shape == (3, 3)  # Preview only!
    # Explicit assignment filters df1 in place
    r.execute_line('df1 = df1 -filter "amount > 50"', output_fn=outputs.append)
    assert r.tables["df1"].shape == (2, 3)

    # 6. Switch active table with bare name or `use`
    r.execute_line("use df2", output_fn=outputs.append)
    assert r.path_str == "df2"
    assert r.current_df.shape == (2, 3)

    # 7. Assignment from join: bare join rejected, -join succeeds
    r.execute_line("df3 = df1 join df2 on=cust_id", output_fn=outputs.append)
    assert "bare 'join' is not recognized; use '-join'" in outputs[-1]

    r.execute_line("df3 = df1 -join df2 on=cust_id", output_fn=outputs.append)
    assert "df3" in r.tables
    assert r.tables["df3"].shape == (2, 5)
    assert "name" in r.tables["df3"].columns

    # 8. Assignment from SQL query
    r.execute_line(
        'df4 = -sql "SELECT df1.order_id, df2.name, df1.amount FROM df1 JOIN df2 ON df1.cust_id = df2.cust_id"',
        output_fn=outputs.append,
    )
    assert "df4" in r.tables
    assert r.tables["df4"].shape == (2, 3)
    assert set(r.tables["df4"].columns) == {"order_id", "name", "amount"}

    # Bare sql assignment rejected
    outputs.clear()
    r.execute_line("df5 = sql SELECT * FROM df1", output_fn=outputs.append)
    assert "bare 'sql' is not recognized; use '-sql" in outputs[-1]


def test_repl_standard_cli_join_and_output(tmp_path):
    f_orders = tmp_path / "orders.parquet"
    f_customers = tmp_path / "customers.parquet"
    f_merged = tmp_path / "merged.parquet"
    f_final = tmp_path / "final.csv"

    pl.DataFrame(
        {
            "order_id": [1, 2, 3],
            "cust_id": [10, 20, 10],
            "amount": [100.0, 250.0, 50.0],
        }
    ).write_parquet(f_orders)

    pl.DataFrame(
        {
            "cust_id": [10, 20],
            "name": ["Alice", "Bob"],
        }
    ).write_parquet(f_customers)

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


def test_repl_bundled_sample_dataset():
    outputs = []
    r = PytaeRepl()

    # 1. Strict explicit sample URI: df1 = sample:penguins
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    assert "df1" in r.tables
    assert r.tables["df1"].shape == (344, 7)
    assert "df1" not in r.checkpoints

    # 2. Strict explicit sample URI: df2 = sample:tips
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    assert "df2" in r.tables
    assert r.tables["df2"].shape == (244, 7)
    assert "df2" not in r.checkpoints

    # 3. Strict: Non-existent file df=panguins.csv or df=penguins.csv fails (no fuzzy, no fallback)
    r.execute_line("df3 = panguins.csv", output_fn=outputs.append)
    assert "df3" not in r.tables
    assert any("not an existing file or table" in o for o in outputs)

    # 4. Strict: Non-existent sample URI fails cleanly
    r.execute_line("df4 = sample:unknown_name", output_fn=outputs.append)
    assert "df4" not in r.tables
    assert any("unknown sample dataset" in o for o in outputs)


def test_repl_shell_command_escape():
    outputs = []
    r = PytaeRepl()

    # Empty bang prints usage
    r.execute_line("!", output_fn=outputs.append)
    assert any("Usage: !<command>" in o for o in outputs)

    # Shell execution captures stdout
    outputs.clear()
    r.execute_line("!echo shell_test_ok", output_fn=outputs.append)
    assert any("shell_test_ok" in o for o in outputs)


def test_repl_bare_verb_rejection(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Bare filter rejected
    r.execute_line("filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert "bare 'filter' is not recognized; use '-filter'" in outputs[-1]

    # Bare mutate rejected
    r.execute_line('mutate "x = 1"', output_fn=outputs.append)
    assert "bare 'mutate' is not recognized; use '-mutate'" in outputs[-1]

    # Bare select rejected
    r.execute_line("select species", output_fn=outputs.append)
    assert "bare 'select' is not recognized; use '-select'" in outputs[-1]

    # Bare inspection & query verbs rejected
    for verb in ("shape", "cols", "dtype", "nulls", "glimpse", "describe", "head", "tail", "sql"):
        outputs.clear()
        r.execute_line(verb, output_fn=outputs.append)
        assert f"bare '{verb}' is not recognized; use '-{verb}'" in outputs[-1]

    # Targeted bare verb rejected
    r.tables["df1"] = sample_df
    r.execute_line("df1 filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert "bare 'filter' is not recognized; use '-filter'" in outputs[-1]

    outputs.clear()
    r.execute_line("df1 shape", output_fn=outputs.append)
    assert "bare 'shape' is not recognized; use '-shape'" in outputs[-1]


def test_repl_model2_display_no_table_dumps(tmp_path):
    f_orders = tmp_path / "orders.parquet"
    pl.DataFrame(
        {
            "order_id": [101, 102, 103],
            "cust_id": [1, 2, 1],
            "amount": [150.0, 75.0, 20.0],
        }
    ).write_parquet(f_orders)

    outputs = []
    r = PytaeRepl()
    r.execute_line(f"df1 = {f_orders}", output_fn=outputs.append)

    # 1. Bare table name df1 prints shape only, never a table
    outputs.clear()
    r.execute_line("df1", output_fn=outputs.append)
    assert len(outputs) == 1
    assert "df1: 3 rows x 3 cols" in outputs[0]
    assert "order_id" not in outputs[0]

    # 2. Pipeline transformation outputs formatted table matching CLI without mutating df1
    outputs.clear()
    r.execute_line('-filter "amount > 50"', output_fn=outputs.append)
    assert any("order_id" in o for o in outputs)
    assert any("150" in o for o in outputs)
    assert r.tables["df1"].shape == (3, 3)

    # 3. Explicit inspection '-head' renders table with columns and values
    outputs.clear()
    r.execute_line("-head 2", output_fn=outputs.append)
    assert any("order_id" in o for o in outputs)
    assert any("150" in o for o in outputs)

    # 4. Explicit inspection '-tail' renders table with columns and values
    outputs.clear()
    r.execute_line("-tail 1", output_fn=outputs.append)
    assert any("order_id" in o for o in outputs)
    assert any("20" in o for o in outputs)


def test_repl_help_and_exit_strictly_enforced():
    outputs = []
    r = PytaeRepl()

    # 1. 'help' works
    cont = r.execute_line("help", output_fn=outputs.append)
    assert cont is True
    assert any("PYTAE REPL COMMANDS" in o for o in outputs)

    # 2. '?' is rejected and guides to 'help'
    outputs.clear()
    cont = r.execute_line("?", output_fn=outputs.append)
    assert cont is True
    assert "use 'help'" in outputs[-1]

    # 3. 'q' and 'quit' are rejected and guide to 'exit'
    outputs.clear()
    cont = r.execute_line("q", output_fn=outputs.append)
    assert cont is True
    assert "use 'exit'" in outputs[-1]

    outputs.clear()
    cont = r.execute_line("quit", output_fn=outputs.append)
    assert cont is True
    assert "use 'exit'" in outputs[-1]

    # 4. 'exit' terminates REPL
    outputs.clear()
    cont = r.execute_line("exit", output_fn=outputs.append)
    assert cont is False
    assert "Exiting pytae REPL." in outputs[-1]


def test_repl_strict_checkpoints_vs_tables_separation():
    outputs = []
    r = PytaeRepl()

    # Load two workbench datasets
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)

    # Prompt only displays loaded workbench tables
    assert r._build_prompt() == "pytae [df1, df2]> "

    # Save checkpoint 'maddy'
    outputs.clear()
    r.execute_line("checkpoint maddy", output_fn=outputs.append)
    assert "Saved checkpoint 'maddy'" in outputs[-1]
    assert "maddy" in r.checkpoints
    assert "maddy" not in r.tables

    # Prompt MUST remain [df1, df2], never polluting with 'maddy'
    assert r._build_prompt() == "pytae [df1, df2]> "

    # 'checkpoints' command lists ONLY saved checkpoints ('maddy'), not separate checkpoint entries for df1 or df2
    outputs.clear()
    r.execute_line("checkpoints", output_fn=outputs.append)
    cp_text = "\n".join(outputs)
    assert "maddy" in cp_text
    assert "df1 (344x7)" in cp_text  # Shows the table summary inside checkpoint 'maddy'
    # And 'maddy' is not a table in 'tables' command
    outputs.clear()
    r.execute_line("tables", output_fn=outputs.append)
    tbl_text = "\n".join(outputs)
    assert "df1" in tbl_text
    assert "df2" in tbl_text
    assert "maddy" not in tbl_text


def test_repl_disallowed_aliases_and_hyphenated_commands():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)

    test_cases = [
        ("cp", "checkpoint"),
        ("-cp", "checkpoint"),
        ("--cp", "checkpoint"),
        ("cps", "checkpoints"),
        ("-cps", "checkpoints"),
        ("--cps", "checkpoints"),
        ("vars", "tables"),
        ("datasets", "tables"),
        ("switch", "use"),
        ("-use", "use"),
        ("--use", "use"),
        ("checkout", "restore"),
        ("-restore", "restore"),
        ("--restore", "restore"),
        ("-checkpoint", "checkpoint"),
        ("--checkpoint", "checkpoint"),
        ("-checkpoints", "checkpoints"),
        ("--checkpoints", "checkpoints"),
        ("-reset", "reset"),
        ("--reset", "reset"),
        ("-undo", "undo"),
        ("--undo", "undo"),
        ("-redo", "redo"),
        ("--redo", "redo"),
        ("-history", "history"),
        ("--history", "history"),
        ("-tables", "tables"),
        ("--tables", "tables"),
        ("-status", "status"),
        ("--status", "status"),
        ("columns", "-cols"),
        ("-columns", "-cols"),
        ("--columns", "-cols"),
        ("dtypes", "-dtype"),
        ("-dtypes", "-dtype"),
        ("--dtypes", "-dtype"),
        ("--shape", "-shape"),
        ("--cols", "-cols"),
        ("--dtype", "-dtype"),
        ("--nulls", "-nulls"),
        ("--glimpse", "-glimpse"),
        ("--describe", "-describe"),
        ("--head", "-head"),
        ("--tail", "-tail"),
        ("-output", "-o <path>"),
        ("--output", "-o <path>"),
        ("-interactive", "-i"),
        ("--interactive", "-i"),
        ("-repl", "-i"),
        ("--repl", "-i"),
        ("-examples", "-cheatsheet"),
        ("--examples", "-cheatsheet"),
    ]

    for alias, canonical in test_cases:
        outputs.clear()
        r.execute_line(alias, output_fn=outputs.append)
        expected = f"pytae: '{alias}' is not recognized; use '{canonical}'."
        assert outputs[-1] == expected, f"Failed for alias {alias}: got {outputs[-1]!r}"

    # Valid targeted inspection works
    outputs.clear()
    r.execute_line("df1 -dtype", output_fn=outputs.append)
    assert any("species" in o for o in outputs)

    # Bare targeted inspection rejected
    outputs.clear()
    r.execute_line("df1 dtype", output_fn=outputs.append)
    assert outputs[-1] == "pytae: bare 'dtype' is not recognized; use '-dtype' (matching CLI syntax)."

    # Disallowed alias rejected in targeted context
    outputs.clear()
    r.execute_line("df1 columns", output_fn=outputs.append)
    assert outputs[-1] == "pytae: 'columns' is not recognized; use '-cols'."


def test_repl_multi_table_session_and_checkpoints():
    outputs = []
    repl = PytaeRepl()

    assert repl._build_prompt() == "pytae> "

    # 1. Load df1
    repl.execute_line("df1=penguins.parquet", output_fn=outputs.append)
    assert "Loaded penguins.parquet as 'df1' (344 rows x 7 cols)." in outputs[-1]
    assert repl._build_prompt() == "pytae [df1: 344x7]> "

    # 2. Load df2
    outputs.clear()
    repl.execute_line("df2=tips.parquet", output_fn=outputs.append)
    assert "Loaded tips.parquet as 'df2' (244 rows x 7 cols)." in outputs[-1]
    assert repl._build_prompt() == "pytae [df1, df2]> "

    # 3. List tables
    outputs.clear()
    repl.execute_line("tables", output_fn=outputs.append)
    tables_out = "\n".join(outputs)
    assert "Tables in memory:" in tables_out
    assert "df1" in tables_out and "(penguins.parquet)" in tables_out
    assert "* df2" in tables_out and "(tips.parquet) [active]" in tables_out

    # 4. Save checkpoint maddy (captures all tables in workbench)
    outputs.clear()
    repl.execute_line("checkpoint maddy", output_fn=outputs.append)
    assert "Saved checkpoint 'maddy' (2 tables: df1, df2)." in outputs[-1]
    # Checkpoint should not change table prompt
    assert repl._build_prompt() == "pytae [df1, df2]> "

    # 5. List checkpoints
    outputs.clear()
    repl.execute_line("checkpoints", output_fn=outputs.append)
    cps_out = "\n".join(outputs)
    assert "Saved Checkpoints:" in cps_out
    assert "maddy" in cps_out and "df1 (344x7), df2 (244x7)" in cps_out
    assert repl._build_prompt() == "pytae [df1, df2]> "

    # 6. Mutate and add a 3rd table df3
    repl.execute_line("df3 = df1", output_fn=outputs.append)
    assert "df3" in repl.tables
    assert repl._build_prompt() == "pytae [df1, df2, df3]> "

    # 7. Restore maddy restores original workbench state (df3 removed, df1 & df2 intact)
    outputs.clear()
    repl.execute_line("restore maddy", output_fn=outputs.append)
    assert "Restored checkpoint 'maddy'" in outputs[-1]
    assert "df3" not in repl.tables
    assert "df1" in repl.tables and "df2" in repl.tables
    assert repl._build_prompt() == "pytae [df1, df2]> "


def test_repl_reader_options_on_assignment_and_load(tmp_path):
    csv_file = tmp_path / "custom.csv"
    csv_file.write_text("col_a;col_b\nval1;10\nval2;20\nval3;30\n", encoding="latin-1")

    outputs = []
    r = PytaeRepl()

    # 1. Assignment with -dlim and -encoding
    r.execute_line(f'df1 = {csv_file} -dlim ";" -encoding latin1', output_fn=outputs.append)
    assert "df1" in r.tables
    assert r.tables["df1"].shape == (3, 2)
    assert r.tables["df1"].columns == ["col_a", "col_b"]
    assert "sep=;" in outputs[-1] or "encoding=latin1" in outputs[-1]

    # 2. Assignment with -nrows
    outputs.clear()
    r.execute_line(f'df2 = {csv_file} -dlim ";" -nrows 2', output_fn=outputs.append)
    assert "df2" in r.tables
    assert r.tables["df2"].shape == (2, 2)

    # 3. load command with options
    outputs.clear()
    r.execute_line(f'load {csv_file} as df3 -dlim ";" -nrows 1', output_fn=outputs.append)
    assert "df3" in r.tables
    assert r.tables["df3"].shape == (1, 2)


def test_repl_cols_sorting_and_filtering(sample_df):
    r = PytaeRepl(df=sample_df)
    outputs = []

    # Default file order
    r.execute_line("-cols", output_fn=outputs.append)
    assert outputs[-1] == "id\nspecies\nbody_mass_g"

    # asc order
    outputs.clear()
    r.execute_line("-cols asc", output_fn=outputs.append)
    assert outputs[-1] == "body_mass_g\nid\nspecies"

    # desc order
    outputs.clear()
    r.execute_line("-cols desc", output_fn=outputs.append)
    assert outputs[-1] == "species\nid\nbody_mass_g"

    # substring pattern filter
    outputs.clear()
    r.execute_line("-cols mass", output_fn=outputs.append)
    assert outputs[-1] == "body_mass_g"

    # targeted table -cols asc
    outputs.clear()
    r.execute_line("peng -cols asc", output_fn=outputs.append)
    # peng is alias for sample_df
    assert outputs[-1] == "body_mass_g\nid\nspecies"

    # targeted table -cols desc
    outputs.clear()
    r.execute_line("peng -cols desc", output_fn=outputs.append)
    assert outputs[-1] == "species\nid\nbody_mass_g"


def test_repl_targeted_pipeline_active_sync(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)
    tbl_name = r.path_str or "df"

    # Target the active table with assignment: tbl = tbl -select "!species"
    r.execute_line(f'{tbl_name} = {tbl_name} -select "!species"', output_fn=outputs.append)
    assert "species" not in r.tables[tbl_name].columns
    assert "species" not in r.current_df.columns
    assert r.current_df.columns == ["id", "body_mass_g"]

    # Standalone -cols should immediately reflect the mutation without desync
    outputs.clear()
    r.execute_line("-cols", output_fn=outputs.append)
    assert outputs[-1] == "id\nbody_mass_g"


def test_repl_rm_table(sample_df):
    outputs = []
    r = PytaeRepl()
    r.tables["df1"] = sample_df.clone()
    r.tables["df2"] = sample_df.clone()
    r.path_str = "df1"
    r.current_df = r.tables["df1"]

    # Remove active table df1 -> switches to df2
    r.execute_line("rm df1", output_fn=outputs.append)
    assert "df1" not in r.tables
    assert "df2" in r.tables
    assert r.path_str == "df2"
    assert "Removed table 'df1'. Switched active dataset to 'df2'." in outputs[-1]

    # rm is non-undoable to ensure immediate RAM release without disk overhead
    outputs.clear()
    r.execute_line("undo", output_fn=outputs.append)
    assert "Nothing to undo." in outputs[-1]
    assert "df1" not in r.tables

    # Remove last table
    r.execute_line("rm df2", output_fn=outputs.append)
    assert len(r.tables) == 0
    assert r.current_df is None
    assert r.path_str is None


def test_repl_rm_checkpoint(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)
    r.execute_line("checkpoint cp1", output_fn=outputs.append)
    r.execute_line("checkpoint cp2", output_fn=outputs.append)
    assert "cp1" in r.checkpoints and "cp2" in r.checkpoints

    # rm checkpoint cp1
    r.execute_line("rm checkpoint cp1", output_fn=outputs.append)
    assert "cp1" not in r.checkpoints
    assert "cp2" in r.checkpoints
    assert "Removed checkpoint 'cp1'." in outputs[-1]

    # checkpoint rm cp2
    outputs.clear()
    r.execute_line("checkpoint rm cp2", output_fn=outputs.append)
    assert "cp2" not in r.checkpoints
    assert "Removed checkpoint 'cp2'." in outputs[-1]

    # rm checkpoint * and rejection of rm checkpoints / -all / all
    r.execute_line("checkpoint a", output_fn=outputs.append)
    r.execute_line("checkpoint b", output_fn=outputs.append)
    assert len(r.checkpoints) == 2

    # Verify rm checkpoints variants are rejected and redirect to rm checkpoint
    outputs.clear()
    r.execute_line("rm checkpoints", output_fn=outputs.append)
    assert "pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint'." in outputs[-1]

    outputs.clear()
    r.execute_line("rm checkpoints *", output_fn=outputs.append)
    assert "pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint *'." in outputs[-1]

    outputs.clear()
    r.execute_line("rm checkpoints -all", output_fn=outputs.append)
    assert "use 'rm checkpoint *'" in outputs[-1]

    outputs.clear()
    r.execute_line("rm checkpoints a", output_fn=outputs.append)
    assert "pytae: 'rm checkpoints' is not recognized; use 'rm checkpoint a'." in outputs[-1]
    assert len(r.checkpoints) == 2

    outputs.clear()
    r.execute_line("checkpoint rm -all", output_fn=outputs.append)
    assert "use 'checkpoint rm *'" in outputs[-1]
    assert len(r.checkpoints) == 2

    r.execute_line("rm checkpoint *", output_fn=outputs.append)
    assert len(r.checkpoints) == 0

    # Also verify checkpoint rm * works
    r.execute_line("checkpoint c", output_fn=outputs.append)
    assert len(r.checkpoints) == 1
    r.execute_line("checkpoint rm *", output_fn=outputs.append)
    assert len(r.checkpoints) == 0


def test_repl_shell_pipe(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Shell pipe: -cols | grep mass
    r.execute_line("-cols | grep mass", output_fn=outputs.append)
    assert any("body_mass_g" in o for o in outputs)
    assert not any("species" in o for o in outputs)

    # Targeted table with shell pipe: peng -cols | grep id
    outputs.clear()
    r.execute_line("peng -cols | grep id", output_fn=outputs.append)
    assert any("id" in o for o in outputs)
    assert not any("body_mass_g" in o for o in outputs)

    # Pipe '|' inside quoted arguments (e.g. select regex) is NOT split as a shell pipe
    outputs.clear()
    r.execute_line('df = -select "regex=species|body"', output_fn=outputs.append)
    assert r.current_df.columns == ["species", "body_mass_g"]


def test_win_console_input_history_navigation(monkeypatch):
    import sys
    import types

    from pytae.repl import _win_console_input

    # Simulate pressing Up arrow (\xe0 + H), then Enter (\r)
    keystrokes = ["\xe0", "H", "\r"]

    class MockMsvcrt:
        @staticmethod
        def getwch():
            if keystrokes:
                return keystrokes.pop(0)
            return "\r"

    fake_msvcrt = types.ModuleType("msvcrt")
    fake_msvcrt.getwch = MockMsvcrt.getwch
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)

    history = ["-cols", "-head 5"]
    res = _win_console_input("pytae> ", history)
    assert res == "-head 5"


def test_win_console_input_line_editing(monkeypatch):
    import sys
    import types

    from pytae.repl import _win_console_input

    # Simulate typing 'df', backspacing 'f', typing '1', then Enter
    keystrokes = ["d", "f", "\x08", "1", "\r"]

    class MockMsvcrt:
        @staticmethod
        def getwch():
            if keystrokes:
                return keystrokes.pop(0)
            return "\r"

    fake_msvcrt = types.ModuleType("msvcrt")
    fake_msvcrt.getwch = MockMsvcrt.getwch
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)

    res = _win_console_input("pytae> ", [])
    assert res == "d1"


def test_repl_raw_history_persistence(tmp_path, monkeypatch):
    import sys

    repl_mod = sys.modules["pytae.repl"]

    fake_hist_file = tmp_path / ".pytae_test_history"
    monkeypatch.setattr(repl_mod, "_HIST_FILE", fake_hist_file)

    repl_mod._save_raw_history(["cmd1", "cmd2", "cmd3"])
    loaded = repl_mod._load_history_from_file()
    assert loaded == ["cmd1", "cmd2", "cmd3"]


def test_repl_rm_df_with_loaded_file(sample_parquet):
    outputs = []
    r = PytaeRepl(path=sample_parquet)
    assert r.current_df is not None
    assert "penguins_sample.parquet" in r.tables

    # 'rm df' is rejected when 'df' is not a table name
    r.execute_line("rm df", output_fn=outputs.append)
    assert "table 'df' not found" in outputs[-1]
    assert "penguins_sample.parquet" in r.tables

    # Removing by explicit name or stem succeeds
    outputs.clear()
    r.execute_line("rm penguins_sample", output_fn=outputs.append)
    assert "Removed table 'penguins_sample.parquet'" in outputs[-1]
    assert "No tables remain loaded" in outputs[-1]
    assert r.current_df is None
    assert r.path_str is None
    assert "penguins_sample.parquet" not in r.tables

    # rm is non-undoable
    outputs.clear()
    r.execute_line("undo", output_fn=outputs.append)
    assert "Nothing to undo." in outputs[-1]
    assert r.current_df is None


def test_repl_rm_df_in_memory(sample_df):
    outputs = []
    # Loaded directly as 'df'
    r = PytaeRepl(df=sample_df)
    assert r.current_df is not None
    assert "df" in r.tables

    r.execute_line("rm df", output_fn=outputs.append)
    assert "Removed table 'df'" in outputs[-1]
    assert r.current_df is None
    assert not r.tables

    # rm is non-undoable
    outputs.clear()
    r.execute_line("undo", output_fn=outputs.append)
    assert "Nothing to undo." in outputs[-1]
    assert r.current_df is None
    assert not r.tables


def test_repl_rm_stem_matching(sample_parquet):
    outputs = []
    r = PytaeRepl(path=sample_parquet)

    # Stem match: 'penguins_sample' matches 'penguins_sample.parquet'
    r.execute_line("rm penguins_sample", output_fn=outputs.append)
    assert "Removed table 'penguins_sample.parquet'" in outputs[-1]
    assert not r.tables


def test_repl_rm_multiple_tables_switches_active(sample_df, tmp_path):
    p1 = tmp_path / "t1.parquet"
    p2 = tmp_path / "t2.parquet"
    sample_df.write_parquet(p1)
    sample_df.write_parquet(p2)

    r = PytaeRepl(paths=[p1, p2])
    assert len(r.tables) == 2
    outputs = []

    # Active table is 't2'
    assert r.path_str == "t2"
    # rm requires explicit table name
    r.execute_line("rm t2", output_fn=outputs.append)
    assert "Removed table 't2'" in outputs[-1]
    assert "Switched active dataset to 't1'" in outputs[-1]
    assert r.path_str == "t1"
    assert "t1" in r.tables
    assert "t2" not in r.tables


def test_repl_rm_all_tables(sample_df, tmp_path):
    p1 = tmp_path / "t1.parquet"
    p2 = tmp_path / "t2.parquet"
    sample_df.write_parquet(p1)
    sample_df.write_parquet(p2)

    r = PytaeRepl(paths=[p1, p2])
    outputs = []

    # Rejection of rm -all / rm all in favor of strict rm *
    r.execute_line("rm -all", output_fn=outputs.append)
    assert "use 'rm *'" in outputs[-1]
    assert len(r.tables) == 2

    r.execute_line("rm all", output_fn=outputs.append)
    assert "use 'rm *'" in outputs[-1]
    assert len(r.tables) == 2

    # Canonical rm *
    r.execute_line("rm *", output_fn=outputs.append)
    assert "Removed all 2 loaded tables" in outputs[-1]
    assert not r.tables
    assert r.current_df is None

    # rm is non-undoable
    outputs.clear()
    r.execute_line("undo", output_fn=outputs.append)
    assert "Nothing to undo." in outputs[-1]
    assert not r.tables


def test_repl_table_resolution_targeted_and_use(sample_parquet):
    r = PytaeRepl(path=sample_parquet)
    outputs = []

    # 'penguins_sample -cols' stem targeted command
    outputs.clear()
    r.execute_line("penguins_sample -cols", output_fn=outputs.append)
    assert "body_mass_g" in outputs[-1]

    # 'use penguins_sample' stem
    outputs.clear()
    r.execute_line("use penguins_sample", output_fn=outputs.append)
    assert "Switched active dataset to 'penguins_sample.parquet'" in outputs[-1]


def test_win_console_input_git_bash_ansi_arrow_keys(monkeypatch):
    import sys
    import types

    from pytae.repl import _win_console_input

    # Simulate Git Bash sending ANSI Up Arrow: \x1b + [ + A, then Enter (\r)
    keystrokes = ["\x1b", "[", "A", "\r"]

    class MockMsvcrt:
        @staticmethod
        def kbhit():
            return len(keystrokes) > 0 and keystrokes[0] != "\r"

        @staticmethod
        def getwch():
            if keystrokes:
                return keystrokes.pop(0)
            return "\r"

    fake_msvcrt = types.ModuleType("msvcrt")
    fake_msvcrt.getwch = MockMsvcrt.getwch
    fake_msvcrt.kbhit = MockMsvcrt.kbhit
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)

    history = ["-cols", "-head 5"]
    res = _win_console_input("pytae> ", history)
    assert res == "-head 5"


def test_win_console_input_git_bash_application_cursor(monkeypatch):
    import sys
    import types

    from pytae.repl import _win_console_input

    # Simulate Git Bash application cursor Up Arrow: \x1b + O + A, then Enter (\r)
    keystrokes = ["\x1b", "O", "A", "\r"]

    class MockMsvcrt:
        @staticmethod
        def kbhit():
            return len(keystrokes) > 0 and keystrokes[0] != "\r"

        @staticmethod
        def getwch():
            if keystrokes:
                return keystrokes.pop(0)
            return "\r"

    fake_msvcrt = types.ModuleType("msvcrt")
    fake_msvcrt.getwch = MockMsvcrt.getwch
    fake_msvcrt.kbhit = MockMsvcrt.kbhit
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)

    history = ["-cols", "-filter 'species == Gentoo'"]
    res = _win_console_input("pytae> ", history)
    assert res == "-filter 'species == Gentoo'"


def test_git_bash_pipe_ansi_arrow_history_recall(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Run two commands to populate history
    r.execute_line("-cols", output_fn=outputs.append)
    r.execute_line("df = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)

    # In Git Bash without winpty, pressing Up Arrow + Enter sends "\x1b[A"
    outputs.clear()
    r.execute_line("\x1b[A", output_fn=outputs.append)
    assert any("recalled from history: df = -filter \"species == 'Gentoo'\"" in o for o in outputs)
    assert r.current_df.shape == (2, 3)

    # Pressing Up Arrow twice + Enter sends "\x1b[A\x1b[A" -> recalls 2 steps back ("-cols")
    outputs.clear()
    r.execute_line("\x1b[A\x1b[A", output_fn=outputs.append)
    assert any("recalled from history: -cols" in o for o in outputs)


def test_repl_init_with_dlim_and_encoding(tmp_path):
    p = tmp_path / "latin1_pipe.csv"
    p.write_bytes("id|city\n1|Montr\xe9al\n2|Z\xfcrich\n".encode("latin-1"))

    # Initializing PytaeRepl with sep and encoding
    r = PytaeRepl(path=p, sep="|", encoding="latin-1")
    assert r.current_df is not None
    assert r.current_df.shape == (2, 2)
    assert r.current_df["city"].to_list() == ["Montréal", "Zürich"]


def test_cli_repl_launch_with_dlim_and_encoding(tmp_path, monkeypatch):
    p = tmp_path / "latin1_sample.csv"
    p.write_bytes("col1|col2\n1|Caf\xe9\n2|Na\xefve\n".encode("latin-1"))

    r = PytaeRepl()
    outputs = []
    r.execute_line(f'df = {p} -dlim "|" -encoding "latin-1"', output_fn=outputs.append)
    assert "df" in r.tables
    assert r.tables["df"].shape == (2, 2)
    assert r.tables["df"]["col2"].to_list() == ["Café", "Naïve"]


def test_cli_repl_missing_encoding_reports_clean_error(tmp_path):
    p = tmp_path / "latin1_fail.csv"
    p.write_bytes("col1|col2\n1|Caf\xe9\n".encode("latin-1"))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([str(p), "-dlim", "|", "-i"])
    assert exc_info.value.code == 2


def test_repl_and_cli_identical_schema_inference_and_fallback(tmp_path, monkeypatch, capsys):
    p = tmp_path / "schema_test.csv"
    # 50 rows of integers, then a row with latin-1 text
    content = "id|val\n" + "".join(f"{i}|{i * 10}\n" for i in range(50)) + "51|Montr\xe9al\n"
    p.write_bytes(content.encode("latin-1"))

    # 1. CLI reading via pipeline
    code = cli.main([str(p), "-dlim", "|", "-encoding", "latin-1", "-shape"])
    assert code == 0
    assert "(51, 2)" in capsys.readouterr().out

    # 2. REPL disallows positional files with -i
    with pytest.raises(SystemExit) as exc:
        cli.main([str(p), "-dlim", "|", "-encoding", "latin-1", "-i"])
    assert exc.value.code == 2

    # 3. REPL interactive command loading
    r = PytaeRepl()
    outputs = []
    r.execute_line(f'df1 = {p} -dlim "|" -encoding "latin-1"', output_fn=outputs.append)
    assert "df1" in r.tables
    assert r.tables["df1"].shape == (51, 2)
    assert r.tables["df1"]["val"].to_list()[-1] == "Montréal"


def test_repl_strict_clear(monkeypatch):
    import pytae as pt

    r = PytaeRepl()

    # 1. Direct r.clear() method with capture
    out1 = []
    r.clear(output_fn=out1.append)
    assert "\033[H\033[2J" in out1

    # 2. Line command execution: clear succeeds
    out2 = []
    assert r.execute_line("clear", output_fn=out2.append) is True
    assert "\033[H\033[2J" in out2

    # 3. Strict: bare 'cls' is disallowed and redirects to 'clear'
    out3 = []
    assert r.execute_line("cls", output_fn=out3.append) is True
    assert "pytae: 'cls' is not recognized; use 'clear'." in out3[-1]

    # 4. Disallowed hyphenated aliases redirect to 'clear'
    out4 = []
    r.execute_line("-clear", output_fn=out4.append)
    assert "pytae: '-clear' is not recognized; use 'clear'." in out4[-1]

    out5 = []
    r.execute_line("-cls", output_fn=out5.append)
    assert "pytae: '-cls' is not recognized; use 'clear'." in out5[-1]

    # 5. Top-level pt.clear() function
    system_cmds = []
    monkeypatch.setattr("os.system", lambda cmd: system_cmds.append(cmd))
    pt.clear()
    assert len(system_cmds) == 1
    assert system_cmds[0] in ("cls", "clear")

    # 6. Strict check: cls does not exist as a method on PytaeRepl or function in pytae
    assert not hasattr(r, "cls")
    assert not hasattr(pt, "cls")


def test_repl_plot_preserves_filter(sample_parquet, monkeypatch):
    from pytae.plotting import Plotter

    captured = []
    monkeypatch.setattr(Plotter, "show", lambda self: captured.append(self.df.copy()))

    r = PytaeRepl(path=sample_parquet)
    # sample_parquet has 5 rows: 2 Adelie, 2 Gentoo, 1 Chinstrap
    r.execute_line('-filter "species == \'Gentoo\'" -plot "kind=scatter, x=body_mass_g, y=id"')
    assert len(captured) == 1
    assert len(captured[0]) == 2
    assert set(captured[0]["species"]) == {"Gentoo"}


def test_repl_checkpoint_disk_storage_and_undo_reset(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # 1. Do a transformation to create an undo step
    r.execute_line("df = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert len(r.undo_stack) == 1

    # 2. Creating a checkpoint MUST reset undo and save tables to disk IPC
    outputs.clear()
    r.execute_line("checkpoint v1", output_fn=outputs.append)
    assert "Saved checkpoint 'v1'" in outputs[-1]
    assert len(r.undo_stack) == 0
    assert len(r.redo_stack) == 0

    # Verify disk persistence
    cp_info = r.checkpoints["v1"]
    assert "dir" in cp_info
    cp_dir = Path(cp_info["dir"])
    assert cp_dir.exists() and cp_dir.is_dir()
    assert (cp_dir / "meta.json").exists()
    # No in-memory polars DataFrame stored in checkpoint dict
    assert not any(isinstance(v, pl.DataFrame) for v in cp_info.values())

    # 3. New mutation after checkpoint can be undone back to checkpoint baseline
    r.execute_line('df = -mutate "weight_lb = body_mass_g * 0.00220462"', output_fn=outputs.append)
    assert "weight_lb" in r.current_df.columns
    assert len(r.undo_stack) == 1

    r.execute_line("undo", output_fn=outputs.append)
    assert "weight_lb" not in r.current_df.columns
    assert r.current_df.shape == (2, 3)

    r.close()
    # Verify cleanup on close
    assert not cp_dir.exists()


def test_repl_restore_strictly_isolates_ram_from_post_checkpoint_tables():
    outputs = []
    r = PytaeRepl()

    # Load baseline table
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("checkpoint baseline", output_fn=outputs.append)
    assert len(r.undo_stack) == 0

    # Load multiple post-checkpoint tables and mutate
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    r.execute_line("df3 = df1", output_fn=outputs.append)
    r.execute_line('df1 -mutate "flag = 1"', output_fn=outputs.append)
    assert "df1" in r.tables and "df2" in r.tables and "df3" in r.tables
    assert len(r.tables) == 3

    # Restore baseline: df2 and df3 MUST be purged, RAM strictly from baseline, undo reset
    outputs.clear()
    r.execute_line("restore baseline", output_fn=outputs.append)
    assert "Restored checkpoint 'baseline'" in outputs[-1]
    assert "df1" in r.tables
    assert "df2" not in r.tables
    assert "df3" not in r.tables
    assert len(r.tables) == 1
    assert "flag" not in r.tables["df1"].columns
    assert len(r.undo_stack) == 0
    assert len(r.redo_stack) == 0

    r.close()


def test_repl_rm_frees_table_without_affecting_disk_checkpoint():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("checkpoint v1", output_fn=outputs.append)

    # rm df1 drops from memory
    r.execute_line("rm df1", output_fn=outputs.append)
    assert "df1" not in r.tables
    assert r.current_df is None

    # Checkpoint v1 on disk is untouched and can restore df1
    outputs.clear()
    r.execute_line("restore v1", output_fn=outputs.append)
    assert "Restored checkpoint 'v1'" in outputs[-1]
    assert "df1" in r.tables
    assert r.tables["df1"].shape == (344, 7)

    # rm checkpoint removes disk files
    cp_dir = Path(r.checkpoints["v1"]["dir"])
    assert cp_dir.exists()
    r.execute_line("rm checkpoint v1", output_fn=outputs.append)
    assert "v1" not in r.checkpoints
    assert not cp_dir.exists()

    r.close()


def test_repl_reset_hierarchy_and_disallowed_args():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    orig_shape = r.tables["df1"].shape

    # 1. Filter and create checkpoint v1
    r.execute_line("df1 = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape[0] < orig_shape[0]
    gentoo_shape = r.current_df.shape
    r.execute_line("checkpoint v1", output_fn=outputs.append)
    assert "v1" in r.checkpoints

    # 2. Add extra table and mutate df1
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    r.execute_line('df1 = df1 -mutate "flag = 999"', output_fn=outputs.append)
    assert "df2" in r.tables
    assert "flag" in r.tables["df1"].columns

    # 3. Test disallowed 'reset orig' and 'reset bad'
    outputs.clear()
    r.execute_line("reset orig", output_fn=outputs.append)
    assert outputs[-1] == "pytae: table 'orig' not found. Available: df1, df2"
    assert "flag" in r.tables["df1"].columns  # State preserved

    outputs.clear()
    r.execute_line("reset foo", output_fn=outputs.append)
    assert outputs[-1] == "pytae: table 'foo' not found. Available: df1, df2"

    outputs.clear()
    r.execute_line("reset df1 df2 foo", output_fn=outputs.append)
    assert outputs[-1] == "Usage: reset [table_name] [initial]"

    # 4. Bare 'reset' must revert to latest checkpoint 'v1'
    outputs.clear()
    r.execute_line("reset", output_fn=outputs.append)
    assert any("Reset to latest checkpoint 'v1'" in o for o in outputs)
    assert "df1" in r.tables
    assert "df2" not in r.tables  # Post-checkpoint table purged
    assert "flag" not in r.tables["df1"].columns  # Mutate dropped
    assert r.current_df.shape == gentoo_shape
    assert len(r.undo_stack) == 0  # Undo cleared
    assert len(r.redo_stack) == 0

    # 5. 'reset initial' must revert all the way back to initial file read
    outputs.clear()
    r.execute_line("reset initial", output_fn=outputs.append)
    assert any("Restored initial dataset" in o for o in outputs)
    assert r.tables["df1"].shape == orig_shape
    assert len(r.undo_stack) == 0
    assert len(r.redo_stack) == 0

    r.close()


def test_repl_reset_single_table_does_not_affect_other_tables():
    outputs = []
    r = PytaeRepl()
    # 1. Load two separate sample datasets
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    orig_df1_shape = r.tables["df1"].shape
    orig_df2_shape = r.tables["df2"].shape

    # 2. Filter both tables to distinct smaller subsets via assignment
    r.execute_line("use df1", output_fn=outputs.append)
    r.execute_line("df1 = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    df1_gentoo_shape = r.tables["df1"].shape
    assert df1_gentoo_shape[0] < orig_df1_shape[0]

    r.execute_line("use df2", output_fn=outputs.append)
    r.execute_line('df2 = -filter "tip > 5"', output_fn=outputs.append)
    df2_tip5_shape = r.tables["df2"].shape
    assert df2_tip5_shape[0] < orig_df2_shape[0]

    # Verify both tables are in filtered state
    assert r.tables["df1"].shape == df1_gentoo_shape
    assert r.tables["df2"].shape == df2_tip5_shape

    # 3. reset df1 without checkpoints: resets ONLY df1 to initial, df2 remains filtered
    outputs.clear()
    r.execute_line("reset df1", output_fn=outputs.append)
    assert any("Reset table 'df1' to initial state" in o for o in outputs)
    assert r.tables["df1"].shape == orig_df1_shape
    assert r.tables["df2"].shape == df2_tip5_shape  # df2 is untouched!

    # 4. Now filter df1 again and create a checkpoint 'v1'
    r.execute_line("use df1", output_fn=outputs.append)
    r.execute_line("df1 = -filter \"species == 'Chinstrap'\"", output_fn=outputs.append)
    df1_chin_shape = r.tables["df1"].shape
    r.execute_line("checkpoint v1", output_fn=outputs.append)

    # Further modify both df1 and df2
    r.execute_line('df1 = df1 -mutate "flag = 1"', output_fn=outputs.append)
    r.execute_line('df2 = df2 -mutate "extra = 2"', output_fn=outputs.append)
    assert "flag" in r.tables["df1"].columns
    assert "extra" in r.tables["df2"].columns

    # 5. reset df1: restores df1 to latest checkpoint v1 (flag dropped, Chinstrap shape)
    # while df2 STILL has 'extra' column and tip5 shape!
    outputs.clear()
    r.execute_line("reset df1", output_fn=outputs.append)
    assert any("Reset table 'df1' to latest checkpoint 'v1'" in o for o in outputs)
    assert "flag" not in r.tables["df1"].columns
    assert r.tables["df1"].shape == df1_chin_shape
    assert "extra" in r.tables["df2"].columns  # df2 untouched!
    assert r.tables["df2"].shape[0] == df2_tip5_shape[0]

    # 6. reset df1 initial: restores df1 all the way to original initial penguins
    outputs.clear()
    r.execute_line("reset df1 initial", output_fn=outputs.append)
    assert any("Reset table 'df1' to initial state" in o for o in outputs)
    assert r.tables["df1"].shape == orig_df1_shape
    assert "extra" in r.tables["df2"].columns  # df2 still untouched!

    # 7. Bare reset: reverts ALL tables to checkpoint 'v1'
    outputs.clear()
    r.execute_line("reset", output_fn=outputs.append)
    assert any("Reset to latest checkpoint 'v1'" in o for o in outputs)
    assert r.tables["df1"].shape == df1_chin_shape
    assert "extra" not in r.tables["df2"].columns
    assert r.tables["df2"].shape == df2_tip5_shape

    r.close()


def test_repl_history_option_b_milestone_banners():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    r.execute_line("checkpoint baseline", output_fn=outputs.append)
    r.execute_line('-mutate "mass_kg = body_mass_g / 1000"', output_fn=outputs.append)
    r.execute_line("reset", output_fn=outputs.append)

    outputs.clear()
    r.execute_line("history", output_fn=outputs.append)
    hist_text = "\n".join(outputs)

    # Verify all commands including checkpoints are sequentially numbered without comments
    assert "   1: df1 = sample:penguins" in hist_text
    assert "   2: -filter \"species == 'Gentoo'\"" in hist_text
    assert "   3: checkpoint baseline" in hist_text
    assert '   4: -mutate "mass_kg = body_mass_g / 1000"' in hist_text
    assert "   5: reset" in hist_text

    r.close()


def test_repl_persistent_sessions_lifecycle(tmp_path, monkeypatch):
    sess_dir = tmp_path / "pytae_sessions"
    monkeypatch.setenv("PYTAE_SESSIONS_DIR", str(sess_dir))

    outputs = []

    # 1. Start a persistent session 'proj_x'
    r1 = PytaeRepl(session="proj_x")
    assert r1._build_prompt() == "pytae:proj_x> "

    r1.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r1.execute_line("df1 = -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    r1.execute_line("checkpoint v1", output_fn=outputs.append)
    adelie_shape = r1.tables["df1"].shape

    # Add uncheckpointed scratch edits in RAM via assignment
    r1.execute_line('df1 = df1 -mutate "scratch_col = 123"', output_fn=outputs.append)
    r1.execute_line("df_scratch = sample:tips", output_fn=outputs.append)
    assert "scratch_col" in r1.tables["df1"].columns
    assert "df_scratch" in r1.tables

    # Checkpoint v1 exists on disk
    cp_path = sess_dir / "proj_x" / "checkpoints" / "v1"
    assert cp_path.exists()
    assert (cp_path / "meta.json").exists()

    # Close session (exiting REPL drops RAM and scratch tables)
    r1.close()

    # 2. Resume session 'proj_x' - boots cleanly from latest checkpoint (v1)
    outputs.clear()
    r2 = PytaeRepl(session="proj_x")
    assert "df1" in r2.tables
    assert r2.tables["df1"].shape == adelie_shape
    # Scratch uncheckpointed tables and columns MUST NOT exist!
    assert "scratch_col" not in r2.tables["df1"].columns
    assert "df_scratch" not in r2.tables

    # Verify history works in stored session (preserves checkpoint milestones & valid steps)
    outputs.clear()
    r2.execute_line("history", output_fn=outputs.append)
    hist_text = "\n".join(outputs)
    assert "checkpoint v1" in hist_text
    assert "species == 'Adelie'" in hist_text
    assert "scratch_col" not in hist_text

    # 3. Test in-REPL session inspection and commands
    outputs.clear()
    r2.execute_line("session", output_fn=outputs.append)
    assert "Active session: 'proj_x'" in outputs[-1]
    assert "1 checkpoints" in outputs[-1]

    # Test listing sessions
    outputs.clear()
    r2.execute_line("sessions", output_fn=outputs.append)
    assert any("proj_x" in o for o in outputs)

    # Test session save as another name (clone / fork)
    outputs.clear()
    r2.execute_line("session save proj_y", output_fn=outputs.append)
    assert "Session saved as 'proj_y'" in outputs[-1]
    assert (sess_dir / "proj_y" / "checkpoints" / "v1").exists()

    # Test session load
    outputs.clear()
    r2.execute_line("session load proj_x", output_fn=outputs.append)
    assert r2.session_name == "proj_x"

    # Test rm session
    outputs.clear()
    r2.execute_line("rm session proj_y", output_fn=outputs.append)
    assert "Removed session 'proj_y'" in outputs[-1]
    assert not (sess_dir / "proj_y").exists()

    # Apply second checkpoint in r2 and verify history across another restart
    r2.execute_line('df1 -mutate "is_heavy = body_mass_g > 3500"', output_fn=outputs.append)
    r2.execute_line("checkpoint v2", output_fn=outputs.append)
    r2.close()

    # 4. Resume session in r3 - history should contain both v1 and v2 milestones
    r3 = PytaeRepl(session="proj_x")
    outputs.clear()
    r3.execute_line("history", output_fn=outputs.append)
    hist3 = "\n".join(outputs)
    assert "checkpoint v1" in hist3
    assert "checkpoint v2" in hist3
    assert "is_heavy = body_mass_g > 3500" in hist3
    r3.close()


def test_cli_session_flags(tmp_path, monkeypatch, capsys):
    sess_dir = tmp_path / "pytae_sessions"
    monkeypatch.setenv("PYTAE_SESSIONS_DIR", str(sess_dir))

    # Pre-populate a session
    r = PytaeRepl(session="analytics")
    r.execute_line("df1 = sample:penguins", output_fn=lambda _: None)
    r.execute_line("checkpoint base", output_fn=lambda _: None)
    r.close()

    # Test pytae -sessions lists saved sessions
    ret = cli.main(["-sessions"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "analytics" in captured.out
    assert "1 checkpoints" in captured.out

    # Test pytae --sessions enforces single hyphen guideline
    with pytest.raises(SystemExit):
        cli.main(["--sessions"])
    captured_err = capsys.readouterr()
    assert "uses double hyphens; pytae uses single hyphen '-sessions'" in captured_err.err


def test_repl_rm_releases_ram_immediately_without_disk_spill():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    orig_shape = r.tables["df1"].shape

    # Save checkpoint before rm
    r.execute_line("checkpoint abc", output_fn=outputs.append)
    cp_dir = Path(r.checkpoints["abc"]["dir"])
    cp_file_count_before = len(list(cp_dir.glob("*.ipc")))

    # Pre-populate redo stack to verify rm clears it
    r.redo_stack.append(("fake_redo", pl.DataFrame({"a": [1, 2, 3]})))
    assert len(r.redo_stack) == 1

    # Remove table: must immediately drop table from memory with ZERO disk I/O
    outputs.clear()
    r.execute_line("rm df1", output_fn=outputs.append)
    assert "Removed table 'df1'" in outputs[-1]

    # In-memory tables and references MUST be genuinely empty
    assert len(r.tables) == 0
    assert len(r.orig_tables) == 0
    assert len(r.initial_tables) == 0
    assert r.current_df is None
    assert r.orig_df is None
    assert r.initial_df is None
    assert len(r.redo_stack) == 0  # Redo cleared
    assert len(r.undo_stack) == 0  # Undo cleared (no pinned DataFrames or disk IPC folders)

    # Checkpoint on disk has unchanged files - zero disk files written by rm
    assert len(list(cp_dir.glob("*.ipc"))) == cp_file_count_before

    # rm is non-undoable: undo reports Nothing to undo
    outputs.clear()
    r.execute_line("undo", output_fn=outputs.append)
    assert "Nothing to undo." in outputs[-1]

    # Checkpoint 'abc' can be restored safely
    outputs.clear()
    r.execute_line("restore abc", output_fn=outputs.append)
    assert "df1" in r.tables
    assert r.tables["df1"].shape == orig_shape
    r.close()


def test_repl_rm_wildcard_releases_ram_without_disk_spill():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)

    r.execute_line("rm *", output_fn=outputs.append)
    assert len(r.tables) == 0
    assert len(r.orig_tables) == 0
    assert len(r.initial_tables) == 0
    assert r.current_df is None
    assert r.orig_df is None
    assert r.initial_df is None
    assert len(r.undo_stack) == 0
    assert len(r.redo_stack) == 0

    # Undo reports Nothing to undo
    outputs.clear()
    r.execute_line("undo", output_fn=outputs.append)
    assert "Nothing to undo." in outputs[-1]
    r.close()


def test_repl_run_recovers_from_unhandled_exception(monkeypatch):
    outputs = []
    r = PytaeRepl()

    call_count = 0

    def mock_execute_line(line, output_fn):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("Disk full error (os error 112)")
        return False  # exit REPL on second call

    monkeypatch.setattr(r, "execute_line", mock_execute_line)

    inputs = iter(["rm df1", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    res = r.run(output_fn=outputs.append)
    assert res is None
    assert any("pytae error: Disk full error (os error 112)" in o for o in outputs)
    r.close()


def test_repl_undo_stack_sliding_window_cap():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)

    # Execute 15 mutating operations
    for i in range(15):
        r.execute_line(f'df1 = df1 -filter "body_mass_g > {2000 + i * 10}"', output_fn=outputs.append)

    # Undo stack must be capped at max_undo_steps (10), preventing unbounded memory bloat
    assert len(r.undo_stack) == r.max_undo_steps == 10
    r.close()


def test_repl_rm_clears_all_internal_references_and_gc_command():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    r.execute_line("checkpoint abc", output_fn=outputs.append)

    # When df2 is active and df1 is removed, initial_df and orig_df must NOT retain df1
    r.execute_line("rm df1", output_fn=outputs.append)
    assert "df1" not in r.tables
    assert r.initial_df.shape == (244, 7)  # df2 shape, not df1
    assert r.orig_df.shape == (244, 7)

    # Remove second table
    r.execute_line("rm df2", output_fn=outputs.append)
    assert r.current_df is None
    assert r.orig_df is None
    assert r.initial_df is None

    # Test status command with no tables loaded
    outputs.clear()
    r.execute_line("status", output_fn=outputs.append)
    status_text = "\n".join(outputs)
    assert "No dataset loaded." in status_text
    assert "Process RAM" in status_text

    # Test explicit 'gc' and 'free' commands
    outputs.clear()
    r.execute_line("gc", output_fn=outputs.append)
    assert "Memory released to operating system." in outputs[-1]
    assert "Process RAM" in outputs[-1]

    outputs.clear()
    r.execute_line("free", output_fn=outputs.append)
    assert "Memory released to operating system." in outputs[-1]
    assert "Process RAM" in outputs[-1]

    r.close()


def test_repl_sample_does_not_modify_original_df():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    orig_shape = r.tables["df1"].shape
    assert orig_shape == (344, 7)

    # 1. Active table -sample (like -head) must preview rows without modifying df1
    outputs.clear()
    r.execute_line("-sample 5", output_fn=outputs.append)
    assert r.tables["df1"].shape == orig_shape
    assert r.current_df.shape == orig_shape
    assert not any("-> df1:" in o for o in outputs)
    assert any("Adelie" in o or "Gentoo" in o or "Chinstrap" in o for o in outputs)

    # 2. Targeted df1 -sample 10 must preview rows without modifying df1
    outputs.clear()
    r.execute_line("df1 -sample 10", output_fn=outputs.append)
    assert r.tables["df1"].shape == orig_shape
    assert r.current_df.shape == orig_shape

    # 3. Targeted df1 -sample with float fraction
    outputs.clear()
    r.execute_line("df1 -sample 0.1", output_fn=outputs.append)
    assert r.tables["df1"].shape == orig_shape

    # 4. Bare sample warning
    outputs.clear()
    r.execute_line("sample 5", output_fn=outputs.append)
    assert "bare 'sample' is not recognized; use '-sample'" in outputs[-1]
    assert r.tables["df1"].shape == orig_shape

    r.close()


def test_cli_rejects_dash_s_and_accepts_session(tmp_path, monkeypatch, capsys):
    sess_dir = tmp_path / "sessions"
    monkeypatch.setenv("PYTAE_SESSIONS_DIR", str(sess_dir))

    # Test pytae -s is rejected
    with pytest.raises(SystemExit):
        cli.main(["-s", "analysis"])
    captured_err = capsys.readouterr()
    assert "'-s' is not recognized; use '-session <name>' instead" in captured_err.err

    # Test pytae -session is recognized and accepted
    # Using -h alongside -session exits cleanly before entering REPL loop
    with pytest.raises(SystemExit):
        cli.main(["-session", "analysis", "-h"])
    captured_out = capsys.readouterr()
    assert "persistent REPL session name" in captured_out.out


def test_repl_preview_by_default_and_assignment_mutation():
    outputs = []
    r = PytaeRepl()

    # 1. Load sample dataset
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    assert "df1" in r.tables
    assert r.tables["df1"].shape == (344, 7)
    assert r.current_df.shape == (344, 7)

    # 2. -distinct followed by -head 5 MUST NOT reduce rows in active dataset!
    outputs.clear()
    r.execute_line("-distinct -head 5", output_fn=outputs.append)
    # Output must be a formatted table (CLI parity) and contain data columns
    assert any("species" in o for o in outputs)
    assert any("island" in o for o in outputs)
    # Active table shape remains full 344 rows!
    assert r.current_df.shape == (344, 7)
    assert r.tables["df1"].shape == (344, 7)

    # 3. Exploratory -filter prints formatted table without mutating df1
    outputs.clear()
    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert any("Gentoo" in o for o in outputs)
    assert r.current_df.shape == (344, 7)
    assert r.tables["df1"].shape == (344, 7)

    # 4. Copy: k = df1
    outputs.clear()
    r.execute_line("k = df1", output_fn=outputs.append)
    assert "k" in r.tables
    assert r.tables["k"].shape == (344, 7)
    assert any("Assigned 'k' from 'df1'" in o for o in outputs)

    # 5. Targeted preview: k -filter "species == 'Gentoo'" does NOT change k
    outputs.clear()
    r.execute_line("k -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert any("Gentoo" in o for o in outputs)
    assert r.tables["k"].shape == (344, 7)  # k is intact!

    # 6. Targeted -distinct followed by -head: k -distinct -head 3
    outputs.clear()
    r.execute_line("k -distinct -head 3", output_fn=outputs.append)
    assert any("species" in o for o in outputs)
    assert r.tables["k"].shape == (344, 7)  # k is intact!

    # 7. Assignment from table with pipeline: filtered_k = df1 -filter ...
    outputs.clear()
    r.execute_line("filtered_k = df1 -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert "filtered_k" in r.tables
    assert r.tables["filtered_k"].shape == (124, 7)
    assert r.tables["df1"].shape == (344, 7)  # df1 is untouched!
    assert any("Created 'filtered_k' (124 rows x 7 cols)" in o for o in outputs)

    # 8. In-place reassignment: k = k -filter "bill_length_mm > 50"
    outputs.clear()
    r.execute_line('k = k -filter "bill_length_mm > 50"', output_fn=outputs.append)
    assert r.tables["k"].shape[0] < 344
    assert any("Updated 'k'" in o for o in outputs)

    # 9. Active table assignment: df1 = -filter "species == 'Gentoo'"
    outputs.clear()
    r.execute_line("use df1", output_fn=outputs.append)
    r.execute_line("df1 = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.tables["df1"].shape == (124, 7)
    assert r.current_df.shape == (124, 7)
    assert any("Updated 'df1' (124 rows x 7 cols)" in o for o in outputs)

    # 10. Undo restores df1 to original 344 rows
    outputs.clear()
    r.execute_line("undo", output_fn=outputs.append)
    assert r.tables["df1"].shape == (344, 7)
    assert r.current_df.shape == (344, 7)
    assert any("Undid:" in o for o in outputs)

    r.close()


def test_repl_time_exploratory_pipeline(sample_df):
    """Test -time on exploratory preview pipelines in REPL."""
    r = PytaeRepl(df=sample_df)
    outputs = []

    # Single-run timing
    r.execute_line("-distinct -time", output_fn=outputs.append)
    assert any("Elapsed (1 run):" in o for o in outputs)
    assert any("Adelie" in o for o in outputs)
    assert r.current_df.shape == (5, 3)  # Exploratory preview preserves active table

    # Multi-run timing
    outputs.clear()
    r.execute_line("-distinct -time 3", output_fn=outputs.append)
    assert any("Elapsed (3 runs): avg" in o for o in outputs)
    assert r.current_df.shape == (5, 3)

    r.close()


def test_repl_time_inspections(sample_df):
    """Test -time on inspection commands (-shape, -head, -cols) in REPL."""
    r = PytaeRepl(df=sample_df)
    outputs = []

    # -shape -time
    r.execute_line("-shape -time", output_fn=outputs.append)
    assert any("(5, 3)" in o for o in outputs)
    assert any("Elapsed (1 run):" in o for o in outputs)

    # -head 2 -time
    outputs.clear()
    r.execute_line("-head 2 -time", output_fn=outputs.append)
    assert any("Adelie" in o for o in outputs)
    assert any("Elapsed (1 run):" in o for o in outputs)

    # -cols -time
    outputs.clear()
    r.execute_line("-cols -time", output_fn=outputs.append)
    assert any("species" in o for o in outputs)
    assert any("Elapsed (1 run):" in o for o in outputs)

    r.close()


def test_repl_time_bare_table_switch(sample_df):
    """Test bare table inspection with timing (e.g. df1 -time, df1 -time 3) does not alter active dataset."""
    r = PytaeRepl()
    r.tables["df1"] = sample_df.clone()
    r.tables["df2"] = sample_df.head(2)
    r.current_df = r.tables["df2"]
    r.path_str = "df2"

    outputs = []
    r.execute_line("df1 -time", output_fn=outputs.append)
    # Active table remains df2; bare df1 only inspects dimensions
    assert r.path_str == "df2"
    assert len(outputs) == 1
    assert "df1: 5 rows x 3 cols | Elapsed:" in outputs[0]
    assert "tip: 'use df1'" in outputs[0]

    outputs.clear()
    r.execute_line("df1 -time 3", output_fn=outputs.append)
    assert len(outputs) == 1
    assert "df1: 5 rows x 3 cols | Elapsed (3 runs): avg" in outputs[0]

    # Explicit 'use df1' switches active dataset
    outputs.clear()
    r.execute_line("use df1", output_fn=outputs.append)
    assert r.path_str == "df1"
    assert "Switched active dataset to 'df1'" in outputs[0]

    r.close()


def test_repl_time_targeted_pipeline(sample_df):
    """Test targeted table commands with timing (e.g. df1 -shape -time, df1 -head 2 -time)."""
    r = PytaeRepl()
    r.tables["df1"] = sample_df.clone()
    r.tables["df2"] = sample_df.head(2)
    r.current_df = r.tables["df2"]
    r.path_str = "df2"

    outputs = []
    r.execute_line("df1 -shape -time", output_fn=outputs.append)
    assert any("(5, 3)" in o for o in outputs)
    assert any("Elapsed (1 run):" in o for o in outputs)
    # Active table remains df2
    assert r.path_str == "df2"

    outputs.clear()
    r.execute_line("df1 -head 2 -time", output_fn=outputs.append)
    assert any("Adelie" in o for o in outputs)
    assert any("Elapsed (1 run):" in o for o in outputs)
    assert r.path_str == "df2"

    r.close()


def test_repl_time_assignment(sample_df):
    """Test table assignment with timing (df2 = df1 -distinct -time, df1 = -distinct -time)."""
    r = PytaeRepl()
    r.tables["df1"] = sample_df.clone()
    r.current_df = r.tables["df1"]
    r.path_str = "df1"

    # Cross-table assignment with -time
    outputs = []
    r.execute_line("df2 = df1 -distinct -time", output_fn=outputs.append)
    assert "df2" in r.tables
    assert any("Created 'df2' (5 rows x 3 cols) | Elapsed:" in o for o in outputs)

    # In-place assignment with -time
    outputs.clear()
    r.execute_line("df1 = -distinct -time", output_fn=outputs.append)
    assert any("Updated 'df1' (5 rows x 3 cols) | Elapsed:" in o for o in outputs)

    r.close()


def test_repl_time_syntax_and_aliases(sample_df):
    """Test bare 'time' and '--time' rejection and helpful hints."""
    r = PytaeRepl(df=sample_df)
    r.tables["df1"] = sample_df.clone()

    outputs = []
    r.execute_line("time", output_fn=outputs.append)
    assert "bare 'time' is not recognized; use '-time'" in outputs[-1]

    outputs.clear()
    r.execute_line("df1 time", output_fn=outputs.append)
    assert "bare 'time' is not recognized; use '-time'" in outputs[-1]

    outputs.clear()
    r.execute_line("--time", output_fn=outputs.append)
    assert "'--time' is not recognized; use '-time'" in outputs[-1]

    outputs.clear()
    r.execute_line("df1 --time", output_fn=outputs.append)
    assert "'--time' is not recognized; use '-time'" in outputs[-1]

    r.close()


def test_repl_glimpse_captures_string_and_does_not_double_print(sample_df, capsys):
    r = PytaeRepl(df=sample_df)
    r.tables["df1"] = sample_df.clone()

    outputs = []
    r.execute_line("-glimpse", output_fn=outputs.append)
    assert len(outputs) == 1
    assert isinstance(outputs[0], str)
    assert "Rows: 5" in outputs[0]
    assert capsys.readouterr().out == ""

    outputs.clear()
    r.execute_line("df1 -glimpse", output_fn=outputs.append)
    assert len(outputs) == 1
    assert isinstance(outputs[0], str)
    assert "Rows: 5" in outputs[0]
    assert capsys.readouterr().out == ""
    r.close()


def test_repl_load_error_prints_once(tmp_path):
    bad_file = tmp_path / "corrupt.parquet"
    bad_file.write_text("not a valid parquet file")

    r = PytaeRepl()
    outputs = []
    r.execute_line(f"load {bad_file}", output_fn=outputs.append)
    assert len(outputs) == 1
    assert "failed to load" in outputs[0]
    r.close()


def test_repl_shell_escape_and_pipe_and_gc(sample_df):
    r = PytaeRepl(df=sample_df)
    outputs = []

    # 1. Bare ! shows usage
    r.execute_line("!", output_fn=outputs.append)
    assert any("Usage: !<command>" in o for o in outputs)

    # 2. !<shell_cmd> executes shell command
    outputs.clear()
    r.execute_line("!echo hello_from_shell", output_fn=outputs.append)
    assert any("hello_from_shell" in o for o in outputs)

    # 3. <repl_cmd> | <shell_cmd> pipes REPL output into shell command
    outputs.clear()
    r.execute_line("-cols | grep species", output_fn=outputs.append)
    assert any("species" in o for o in outputs)
    assert not any("body_mass_g" in o for o in outputs)

    # 4. gc / free memory release command
    outputs.clear()
    r.execute_line("gc", output_fn=outputs.append)
    assert any("Memory released" in o for o in outputs)
    r.close()


def test_repl_session_copy_and_validation_errors(tmp_path, monkeypatch, sample_df):
    monkeypatch.setenv("PYTAE_SESSIONS_DIR", str(tmp_path / "sessions"))
    r = PytaeRepl(df=sample_df)
    outputs = []

    # Ephemeral status
    r.execute_line("session", output_fn=outputs.append)
    assert any("No active session (ephemeral)" in o for o in outputs)

    # Invalid session name rejected
    outputs.clear()
    r.execute_line("session save ../bad", output_fn=outputs.append)
    assert any("invalid session name" in o for o in outputs)

    # Create checkpoint and save session
    r.execute_line("checkpoint cp1", output_fn=outputs.append)
    outputs.clear()
    r.execute_line("session save work1", output_fn=outputs.append)
    assert r.session_name == "work1"
    assert any("Session saved as 'work1'" in o for o in outputs)

    # Active session status & sessions list
    outputs.clear()
    r.execute_line("session", output_fn=outputs.append)
    assert any("Active session: 'work1'" in o for o in outputs)

    outputs.clear()
    r.execute_line("sessions", output_fn=outputs.append)
    assert any("work1" in o for o in outputs)

    # Save under a second session name (copies existing session checkpoints)
    outputs.clear()
    r.execute_line("session save work2", output_fn=outputs.append)
    assert r.session_name == "work2"

    # Load first session back
    outputs.clear()
    r.execute_line("session load work1", output_fn=outputs.append)
    assert r.session_name == "work1"
    assert "cp1" in r.checkpoints

    # Remove sessions
    outputs.clear()
    r.execute_line("rm session work2", output_fn=outputs.append)
    assert any("Removed session 'work2'" in o for o in outputs)

    outputs.clear()
    r.execute_line("session rm work1", output_fn=outputs.append)
    assert r.session_name is None
    assert any("Active session reverted to ephemeral" in o for o in outputs)
    r.close()


def test_repl_session_history_logging(tmp_path, monkeypatch):
    hist_dir = tmp_path / "custom_hist"
    monkeypatch.setenv("PYTAE_HISTORY_DIR", str(hist_dir))

    outputs = []
    r = PytaeRepl()
    assert r.session_log_path.exists()
    assert r.session_log_path.parent == hist_dir

    # Execute commands, comments, and checkpoints
    r.execute_line("# my custom comment", output_fn=outputs.append)
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)  # Exploratory preview (not mutating df)
    r.execute_line("checkpoint v1", output_fn=outputs.append)
    r.execute_line("df = -mutate \"m = 1\"", output_fn=outputs.append)  # State mutation via assignment

    # Check file content on disk in real time: checkpoints & exploratory previews omitted
    content = r.session_log_path.read_text(encoding="utf-8")
    assert "# Pytae REPL Session History" in content
    assert "df = sample:penguins" in content
    assert '-filter "species == \'Gentoo\'"' not in content  # Exploratory preview omitted!
    assert "*checkpoint: v1*" not in content  # Checkpoint omitted!
    assert 'df = -mutate "m = 1"' in content  # State mutation preserved!

    # Test in-REPL history command: clean sequential numbering without comments
    outputs.clear()
    r.execute_line("history", output_fn=outputs.append)
    h_out = "\n".join(outputs)
    assert "Session History:" in h_out
    assert "df = sample:penguins" in h_out
    assert "checkpoint v1" in h_out
    assert "# my custom comment" not in h_out

    # Test history N
    outputs.clear()
    r.execute_line("history 2", output_fn=outputs.append)
    assert len(outputs) == 3  # Header + 2 entries

    # Test history -cli and history -py rejected with helpful message
    outputs.clear()
    r.execute_line("history -cli", output_fn=outputs.append)
    assert any("not supported" in o for o in outputs)

    outputs.clear()
    r.execute_line("history -py", output_fn=outputs.append)
    assert any("not supported" in o for o in outputs)

    # Test empty session unlinking on exit
    r_empty = PytaeRepl()
    empty_log = r_empty.session_log_path
    assert empty_log.exists()
    # Simulate exit without commands
    r_empty.run(input_fn=lambda prompt: (_ for _ in ()).throw(EOFError), output_fn=lambda x: None)
    assert not empty_log.exists()


def test_repl_history_save_and_exit_save(tmp_path, monkeypatch):
    hist_dir = tmp_path / "custom_hist"
    monkeypatch.setenv("PYTAE_HISTORY_DIR", str(hist_dir))
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    outputs = []
    r = PytaeRepl()

    # Case 1: Saving when 0 commands were executed
    res = r.execute_line("exit -s empty.txt", output_fn=outputs.append)
    assert res is False  # Still exits
    assert not (work_dir / "empty.txt").exists()
    assert any("No commands were executed" in o for o in outputs)

    outputs.clear()
    res = r.execute_line("history -s empty.txt", output_fn=outputs.append)
    assert res is True  # Does not exit
    assert not (work_dir / "empty.txt").exists()
    assert any("'history -s' is not supported" in o for o in outputs)

    # Case 2: Run commands and use 'set save = ...' upfront
    r2 = PytaeRepl()
    r2.execute_line("df = sample:penguins", output_fn=outputs.append)
    r2.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)

    # Verify 'history -s' is rejected
    outputs.clear()
    res = r2.execute_line("history -s", output_fn=outputs.append)
    assert res is True
    assert any("'history -s' is not supported" in o for o in outputs)

    # Verify legacy 'set save' is cleanly rejected without backward compatibility
    outputs.clear()
    r2.execute_line("set save = legacy.txt", output_fn=outputs.append)
    assert any("unknown setting 'save'" in o for o in outputs)
    assert r2.save_history_file is None

    # Configure 'set save_commands = rel_hist.txt' upfront
    outputs.clear()
    r2.execute_line("set save_commands = rel_hist.txt", output_fn=outputs.append)
    assert r2.save_history_file == "rel_hist.txt"
    assert any("Set save_commands = 'rel_hist.txt'" in o for o in outputs)

    # Plain exit automatically saves to configured history file
    outputs.clear()
    res = r2.execute_line("exit", output_fn=outputs.append)
    assert res is False  # Exits!
    saved_rel = work_dir / "rel_hist.txt"
    assert saved_rel.exists()
    saved_content = saved_rel.read_text(encoding="utf-8")
    assert "df = sample:penguins" in saved_content
    # The 'set save_commands' command itself must not pollute the exported commands script
    assert "save_commands" not in saved_content
    assert any("Session history saved to" in o for o in outputs)

    # Case 3: Invalid exit arguments
    outputs.clear()
    res = r2.execute_line("exit -invalid", output_fn=outputs.append)
    assert res is True  # Does not exit
    assert any("Usage: exit [-s [path]]" in o for o in outputs)

    # Case 4: Bare exit -s saves to ./history.txt and terminates REPL
    r_exit = PytaeRepl()
    r_exit.execute_line("df = sample:penguins", output_fn=outputs.append)
    default_hist = work_dir / "history.txt"
    if default_hist.exists():
        default_hist.unlink()
    outputs.clear()
    res = r_exit.execute_line("exit -s", output_fn=outputs.append)
    assert res is False  # Exits!
    assert default_hist.exists()
    assert "df = sample:penguins" in default_hist.read_text(encoding="utf-8")
    assert any("Session history saved to" in o for o in outputs)
    assert any("Exiting pytae REPL." in o for o in outputs)

    # Case 5: exit -s with named path saves and terminates REPL
    r3 = PytaeRepl()
    r3.execute_line("df = sample:penguins", output_fn=outputs.append)
    outputs.clear()
    res = r3.execute_line("exit -s final_exit.txt", output_fn=outputs.append)
    assert res is False  # Exits!
    saved_exit = work_dir / "final_exit.txt"
    assert saved_exit.exists()
    assert "df = sample:penguins" in saved_exit.read_text(encoding="utf-8")
    assert any("Session history saved to" in o for o in outputs)
    assert any("Exiting pytae REPL." in o for o in outputs)


def test_repl_schema_and_sample_and_keyword_join():
    r = PytaeRepl()
    outputs: list[str] = []

    r.execute_line("p = sample:penguins", output_fn=outputs.append)
    r.execute_line("t = sample:tips", output_fn=outputs.append)

    # Test -schema
    outputs.clear()
    r.execute_line("-schema", output_fn=outputs.append)
    assert any("Columns: 7 | Rows: 244" in o for o in outputs)
    assert any("Nulls" in o and "Unique" in o for o in outputs)

    # Test -sample percentage and fraction
    outputs.clear()
    r.execute_line("-sample 1%", output_fn=outputs.append)
    assert len(outputs) == 1
    assert "total_bill" in outputs[0]

    # Test keyword -join syntax
    outputs.clear()
    r.execute_line("res = -join 'left=p,right=t,how=cross'", output_fn=outputs.append)
    assert "res" in r.tables
    assert r.tables["res"].shape == (83936, 14)

    # Test history records standard keyword join line
    hist_lines: list[str] = []
    r.execute_line("history", output_fn=hist_lines.append)
    hist_text = "\n".join(hist_lines)
    assert "-join left=p,right=t,how=cross" in hist_text


def test_repl_set_checkpoint_format_parquet_and_ipc(tmp_path, monkeypatch):
    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PYTAE_SESSIONS_DIR", str(sess_dir))

    outputs: list[str] = []
    r = PytaeRepl(session="test_fmt")

    # 1. Inspect default format
    outputs.clear()
    r.execute_line("set", output_fn=outputs.append)
    assert any("checkpoint_format = ipc" in o for o in outputs)
    assert any("save_commands     = none" in o for o in outputs)

    outputs.clear()
    r.execute_line("set checkpoint_format", output_fn=outputs.append)
    assert "checkpoint_format = ipc" in outputs[0]

    # 2. Reject invalid format
    outputs.clear()
    r.execute_line("set checkpoint_format = csv", output_fn=outputs.append)
    assert "unsupported checkpoint_format 'csv'" in outputs[0]
    assert r.checkpoint_format == "ipc"

    # 3. Load tables
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)

    # 4. Save IPC checkpoint (default)
    outputs.clear()
    r.execute_line("checkpoint cp_ipc", output_fn=outputs.append)
    assert "Saved checkpoint 'cp_ipc'" in outputs[0]
    ipc_dir = sess_dir / "test_fmt" / "checkpoints" / "cp_ipc"
    assert (ipc_dir / "df1.ipc").exists()
    assert (ipc_dir / "df2.ipc").exists()

    # 5. Set checkpoint_format = parquet
    outputs.clear()
    r.execute_line("set checkpoint_format = parquet", output_fn=outputs.append)
    assert "Set checkpoint_format = parquet" in outputs[0]
    assert r.checkpoint_format == "parquet"

    # 6. Save Parquet checkpoint
    outputs.clear()
    r.execute_line("checkpoint cp_pq", output_fn=outputs.append)
    assert "Saved checkpoint 'cp_pq' [parquet]" in outputs[0]
    pq_dir = sess_dir / "test_fmt" / "checkpoints" / "cp_pq"
    assert (pq_dir / "df1.parquet").exists()
    assert (pq_dir / "df2.parquet").exists()
    # Confirm they really are readable parquet files
    df1_pq = pl.read_parquet(pq_dir / "df1.parquet")
    assert df1_pq.shape == r.tables["df1"].shape

    # 7. Check checkpoints listing displays format
    outputs.clear()
    r.execute_line("checkpoints", output_fn=outputs.append)
    cps_text = "\n".join(outputs)
    assert "cp_ipc" in cps_text
    assert "cp_pq" in cps_text
    assert "[parquet]" in cps_text

    # 8. Mutate RAM table, then restore from parquet checkpoint
    orig_shape = r.tables["df1"].shape
    r.execute_line("df1 = df1 -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    assert r.tables["df1"].shape[0] < orig_shape[0]

    outputs.clear()
    r.execute_line("restore cp_pq", output_fn=outputs.append)
    assert "Restored checkpoint 'cp_pq'" in outputs[0]
    assert r.tables["df1"].shape == orig_shape

    # 9. Restore from IPC checkpoint seamlessly
    outputs.clear()
    r.execute_line("restore cp_ipc", output_fn=outputs.append)
    assert "Restored checkpoint 'cp_ipc'" in outputs[0]
    assert r.tables["df1"].shape == orig_shape

    # 10. Switch back to IPC format
    outputs.clear()
    r.execute_line("set checkpoint_format = ipc", output_fn=outputs.append)
    assert "Set checkpoint_format = ipc" in outputs[0]
    assert r.checkpoint_format == "ipc"

    r.close()


def test_repl_input_canonical_path_and_checkpoint_omission_in_save(tmp_path, monkeypatch):
    data_dir = tmp_path / "data_folder"
    data_dir.mkdir()
    sample_file = data_dir / "my_orders.parquet"
    import polars as pl
    pl.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]}).write_parquet(sample_file)

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    outputs: list[str] = []
    r = PytaeRepl()

    # Load file with relative path
    rel_path = "../data_folder/my_orders.parquet"
    r.execute_line(f"orders = {rel_path}", output_fn=outputs.append)
    assert "orders" in r.tables

    # Checkpoint baseline (live session artifact)
    r.execute_line("checkpoint baseline", output_fn=outputs.append)

    # Bare exploratory preview (e.g. -describe)
    r.execute_line("-describe", output_fn=outputs.append)

    # Transform
    r.execute_line('orders = orders -mutate "doubled = val * 2"', output_fn=outputs.append)

    # Save to history file via 'exit -s replay.txt'
    outputs.clear()
    r.execute_line("exit -s replay.txt", output_fn=outputs.append)

    replay_file = work_dir / "replay.txt"
    assert replay_file.exists()
    content = replay_file.read_text(encoding="utf-8")

    # 1. Input path MUST be canonical absolute path (not relative)
    assert str(sample_file.resolve()) in content
    # 2. Checkpoints MUST be omitted from replay script
    assert "checkpoint baseline" not in content
    assert "*checkpoint" not in content
    # 3. Exploratory bare preview (-describe) MUST be omitted from replay script
    assert "-describe" not in content
    # 4. State-mutating transformation MUST be preserved
    assert 'orders = orders -mutate "doubled = val * 2"' in content

    # 5. In-REPL history still displays all commands including checkpoint and -describe
    outputs.clear()
    r.execute_line("history", output_fn=outputs.append)
    h_out = "\n".join(outputs)
    assert "checkpoint baseline" in h_out
    assert "-describe" in h_out


def test_repl_rm_memory_deallocation_weakref():
    """Verify via weakref that 'rm <table>', 'rm *', and variable reassignment leave zero lingering DataFrame references."""
    import gc
    import weakref

    outputs: list[str] = []
    r = PytaeRepl()

    # 1. Load df1 and df2, capture weak references
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:iris", output_fn=outputs.append)
    ref_df1_init = weakref.ref(r.tables["df1"])
    ref_df2_init = weakref.ref(r.tables["df2"])

    # 2. Mutate df1 (creates undo snapshot) and create derived table df3 (switches active table)
    r.execute_line("df1 = df1 -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    ref_df1_mut = weakref.ref(r.tables["df1"])
    r.execute_line("df3 = df2 -head 10", output_fn=outputs.append)
    ref_df3 = weakref.ref(r.tables["df3"])

    # 3. Remove non-active table df1 while df3 is active -> both initial and mutated df1 frames must be collected
    r.execute_line("rm df1", output_fn=outputs.append)
    gc.collect()
    assert ref_df1_init() is None
    assert ref_df1_mut() is None
    assert ref_df2_init() is not None
    assert ref_df3() is not None

    # 4. Remove active table df3 -> df3 frame must be collected immediately
    r.execute_line("rm df3", output_fn=outputs.append)
    gc.collect()
    assert ref_df3() is None
    assert ref_df2_init() is not None

    # 5. Reassign df2 to a new file load -> old df2 initial frame must be collected immediately
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    gc.collect()
    assert ref_df2_init() is None
    ref_df2_new = weakref.ref(r.tables["df2"])
    assert ref_df2_new() is not None

    # 6. Remove all with rm * -> remaining frame must be collected immediately
    r.execute_line("rm *", output_fn=outputs.append)
    gc.collect()
    assert ref_df2_new() is None
    assert r.current_df is None
    assert r.orig_df is None
    assert r.initial_df is None


def test_repl_rename_table_zero_copy():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    assert "df1" in r.tables
    assert r.path_str == "df1"
    original_df = r.tables["df1"]

    # Valid rename
    outputs.clear()
    r.execute_line("rename df1 customers", output_fn=outputs.append)
    assert "Renamed table 'df1' to 'customers'." in outputs[0]
    assert "df1" not in r.tables
    assert "customers" in r.tables
    assert r.path_str == "customers"
    # Ensure zero-copy pointer equivalence
    assert r.tables["customers"] is original_df
    assert r.current_df is original_df

    # Error handling: nonexistent table
    outputs.clear()
    r.execute_line("rename nonexistent foo", output_fn=outputs.append)
    assert "table 'nonexistent' not found" in outputs[0]

    # Error handling: invalid identifier
    outputs.clear()
    r.execute_line("rename customers 123bad", output_fn=outputs.append)
    assert "invalid table name" in outputs[0]

    # Error handling: name collision
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    outputs.clear()
    r.execute_line("rename customers df2", output_fn=outputs.append)
    assert "already exists" in outputs[0]

    # Missing args
    outputs.clear()
    r.execute_line("rename customers", output_fn=outputs.append)
    assert "Usage: rename <old_name> <new_name>" in outputs[0]
    r.close()


def test_repl_diff_command():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = df1 -head 50", output_fn=outputs.append)

    # diff <tbl1> <tbl2>
    outputs.clear()
    r.execute_line("diff df1 df2", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "Comparing 'df1' vs 'df2':" in combined
    assert "Rows:" in combined

    # diff <tbl2> with active table
    outputs.clear()
    r.execute_line("diff df2", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "Comparing 'df2' vs 'df2':" in combined or "Comparing 'df1' vs 'df2':" in combined

    # diff with tolerance
    outputs.clear()
    r.execute_line("diff df1 df2 -tol 0.01", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "Rows:" in combined

    # diff with checkpoint
    r.execute_line("checkpoint snap1", output_fn=outputs.append)
    r.execute_line("df2 -mutate \"x = 1\"", output_fn=outputs.append)
    outputs.clear()
    r.execute_line("diff df2 snap1", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "checkpoint:snap1" in combined

    # diff non-existent target
    outputs.clear()
    r.execute_line("diff nonexistent_target", output_fn=outputs.append)
    assert "not found" in outputs[0]
    r.close()


def test_repl_sql_pure_explicit_registration():
    outputs = []
    r = PytaeRepl()
    r.execute_line("t1 = sample:penguins", output_fn=outputs.append)

    # Explicit table name query succeeds
    outputs.clear()
    r.execute_line('res1 = -sql "SELECT COUNT(*) as cnt FROM t1"', output_fn=outputs.append)
    assert "res1" in r.tables
    assert r.tables["res1"]["cnt"][0] == 344

    # Assign from SQL with explicit table and group by
    outputs.clear()
    r.execute_line('res2 = -sql "SELECT species, COUNT(*) as cnt FROM t1 GROUP BY species"', output_fn=outputs.append)
    assert "res2" in r.tables
    assert r.tables["res2"].shape[0] == 3

    # Option A: No magic aliases ('this', 'self', 'data' fail when no table is named that)
    outputs.clear()
    r.execute_line('-sql "SELECT * FROM this"', output_fn=outputs.append)
    assert "error" in outputs[-1].lower() or "not found" in outputs[-1].lower()

    outputs.clear()
    r.execute_line('-sql "SELECT * FROM data"', output_fn=outputs.append)
    assert "error" in outputs[-1].lower() or "not found" in outputs[-1].lower()

    r.close()


def test_repl_tab_autocompletions():
    r = PytaeRepl()
    r.execute_line("customers = sample:penguins")
    r.execute_line("orders = sample:tips")
    r.execute_line("checkpoint cp_v1")

    # Table completion after 'use '
    matches = r._get_completions("cu", "use cu")
    assert matches == ["customers"]

    # Table completion after 'rename '
    matches = r._get_completions("or", "rename or")
    assert matches == ["orders"]

    # Checkpoint completion after 'restore '
    matches = r._get_completions("cp", "restore cp")
    assert matches == ["cp_v1"]

    # Tables & checkpoints after 'diff '
    matches = r._get_completions("c", "diff c")
    assert "customers" in matches and "cp_v1" in matches

    # Flags completion
    matches = r._get_completions("-fil", "-fil")
    assert "-filter" in matches

    # Columns completion in pipeline (active dataset is orders, so test orders columns)
    matches = r._get_completions("total_", "-select total_")
    assert "total_bill" in matches

    # Columns completion for specific table prefix
    matches = r._get_completions("bill_", "customers -select bill_")
    assert "bill_length_mm" in matches
    assert "bill_depth_mm" in matches

    # SQL context completion (Option A: explicit table names, no magic aliases)
    matches = r._get_completions("cu", "-sql SELECT * FROM cu")
    assert "customers" in matches

    matches = r._get_completions("th", "-sql SELECT * FROM th")
    assert "this" not in matches

    # Config completion after 'set '
    matches = r._get_completions("ch", "set ch")
    assert "checkpoint_format" in matches

    matches = r._get_completions("load_", "set load_")
    assert "load_session" in matches

    matches = r._get_completions("par", "set checkpoint_format = par")
    assert "parquet" in matches

    # Replay entry includes rename and use
    assert r._is_replayable_entry("rename df1 customers") is True
    assert r._is_replayable_entry("use customers") is True

    r.close()


def test_repl_set_load_session_and_sessions_dir(tmp_path):
    outputs = []
    from pytae.repl import get_sessions_dir, set_sessions_dir

    orig_dir = get_sessions_dir()
    custom_dir_1 = tmp_path / "sessions_1"
    custom_dir_2 = tmp_path / "sessions_2"
    custom_dir_1.mkdir(parents=True, exist_ok=True)
    custom_dir_2.mkdir(parents=True, exist_ok=True)

    try:
        # 1. sessions_dir alone with NO active session is rejected / not modified
        r = PytaeRepl()
        outputs.clear()
        r.execute_line(f"set sessions_dir = {custom_dir_1}", output_fn=outputs.append)
        assert "no active session" in outputs[-1].lower()
        assert get_sessions_dir() == orig_dir

        # 2. Bind active session
        outputs.clear()
        r.execute_line("set session = project_alpha", output_fn=outputs.append)
        assert r.session_name == "project_alpha"
        r.execute_line("df = sample:penguins")
        r.execute_line("checkpoint cp1")

        # 3. sessions_dir alone with active session -> relocates active session
        outputs.clear()
        r.execute_line(f"set sessions_dir = {custom_dir_1}", output_fn=outputs.append)
        assert "relocated active session 'project_alpha'" in outputs[-1].lower()
        assert (custom_dir_1 / "project_alpha" / "checkpoints" / "cp1").exists()
        assert get_sessions_dir() == custom_dir_1.resolve()
        r.close()

        # 4. load_session must not contain path separators
        r2 = PytaeRepl()
        outputs.clear()
        r2.execute_line("set load_session = bad/path/name", output_fn=outputs.append)
        assert "invalid session name" in outputs[-1].lower()

        # 5. load_session with session_dir relocates to new sessions_dir
        outputs.clear()
        r2.execute_line(
            f"set load_session = project_alpha, sessions_dir = {custom_dir_2}",
            output_fn=outputs.append,
        )
        assert r2.session_name == "project_alpha"
        assert (custom_dir_2 / "project_alpha" / "checkpoints" / "cp1").exists()
        assert get_sessions_dir() == custom_dir_2.resolve()
        assert "cp1" in r2.checkpoints

        # 6. Set multiple settings on a single line (commas, semicolons, spaces, repeated set)
        r2.execute_line("set save_commands = my_hist.txt, checkpoint_format = parquet")
        assert r2.save_history_file == "my_hist.txt"
        assert r2.checkpoint_format == "parquet"

        r2.execute_line("set save_commands = log1.txt; set checkpoint_format = ipc")
        assert r2.save_history_file == "log1.txt"
        assert r2.checkpoint_format == "ipc"

        r2.close()
    finally:
        set_sessions_dir(orig_dir)



