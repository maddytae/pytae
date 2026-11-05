"""Tests for REPL multi-line input support (Model 1 + Model 3)."""

from __future__ import annotations

from pytae.repl import PytaeRepl, _is_multiline_complete


def test_is_multiline_complete_helper():
    # Empty or single line commands are complete
    assert _is_multiline_complete("") is True
    assert _is_multiline_complete("df = sample:penguins") is True
    assert _is_multiline_complete("status table") is True

    # Trailing backslash means incomplete
    assert _is_multiline_complete("df_clean = df \\") is False
    assert _is_multiline_complete("df_clean = df \\\n -filter 'x > 1' \\") is False

    # Once final line does not end in backslash, it is complete
    assert _is_multiline_complete("df_clean = df \\\n -filter 'x > 1'") is True

    # Unclosed string quotes mean incomplete
    assert _is_multiline_complete('-sql "SELECT *') is False
    assert _is_multiline_complete("-sql 'SELECT *") is False
    assert _is_multiline_complete('-sql """SELECT *') is False

    # Closed string quotes are complete
    assert _is_multiline_complete('-sql "SELECT *\nFROM df"') is True
    assert _is_multiline_complete('-sql """SELECT *\nFROM df"""') is True

    # Unclosed brackets mean incomplete
    assert _is_multiline_complete("cfg = {") is False
    assert _is_multiline_complete("cfg = {\n 'a': 1,") is False
    assert _is_multiline_complete("species = [") is False
    assert _is_multiline_complete("species = ['Gentoo',") is False

    # Closed brackets are complete
    assert _is_multiline_complete("cfg = {\n 'a': 1,\n 'b': 2\n}") is True
    assert _is_multiline_complete("species = [\n 'Gentoo',\n 'Adelie'\n]") is True

    # Brackets inside strings do not alter bracket depth
    assert _is_multiline_complete('-filter "species in (\'Gentoo\', \'Adelie\')"') is True


def test_repl_multiline_pipeline_with_backslash():
    outputs: list[str] = []
    r = PytaeRepl()
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    assert r.current_df is not None

    # Multi-line pipeline with trailing backslashes
    multiline_cmd = (
        "df_clean = df \\\n"
        "  -filter 'body_mass_g > 3500' \\\n"
        "  -mutate 'kg = body_mass_g / 1000' \\\n"
        "  -arrange 'kg desc'"
    )
    outputs.clear()
    r.execute_line(multiline_cmd, output_fn=outputs.append)

    assert "df_clean" in r.tables
    res_df = r.tables["df_clean"]
    assert "kg" in res_df.columns
    assert (res_df["body_mass_g"] > 3500).all()
    # Check that kg is sorted descending
    kg_vals = res_df["kg"].to_list()
    assert kg_vals == sorted(kg_vals, reverse=True)


def test_repl_multiline_sql_query():
    outputs: list[str] = []
    r = PytaeRepl()
    r.execute_line("df = sample:penguins", output_fn=outputs.append)

    # Multi-line preview SQL
    sql_cmd = (
        "-sql '\n"
        "  SELECT species, COUNT(*) as n\n"
        "  FROM df\n"
        "  WHERE body_mass_g > 3500\n"
        "  GROUP BY species\n"
        "  ORDER BY n DESC\n"
        "'"
    )
    outputs.clear()
    r.execute_line(sql_cmd, output_fn=outputs.append)
    assert any("-> df: 3 rows x 2 cols" in o for o in outputs)
    assert r.current_df is not None
    assert r.current_df.shape == (3, 2)
    assert "Gentoo" in r.current_df["species"].to_list()

    # Reload full dataset for next query
    r.execute_line("df = sample:penguins", output_fn=outputs.append)

    # Multi-line assigned SQL
    assign_sql_cmd = (
        "summary = -sql '\n"
        "  SELECT island, COUNT(*) as n\n"
        "  FROM df\n"
        "  GROUP BY island\n"
        "'"
    )
    outputs.clear()
    r.execute_line(assign_sql_cmd, output_fn=outputs.append)
    assert "summary" in r.tables
    assert r.tables["summary"].shape[0] == 3


def test_repl_multiline_variable_assignment():
    outputs: list[str] = []
    r = PytaeRepl()

    dict_cmd = (
        "cfg = {\n"
        "  'min_mass': 3500,\n"
        "  'islands': ['Biscoe', 'Dream'],\n"
        "  'thresholds': {'p10': 3200, 'p90': 5500}\n"
        "}"
    )
    r.execute_line(dict_cmd, output_fn=outputs.append)
    assert "cfg" in r.variables
    assert r.variables["cfg"]["min_mass"] == 3500
    assert r.variables["cfg"]["islands"] == ["Biscoe", "Dream"]
    assert r.variables["cfg"]["thresholds"]["p90"] == 5500


def test_repl_multiline_py_block():
    outputs: list[str] = []
    r = PytaeRepl()
    r.execute_line("df = sample:penguins", output_fn=outputs.append)

    # Multi-line py statement with for loop and print
    py_code = (
        "py\n"
        "cols = [c for c in pldf.columns if 'mass' in c]\n"
        "for c in cols:\n"
        "    print(f'FOUND_COL: {c}')"
    )
    outputs.clear()
    r.execute_line(py_code, output_fn=outputs.append)
    assert any("FOUND_COL: body_mass_g" in o for o in outputs)


def test_repl_run_input_loop_continuation_prompt():
    """Verify that PytaeRepl.run() presents '... ' continuation prompts until input is complete."""
    lines_to_feed = [
        "df = sample:penguins",
        "df_test = df \\",
        "  -filter 'body_mass_g > 4000'",
        "status table",
        "exit",
    ]
    prompts_seen: list[str] = []
    outputs: list[str] = []

    def mock_input(prompt: str) -> str:
        prompts_seen.append(prompt)
        if lines_to_feed:
            return lines_to_feed.pop(0)
        raise EOFError

    r = PytaeRepl()
    r.run(input_fn=mock_input, output_fn=outputs.append)

    assert "df_test" in r.tables
    # Check prompts: initial prompt, then continuation '... ', then primary prompt
    assert any("pytae" in p for p in prompts_seen)
    assert "... " in prompts_seen


def test_repl_run_py_block_mode_and_empty_line_termination():
    """Verify that bare 'py' enters multi-line block mode and terminates on empty line."""
    lines_to_feed = [
        "df = sample:penguins",
        "py",
        "for col in pldf.columns[:2]:",
        "    print(f'TEST_LOOP: {col}')",
        "",  # Empty line terminates py block mode
        "exit",
    ]
    prompts_seen: list[str] = []
    outputs: list[str] = []

    def mock_input(prompt: str) -> str:
        prompts_seen.append(prompt)
        if lines_to_feed:
            return lines_to_feed.pop(0)
        raise EOFError

    r = PytaeRepl()
    r.run(input_fn=mock_input, output_fn=outputs.append)

    assert any("TEST_LOOP: species" in o for o in outputs)
    assert any("TEST_LOOP: island" in o for o in outputs)
    assert "... " in prompts_seen
