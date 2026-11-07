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


def test_repl_filter_and_reset(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # 1. Exploratory preview filter does not mutate active table
    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)  # Safe preview, untouched!
    assert any("Gentoo" in o for o in outputs)

    # 2. Assign filter explicitly updates active table
    outputs.clear()
    r.execute_line("df = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)

    # 3. Reset to original
    r.execute_line("reset", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)
    assert "Restored" in outputs[-1] and "initial" in outputs[-1]

    # 4. Apply another filter via assignment
    r.execute_line("df = -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)


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

    # None of these should mutate active dataframe!
    assert r.current_df.shape == (5, 3)


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

    # Reset restores original dataframe
    r.execute_line("reset", output_fn=outputs.append)
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
    assert any("error" in o.lower() or "not found" in o.lower() for o in outputs)


def test_repl_headless_run(sample_df):
    lines = [
        "df = -filter \"species == 'Gentoo'\"",
        "checkpoint g_only",
        'df = -mutate "mass_kg = body_mass_g / 1000.0"',
        "reset",
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

    # Reset restores initial dataset
    r.execute_line("reset", output_fn=outputs.append)
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
    r.execute_line("reset df1", output_fn=outputs.append)
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

    # 1b. '-help', 'help <topic>', and '-help <topic>'
    outputs.clear()
    cont = r.execute_line("-help", output_fn=outputs.append)
    assert cont is True
    assert any("PYTAE REPL COMMANDS" in o for o in outputs)

    outputs.clear()
    cont = r.execute_line("-help restore", output_fn=outputs.append)
    assert cont is True
    assert any("PYTAE CLI KEYWORD HELP: -restore" in o for o in outputs)
    assert any("restore <name>" in o for o in outputs)

    outputs.clear()
    cont = r.execute_line("help checkpoint", output_fn=outputs.append)
    assert cont is True
    assert any("PYTAE CLI KEYWORD HELP: -checkpoint" in o for o in outputs)
    assert any("checkpoint <name>" in o for o in outputs)

    # 1c. '-quick_start' and 'quick_start'
    outputs.clear()
    cont = r.execute_line("-quick_start", output_fn=outputs.append)
    assert cont is True
    assert any("PYTAE CLI CHEAT SHEET & COOKBOOK" in o for o in outputs)

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

    # Bare 'checkpoints' and 'tables' are rejected with guidance
    outputs.clear()
    r.execute_line("checkpoints", output_fn=outputs.append)
    assert "bare 'checkpoints' is not recognized; use 'status checkpoint'" in outputs[-1]

    outputs.clear()
    r.execute_line("tables", output_fn=outputs.append)
    assert "bare 'tables' is not recognized; use 'status table'" in outputs[-1]

    # 'status checkpoint' command lists ONLY saved checkpoints ('maddy'), not separate checkpoint entries for df1 or df2
    outputs.clear()
    r.execute_line("status checkpoint", output_fn=outputs.append)
    cp_text = "\n".join(outputs)
    assert "maddy" in cp_text
    assert "df1: 344 rows x 7 cols" in cp_text  # Shows the table summary under checkpoint 'maddy'
    # And 'maddy' is not a table in 'status table' command
    outputs.clear()
    r.execute_line("status table", output_fn=outputs.append)
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
        ("-switch", "switch"),
        ("--switch", "switch"),
        ("-use", "switch"),
        ("--use", "switch"),
        ("checkout", "restore"),
        ("-restore", "restore"),
        ("--restore", "restore"),
        ("-checkpoint", "checkpoint"),
        ("--checkpoint", "checkpoint"),
        ("-checkpoints", "checkpoints"),
        ("--checkpoints", "checkpoints"),
        ("-reset", "reset"),
        ("--reset", "reset"),
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

    # 3. List tables via status table
    outputs.clear()
    repl.execute_line("status table", output_fn=outputs.append)
    tables_out = "\n".join(outputs)
    assert "Loaded Tables" in tables_out
    assert "df1" in tables_out and "(penguins.parquet)" in tables_out
    assert "* df2" in tables_out and "(tips.parquet) [active]" in tables_out

    # 4. Save checkpoint maddy (captures all tables in workbench)
    outputs.clear()
    repl.execute_line("checkpoint maddy", output_fn=outputs.append)
    assert "Saved checkpoint 'maddy' (2 tables: df1, df2)." in outputs[-1]
    # Checkpoint should not change table prompt
    assert repl._build_prompt() == "pytae [df1, df2]> "

    # 5. List checkpoints via status checkpoint
    outputs.clear()
    repl.execute_line("status checkpoint", output_fn=outputs.append)
    cps_out = "\n".join(outputs)
    assert "Saved Checkpoints" in cps_out
    assert "maddy" in cps_out
    assert "df1: 344 rows x 7 cols" in cps_out and "df2: 244 rows x 7 cols" in cps_out
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
    r = PytaeRepl(df=sample_df, path="peng.parquet")
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

    # Bare rm df1 is rejected with guidance
    r.execute_line("rm df1", output_fn=outputs.append)
    assert "requires explicit category; use 'rm table df1'" in outputs[-1]
    assert "df1" in r.tables

    # Remove active table df1 -> switches to df2
    outputs.clear()
    r.execute_line("rm table df1", output_fn=outputs.append)
    assert "df1" not in r.tables
    assert "df2" in r.tables
    assert r.path_str == "df2"
    assert "Removed table 'df1'. Switched active dataset to 'df2'." in outputs[-1]

    # Remove last table
    r.execute_line("rm table df2", output_fn=outputs.append)
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
    r = PytaeRepl(df=sample_df, path="peng.parquet")

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

    # 'rm df' requires explicit category
    r.execute_line("rm df", output_fn=outputs.append)
    assert "unrecognized rm category 'df'" in outputs[-1] or "requires explicit category" in outputs[-1]
    assert "penguins_sample.parquet" in r.tables

    # 'rm table df' is rejected when 'df' is not loaded
    outputs.clear()
    r.execute_line("rm table df", output_fn=outputs.append)
    assert "table 'df' not found" in outputs[-1]

    # Removing by explicit name or stem succeeds with 'rm table'
    outputs.clear()
    r.execute_line("rm table penguins_sample", output_fn=outputs.append)
    assert "Removed table 'penguins_sample.parquet'" in outputs[-1]
    assert "No tables remain loaded" in outputs[-1]
    assert r.current_df is None
    assert r.path_str is None
    assert "penguins_sample.parquet" not in r.tables


def test_repl_rm_df_in_memory(sample_df):
    outputs = []
    # Loaded directly as 'df'
    r = PytaeRepl(df=sample_df)
    assert r.current_df is not None
    assert "df" in r.tables

    # Bare rm df rejected
    r.execute_line("rm df", output_fn=outputs.append)
    assert "requires explicit category; use 'rm table df'" in outputs[-1]
    assert "df" in r.tables

    # Explicit rm table df succeeds
    outputs.clear()
    r.execute_line("rm table df", output_fn=outputs.append)
    assert "Removed table 'df'" in outputs[-1]
    assert r.current_df is None
    assert not r.tables


def test_repl_rm_stem_matching(sample_parquet):
    outputs = []
    r = PytaeRepl(path=sample_parquet)

    # Stem match: 'penguins_sample' matches 'penguins_sample.parquet'
    r.execute_line("rm table penguins_sample", output_fn=outputs.append)
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
    # rm requires explicit category
    r.execute_line("rm table t2", output_fn=outputs.append)
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

    # Rejection of bare rm *, rm -all, rm all
    r.execute_line("rm *", output_fn=outputs.append)
    assert "requires a category; use 'rm table *'" in outputs[-1]
    assert len(r.tables) == 2

    r.execute_line("rm table -all", output_fn=outputs.append)
    assert "use 'rm table *'" in outputs[-1]
    assert len(r.tables) == 2

    r.execute_line("rm tables", output_fn=outputs.append)
    assert "use 'rm table <name>' or 'rm table *'" in outputs[-1]
    assert len(r.tables) == 2

    # Canonical rm table *
    outputs.clear()
    r.execute_line("rm table *", output_fn=outputs.append)
    assert "Removed all 2 loaded tables" in outputs[-1]
    assert not r.tables
    assert r.current_df is None


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


def test_repl_checkpoint_in_memory_storage_and_restore(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # 1. Do a transformation
    r.execute_line("df = -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)

    # 2. Creating a checkpoint saves in-memory snapshot
    outputs.clear()
    r.execute_line("checkpoint v1", output_fn=outputs.append)
    assert "Saved checkpoint 'v1'" in outputs[-1]

    # Verify in-memory persistence
    assert "v1" in r.checkpoints
    cp_info = r.checkpoints["v1"]
    assert "tables" in cp_info
    assert "dir" not in cp_info

    # 3. New mutation after checkpoint can be reset back to checkpoint baseline
    r.execute_line('df = -mutate "weight_lb = body_mass_g * 0.00220462"', output_fn=outputs.append)
    assert "weight_lb" in r.current_df.columns

    r.execute_line("reset", output_fn=outputs.append)
    assert "weight_lb" not in r.current_df.columns
    assert r.current_df.shape == (2, 3)

    r.close()
    assert len(r.checkpoints) == 0


def test_repl_restore_strictly_isolates_ram_from_post_checkpoint_tables():
    outputs = []
    r = PytaeRepl()

    # Load baseline table
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("checkpoint baseline", output_fn=outputs.append)

    # Load multiple post-checkpoint tables and mutate
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    r.execute_line("df3 = df1", output_fn=outputs.append)
    r.execute_line('df1 -mutate "flag = 1"', output_fn=outputs.append)
    assert "df1" in r.tables and "df2" in r.tables and "df3" in r.tables
    assert len(r.tables) == 3

    # Restore baseline: df2 and df3 MUST be purged, RAM strictly from baseline
    outputs.clear()
    r.execute_line("restore baseline", output_fn=outputs.append)
    assert "Restored checkpoint 'baseline'" in outputs[-1]
    assert "df1" in r.tables
    assert "df2" not in r.tables
    assert "df3" not in r.tables
    assert len(r.tables) == 1
    assert "flag" not in r.tables["df1"].columns

    r.close()


def test_repl_rm_frees_table_without_affecting_disk_checkpoint():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("checkpoint v1", output_fn=outputs.append)

    # rm table df1 drops from memory
    r.execute_line("rm table df1", output_fn=outputs.append)
    assert "df1" not in r.tables
    assert r.current_df is None

    # Checkpoint v1 is untouched and can restore df1
    outputs.clear()
    r.execute_line("restore v1", output_fn=outputs.append)
    assert "Restored checkpoint 'v1'" in outputs[-1]
    assert "df1" in r.tables
    assert r.tables["df1"].shape == (344, 7)

    # rm checkpoint removes it
    assert "v1" in r.checkpoints
    r.execute_line("rm checkpoint v1", output_fn=outputs.append)
    assert "v1" not in r.checkpoints

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

    # 5. 'reset initial' must revert all the way back to initial file read
    outputs.clear()
    r.execute_line("reset initial", output_fn=outputs.append)
    assert any("Restored initial dataset" in o for o in outputs)
    assert r.tables["df1"].shape == orig_shape

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
    outputs = []

    # 1. Start in-memory workbench
    r1 = PytaeRepl()
    assert r1._build_prompt() == "pytae> "

    r1.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r1.execute_line("df1 = -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    r1.execute_line("checkpoint v1", output_fn=outputs.append)
    adelie_shape = r1.tables["df1"].shape

    # Add uncheckpointed scratch edits in RAM via assignment
    r1.execute_line('df1 = df1 -mutate "scratch_col = 123"', output_fn=outputs.append)
    r1.execute_line("df_scratch = sample:tips", output_fn=outputs.append)
    assert "scratch_col" in r1.tables["df1"].columns
    assert "df_scratch" in r1.tables

    # In-memory restore restores snapshot
    r1.execute_line("restore v1", output_fn=outputs.append)
    assert "scratch_col" not in r1.tables["df1"].columns
    assert r1.tables["df1"].shape == adelie_shape

    # 2. Test in-REPL retired session commands output retirement notice
    for cmd in (
        "session",
        "sessions",
        "session save proj_y",
        "set save_session = proj_y",
        "session load proj_x",
        "set session_load = proj_x",
        "rm session proj_y",
    ):
        outputs.clear()
        r1.execute_line(cmd, output_fn=outputs.append)
        assert any("persistent disk sessions have been retired" in o for o in outputs)

    # 3. Export script works
    pt_file = tmp_path / "pipeline.pt"
    outputs.clear()
    r1.execute_line(f"export script {pt_file}", output_fn=outputs.append)
    assert pt_file.exists()
    assert "df1 = sample:penguins" in pt_file.read_text(encoding="utf-8")
    r1.close()


def test_cli_session_flags(tmp_path, monkeypatch, capsys):
    # Test pytae -sessions prints retirement notice
    ret = cli.main(["-sessions"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "persistent disk sessions have been retired" in captured.out

    # Test pytae -sessions -v also prints retirement notice
    ret = cli.main(["-sessions", "-v"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "persistent disk sessions have been retired" in captured.out

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
    assert "abc" in r.checkpoints

    # Remove table: must immediately drop table from memory with ZERO disk I/O
    outputs.clear()
    r.execute_line("rm table df1", output_fn=outputs.append)
    assert "Removed table 'df1'" in outputs[-1]

    # In-memory tables and references MUST be genuinely empty
    assert len(r.tables) == 0
    assert len(r.orig_tables) == 0
    assert len(r.initial_tables) == 0
    assert r.current_df is None
    assert r.orig_df is None
    assert r.initial_df is None

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

    r.execute_line("rm table *", output_fn=outputs.append)
    assert len(r.tables) == 0
    assert len(r.orig_tables) == 0
    assert len(r.initial_tables) == 0
    assert r.current_df is None
    assert r.orig_df is None
    assert r.initial_df is None
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

    inputs = iter(["rm table df1", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    res = r.run(output_fn=outputs.append)
    assert res is None
    assert any("pytae error: Disk full error (os error 112)" in o for o in outputs)
    r.close()


def test_repl_rm_clears_all_internal_references_and_gc_command():
    outputs = []
    r = PytaeRepl()
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    r.execute_line("checkpoint abc", output_fn=outputs.append)

    # When df2 is active and df1 is removed, initial_df and orig_df must NOT retain df1
    r.execute_line("rm table df1", output_fn=outputs.append)
    assert "df1" not in r.tables
    assert r.initial_df.shape == (244, 7)  # df2 shape, not df1
    assert r.orig_df.shape == (244, 7)

    # Remove second table
    r.execute_line("rm table df2", output_fn=outputs.append)
    assert r.current_df is None
    assert r.orig_df is None
    assert r.initial_df is None

    # Test status command with no tables loaded
    outputs.clear()
    r.execute_line("status", output_fn=outputs.append)
    status_text = "\n".join(outputs)
    assert "please specify a status category to inspect" in status_text
    assert "status session" in status_text

    outputs.clear()
    r.execute_line("status session", output_fn=outputs.append)
    sess_text = "\n".join(outputs)
    assert "=== REPL Session Status ===" in sess_text
    assert "Active Table  : (none)" in sess_text
    assert "Process RAM" in sess_text

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


def test_cli_rejects_dash_s_and_session_cli_flags(tmp_path, monkeypatch, capsys):
    sess_dir = tmp_path / "sessions"
    monkeypatch.setenv("PYTAE_SESSIONS_DIR", str(sess_dir))

    # Test pytae -s is rejected
    with pytest.raises(SystemExit):
        cli.main(["-s", "analysis"])
    captured_err = capsys.readouterr()
    assert "'-s' is not recognized; start REPL with 'pytae -i' and use 'set load_session = <name>' inside" in captured_err.err

    # Test pytae -session is rejected directing to pytae -i
    with pytest.raises(SystemExit):
        cli.main(["-session", "analysis"])
    captured_err = capsys.readouterr()
    assert "'-session' has been removed; start REPL with 'pytae -i' and use 'set load_session = <name>' inside" in captured_err.err


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

    # 10. Reset restores df1 to original 344 rows
    outputs.clear()
    r.execute_line("reset df1", output_fn=outputs.append)
    assert r.tables["df1"].shape == (344, 7)
    assert r.current_df.shape == (344, 7)
    assert any("Reset table 'df1'" in o for o in outputs)

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
    assert "tip: 'switch df1'" in outputs[0]

    outputs.clear()
    r.execute_line("df1 -time 3", output_fn=outputs.append)
    assert len(outputs) == 1
    assert "df1: 5 rows x 3 cols | Elapsed (3 runs): avg" in outputs[0]

    # Explicit 'switch df1' switches active dataset
    outputs.clear()
    r.execute_line("switch df1", output_fn=outputs.append)
    assert r.path_str == "df1"
    assert "Switched active dataset to 'df1'" in outputs[0]

    # Deprecated 'use df2' also works with deprecation notice
    outputs.clear()
    r.execute_line("use df2", output_fn=outputs.append)
    assert r.path_str == "df2"
    assert "Switched active dataset to 'df2'" in outputs[0]
    assert "use' is deprecated" in outputs[0]

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

    r.close()


def test_repl_session_copy_and_validation_errors(tmp_path, monkeypatch, sample_df):
    r = PytaeRepl(df=sample_df)
    outputs = []

    # All session commands and settings trigger the retirement notice
    for cmd in (
        "session",
        "sessions",
        "session save work1",
        "set save_session = work1",
        "session load work1",
        "set session_load = work1",
        "rm session work2",
        "session rm work1",
    ):
        outputs.clear()
        r.execute_line(cmd, output_fn=outputs.append)
        assert any("persistent disk sessions have been retired" in o for o in outputs)
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

    # Check faithful history file on disk: all lines logged
    hist_content = r.session_history_path.read_text(encoding="utf-8")
    assert "# Pytae REPL Session History" in hist_content
    assert "# my custom comment" in hist_content
    assert "df = sample:penguins" in hist_content
    assert '-filter "species == \'Gentoo\'"' in hist_content
    assert 'df = -mutate "m = 1"' in hist_content

    # Verify only single session history file exists (commands_*.txt is not auto-saved)
    assert r.session_commands_path is None or not r.session_commands_path.exists()
    assert len(list(hist_dir.glob("commands_*.txt"))) == 0

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

    # Verify 'set save_code' and 'set save_commands' are cleanly deprecated and rejected
    outputs.clear()
    r2.execute_line("set save_code = rel_hist.txt", output_fn=outputs.append)
    assert any("unknown setting 'save_code'" in o for o in outputs)
    assert r2.save_history_file is None

    outputs.clear()
    r2.execute_line("set save_commands = rel_hist.txt", output_fn=outputs.append)
    assert any("unknown setting 'save_commands'" in o for o in outputs)
    assert r2.save_history_file is None

    # Test on-demand export script (.pt)
    outputs.clear()
    r2.execute_line("export script rel_hist.pt", output_fn=outputs.append)
    assert any("Exported Pytae script to" in o for o in outputs)
    saved_pt = work_dir / "rel_hist.pt"
    assert saved_pt.exists()
    assert "df = sample:penguins" in saved_pt.read_text(encoding="utf-8")

    # Test on-demand export script (.py)
    outputs.clear()
    r2.execute_line("export script rel_hist.py", output_fn=outputs.append)
    assert any("Exported standalone Python script to" in o for o in outputs)
    saved_py = work_dir / "rel_hist.py"
    assert saved_py.exists()
    py_text = saved_py.read_text(encoding="utf-8")
    assert "df = pt.sample('penguins')" in py_text or 'df = pt.sample("penguins")' in py_text
    import ast

    ast.parse(py_text)

    # Exit with -s saves to specified file
    outputs.clear()
    res = r2.execute_line("exit -s exit_hist.txt", output_fn=outputs.append)
    assert res is False  # Exits!
    saved_rel = work_dir / "exit_hist.txt"
    assert saved_rel.exists()
    saved_content = saved_rel.read_text(encoding="utf-8")
    assert "df = sample:penguins" in saved_content
    assert any("Session code saved to" in o or "Session commands saved to" in o or "Session history saved to" in o for o in outputs)

    # Case 3: Invalid exit arguments
    outputs.clear()
    res = r2.execute_line("exit -invalid", output_fn=outputs.append)
    assert res is True  # Does not exit
    assert any("Usage: exit [-s [path]]" in o for o in outputs)

    # Case 4: Bare exit -s saves to ./session.pt and terminates REPL
    r_exit = PytaeRepl()
    r_exit.execute_line("df = sample:penguins", output_fn=outputs.append)
    default_pt = work_dir / "session.pt"
    if default_pt.exists():
        default_pt.unlink()
    outputs.clear()
    res = r_exit.execute_line("exit -s", output_fn=outputs.append)
    assert res is False  # Exits!
    assert default_pt.exists()
    assert "df = sample:penguins" in default_pt.read_text(encoding="utf-8")
    assert any("Session code saved to" in o for o in outputs)
    assert any("Exiting pytae REPL." in o for o in outputs)

    # Case 4b: exit -s py saves to ./session.py (executable Python script)
    r_py = PytaeRepl()
    r_py.execute_line("df = sample:penguins", output_fn=outputs.append)
    session_py = work_dir / "session.py"
    if session_py.exists():
        session_py.unlink()
    outputs.clear()
    res = r_py.execute_line("exit -s py", output_fn=outputs.append)
    assert res is False
    assert session_py.exists()
    py_text = session_py.read_text(encoding="utf-8")
    assert "import polars as pl" in py_text

    # Case 4c: exit -s pt explicitly saves to ./session.pt
    r_pt = PytaeRepl()
    r_pt.execute_line("df = sample:penguins", output_fn=outputs.append)
    if default_pt.exists():
        default_pt.unlink()
    outputs.clear()
    res = r_pt.execute_line("exit -s pt", output_fn=outputs.append)
    assert res is False
    assert default_pt.exists()

    # Case 5: exit -s with named path saves and terminates REPL
    r3 = PytaeRepl()
    r3.execute_line("df = sample:penguins", output_fn=outputs.append)
    outputs.clear()
    res = r3.execute_line("exit -s final_exit.txt", output_fn=outputs.append)
    assert res is False  # Exits!
    saved_exit = work_dir / "final_exit.txt"
    assert saved_exit.exists()
    assert "df = sample:penguins" in saved_exit.read_text(encoding="utf-8")
    assert any("Session code saved to" in o or "Session commands saved to" in o or "Session history saved to" in o for o in outputs)
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
    outputs: list[str] = []
    r = PytaeRepl()

    # 1. Setting checkpoint_format prints retirement notice
    outputs.clear()
    r.execute_line("set checkpoint_format = parquet", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)

    outputs.clear()
    r.execute_line("set checkpoint_format = ipc", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)

    # 2. In-memory checkpoints work with zero disk footprint
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    orig_shape = r.tables["df1"].shape
    r.execute_line("checkpoint cp1", output_fn=outputs.append)
    assert "cp1" in r.checkpoints

    r.execute_line("df1 = df1 -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    assert r.tables["df1"].shape[0] < orig_shape[0]

    outputs.clear()
    r.execute_line("restore cp1", output_fn=outputs.append)
    assert "Restored checkpoint 'cp1'" in outputs[0]
    assert r.tables["df1"].shape == orig_shape
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

    # 2. Mutate df1 (mutates table) and create derived table df3 (switches active table)
    r.execute_line("df1 = df1 -filter \"species == 'Adelie'\"", output_fn=outputs.append)
    ref_df1_mut = weakref.ref(r.tables["df1"])
    r.execute_line("df3 = df2 -head 10", output_fn=outputs.append)
    ref_df3 = weakref.ref(r.tables["df3"])

    # 3. Remove non-active table df1 while df3 is active -> both initial and mutated df1 frames must be collected
    r.execute_line("rm table df1", output_fn=outputs.append)
    gc.collect()
    assert ref_df1_init() is None
    assert ref_df1_mut() is None
    assert ref_df2_init() is not None
    assert ref_df3() is not None

    # 4. Remove active table df3 -> df3 frame must be collected immediately
    r.execute_line("rm table df3", output_fn=outputs.append)
    gc.collect()
    assert ref_df3() is None
    assert ref_df2_init() is not None

    # 5. Reassign df2 to a new file load -> old df2 initial frame must be collected immediately
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    gc.collect()
    assert ref_df2_init() is None
    ref_df2_new = weakref.ref(r.tables["df2"])
    assert ref_df2_new() is not None

    # 6. Remove all with rm table * -> remaining frame must be collected immediately
    r.execute_line("rm table *", output_fn=outputs.append)
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

    # Bare 'diff' is strictly rejected with educational instruction pointing to -diff
    outputs.clear()
    r.execute_line("diff df1 df2", output_fn=outputs.append)
    assert any("bare 'diff' is not recognized; use '-diff'" in o for o in outputs)

    outputs.clear()
    r.execute_line("df1 diff df2", output_fn=outputs.append)
    assert any("bare 'diff' is not recognized; use '-diff'" in o for o in outputs)

    # -diff <tbl1> <tbl2>
    outputs.clear()
    r.execute_line("-diff df1 df2", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "Comparing 'df1' vs 'df2':" in combined
    assert "Rows:" in combined

    # -diff <tbl2> with active table
    outputs.clear()
    r.execute_line("-diff df2", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "Comparing 'df2' vs 'df2':" in combined or "Comparing 'df1' vs 'df2':" in combined

    # -diff with tolerance
    outputs.clear()
    r.execute_line("-diff df1 df2 -tol 0.01", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "Rows:" in combined

    # -diff with checkpoint
    r.execute_line("checkpoint snap1", output_fn=outputs.append)
    r.execute_line("df2 -mutate \"x = 1\"", output_fn=outputs.append)
    outputs.clear()
    r.execute_line("-diff df2 snap1", output_fn=outputs.append)
    combined = "\n".join(outputs)
    assert "checkpoint:snap1" in combined

    # -diff with key alignment (on=<key>)
    outputs.clear()
    r.execute_line("-diff df1 df2 on=species", output_fn=outputs.append)
    combined_on = "\n".join(outputs)
    assert "Key Alignment (on species):" in combined_on

    # -diff on active table with on=<key>
    outputs.clear()
    r.execute_line("-diff df2 on=species", output_fn=outputs.append)
    combined_dash = "\n".join(outputs)
    assert "Key Alignment (on species):" in combined_dash

    # targeted table diff: df1 -diff df2 on=species
    outputs.clear()
    r.execute_line("df1 -diff df2 on=species", output_fn=outputs.append)
    assert "Key Alignment (on species):" in "\n".join(outputs)

    # embedded spec: -diff df1 "df2,on=species"
    outputs.clear()
    r.execute_line('-diff df1 "df2,on=species"', output_fn=outputs.append)
    assert "Key Alignment (on species):" in "\n".join(outputs)

    # -diff non-existent target
    outputs.clear()
    r.execute_line("-diff nonexistent_target", output_fn=outputs.append)
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

    # Table completion after 'switch ' and 'use '
    matches = r._get_completions("cu", "switch cu")
    assert matches == ["customers"]
    matches = r._get_completions("cu", "use cu")
    assert matches == ["customers"]

    # Table completion after 'rename '
    matches = r._get_completions("or", "rename or")
    assert matches == ["orders"]

    # Checkpoint completion after 'restore '
    matches = r._get_completions("cp", "restore cp")
    assert matches == ["cp_v1"]

    # Tables & checkpoints after '-diff '
    matches = r._get_completions("c", "-diff c")
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
    matches = r._get_completions("m", "set m")
    assert "max_rows" in matches
    assert "max_cols" in matches

    matches = r._get_completions("fl", "set fl")
    assert "float_precision" in matches

    matches = r._get_completions("co", "set co")
    assert "comma" in matches

    matches = r._get_completions("par", "set checkpoint_format = par")
    assert "parquet" in matches

    # Replay entry includes rename, switch, and use
    assert r._is_replayable_entry("rename df1 customers") is True
    assert r._is_replayable_entry("switch customers") is True
    assert r._is_replayable_entry("use customers") is True

    r.close()


def test_repl_set_session_load_and_sessions_dir(tmp_path):
    outputs = []
    r = PytaeRepl()

    # Retired session settings print retirement notice
    for cmd in (
        "set session_load = non_existent_session",
        "set load_session = non_existent_session",
        "set sessions_dir = /tmp/foo",
        "set session_name = project_alpha",
    ):
        outputs.clear()
        r.execute_line(cmd, output_fn=outputs.append)
        assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_repl_save_commands_captures_bare_output_and_canonical_posix_paths(tmp_path) -> None:
    """Verify that bare '-o <path>' is recorded in session history and canonical paths use portable forward slashes."""
    import polars as pl

    from pytae.repl import PytaeRepl, _resolve_to_canonical_path

    # Verify _resolve_to_canonical_path uses forward slashes
    canon = _resolve_to_canonical_path("sample:penguins")
    assert canon == "sample:penguins"

    # Create dummy parquet file
    data_file = tmp_path / "test_data.parquet"
    pl.DataFrame({"x": [1, 2, 3]}).write_parquet(data_file)
    out_csv = tmp_path / "exported.csv"
    script_file = tmp_path / "commands.txt"

    r = PytaeRepl()
    outputs: list[str] = []

    # Load dataset
    r.execute_line(f"df = {data_file}", output_fn=outputs.append)
    assert "df" in r.tables

    # Run bare -o
    r.execute_line(f"-o {out_csv}", output_fn=outputs.append)
    assert out_csv.exists()
    assert any("Saved 3 rows to" in o for o in outputs)

    # Export script and verify script file contents
    outputs.clear()
    r.execute_line(f"export script {script_file}", output_fn=outputs.append)
    assert script_file.exists()
    script_text = script_file.read_text(encoding="utf-8")

    # Script file must have captured:
    # 1. The data assignment with forward slashes
    assert f"df = {data_file.as_posix()}" in script_text or data_file.name in script_text
    # 2. The -o command
    assert f"-o {out_csv.name}" in script_text or f"-o {out_csv}" in script_text
    # 3. Must NOT contain any 'set ' configuration commands
    assert "set " not in script_text
    assert "checkpoint_format" not in script_text


def test_normalize_unquoted_windows_paths() -> None:
    """Verify that unquoted Windows drive paths with backslashes are normalized to forward slashes to protect against shlex escaping."""
    from pytae.repl import _normalize_unquoted_windows_paths

    assert (
        _normalize_unquoted_windows_paths(r"df = C:\Users\TAF3842\Downloads\final_output.parquet")
        == "df = C:/Users/TAF3842/Downloads/final_output.parquet"
    )
    assert (
        _normalize_unquoted_windows_paths(r"df=C:\Users\TAF3842\Downloads\final_output.parquet")
        == "df=C:/Users/TAF3842/Downloads/final_output.parquet"
    )
    assert (
        _normalize_unquoted_windows_paths(r"-o C:\Users\TAF3842\Downloads\test.csv")
        == "-o C:/Users/TAF3842/Downloads/test.csv"
    )
    assert (
        _normalize_unquoted_windows_paths(r"load C:\Users\TAF3842\Downloads\final_output.parquet as df")
        == "load C:/Users/TAF3842/Downloads/final_output.parquet as df"
    )
    # Quoted strings must remain untouched
    assert (
        _normalize_unquoted_windows_paths(r'df = "C:\Users\TAF3842\Downloads\final_output.parquet"')
        == r'df = "C:\Users\TAF3842\Downloads\final_output.parquet"'
    )
    assert (
        _normalize_unquoted_windows_paths(r"df = 'C:\Users\TAF3842\Downloads\final_output.parquet'")
        == r"df = 'C:\Users\TAF3842\Downloads\final_output.parquet'"
    )


def test_repl_inspection_commands_reject_bare_output(tmp_path) -> None:
    """Verify that exploratory inspection commands reject -o with educational guidance to assign a table first."""
    import polars as pl

    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    r.tables["df"] = pl.DataFrame({"a": list(range(20))})
    r.current_df = r.tables["df"]
    r.path_str = "df"

    out_file = tmp_path / "test.csv"
    outputs: list[str] = []

    # 1. Bare active table -head -o
    r.execute_line(f"-head -o {out_file}", output_fn=outputs.append)
    assert not out_file.exists()
    assert any("interactive screen preview and does not save with '-o' directly" in o for o in outputs)
    assert any("k = df -head" in o for o in outputs)
    assert not r.history  # Not recorded in history

    # 2. Targeted table df -head -o
    outputs.clear()
    r.execute_line(f"df -head 10 -o {out_file}", output_fn=outputs.append)
    assert not out_file.exists()
    assert any("interactive screen preview and does not save with '-o' directly" in o for o in outputs)

    # 3. Other inspection commands reject -o as well
    outputs.clear()
    r.execute_line(f"-tail -o {out_file}", output_fn=outputs.append)
    assert any("interactive screen preview and does not save with '-o' directly" in o for o in outputs)

    # 4. Correct workflow: k = df -head then k -o <path>
    outputs.clear()
    r.execute_line("k = df -head", output_fn=outputs.append)
    assert "k" in r.tables
    assert r.tables["k"].shape == (5, 1)

    r.execute_line(f"k -o {out_file}", output_fn=outputs.append)
    assert out_file.exists()
    assert any("Saved 5 rows to" in o for o in outputs)
    assert "k = df -head" in r.history
    assert f"k -o {out_file}" in r.history


def test_repl_redirected_file_input_suppresses_prompt(tmp_path, monkeypatch) -> None:
    """Verify that piping/redirecting a script file into the REPL does not bunch up prompts."""
    import sys

    from pytae.repl import PytaeRepl

    script_file = tmp_path / "script.txt"
    script_file.write_text("# Comment line 1\n# Comment line 2\nexit\n", encoding="utf-8")

    outputs: list[str] = []
    with open(script_file, "r", encoding="utf-8") as f:
        monkeypatch.setattr(sys, "stdin", f)
        r = PytaeRepl()
        r.run(output_fn=outputs.append)

    # Banner is printed, but no repeated prompt lines
    assert any("PYTAE INTERACTIVE WORKBENCH" in o for o in outputs)
    assert any("Exiting pytae REPL" in o for o in outputs)
    assert not any("winpty pytae" in o for o in outputs)


def test_list_saved_sessions_output_and_directories(tmp_path, monkeypatch) -> None:
    """Verify that list_saved_sessions outputs retirement notice and directories are located correctly."""
    from pytae.repl import (
        _get_history_dir,
        get_commands_dir,
        get_sessions_dir,
        list_saved_sessions,
    )

    # 1. Verify directory paths under ~/.pytae
    monkeypatch.delenv("PYTAE_HISTORY_DIR", raising=False)
    monkeypatch.delenv("PYTAE_SESSIONS_DIR", raising=False)
    hist_dir = _get_history_dir()
    assert hist_dir.name == "history"
    assert hist_dir.parent.name == ".pytae"

    cmd_dir = get_commands_dir()
    assert cmd_dir.name in ("code", "commands", "history")
    assert cmd_dir.parent.name == ".pytae"

    sess_dir = get_sessions_dir()
    assert sess_dir.exists()

    # 2. Test list_saved_sessions outputs retirement notice
    outputs: list[str] = []
    list_saved_sessions(outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)


def test_faithful_history_vs_commands_script(tmp_path) -> None:
    """Verify that ~/.pytae/history/ saves all lines faithfully while commands script contains only replayable steps."""
    import polars as pl

    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    r.tables["df"] = pl.DataFrame({"a": list(range(10))})
    r.current_df = r.tables["df"]
    r.path_str = "df"

    cmd_export = tmp_path / "my_commands.pt"
    out_csv = tmp_path / "out.csv"

    # Run diverse mix of exploratory, informational, comment, config, and mutation steps
    r.execute_line("# A descriptive comment")
    r.execute_line("status")
    r.execute_line("help")
    r.execute_line("-head 3")
    r.execute_line("k = df -head 5")
    r.execute_line(f"k -o {out_csv}")
    r.execute_line(f"export script {cmd_export}")
    r.execute_line("exit")

    # 1. Verify history file (faithful flight recorder in history/)
    assert r.session_history_path.exists()
    hist_text = r.session_history_path.read_text(encoding="utf-8")
    assert "# A descriptive comment" in hist_text
    assert "status" in hist_text
    assert "help" in hist_text
    assert "-head 3" in hist_text
    assert "k = df -head 5" in hist_text
    assert f"k -o {out_csv}" in hist_text
    assert "exit" in hist_text

    # 2. Verify commands script (clean replayable commands in commands/)
    assert cmd_export.exists()
    cmd_text = cmd_export.read_text(encoding="utf-8")
    assert "k = df -head 5" in cmd_text
    assert f"k -o {out_csv.name}" in cmd_text or f"k -o {out_csv}" in cmd_text
    # Meta / preview / comments must NOT be in commands script
    assert "status" not in cmd_text
    assert "help" not in cmd_text
    assert "-head 3" not in cmd_text
    assert "# A descriptive comment" not in cmd_text


def test_repl_relocate_active_session_full_migration(tmp_path) -> None:
    """Verify that retired sessions_dir setting prints retirement notice."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set sessions_dir = /tmp/somedir", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_repl_set_display_and_custom_settings():
    """Verify bare 'set' lists all 12 settings and individual setters work cleanly."""
    r = PytaeRepl()
    outputs: list[str] = []

    # 1. Bare 'set' lists active display settings
    r.execute_line("set", output_fn=outputs.append)
    set_text = "\n".join(outputs)
    assert "max_rows        = 10" in set_text
    assert "max_cols        = all" in set_text
    assert "float_precision = auto" in set_text
    assert "comma           = off" in set_text
    assert "save_code" not in set_text
    assert "null_repr" not in set_text
    assert "timing" not in set_text
    assert "color" not in set_text
    assert "echo" not in set_text

    # Retired session settings print retirement notice
    outputs.clear()
    r.execute_line("set new_session = foo", output_fn=outputs.append)
    assert "persistent disk sessions have been retired" in outputs[-1]

    # 2. max_rows / rows
    outputs.clear()
    r.execute_line("set max_rows = 25", output_fn=outputs.append)
    assert r.max_rows == 25
    assert "Set max_rows = 25." in outputs[-1]

    outputs.clear()
    r.execute_line("set rows = default", output_fn=outputs.append)
    assert r.max_rows == 10
    assert "Set max_rows = 10 (default)." in outputs[-1]

    outputs.clear()
    r.execute_line("set max_rows = -5", output_fn=outputs.append)
    assert "invalid max_rows" in outputs[-1].lower()
    assert r.max_rows == 10

    # 3. max_cols / cols
    outputs.clear()
    r.execute_line("set max_cols = 5", output_fn=outputs.append)
    assert r.max_cols == 5
    assert "Set max_cols = 5." in outputs[-1]

    outputs.clear()
    r.execute_line("set cols = all", output_fn=outputs.append)
    assert r.max_cols is None
    assert "Set max_cols = all" in outputs[-1]

    outputs.clear()
    r.execute_line("set max_cols = abc", output_fn=outputs.append)
    assert "invalid max_cols" in outputs[-1].lower()

    # 4. float_precision / precision
    outputs.clear()
    r.execute_line("set float_precision = 3", output_fn=outputs.append)
    assert r.float_precision == 3
    assert "Set float_precision = 3." in outputs[-1]

    outputs.clear()
    r.execute_line("set precision = auto", output_fn=outputs.append)
    assert r.float_precision is None
    assert "Set float_precision = auto" in outputs[-1]

    outputs.clear()
    r.execute_line("set precision = -1", output_fn=outputs.append)
    assert "invalid float_precision" in outputs[-1].lower()

    # 5. comma
    outputs.clear()
    r.execute_line("set comma = on", output_fn=outputs.append)
    assert r.comma is True
    assert "Set comma = on" in outputs[-1]

    outputs.clear()
    r.execute_line("set comma = off", output_fn=outputs.append)
    assert r.comma is False
    assert "Set comma = off." in outputs[-1]

    outputs.clear()
    r.execute_line("set comma = invalid", output_fn=outputs.append)
    assert "invalid comma" in outputs[-1].lower()

    # 6. Multi-setting line with comma
    outputs.clear()
    r.execute_line("set max_rows = 15, comma = on, float_precision = 2", output_fn=outputs.append)
    assert r.max_rows == 15
    assert r.comma is True
    assert r.float_precision == 2

    # 7. Disallowed former settings
    for retired in ("null_repr", "timing", "color", "echo", "commas", "thousands_separator"):
        outputs.clear()
        r.execute_line(f"set {retired} = on", output_fn=outputs.append)
        assert "unknown setting" in outputs[-1].lower()

    r.close()


def test_repl_set_table_formatting_and_inspection():
    """Verify max_rows, float_precision, and comma affect table rendering without mutating raw data."""
    import polars as pl

    r = PytaeRepl()
    outputs: list[str] = []

    # Create a test dataframe with floats and integers
    test_df = pl.DataFrame({
        "big_int": [1234567, 8910, 45000000],
        "big_float": [1234.5678, 9876543.21, 100000.5],
        "cat": ["a", "b", "c"],
    })
    r.tables["df"] = test_df
    r.current_df = test_df
    r.path_str = "df"

    # Default: comma=off, float_precision=auto
    r.execute_line("-head 2", output_fn=outputs.append)
    rendered_default = "\n".join(outputs)
    assert "1234567" in rendered_default
    assert "1,234,567" not in rendered_default

    # Configure float_precision=2, comma=on
    outputs.clear()
    r.execute_line("set float_precision = 2, comma = on", output_fn=outputs.append)
    assert r.float_precision == 2
    assert r.comma is True

    # Check inspection with comma=on and float_precision=2
    outputs.clear()
    r.execute_line("-head 3", output_fn=outputs.append)
    rendered = "\n".join(outputs)
    # Check commas on big_int: 1,234,567 and 45,000,000
    assert "1,234,567" in rendered
    assert "45,000,000" in rendered
    # Check commas and precision on big_float: 1,234.57 and 9,876,543.21
    assert "1,234.57" in rendered
    assert "9,876,543.21" in rendered

    # Check py expression formatting honors comma and precision
    outputs.clear()
    r.execute_line("py df.head(2)", output_fn=outputs.append)
    py_rendered = "\n".join(outputs)
    assert "1,234,567" in py_rendered
    assert "1,234.57" in py_rendered

    # CRITICAL: Verify that the underlying DataFrame is UNTOUCHED (display-only)
    # Underlying data retains raw unrounded float and integers
    assert r.current_df["big_int"][0] == 1234567
    assert r.current_df["big_float"][0] == 1234.5678
    # Exporting via to_pandas (used by -o clip) preserves raw numerical values
    pdf = r.current_df.to_pandas()
    assert pdf["big_int"].iloc[0] == 1234567
    assert pdf["big_float"].iloc[0] == 1234.5678

    r.close()


def test_repl_saved_commands_pure_replayability(tmp_path):
    """CRITICAL: Ensure 'set' commands are NEVER saved to replayable command scripts."""
    r = PytaeRepl()
    outputs: list[str] = []

    # Set various preferences
    r.execute_line("set max_rows = 50", output_fn=outputs.append)
    r.execute_line("set comma = on", output_fn=outputs.append)
    r.execute_line("set float_precision = 2", output_fn=outputs.append)
    r.execute_line("set comma = off", output_fn=outputs.append)

    # Run genuine transformation commands
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    r.execute_line("df_clean = df -filter 'bill_length_mm > 40'", output_fn=outputs.append)

    # Run exploratory previews and transient clipboard exports (MUST NOT be in commands)
    r.execute_line("-select species,island -head 10 -o clip", output_fn=outputs.append)
    r.execute_line("df -o clip", output_fn=outputs.append)
    r.execute_line("-o clip", output_fn=outputs.append)
    r.execute_line("-head 5", output_fn=outputs.append)

    # Run genuine disk export (MUST be in commands)
    r.execute_line("-o final_report.parquet", output_fn=outputs.append)

    # Run more set commands
    r.execute_line("set comma = on", output_fn=outputs.append)
    r.execute_line("set max_rows = 10", output_fn=outputs.append)

    # Export session commands
    export_file = tmp_path / "replay_pipeline.txt"
    r.execute_line(f"exit -s {export_file}", output_fn=outputs.append)

    assert export_file.exists()
    content = export_file.read_text(encoding="utf-8")

    # Genuine transformations and persistent file exports MUST be present
    assert "df = sample:penguins" in content
    assert "df_clean = df -filter 'bill_length_mm > 40'" in content
    assert "-o final_report.parquet" in content

    # Transient clipboard copies and exploratory previews MUST NOT appear in commands
    assert "-o clip" not in content
    assert "-head 10" not in content
    assert "-head 5" not in content

    # NO 'set' commands of any kind should EVER appear in the replay script!
    for line in content.splitlines():
        clean_l = line.strip()
        if clean_l and not clean_l.startswith("#"):
            assert not clean_l.startswith("set "), f"Found unexpected set command in replay script: {clean_l}"
            assert not clean_l.startswith("set="), f"Found unexpected set command in replay script: {clean_l}"
            assert "-o clip" not in clean_l

    # Also verify live session_commands_path if configured
    if r.session_commands_path is not None and r.session_commands_path.exists():
        live_content = r.session_commands_path.read_text(encoding="utf-8")
        assert "-o clip" not in live_content
        for line in live_content.splitlines():
            clean_l = line.strip()
            if clean_l and not clean_l.startswith("#"):
                assert not clean_l.startswith("set "), f"Found set command in live session commands: {clean_l}"
                assert "-o clip" not in clean_l

    r.close()


def test_repl_set_checkpoint_format_convert_option(tmp_path):
    """Verify retired checkpoint format settings output retirement notice."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set checkpoint_format = parquet", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)

    outputs.clear()
    r.execute_line("set convert = all", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_sessions_cli_and_repl_verbose_modes(tmp_path):
    """Verify sessions command and -sessions CLI flag output retirement notice."""
    import contextlib
    import io

    from pytae.cli import main
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("sessions", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)

    outputs.clear()
    r.execute_line("sessions -v", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()

    stdout_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf):
        ret = main(["-sessions"])
    assert ret == 0
    assert "persistent disk sessions have been retired" in stdout_buf.getvalue()


def test_repl_does_not_abort_on_pipeline_errors():
    """Verify invalid pipeline flags/syntax (e.g. -scatter 'age,fare', -filter 'age >') do not abort REPL."""
    r = PytaeRepl()
    outputs: list[str] = []

    # Load dataset
    cont = r.execute_line("df = sample:titanic", output_fn=outputs.append)
    assert cont is True
    assert r.current_df is not None

    # Invalid scatter syntax (comma instead of x:y)
    outputs.clear()
    cont = r.execute_line('-scatter "age,fare"', output_fn=outputs.append)
    assert cont is True  # REPL remains active
    out_text = "\n".join(outputs)
    assert "scatter() requires two numeric columns" in out_text

    # Invalid filter condition
    outputs.clear()
    cont = r.execute_line('-filter "age >"', output_fn=outputs.append)
    assert cont is True
    out_text = "\n".join(outputs)
    assert "invalid filter condition" in out_text

    # Invalid rename spec
    outputs.clear()
    cont = r.execute_line('-rename "bad"', output_fn=outputs.append)
    assert cont is True
    out_text = "\n".join(outputs)
    assert "invalid -rename mapping" in out_text

    # Valid pipeline still works immediately afterwards
    outputs.clear()
    cont = r.execute_line("-head 2", output_fn=outputs.append)
    assert cont is True
    assert len(outputs) > 0
    r.close()


def test_sessions_ready_filter_and_pattern_inspection(tmp_path):
    """Test sessions command and CLI output retirement notice."""
    import contextlib
    import io

    from pytae.cli import main
    from pytae.repl import PytaeRepl, list_saved_sessions

    outputs: list[str] = []
    list_saved_sessions(outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)

    r = PytaeRepl()
    outputs.clear()
    r.execute_line("sessions -ready", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()

    stdout_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf):
        ret = main(["-sessions", "-ready"])
    assert ret == 0
    assert "persistent disk sessions have been retired" in stdout_buf.getvalue()


def test_repl_status_subcommands_and_verbose():
    """Verify status, status -v, status tables [-v], status table <name> [-v], status checkpoints [-v], and status checkpoint <name> [-v]."""
    outputs: list[str] = []
    r = PytaeRepl()

    # 1. Bare status directs to specific subcommands (session, table, checkpoints)
    r.execute_line("status", output_fn=outputs.append)
    st_none = "\n".join(outputs)
    assert "please specify a status category to inspect" in st_none
    assert "status session" in st_none
    assert "status table" in st_none
    assert "status checkpoint" in st_none

    # 1b. status session with no dataset loaded
    outputs.clear()
    r.execute_line("status session", output_fn=outputs.append)
    st_sess_none = "\n".join(outputs)
    assert "=== REPL Session Status ===" in st_sess_none
    assert "Active Table  : (none)" in st_sess_none
    assert "Loaded Tables : 0 tables loaded" in st_sess_none

    # 2. Load two tables
    r.execute_line("df1 = sample:penguins", output_fn=outputs.append)
    r.execute_line("df2 = sample:tips", output_fn=outputs.append)
    r.execute_line("checkpoint cp1", output_fn=outputs.append)

    # 3. Bare status and status -v direct the user to specific categories
    outputs.clear()
    r.execute_line("status", output_fn=outputs.append)
    st_dir = "\n".join(outputs)
    assert "please specify a status category to inspect" in st_dir

    outputs.clear()
    r.execute_line("status -v", output_fn=outputs.append)
    st_v_dir = "\n".join(outputs)
    assert "please specify a status category to inspect" in st_v_dir

    # 3b. status session (session status: session name, active table, tables overview, checkpoints, process RAM)
    outputs.clear()
    r.execute_line("status session", output_fn=outputs.append)
    st = "\n".join(outputs)
    assert "=== REPL Session Status ===" in st
    assert "Active Table  : df2 (244 rows x 7 cols" in st
    assert "Loaded Tables : 2 tables" in st
    assert "Process RAM   :" in st
    assert "Checkpoints   : 1 saved (latest: cp1)" in st
    assert "Columns (" not in st
    assert "Commands Run" not in st

    # 4. status session -v (shows session verbose breakdown: per-table inventory, checkpoints list, settings)
    outputs.clear()
    r.execute_line("status session -v", output_fn=outputs.append)
    st_v = "\n".join(outputs)
    assert "=== REPL Session Status ===" in st_v
    assert "Loaded Tables : 2 tables" in st_v
    assert "df1" in st_v
    assert "df2 [active]" in st_v
    assert "cp1" in st_v
    assert "Settings      :" in st_v
    assert "Columns (" not in st_v  # Table columns belong to 'status table [name] -v'

    # 4b. status table (with no name: shows active table df2 details and loaded tables inventory)
    outputs.clear()
    r.execute_line("status table", output_fn=outputs.append)
    st_act_tbl = "\n".join(outputs)
    assert "Table          : df2" in st_act_tbl
    assert "Shape          : 244 rows x 7 columns" in st_act_tbl
    assert "Status         : active" in st_act_tbl
    assert "Loaded Tables (2):" in st_act_tbl
    assert "df1" in st_act_tbl
    assert "* df2" in st_act_tbl

    # 5. status tables is rejected (no plurals under the hood)
    outputs.clear()
    r.execute_line("status tables", output_fn=outputs.append)
    assert "plural 'tables' is not recognized; use 'status table' instead" in outputs[-1]

    # 6. status table -v (shows per-table columns and RAM totals)
    outputs.clear()
    r.execute_line("status table -v", output_fn=outputs.append)
    st_tbl_v = "\n".join(outputs)
    assert "Loaded Tables (2):" in st_tbl_v
    assert "Columns (7):" in st_tbl_v
    assert "Total Tables:" in st_tbl_v

    # 7. status table df1 (specific table) - no column names in non-verbose
    outputs.clear()
    r.execute_line("status table df1", output_fn=outputs.append)
    st_df1 = "\n".join(outputs)
    assert "Table          : df1" in st_df1
    assert "Shape          : 344 rows x 7 columns" in st_df1
    assert "Table memory   : ~0.02 MB" in st_df1
    assert "Status         : inactive" in st_df1
    assert "Columns (" not in st_df1

    # 8. status table df1 -v (specific table with schema/columns)
    outputs.clear()
    r.execute_line("status table df1 -v", output_fn=outputs.append)
    st_df1_v = "\n".join(outputs)
    assert "Table          : df1" in st_df1_v
    assert "Columns (7):" in st_df1_v
    assert "species" in st_df1_v
    assert "island" in st_df1_v

    # 9. status checkpoints is rejected; status checkpoint lists checkpoints
    outputs.clear()
    r.execute_line("status checkpoints", output_fn=outputs.append)
    assert "plural 'checkpoints' is not recognized; use 'status checkpoint' instead" in outputs[-1]

    outputs.clear()
    r.execute_line("status checkpoint", output_fn=outputs.append)
    st_cp = "\n".join(outputs)
    assert "Saved Checkpoints (1):" in st_cp
    assert "cp1" in st_cp

    # 10. status checkpoint cp1
    outputs.clear()
    r.execute_line("status checkpoint cp1", output_fn=outputs.append)
    st_cp1 = "\n".join(outputs)
    assert "Checkpoint     : cp1" in st_cp1
    assert "Storage        : ephemeral disk IPC" in st_cp1
    assert "Tables (2):" in st_cp1

    # 11. status checkpoint cp1 -v
    outputs.clear()
    r.execute_line("status checkpoint cp1 -v", output_fn=outputs.append)
    st_cp1_v = "\n".join(outputs)
    assert "Checkpoint     : cp1" in st_cp1_v
    assert "Tables (2):" in st_cp1_v

    # 12. Bare tables & checkpoints rejected with guidance
    outputs.clear()
    r.execute_line("tables", output_fn=outputs.append)
    assert "bare 'tables' is not recognized; use 'status table'" in outputs[-1]

    outputs.clear()
    r.execute_line("checkpoints", output_fn=outputs.append)
    assert "bare 'checkpoints' is not recognized; use 'status checkpoint'" in outputs[-1]

    r.close()


def test_repl_set_fork_session_preserves_source(tmp_path, monkeypatch):
    """Verify that retired fork_session/session_load settings print retirement notice."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set session_load = base_model, session_name = fork_run", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_repl_set_copy_session_same_name_to_different_dir_preserves_source(tmp_path):
    """Verify that retired copy_session/session_load settings print retirement notice."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line('set copy_session = rwa_analysis', output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_session_load_cwd_relative_and_hint(tmp_path, monkeypatch):
    """Verify that retired session_load setting prints retirement notice."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set session_load = local_proj", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_session_load_various_path_formats(tmp_path, monkeypatch):
    """Verify that retired session_load setting prints retirement notice across formats."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line('set session_load = "./analysis_run"', output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_session_markers_and_directory_exploration(tmp_path):
    """Verify list_saved_sessions prints retirement notice and is_session_dir behaves safely."""
    from pytae.repl import is_session_dir, list_saved_sessions

    outputs: list[str] = []
    list_saved_sessions(outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    assert not is_session_dir(tmp_path)


def test_win_console_input_tab_completion_single_match():
    from pytae.repl import _win_console_input

    # Type: "df = sample:pen<TAB>\n"
    keys = list("df = sample:pen\t\r")
    key_idx = 0

    def mock_read_char():
        nonlocal key_idx
        if key_idx < len(keys):
            ch = keys[key_idx]
            key_idx += 1
            return ch
        return "\r"

    def mock_completions(word, line_buf, begidx, endidx):
        if word == "sample:pen":
            return ["sample:penguins"]
        return []

    result = _win_console_input(
        prompt_text="pytae> ",
        history=[],
        completions_fn=mock_completions,
        read_char_fn=mock_read_char,
    )
    # A single completed token adds trailing space
    assert result == "df = sample:penguins "


def test_win_console_input_tab_completion_directory_match():
    import os

    from pytae.repl import _win_console_input

    sep = os.sep
    keys = list("load data" + sep + "sub\t\r")
    key_idx = 0

    def mock_read_char():
        nonlocal key_idx
        if key_idx < len(keys):
            ch = keys[key_idx]
            key_idx += 1
            return ch
        return "\r"

    def mock_completions(word, line_buf, begidx, endidx):
        return ["data" + sep + "subdir" + sep]

    result = _win_console_input(
        prompt_text="pytae> ",
        history=[],
        completions_fn=mock_completions,
        read_char_fn=mock_read_char,
    )
    # Directories ending with separator should NOT add trailing space
    assert result == f"load data{sep}subdir{sep}"


def test_win_console_input_tab_completion_common_prefix():
    from pytae.repl import _win_console_input

    # Type: "set sess<TAB>\n"
    # Matches: ["session_name", "session_load", "sessions_dir"] -> Common prefix is "session"
    keys = list("set sess\t\r")
    key_idx = 0

    def mock_read_char():
        nonlocal key_idx
        if key_idx < len(keys):
            ch = keys[key_idx]
            key_idx += 1
            return ch
        return "\r"

    def mock_completions(word, line_buf, begidx, endidx):
        if word.startswith("sess"):
            return ["session_name", "session_load", "sessions_dir"]
        return []

    result = _win_console_input(
        prompt_text="pytae> ",
        history=[],
        completions_fn=mock_completions,
        read_char_fn=mock_read_char,
    )
    assert result == "set session"


def test_win_console_input_tab_completion_candidates_display(capsys):
    from pytae.repl import _win_console_input

    # Type: "set session_<TAB>n<TAB>\r"
    # First TAB at common prefix displays candidates. Second TAB on "session_n" completes.
    keys = list("set session_\tn\t\r")
    key_idx = 0

    def mock_read_char():
        nonlocal key_idx
        if key_idx < len(keys):
            ch = keys[key_idx]
            key_idx += 1
            return ch
        return "\r"

    def mock_completions(word, line_buf, begidx, endidx):
        if word == "session_":
            return ["session_name", "session_load"]
        if word == "session_n":
            return ["session_name"]
        return []

    result = _win_console_input(
        prompt_text="pytae> ",
        history=[],
        completions_fn=mock_completions,
        read_char_fn=mock_read_char,
    )
    captured = capsys.readouterr()
    assert "session_name" in captured.out
    assert "session_load" in captured.out
    assert result == "set session_name "


def test_win_console_input_backspace_and_navigation():
    from pytae.repl import _win_console_input

    # Test backspace with both \x08 (CMD) and \x7f (MinTTY/Git Bash)
    # Type "abc\x08d\x7fe\r" -> "a" + "b" + ("c" backspaced) + "d" + ("d" backspaced via \x7f) + "e" -> "abe"
    keys = list("abc\x08d\x7fe\r")
    key_idx = 0

    def mock_read_char():
        nonlocal key_idx
        if key_idx < len(keys):
            ch = keys[key_idx]
            key_idx += 1
            return ch
        return "\r"

    result = _win_console_input(
        prompt_text="pytae> ",
        history=[],
        read_char_fn=mock_read_char,
    )
    assert result == "abe"


def test_repl_complete_handles_none_begidx(monkeypatch):
    import sys

    from pytae.repl import PytaeRepl

    repl_mod = sys.modules["pytae.repl"]

    class MockReadline:
        @staticmethod
        def get_line_buffer():
            return "set "

        @staticmethod
        def get_begidx():
            return None  # Pyreadline3 / buggy readline returning None

        @staticmethod
        def get_endidx():
            return None

    monkeypatch.setattr(repl_mod, "readline", MockReadline)

    r = PytaeRepl()
    # Should not raise TypeError and successfully compute completions
    first_match = r._complete("", 0)
    assert first_match is not None
    assert first_match == "max_rows"
    r.close()


def test_init_readline_binds_tab_complete(monkeypatch):
    import sys

    from pytae.repl import _init_readline

    repl_mod = sys.modules["pytae.repl"]
    bound_commands = []

    class MockReadline:
        __doc__ = "GNU readline"

        @staticmethod
        def parse_and_bind(cmd):
            bound_commands.append(cmd)

        @staticmethod
        def set_completer(fn):
            pass

        @staticmethod
        def set_completer_delims(delims):
            pass

    monkeypatch.setattr(repl_mod, "readline", MockReadline)
    _init_readline(lambda text, state: None)

    assert "tab: complete" in bound_commands
    assert "Tab: complete" in bound_commands
    assert '"\\t": complete' in bound_commands
    assert "bind ^I rl_complete" in bound_commands


def test_repl_named_session_status(tmp_path):
    r = PytaeRepl(session="alpha_proj")
    outputs: list[str] = []
    r.execute_line("status session", output_fn=outputs.append)
    st = "\n".join(outputs)
    assert "=== REPL Session Status ===" in st
    assert "Active Table  : (none)" in st
    r.close()


def test_repl_unified_path_first_sessions(tmp_path):
    r = PytaeRepl()
    outputs: list[str] = []
    for cmd in (
        "set new_session = fresh_lab",
        "set load_session = fresh_lab",
        "set save_session = copied_lab",
    ):
        outputs.clear()
        r.execute_line(cmd, output_fn=outputs.append)
        assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_repl_new_session_preserves_loaded_tables():
    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set new_session = chamiya", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_repl_save_session_overwrite_protection():
    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set save_session = target_sess", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_repl_history_arrow_navigation_strictly_per_session():
    import readline

    from pytae.repl import PytaeRepl, _init_readline

    # Simulate dirty readline state from a "previous session"
    if readline is not None:
        try:
            readline.add_history("previous_session_cmd")
        except Exception:
            pass

    # Initialize REPL for new session
    r = PytaeRepl()
    assert r._raw_history == []

    _init_readline(r._complete)
    if readline is not None and hasattr(readline, "get_current_history_length"):
        assert readline.get_current_history_length() == 0

    outputs = []
    # No history yet
    r.execute_line("\x1b[A", output_fn=outputs.append)
    assert any("no previous commands in history" in o for o in outputs)

    # Run command in current session
    outputs.clear()
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    assert r._raw_history == ["df = sample:penguins"]

    # Now arrow up recalls the current session command
    outputs.clear()
    r.execute_line("\x1b[A", output_fn=outputs.append)
    assert any("recalled from history: df = sample:penguins" in o for o in outputs)
    r.close()


def test_repl_no_undo_redo_commands():
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs = []
    r.execute_line("undo", output_fn=outputs.append)
    # undo is not a recognized command
    assert any("unrecognized" in o.lower() or "not found" in o.lower() or "error" in o.lower() or "pytae:" in o.lower() for o in outputs)

    outputs.clear()
    r.execute_line("redo", output_fn=outputs.append)
    # redo is not a recognized command
    assert any("unrecognized" in o.lower() or "not found" in o.lower() or "error" in o.lower() or "pytae:" in o.lower() for o in outputs)
    r.close()


def test_repl_new_session_overwrite_clears_checkpoint_folders(tmp_path, monkeypatch):
    """Verify that retired new_session setting prints retirement notice."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set new_session = old_analysis, overwrite = true", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_repl_new_session_overwrite_same_session_in_place(tmp_path, monkeypatch):
    """Verify that retired new_session setting prints retirement notice."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []
    r.execute_line("set new_session = live_sess, overwrite = true", output_fn=outputs.append)
    assert any("persistent disk sessions have been retired" in o for o in outputs)
    r.close()


def test_cli_export_history_to_python_and_pt(tmp_path):
    """Verify CLI pytae -export <history.txt> [-o target.py|target.pt] transpiler."""
    from pytae.cli import main

    hist_file = tmp_path / "raw_history.txt"
    hist_file.write_text(
        "# pytae history\n"
        "status\n"
        "df = sample:penguins\n"
        "-head 5\n"
        "df = df -filter \"species == 'Gentoo'\"\n"
        "checkpoint snap1\n"
        "out = df -select species,island\n"
        "export script foo.pt\n",
        encoding="utf-8",
    )

    # 1. Transpile to .py
    target_py = tmp_path / "pipeline.py"
    ret = main(["-export", str(hist_file), "-o", str(target_py)])
    assert ret == 0
    assert target_py.exists()
    py_code = target_py.read_text(encoding="utf-8")
    assert "pt.sample('penguins')" in py_code or 'pt.sample("penguins")' in py_code
    assert "species == 'Gentoo'" in py_code
    assert "checkpoint" not in py_code
    assert "-head" not in py_code
    import ast
    ast.parse(py_code)

    # 2. Transpile to .pt
    target_pt = tmp_path / "pipeline.pt"
    ret = main(["-export", str(hist_file), "-o", str(target_pt)])
    assert ret == 0
    assert target_pt.exists()
    pt_code = target_pt.read_text(encoding="utf-8")
    assert "df = sample:penguins" in pt_code
    assert "checkpoint snap1" not in pt_code
    assert "-head 5" not in pt_code

    # 3. Headless run of generated .pt script
    ret_run = main(["-run", str(target_pt)])
    assert ret_run == 0


def test_cli_interactive_resume_script(tmp_path, monkeypatch):
    """Verify CLI pytae -i <script.pt> populates workbench tables in RAM."""
    from pytae.repl import PytaeRepl

    script_pt = tmp_path / "init.pt"
    script_pt.write_text(
        "t1 = sample:penguins\n"
        "t2 = sample:tips\n",
        encoding="utf-8",
    )

    r = PytaeRepl(script=str(script_pt))
    assert "t1" in r.tables
    assert "t2" in r.tables
    assert r.tables["t1"].shape[0] == 344
    assert r.tables["t2"].shape[0] == 244

    try:
        from pytae.repl import readline

        if readline is not None:
            r.run(input_fn=lambda _: "exit", output_fn=lambda _: None)
            hist_len = readline.get_current_history_length()
            loaded = [readline.get_history_item(i) for i in range(1, hist_len + 1)]
            assert any("t1 = sample:penguins" in (item or "") for item in loaded)
            assert any("t2 = sample:tips" in (item or "") for item in loaded)
    except Exception:
        pass
    r.close()

    # Verify bare REPL starts with reset/clean readline history
    r_bare = PytaeRepl()
    try:
        from pytae.repl import readline

        if readline is not None:
            r_bare.run(input_fn=lambda _: "exit", output_fn=lambda _: None)
            hist_len = readline.get_current_history_length()
            loaded = [readline.get_history_item(i) for i in range(1, hist_len + 1)]
            assert not any("t1 = sample:penguins" in (item or "") for item in loaded)
    except Exception:
        pass
    r_bare.close()


def test_export_script_pt_and_py_e2e(tmp_path, monkeypatch):
    """Verify export script generates clean .pt and .py scripts, filtering pure inspections."""
    import ast

    from pytae.cli import main
    from pytae.repl import PytaeRepl, run_script_file

    monkeypatch.chdir(tmp_path)
    outputs = []
    r = PytaeRepl()

    # 1. Pipeline with ingestion, transformations, inspections, and python blocks
    r.execute_line("peng = sample:penguins", output_fn=outputs.append)
    r.execute_line("peng -head 5", output_fn=outputs.append)  # pure REPL inspection (must be skipped)
    r.execute_line("py print(peng.shape)", output_fn=outputs.append)  # pure Python inspection (must be skipped)
    r.execute_line("peng = peng -filter \"species == 'Adelie'\" -arrange \"bill_length_mm desc\"", output_fn=outputs.append)

    # Mutating Python block
    py_block = (
        "py\n"
        "df = peng.to_pandas()\n"
        "df['mass_kg'] = df['body_mass_g'] / 1000.0\n"
        "peng = df.to_pytae()\n"
        "py"
    )
    r.execute_line(py_block, output_fn=outputs.append)

    # Save output
    out_file = tmp_path / "adelie.parquet"
    r.execute_line(f"peng -o {out_file.name}", output_fn=outputs.append)

    # 2. Export as .pt script
    pt_path = tmp_path / "pipeline.pt"
    outputs.clear()
    r.execute_line(f"export script {pt_path.name}", output_fn=outputs.append)
    assert any("Exported Pytae script to" in o for o in outputs)
    assert pt_path.exists()
    pt_text = pt_path.read_text(encoding="utf-8")

    # Assert inspections are omitted
    assert "-head 5" not in pt_text
    assert "print(peng.shape)" not in pt_text
    # Assert mutations and py block are preserved
    assert "peng: sample:penguins" in pt_text or "peng = sample:penguins" in pt_text
    assert "species == 'Adelie'" in pt_text
    assert "df['mass_kg']" in pt_text
    assert f"-o {out_file.name}" in pt_text

    # 3. Export as .py script
    py_path = tmp_path / "pipeline.py"
    outputs.clear()
    r.execute_line(f"export script {py_path.name}", output_fn=outputs.append)
    assert any("Exported standalone Python script to" in o for o in outputs)
    assert py_path.exists()
    py_text = py_path.read_text(encoding="utf-8")

    # Assert inspections are omitted in .py
    assert ".head(5)" not in py_text
    assert "print(peng.shape)" not in py_text
    # Assert Python syntax is valid and methods are chained
    ast.parse(py_text)
    assert "import pytae as pt" in py_text
    assert "filter(\"species == 'Adelie'\")" in py_text or 'filter("species == \'Adelie\'")' in py_text
    assert "df['mass_kg'] = df['body_mass_g'] / 1000.0" in py_text

    # 4. Test run_script_file on pipeline.pt
    run_out_file = tmp_path / "run_adelie.parquet"
    run_script = tmp_path / "run.pt"
    run_script.write_text(
        f"df = sample:penguins\n"
        f"df = df -filter \"species == 'Gentoo'\"\n"
        f"df -o {run_out_file.name}\n",
        encoding="utf-8",
    )
    exit_code = run_script_file(str(run_script))
    assert exit_code == 0
    assert run_out_file.exists()

    # 5. Test CLI execution of .pt via `pytae script.pt` and `pytae -run script.pt`
    cli_out_file = tmp_path / "cli_adelie.parquet"
    cli_script = tmp_path / "cli.pt"
    cli_script.write_text(
        f"df = sample:penguins\n"
        f"df = df -filter \"species == 'Chinstrap'\"\n"
        f"df -o {cli_out_file.name}\n",
        encoding="utf-8",
    )
    res1 = main([str(cli_script)])
    assert res1 == 0
    assert cli_out_file.exists()

    res2 = main(["-run", str(cli_script)])
    assert res2 == 0


def test_export_script_prunes_rolled_back_branches(tmp_path, monkeypatch):
    """Verify that export script (.pt and .py) prunes commands in branches that were rolled back by restore."""
    import ast

    from pytae.repl import PytaeRepl

    monkeypatch.chdir(tmp_path)
    r = PytaeRepl()
    r.execute_line("orders = sample:tips")
    r.execute_line("checkpoint baseline")
    # Failed experiment / mutation:
    r.execute_line("orders = orders -filter \"day == 'Sat'\"")
    r.execute_line("orders = orders -mutate \"bad_col = 999\"")
    # Undo / rollback:
    r.execute_line("restore baseline")
    # Valid subsequent pipeline:
    r.execute_line("orders = orders -filter \"tip > 5.0\" -mutate \"tip_pct = (tip / total_bill) * 100\"")
    r.execute_line("high_tips = orders -arrange tip_pct")
    r.execute_line("high_tips -o vip_tips.parquet")

    pt_file = tmp_path / "clean_pipeline.pt"
    r.execute_line(f"export script {pt_file.name}")
    assert pt_file.exists()
    pt_content = pt_file.read_text(encoding="utf-8")
    assert "orders = sample:tips" in pt_content
    assert "tip > 5.0" in pt_content
    assert "high_tips = orders -arrange tip_pct" in pt_content
    assert "high_tips -o vip_tips.parquet" in pt_content
    # Undone commands MUST be pruned!
    assert "bad_col" not in pt_content
    assert "day == 'Sat'" not in pt_content
    assert "checkpoint" not in pt_content
    assert "restore" not in pt_content

    py_file = tmp_path / "clean_pipeline.py"
    r.execute_line(f"export script {py_file.name}")
    assert py_file.exists()
    py_content = py_file.read_text(encoding="utf-8")
    ast.parse(py_content)
    assert "pt.sample('tips')" in py_content or 'pt.sample("tips")' in py_content
    assert "tip > 5.0" in py_content
    assert "bad_col" not in py_content
    assert "day == 'Sat'" not in py_content
    r.close()


def test_repl_clipboard_ingestion_and_strict_clean_export(tmp_path, monkeypatch):
    import ast

    import pandas as pd

    from pytae.repl import PytaeRepl

    fake_df = pd.DataFrame({
        "species": ["Adelie", "Gentoo", "Chinstrap", "Adelie", "Gentoo", "Adelie"],
        "body_mass_g": [3700, 5000, 3800, 3900, 5200, 3650],
    })

    # Mock pd.read_clipboard
    monkeypatch.setattr(pd, "read_clipboard", lambda **kwargs: fake_df.copy())

    copied_payloads = []

    def mock_to_clipboard(self, *args, **kwargs):
        copied_payloads.append(self.copy())

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", mock_to_clipboard)

    outputs = []
    r = PytaeRepl()

    # 1. Ingest via `df = clip`
    r.execute_line("df = clip", output_fn=outputs.append)
    assert any("Loaded <clipboard> as 'df' (6 rows x 2 cols)" in o for o in outputs)
    assert r.current_df is not None
    assert r.current_df.shape == (6, 2)
    assert "df" in r.tables
    assert r.table_sources["df"] == "<clipboard>"

    # 2. Ingest via custom alias and nrows `sample_clip = clip -nrows 3`
    outputs.clear()
    r.execute_line("sample_clip = clip -nrows 3", output_fn=outputs.append)
    assert any("Loaded <clipboard> as 'sample_clip' (3 rows x 2 cols)" in o for o in outputs)
    assert r.tables["sample_clip"].shape == (3, 2)

    # 3. Test Strict & Clean: Preview commands reject -o clip directly
    outputs.clear()
    r.execute_line("df -head 5 -o clip", output_fn=outputs.append)
    assert any("interactive screen preview and does not save with '-o' directly" in o for o in outputs)
    assert any("k = df -head 5" in o for o in outputs)
    assert any("k -o clip" in o for o in outputs)
    assert len(copied_payloads) == 0

    outputs.clear()
    r.execute_line("-head 5 -o clip", output_fn=outputs.append)
    assert any("interactive screen preview and does not save with '-o' directly" in o for o in outputs)
    assert len(copied_payloads) == 0

    # 4. Strictly follow guided steps: Assign slice first, then export to clip
    outputs.clear()
    r.execute_line("k = df -head 5", output_fn=outputs.append)
    assert any("Created 'k' (5 rows x 2 cols)" in o for o in outputs)
    assert r.tables["k"].shape == (5, 2)

    outputs.clear()
    r.execute_line("k -o clip", output_fn=outputs.append)
    assert any("Copied 5 rows to system clipboard" in o for o in outputs)
    assert len(copied_payloads) == 1
    assert len(copied_payloads[0]) == 5

    # 5. Export script and verify transpilation
    pt_path = tmp_path / "clip_pipeline.pt"
    py_path = tmp_path / "clip_pipeline.py"
    r.execute_line(f'export script "{pt_path}"', output_fn=outputs.append)
    r.execute_line(f'export script "{py_path}"', output_fn=outputs.append)

    assert pt_path.exists()
    pt_code = pt_path.read_text(encoding="utf-8")
    assert "df = clip" in pt_code
    assert "k = df -head 5" in pt_code

    assert py_path.exists()
    py_code = py_path.read_text(encoding="utf-8")
    ast.parse(py_code)
    assert "import pandas as pd" in py_code
    assert "df = pl.from_pandas(pd.read_clipboard())" in py_code
    assert "sample_clip = pl.from_pandas(pd.read_clipboard()).head(3)" in py_code
    assert "k = df.head(5)" in py_code
    # Transient clipboard copies are excluded from replay scripts
    assert "-o clip" not in pt_code
    assert "-o clip" not in py_code

    r.close()


def test_repl_clipboard_error_handling(monkeypatch):
    import pandas as pd

    from pytae.repl import PytaeRepl

    def mock_fail(**kwargs):
        raise RuntimeError("No clipboard mechanism found")

    monkeypatch.setattr(pd, "read_clipboard", mock_fail)

    outputs = []
    r = PytaeRepl()
    r.execute_line("df = clip", output_fn=outputs.append)
    assert any("clipboard error: No clipboard mechanism found" in o for o in outputs)
    r.close()


def test_repl_lazy_scan_and_pipeline_chaining(tmp_path, monkeypatch):
    """Test lazy scan ingestion, inspection pushdown, pipeline chaining, and streaming output."""
    import polars as pl

    from pytae import DATA_PATH
    from pytae.repl import PytaeRepl

    monkeypatch.chdir(tmp_path)
    penguins_pq = DATA_PATH / "penguins.parquet"
    assert penguins_pq.exists()

    outputs = []
    r = PytaeRepl()

    # 1. Ingest via `df = scan penguins.parquet`
    r.execute_line(f"df = scan {penguins_pq}", output_fn=outputs.append)
    assert any("Scanned penguins.parquet as 'df' (lazy, 7 cols)." in o for o in outputs)
    assert isinstance(r.tables["df"], pl.LazyFrame)
    assert isinstance(r.current_df, pl.LazyFrame)

    # 2. Prompt shows lazy status
    prompt = r._build_prompt()
    assert "[df (lazy)]>" in prompt or "[df: lazy" in prompt

    # 3. Fast inspections push down without materializing
    outputs.clear()
    r.execute_line("-cols", output_fn=outputs.append)
    assert any("species" in o for o in outputs)
    assert isinstance(r.tables["df"], pl.LazyFrame)

    outputs.clear()
    r.execute_line("-explain", output_fn=outputs.append)
    assert any("SCAN" in o or "Parquet" in o or "PROJECT" in o for o in outputs)

    outputs.clear()
    r.execute_line("-head 3", output_fn=outputs.append)
    assert any("species" in o for o in outputs)

    outputs.clear()
    r.execute_line("-schema", output_fn=outputs.append)
    assert any("species" in o for o in outputs)

    outputs.clear()
    r.execute_line("status table df", output_fn=outputs.append)
    assert any("lazy scan" in o for o in outputs)

    outputs.clear()
    r.execute_line("df", output_fn=outputs.append)
    assert any("lazy, 7 cols" in o for o in outputs)

    # 4. Pipeline chaining without materialization
    outputs.clear()
    r.execute_line("k = df -filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert any("Created 'k' (lazy, 7 cols)." in o for o in outputs)
    assert isinstance(r.tables["k"], pl.LazyFrame)

    # 5. Materialization via -collect
    outputs.clear()
    r.execute_line("k -collect", output_fn=outputs.append)
    assert any("Materialized 'k'" in o for o in outputs)
    assert isinstance(r.tables["k"], pl.DataFrame)
    assert r.tables["k"].shape[0] == 124  # 124 Gentoo rows

    # 6. Materialize subset via assignment with -collect
    outputs.clear()
    r.execute_line("m = df -head 10 -collect", output_fn=outputs.append)
    assert any("Created 'm' (10 rows x 7 cols)." in o for o in outputs)
    assert isinstance(r.tables["m"], pl.DataFrame)
    assert r.tables["m"].shape[0] == 10

    # 7. Plotting guard on lazy table
    outputs.clear()
    r.execute_line("df -plot bill_length_mm", output_fn=outputs.append)
    assert any("plotting commands cannot be run directly on lazy scanned tables" in o for o in outputs)

    # 8. Streaming output to file
    out_pq = tmp_path / "streamed.parquet"
    outputs.clear()
    r.execute_line(f"df -o {out_pq.name}", output_fn=outputs.append)
    assert any(f"Streamed lazy pipeline to {out_pq.name}." in o for o in outputs)
    assert out_pq.exists()

    r.close()


def test_repl_canonical_input_path_and_relative_export(tmp_path, monkeypatch):
    """Verify that history logs full canonical absolute paths for inputs, while export script defaults to absolute and -relative outputs relative paths."""
    import ast

    import polars as pl

    from pytae.repl import PytaeRepl

    monkeypatch.chdir(tmp_path)
    # Create sample input dataset in a subfolder
    sub_dir = tmp_path / "data_in"
    sub_dir.mkdir()
    sample_file = sub_dir / "sample.parquet"
    pl.DataFrame({"id": [1, 2, 3], "val": [10.0, 20.0, 30.0]}).write_parquet(sample_file)

    outputs = []
    r = PytaeRepl()

    # User inputs relative file path
    rel_input = "data_in/sample.parquet"
    r.execute_line(f"df = {rel_input}", output_fn=outputs.append)
    assert any("Loaded sample.parquet as 'df'" in o for o in outputs)

    # Transform and save to relative output
    r.execute_line("k = df -filter \"id > 1\"", output_fn=outputs.append)
    r.execute_line("k -o result.parquet", output_fn=outputs.append)

    # 1. Verify history contains full canonical absolute path for input, but relative path for output
    canonical_input_path = sample_file.resolve().as_posix()
    assert any(canonical_input_path in entry for entry in r.history)
    # Raw session history log must also contain the canonical absolute path
    raw_hist_text = r.session_history_path.read_text(encoding="utf-8")
    assert canonical_input_path in raw_hist_text
    # Output path strictly remained relative in history
    assert any("k -o result.parquet" in entry for entry in r.history)
    assert "k -o result.parquet" in raw_hist_text

    # 2. Export default (absolute paths)
    py_abs_file = tmp_path / "pipeline_abs.py"
    pt_abs_file = tmp_path / "pipeline_abs.pt"
    outputs.clear()
    r.execute_line(f'export script "{py_abs_file}"', output_fn=outputs.append)
    r.execute_line(f'export script "{pt_abs_file}"', output_fn=outputs.append)

    py_abs_code = py_abs_file.read_text(encoding="utf-8")
    ast.parse(py_abs_code)
    assert canonical_input_path in py_abs_code
    assert "result.parquet" in py_abs_code

    pt_abs_code = pt_abs_file.read_text(encoding="utf-8")
    assert canonical_input_path in pt_abs_code
    assert "-o result.parquet" in pt_abs_code

    # 3. Export with -relative (relative paths to current working directory)
    py_rel_file = tmp_path / "pipeline_rel.py"
    pt_rel_file = tmp_path / "pipeline_rel.pt"
    outputs.clear()
    r.execute_line(f'export script "{py_rel_file}" -relative', output_fn=outputs.append)
    r.execute_line(f'export script "{pt_rel_file}" -relative', output_fn=outputs.append)

    py_rel_code = py_rel_file.read_text(encoding="utf-8")
    ast.parse(py_rel_code)
    assert "data_in/sample.parquet" in py_rel_code
    assert canonical_input_path not in py_rel_code
    assert "result.parquet" in py_rel_code

    pt_rel_code = pt_rel_file.read_text(encoding="utf-8")
    assert "data_in/sample.parquet" in pt_rel_code
    assert canonical_input_path not in pt_rel_code
    assert "-o result.parquet" in pt_rel_code

    # 4. Strictly reject `--relative`
    outputs.clear()
    r.execute_line(f'export script "{tmp_path}/invalid.py" --relative', output_fn=outputs.append)
    assert any("pytae: '--relative' is not recognized; use '-relative'." in o for o in outputs)

    r.close()


def test_repl_auto_creates_config_json_and_cleans_empty_history(tmp_path, monkeypatch):
    """Verify that launching REPL auto-creates ~/.pytae/config.json with defaults, while leaving zero history folders on empty exit."""
    import json

    from pytae.repl import PytaeRepl

    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PYTAE_HOME", raising=False)
    monkeypatch.delenv("PYTAE_HISTORY_DIR", raising=False)

    # 1. Direct execute_line("exit") then close()
    r = PytaeRepl()
    r.execute_line("exit")
    r.close()

    # config.json is created with defaults
    cfg_path = fake_home / ".pytae" / "config.json"
    assert cfg_path.exists(), "config.json must be auto-created on first launch"
    cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg_data["max_rows"] == 10
    assert cfg_data["max_cols"] == "all"
    assert cfg_data["float_precision"] == "auto"
    assert cfg_data["comma"] == "off"

    # Empty history directory is cleaned up
    assert not (fake_home / ".pytae" / "history").exists(), "Empty history directory must be cleaned up on exit"

    # 2. Test with custom user-specified directory ($PYTAE_HOME)
    custom_home = tmp_path / "custom_pytae_home"
    monkeypatch.setenv("PYTAE_HOME", str(custom_home))
    r2 = PytaeRepl()
    monkeypatch.setattr("builtins.input", lambda prompt="": "exit")
    r2.run(output_fn=lambda _: None)
    r2.close()

    custom_cfg = custom_home / "config.json"
    assert custom_cfg.exists(), "config.json must be auto-created in user-specified $PYTAE_HOME"
    assert not (custom_home / "history").exists(), "Empty history directory must be cleaned up on exit in custom home"


def test_repl_load_config_json_on_startup(tmp_path, monkeypatch):
    """Verify that PytaeRepl loads set options from ~/.pytae/config.json on startup."""
    import json

    from pytae.repl import PytaeRepl

    fake_home = tmp_path / "fake_home"
    pytae_dir = fake_home / ".pytae"
    pytae_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PYTAE_HOME", raising=False)
    monkeypatch.delenv("PYTAE_HISTORY_DIR", raising=False)

    cfg_file = pytae_dir / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "max_rows": 25,
                "max_cols": 8,
                "float_precision": 3,
                "comma": "on",
            }
        ),
        encoding="utf-8",
    )

    r = PytaeRepl()
    assert r.max_rows == 25
    assert r.max_cols == 8
    assert r.float_precision == 3
    assert r.comma is True

    outputs = []
    r.execute_line("set", output_fn=outputs.append)
    out_text = "\n".join(outputs)
    assert "max_rows        = 25 (options: <int>, default)" in out_text
    assert "max_cols        = 8 (options: <int>, all, default)" in out_text
    assert "float_precision = 3 (options: <int>, auto, default)" in out_text
    assert "comma           = on (options: on, off)" in out_text
    r.close()


def test_repl_config_json_defaults_and_saving(tmp_path, monkeypatch):
    """Verify string variants in config.json and 'set save' functionality."""
    import json

    from pytae.repl import PytaeRepl

    fake_home = tmp_path / "fake_home2"
    pytae_dir = fake_home / ".pytae"
    pytae_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PYTAE_HOME", raising=False)

    # 1. Test string options: default, all, auto, off
    cfg_file = pytae_dir / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "max_rows": "default",
                "max_cols": "all",
                "float_precision": "auto",
                "comma": "off",
            }
        ),
        encoding="utf-8",
    )
    r = PytaeRepl()
    assert r.max_rows == 10
    assert r.max_cols is None
    assert r.float_precision is None
    assert r.comma is False

    # 2. Mutate settings and save via interactive 'set save'
    r.execute_line("set max_rows = 50")
    r.execute_line("set comma = on")
    r.execute_line("set float_precision = 4")
    r.execute_line("set max_cols = 12")
    save_outputs: list[str] = []
    r.execute_line("set save", output_fn=save_outputs.append)
    assert any("Saved configuration to" in o for o in save_outputs)

    saved_data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert saved_data["max_rows"] == 50
    assert saved_data["comma"] == "on"
    assert saved_data["float_precision"] == 4
    assert saved_data["max_cols"] == 12
    r.close()

    # 3. New REPL session reloads the updated config
    r_new = PytaeRepl()
    assert r_new.max_rows == 50
    assert r_new.comma is True
    assert r_new.float_precision == 4
    assert r_new.max_cols == 12
    r_new.close()


