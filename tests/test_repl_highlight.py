"""Tests for REPL live syntax highlighting (src/pytae/_highlight.py and integration)."""

from __future__ import annotations

import io
import json
import sys

from pytae._highlight import (
    detect_multiline_mode,
    highlight_prompt,
    highlight_repl_text,
    is_color_enabled,
    strip_ansi,
)
from pytae.repl import PytaeRepl, _console_input


def test_highlight_preserves_characters_and_newlines():
    samples = [
        ("dsl", ""),
        ("dsl", "df = sample:penguins"),
        ("dsl", 'df_clean = df -filter "species == \'Gentoo\' && body_mass_g > @min_mass" -mutate "kg = body_mass_g / 1000"'),
        ("dsl", 'summary = -sql "SELECT species, COUNT(*) FROM penguins WHERE species = \'Adelie\' GROUP BY 1"'),
        ("dsl", 'df = -sql "SELECT *\nFROM penguins\nWHERE species = \'Gentoo\'"'),
        ("dsl", 'df = -filter "unclosed quote'),
        ("dsl", "py { import math; print(math.sqrt(16)) }"),
        ("py", "def custom_fn(x):\n    d = {'a': 1, 'b': 2}\n    # comment with brace }\n    return f'val={x}'"),
        ("py", 's = """multi\nline\nstring"""\nx = pd.Series([1, 2, 3])'),
        ("py", 'unclosed = "still typing'),
        ("sql_dq", "SELECT species, AVG(body_mass_g)\nFROM penguins\nWHERE sex = 'FEMALE'\nGROUP BY 1"),
        ("sql_dq", 'WHERE sex = \'FEMALE\'" -head 5'),
    ]
    tables = {"df", "penguins", "orders"}
    variables = {"min_mass", "data_dir"}
    py_env = {"math", "custom_fn"}

    for mode, text in samples:
        hl = highlight_repl_text(
            text,
            mode=mode,
            tables=tables,
            variables=variables,
            py_env=py_env,
        )
        assert strip_ansi(hl) == text
        assert hl.count("\n") == text.count("\n")
        # Ensure no ANSI color code is left open across a newline
        for line_part in hl.split("\n")[:-1]:
            last_esc = line_part.rfind("\x1b[")
            if last_esc != -1:
                assert line_part.rfind("\x1b[0m") >= last_esc


def test_highlight_semantic_tokens():
    # DSL tokens
    dsl_hl = highlight_repl_text(
        'orders -filter "amount > @limit" -head 10',
        mode="dsl",
        tables={"orders"},
        variables={"limit"},
    )
    assert "\x1b[1;32morders\x1b[0m" in dsl_hl
    assert "\x1b[1;36m-filter\x1b[0m" in dsl_hl
    assert "\x1b[35m@limit\x1b[0m" in dsl_hl
    assert "\x1b[33m10\x1b[0m" in dsl_hl

    # SQL inside sql { ... } and <var> = sql { ... }
    sql_hl = highlight_repl_text(
        "summary = sql { SELECT COUNT(*) FROM orders WHERE status = 'ok' }",
        mode="dsl",
        tables={"orders"},
    )
    assert "\x1b[1;36msql\x1b[0m" in sql_hl
    assert "\x1b[1;34mSELECT\x1b[0m" in sql_hl
    assert "\x1b[36mCOUNT\x1b[0m" in sql_hl
    assert "\x1b[1;32morders\x1b[0m" in sql_hl
    assert "\x1b[32m'ok'\x1b[0m" in sql_hl
    assert strip_ansi(sql_hl) == "summary = sql { SELECT COUNT(*) FROM orders WHERE status = 'ok' }"

    # Python mode + preloaded stack + persisted py_env + session variables without @
    py_hl = highlight_repl_text(
        "py { import math; s = pd.Series([1, 2]); custom_fn(data_dir) }",
        mode="dsl",
        tables={"df"},
        variables={"data_dir"},
        py_env={"custom_fn"},
    )
    assert "\x1b[1;36mpy\x1b[0m" in py_hl
    assert "\x1b[35mimport\x1b[0m" in py_hl
    assert "\x1b[36mpd\x1b[0m" in py_hl
    assert "\x1b[1;32mcustom_fn\x1b[0m" in py_hl
    assert "\x1b[35mdata_dir\x1b[0m" in py_hl


def test_detect_multiline_mode():
    assert detect_multiline_mode([]) == "dsl"
    assert detect_multiline_mode(["df = sample:penguins \\"]) == "dsl"
    assert detect_multiline_mode(["py {", "  for i in range(3):"]) == "py"
    assert detect_multiline_mode(["py {", "  d = {'a': 1}"]) == "py"
    assert detect_multiline_mode(["py {", "  x = 1", "}"]) == "dsl"
    assert detect_multiline_mode(["sql {", "  SELECT * FROM df"]) == "sql"
    assert detect_multiline_mode(["summary = sql {", "  SELECT * FROM df WHERE msg = '}'"]) == "sql"
    assert detect_multiline_mode(["summary = sql {", "  SELECT * FROM df", "}"]) == "dsl"
    assert detect_multiline_mode(['summary = -sql "', "  SELECT * FROM df", "  WHERE x = 'abc'"]) == "sql_dq"
    assert detect_multiline_mode(['summary = -sql "', '  SELECT * FROM df"']) == "dsl"
    assert detect_multiline_mode(["summary = -sql '", "  SELECT * FROM df"]) == "sql_sq"


def test_highlight_prompt_preserves_text():
    prompts = [
        "pytae> ",
        "pytae [penguins: 344x8]> ",
        "pytae [df1, df2*]> ",
        "... ",
    ]
    for p in prompts:
        hp = highlight_prompt(p)
        assert strip_ansi(hp) == p
        assert "\x1b[" in hp


def test_is_color_enabled_respects_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert is_color_enabled() is True

    monkeypatch.setenv("NO_COLOR", "1")
    assert is_color_enabled() is False


def test_console_input_with_highlight_fn(monkeypatch):
    fake_out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_out)

    chars = list("df = sample:penguins\r")
    res = _console_input(
        highlight_prompt("pytae> "),
        [],
        read_char_fn=lambda: chars.pop(0) if chars else "\r",
        highlight_fn=lambda txt: highlight_repl_text(txt, mode="dsl", tables={"df"}),
        cont_prompt_raw=highlight_prompt("... "),
    )
    assert res == "df = sample:penguins"
    rendered = fake_out.getvalue()
    # ANSI colors appeared in terminal output, while returned text is pure plain string
    assert "\x1b[1;32msample:penguins\x1b[0m" in rendered
    assert "\x1b[1;32mdf\x1b[0m" in rendered

    # Multi-line buffer via Shift+Enter / initial_text preserves line splits & cont prompt color
    fake_out2 = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_out2)
    chars2 = list("print(pd.__name__)\r}\r")
    res2 = _console_input(
        highlight_prompt("pytae> "),
        [],
        read_char_fn=lambda: chars2.pop(0) if chars2 else "\r",
        initial_text="py {\n",
        highlight_fn=lambda txt: highlight_repl_text(txt, mode="dsl"),
        cont_prompt_raw=highlight_prompt("... "),
    )
    assert res2 == "py {\nprint(pd.__name__)\n    }"
    rendered2 = fake_out2.getvalue()
    assert "\x1b[90m... \x1b[0m" in rendered2
    assert "\x1b[36mpd\x1b[0m" in rendered2


def test_repl_set_syntax_highlight_and_config_persistence(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home_hl"
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PYTAE_HOME", raising=False)

    r = PytaeRepl()
    assert r.syntax_highlight is True

    out: list[str] = []
    r.execute_line("set syntax_highlight = off", output_fn=out.append)
    assert r.syntax_highlight is False
    assert any("Set syntax_highlight = off." in o for o in out)

    out.clear()
    r.execute_line("set save", output_fn=out.append)
    cfg_data = json.loads((fake_home / ".pytae" / "config.json").read_text(encoding="utf-8"))
    assert cfg_data["syntax_highlight"] == "off"
    r.close()

    r2 = PytaeRepl()
    assert r2.syntax_highlight is False
    out2: list[str] = []
    r2.execute_line("set", output_fn=out2.append)
    assert any("syntax_highlight = off" in o for o in out2)
    r2.close()


def test_color_themes_preserve_text_and_emit_distinct_palettes():
    from pytae._highlight import AVAILABLE_THEMES, format_theme_preview

    sample = 'orders -filter "amt > @min" | sql { SELECT COUNT(*) FROM orders } | py { pd.Series([1, 2]) }'
    rendered_themes: set[str] = set()
    for t in AVAILABLE_THEMES:
        hl = highlight_repl_text(sample, mode="dsl", tables={"orders"}, variables={"min"}, theme=t)
        assert strip_ansi(hl) == sample
        assert strip_ansi(highlight_prompt("pytae [orders: 10x2]> ", theme=t)) == "pytae [orders: 10x2]> "
        rendered_themes.add(hl)

    # Every theme produces distinct ANSI styling
    assert len(rendered_themes) == len(AVAILABLE_THEMES)
    # 256-color monokai uses 38;5;148 for tables
    mono = highlight_repl_text("orders", mode="dsl", tables={"orders"}, theme="monokai")
    assert "\x1b[38;5;148m" in mono or "\x1b[1;38;5;148m" in mono

    preview_lines = format_theme_preview("dracula", color=True)
    assert any(line.startswith("* dracula") for line in preview_lines)
    assert len(preview_lines) == len(AVAILABLE_THEMES)


def test_repl_set_theme_preview_persistence_and_completion(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home_theme"
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PYTAE_HOME", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    r = PytaeRepl()
    assert r.theme == "default"

    # Completion after 'set ' and 'set theme '
    assert "theme" in r._get_completions("t", "set t")
    assert "monokai" in r._get_completions("mo", "set theme mo")

    # Preview via 'set theme'
    out: list[str] = []
    r.execute_line("set theme", output_fn=out.append)
    out_text = "\n".join(out)
    assert "theme            = default" in out_text
    assert "* default" in out_text
    assert "monokai" in out_text

    # Invalid theme rejected cleanly
    out.clear()
    r.execute_line("set theme = neon_unicorn", output_fn=out.append)
    assert any("invalid theme" in o for o in out)
    assert r.theme == "default"

    # Valid theme applied and persisted
    out.clear()
    r.execute_line("set theme = dracula", output_fn=out.append)
    assert r.theme == "dracula"
    assert any("Set theme = dracula." in o for o in out)
    r.execute_line("set save")
    cfg_data = json.loads((fake_home / ".pytae" / "config.json").read_text(encoding="utf-8"))
    assert cfg_data["theme"] == "dracula"
    r.close()

    r2 = PytaeRepl()
    assert r2.theme == "dracula"
    r2.close()
