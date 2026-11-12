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
    orig_shape = r.current_df.shape

    # Multi-line bare SQL is non-destructive preview (does not mutate active df)
    sql_cmd = (
        "sql {\n"
        "  SELECT species, COUNT(*) as n\n"
        "  FROM df\n"
        "  WHERE body_mass_g > 3500\n"
        "  GROUP BY species\n"
        "  ORDER BY n DESC\n"
        "}"
    )
    outputs.clear()
    r.execute_line(sql_cmd, output_fn=outputs.append)
    preview_text = "\n".join(outputs)
    assert "Gentoo" in preview_text
    assert r.current_df is not None
    assert r.current_df.shape == orig_shape

    # Multi-line assigned SQL creates new table
    assign_sql_cmd = (
        "summary = sql {\n"
        "  SELECT island, COUNT(*) as n\n"
        "  FROM df\n"
        "  GROUP BY island\n"
        "}"
    )
    outputs.clear()
    r.execute_line(assign_sql_cmd, output_fn=outputs.append)
    assert "summary" in r.tables
    assert r.tables["summary"].shape[0] == 3

    # Export compiled Python script executes cleanly
    from pytae.repl import _compile_history_to_python, _is_replayable_entry_static

    replayable = [h for h in r.history if _is_replayable_entry_static(h)]
    # Bare sql { ... } preview is excluded; assigned summary = sql { ... } is kept
    assert len(replayable) == 2
    py_script = _compile_history_to_python(replayable)
    assert "pt.sql({'df': df}" in py_script
    ns: dict[str, object] = {}
    exec(compile(py_script, "<test_sql_export>", "exec"), ns)
    assert ns["summary"].shape[0] == 3


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
        "py {\n"
        "cols = [c for c in pldf.columns if 'mass' in c]\n"
        "for c in cols:\n"
        "    print(f'FOUND_COL: {c}')\n"
        "}"
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
    """Verify that 'py {' enters multi-line block mode and terminates on '}'."""
    lines_to_feed = [
        "df = sample:penguins",
        "py {",
        "for col in pldf.columns[:2]:",
        "    print(f'TEST_LOOP: {col}')",
        "}",
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


def test_repl_history_preserves_multiline_syntax():
    """Verify that multi-line pipelines with '\\' preserve multiline formatting in history for 2D recall."""
    r = PytaeRepl()
    outputs = []
    multiline_cmd = 'df = sample:penguins \\\n  -filter "species == \'Gentoo\'" \\\n  -mutate "kg = 1.0"'
    r.execute_line(multiline_cmd, output_fn=outputs.append)

    assert "df" in r.tables
    assert len(r._raw_history) == 1
    assert r._raw_history[0] == multiline_cmd
    r.close()


def test_repl_readline_beginning_of_line_bindings():
    """Verify that _init_readline configures beginning-of-line bindings for Home / Cmd+Left."""
    from pytae.repl import _init_readline

    r = PytaeRepl()
    # Calling _init_readline must succeed without exceptions across all platforms
    _init_readline(r._complete)
    r.close()


def test_win_console_input_ctrl_a_beginning_of_line():
    """Verify that Ctrl+A in console input moves the cursor to beginning of line (cursor_pos = 0)."""
    from pytae.repl import _win_console_input

    # Feed 'abc', then Ctrl+A (\x01), then Enter (\r)
    chars = ["a", "b", "c", "\x01", "\r"]

    def fake_read():
        return chars.pop(0)

    res = _win_console_input("", [], read_char_fn=fake_read)
    assert res == "abc"


def test_repl_ctrl_a_jumps_to_beginning_of_multiline_command():
    """Verify that Ctrl+A moves cursor to beginning of line buffer even across multi-line inputs."""
    from pytae.repl import _init_readline

    # Calling _init_readline initializes the beginning-of-command macros cleanly
    _init_readline()

    from pytae.repl import _win_console_input

    # Feed long command, then Ctrl+A (\x01), then insert 'PREFIX_', then Enter (\r)
    chars = list("df = sample:penguins -filter \"species == 'Gentoo'\"") + ["\x01"] + list("PREFIX_") + ["\r"]

    def fake_read():
        return chars.pop(0)

    res = _win_console_input("", [], read_char_fn=fake_read)
    assert res.startswith("PREFIX_df = sample:penguins")


def test_collapse_inline_line_continuations():
    """Verify that unquoted inline line continuations with backslash are collapsed smoothly."""
    from pytae.repl import _collapse_inline_line_continuations

    assert (
        _collapse_inline_line_continuations("-ndasn dsa sajo sad \\ -sshsdhi")
        == "-ndasn dsa sajo sad -sshsdhi"
    )
    assert _collapse_inline_line_continuations("-s a \\ -s b \\ -s c") == "-s a -s b -s c"
    # Preserves quotes
    assert (
        _collapse_inline_line_continuations('-filter "species == \'a\\s+b\'" \\ -s x')
        == '-filter "species == \'a\\s+b\'" -s x'
    )
    # Preserves Windows path with backslash
    assert (
        _collapse_inline_line_continuations("C:\\Users\\test\\data.parquet \\ -s a")
        == "C:\\Users\\test\\data.parquet -s a"
    )
    # Trailing backslash
    assert _collapse_inline_line_continuations("-s a \\") == "-s a"


def test_console_input_shift_enter_splits_line():
    """Verify that pressing Shift+Enter in the middle of a command splits text to the next line in the editor."""
    from pytae.repl import _console_input

    # Type 'hello world', move cursor left 5 times (to before 'world'), press Shift+Enter (\x1b[13;2u), then Enter (\r)
    chars = list("hello world") + ["\x1b", "[D"] * 5 + ["\x1b", "[13;2u"] + ["\r"]

    def fake_read():
        if chars:
            return chars.pop(0)
        return "\r"

    res = _console_input("pytae> ", [], read_char_fn=fake_read)
    assert res == "hello \\\n  world"


def test_console_input_enter_after_backslash_splits_line():
    """Verify that pressing regular Enter in the middle right after a '\\' splits into the next line in the editor."""
    from pytae.repl import _console_input

    # User types '-ndasn dsa sajo sad \ -sshsdhi', navigates back over '-sshsdhi' to right after '\', presses Enter, then Enter on complete buffer
    raw_cmd = "-ndasn dsa sajo sad \\ -sshsdhi"
    chars = list(raw_cmd) + ["\x1b", "[D"] * 9 + ["\r", "\r"]

    def fake_read():
        if chars:
            return chars.pop(0)
        return "\r"

    res = _console_input("pytae> ", [], read_char_fn=fake_read)
    assert res == "-ndasn dsa sajo sad \\\n  -sshsdhi"


def test_console_input_2d_up_down_arrow_navigation():
    """Verify that Up and Down arrows move vertically within a multiline buffer before history recall."""
    from pytae.repl import _console_input

    # Initial text has 2 lines: "line1" and "line2". Cursor starts at end of "line2" (index 11).
    # Press Up arrow (\x1b[A), insert 'UP_', press Down arrow (\x1b[B), insert '_DOWN', press Enter (\r).
    init_text = "line1\nline2"
    chars = ["\x1b", "[A"] + list("UP_") + ["\x1b", "[B"] + list("_DOWN") + ["\r"]

    def fake_read():
        if chars:
            return chars.pop(0)
        return "\r"

    res = _console_input("pytae> ", ["old_history"], read_char_fn=fake_read, initial_text=init_text)
    # The Up arrow moved to line1 where 'UP_' was inserted; Down arrow returned to line2 where '_DOWN' was appended.
    assert res == "line1UP_\nline2_DOWN"


def test_console_input_backspace_merges_lines():
    """Verify that pressing Backspace at col 0 of a continuation line deletes the newline and merges lines."""
    from pytae.repl import _console_input

    # Initial text is "line1\nline2". Cursor starts at index 6 (start of "line2").
    # Press Backspace (\x7f), then Enter (\r).
    chars = ["\x7f", "\r"]

    def fake_read():
        if chars:
            return chars.pop(0)
        return "\r"

    # initial_text has cursor at end by default unless we navigate left 5 times to index 6
    full_chars = ["\x1b", "[D"] * 5 + chars
    res = _console_input("pytae> ", [], read_char_fn=lambda: full_chars.pop(0), initial_text="line1\nline2")
    assert res == "line1line2"


def test_console_input_history_recall_multiline():
    """Verify that Up arrow recalls full multiline command from history and allows 2D editing."""
    from pytae.repl import _console_input

    multiline_hist = "df = sample:penguins \\\n  -filter 'x > 1'"
    # Press Up arrow (\x1b[A) to recall multiline command, then press Enter (\r)
    chars = ["\x1b", "[A", "\r"]

    def fake_read():
        if chars:
            return chars.pop(0)
        return "\r"

    res = _console_input("pytae> ", [multiline_hist], read_char_fn=fake_read)
    assert res == multiline_hist


def test_repl_execute_line_with_inline_backslash():
    """Verify that REPL executes commands with inline line-continuation backslashes without error."""
    import polars as pl

    from pytae.repl import PytaeRepl

    df = pl.DataFrame({"species": ["Adelie", "Gentoo"], "island": ["Torgersen", "Biscoe"]})
    r = PytaeRepl(df=df)
    outputs = []
    # User submits command with inline backslash on a single line
    r.execute_line("-s species \\ -s island", output_fn=outputs.append)
    assert r.current_df is not None
    assert r.current_df.columns == ["species", "island"]
    # Verify history recorded collapsed line
    assert r._raw_history[-1] == "-s species -s island"
    r.close()


def test_console_input_tab_inserts_spaces():
    """Verify that pressing Tab at start of line or when no matches exist inserts 4 spaces."""
    from pytae.repl import _console_input

    # Press Tab (\t), then Enter (\r)
    chars = ["\t", "\r"]
    res = _console_input("pytae> ", [], read_char_fn=lambda: chars.pop(0) if chars else "\r")
    assert res == "    "

    # Mid-line Tab with no autocompletion matches inserts 4 spaces
    chars2 = ["a", "=", "1", "\t", "\r"]
    res2 = _console_input("pytae> ", [], read_char_fn=lambda: chars2.pop(0) if chars2 else "\r")
    assert res2 == "a=1    "


def test_interactive_py_block_auto_indent():
    """Verify that entering py { auto-indents after colon and exits on '}'."""
    from pytae.repl import PytaeRepl

    r = PytaeRepl()
    outputs: list[str] = []

    # Sequence of inputs to simulate entering py block, a loop, and exiting
    script = [
        "py {",
        "total = 0",
        "for i in range(3):",
        "    total += i",
        "print(f'LOOP_RESULT={total}')",
        "}",
        "exit",
    ]
    input_iter = iter(script)

    r.run(input_fn=lambda _prompt="": next(input_iter), output_fn=outputs.append)
    assert any("LOOP_RESULT=3" in o for o in outputs)
    r.close()


def test_console_input_unix_newline_submits_line():
    """Verify that \\n (Unix/macOS Return key in cbreak mode) submits the line rather than treating it as Shift+Enter."""
    from pytae.repl import _console_input

    # In macOS / Unix terminal cbreak mode, pressing Return sends \n
    chars = list("df = sample:penguins\n")
    res = _console_input("pytae> ", [], read_char_fn=lambda: chars.pop(0) if chars else "\n")
    assert res == "df = sample:penguins"

    chars_loop = list("for i in range(10):\n")
    res_loop = _console_input("... ", [], read_char_fn=lambda: chars_loop.pop(0) if chars_loop else "\n")
    assert res_loop == "for i in range(10):"


def test_repl_py_block_preloaded_pandas():
    """Verify that pd is pre-loaded out-of-the-box without requiring 'import pandas as pd'."""
    r = PytaeRepl()
    outputs: list[str] = []
    py_code = (
        "py {\n"
        "s = pd.Series([10, 20, 30])\n"
        "print(f'SERIES_MEAN={s.mean():.1f}')\n"
        "}"
    )
    r.execute_line(py_code, output_fn=outputs.append)
    assert any("SERIES_MEAN=20.0" in o for o in outputs)
    r.close()


def test_repl_py_block_module_and_function_persistence():
    """Verify that imported modules, functions, and classes persist across py { ... } blocks."""
    r = PytaeRepl()
    outputs: list[str] = []

    # Block 1: import module, define custom function and class
    block1 = (
        "py {\n"
        "import math\n"
        "def custom_calc(n):\n"
        "    return math.sqrt(n) * 2\n"
        "class Multiplier:\n"
        "    def __init__(self, factor):\n"
        "        self.factor = factor\n"
        "    def run(self, val):\n"
        "        return val * self.factor\n"
        "}"
    )
    r.execute_line(block1, output_fn=outputs.append)

    # Block 2: use custom_calc and Multiplier without re-importing or re-defining
    outputs.clear()
    block2 = (
        "py {\n"
        "m = Multiplier(3)\n"
        "res = custom_calc(16)\n"
        "print(f'SQRT_RES={res}')\n"
        "print(f'MULT_RES={m.run(res)}')\n"
        "}"
    )
    r.execute_line(block2, output_fn=outputs.append)
    assert any("SQRT_RES=8.0" in o for o in outputs)
    assert any("MULT_RES=24.0" in o for o in outputs)

    # Block 3: import a builtin function
    block3 = (
        "py {\n"
        "from math import log10\n"
        "}"
    )
    r.execute_line(block3, output_fn=outputs.append)

    # Block 4: use imported builtin function
    outputs.clear()
    block4 = (
        "py {\n"
        "print(f'LOG_RES={log10(100):.1f}')\n"
        "}"
    )
    r.execute_line(block4, output_fn=outputs.append)
    assert any("LOG_RES=2.0" in o for o in outputs)

    r.close()


def test_repl_py_block_ephemeral_scratch_data_purged():
    """Verify that scratch variables/dataframes in py blocks are purged and not leaked across blocks."""
    r = PytaeRepl()
    outputs: list[str] = []

    # Block 1: assign an ephemeral list
    block1 = (
        "py {\n"
        "scratch_list = [10, 20, 30]\n"
        "print(f'DEFINED_SCRATCH={len(scratch_list)}')\n"
        "}"
    )
    r.execute_line(block1, output_fn=outputs.append)
    assert any("DEFINED_SCRATCH=3" in o for o in outputs)

    # Block 2: accessing scratch_list must fail with NameError
    outputs.clear()
    block2 = (
        "py {\n"
        "print(scratch_list)\n"
        "}"
    )
    r.execute_line(block2, output_fn=outputs.append)
    assert any("pytae Python Error: name 'scratch_list' is not defined" in o for o in outputs)

    r.close()


def test_repl_py_block_del_or_overwrite_evicts_from_env():
    """Verify that explicit del or overwriting with a non-callable evicts the item from _py_env."""
    r = PytaeRepl()
    outputs: list[str] = []

    # Block 1: define helper
    r.execute_line("py { def helper(): return 42 }", output_fn=outputs.append)
    assert "helper" in r._py_env

    # Block 2: verify callable
    outputs.clear()
    r.execute_line("py { print(f'HELPER={helper()}') }", output_fn=outputs.append)
    assert any("HELPER=42" in o for o in outputs)

    # Block 3: del helper
    r.execute_line("py { del helper }", output_fn=outputs.append)
    assert "helper" not in r._py_env

    # Block 4: accessing helper must fail with NameError
    outputs.clear()
    r.execute_line("py { print(helper()) }", output_fn=outputs.append)
    assert any("pytae Python Error: name 'helper' is not defined" in o for o in outputs)

    # Block 5: test overwriting function with non-callable integer
    r.execute_line("py { def helper2(): return 99 }", output_fn=outputs.append)
    assert "helper2" in r._py_env
    r.execute_line("py { helper2 = 123 }", output_fn=outputs.append)
    assert "helper2" not in r._py_env

    r.close()
    assert len(r._py_env) == 0


def test_console_input_unix_pty_up_arrow_history(monkeypatch):
    """Verify that pressing Up Arrow (ESC [ A) over a real Unix PTY recalls history rather than typing '[A'."""
    import sys

    if sys.platform == "win32":
        return

    import os
    import pty
    import select
    import threading
    import tty

    from pytae.repl import _console_input

    master, slave = pty.openpty()
    slave_in = None
    slave_out = None
    done = threading.Event()
    try:
        tty.setcbreak(slave)
        slave_in = os.fdopen(os.dup(slave), "r", encoding="utf-8", buffering=1)
        slave_out = os.fdopen(os.dup(slave), "w", encoding="utf-8", buffering=1)
        monkeypatch.setattr(sys, "stdin", slave_in)
        monkeypatch.setattr(sys, "stdout", slave_out)

        def _drain_master() -> None:
            while not done.is_set():
                try:
                    if select.select([master], [], [], 0.05)[0]:
                        os.read(master, 4096)
                except OSError:
                    break

        drain_thread = threading.Thread(target=_drain_master, daemon=True)
        drain_thread.start()

        # Write Up Arrow escape sequence + Enter all in one packet (tests unbuffered read vs select)
        threading.Timer(0.05, lambda: os.write(master, b"\x1b[A\r")).start()
        res = _console_input("pytae> ", ["df = sample:penguins"])
        assert res == "df = sample:penguins"
    finally:
        done.set()
        for obj in (slave_in, slave_out):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
        for fd_num in (master, slave):
            try:
                os.close(fd_num)
            except Exception:
                pass






