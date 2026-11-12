"""Lightweight, dependency-free ANSI syntax highlighter for the Pytae REPL."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Set as AbstractSet

RESET = "\x1b[0m"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Portable 16-color / bright ANSI palette (adapts cleanly to dark & light terminals)
_COLOR_CMD = "\x1b[1;36m"       # Bold Cyan: Pytae verbs (-filter, -sql), REPL commands, 'py'
_COLOR_KEYWORD = "\x1b[35m"     # Magenta: Python keywords, @variables
_COLOR_SQL_KW = "\x1b[1;34m"    # Bold Blue: SQL keywords (SELECT, FROM, WHERE...)
_COLOR_BUILTIN = "\x1b[36m"     # Cyan: pd, pl, pt, DataFrame, df, Python builtins, SQL functions
_COLOR_TABLE = "\x1b[1;32m"     # Bold Green: loaded workbench tables, sample:*, persisted py funcs/modules
_COLOR_STRING = "\x1b[32m"      # Green: quoted string literals
_COLOR_NUMBER = "\x1b[33m"      # Yellow: numeric literals
_COLOR_BRACE = "\x1b[33m"       # Yellow: { } [ ] ( )
_COLOR_COMMENT = "\x1b[90m"     # Dim gray: # comments, -- SQL comments, trailing \
_COLOR_PROMPT_DIM = "\x1b[90m"  # Dim gray: prompt brackets & continuation '... '

_REPL_COMMANDS: frozenset[str] = frozenset(
    {
        "status",
        "switch",
        "use",
        "rename",
        "rm",
        "checkpoint",
        "restore",
        "reset",
        "history",
        "export",
        "set",
        "clear",
        "exit",
        "quit",
        "help",
        "scan",
        "load",
        "table",
        "tables",
        "var",
        "vars",
        "save",
        "all",
        "default",
        "on",
        "off",
        "diff",
        "sql",
    }
)

_PY_KEYWORDS: frozenset[str] = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    }
)

_PY_BUILTINS: frozenset[str] = frozenset(
    {
        "pd",
        "pl",
        "pt",
        "DataFrame",
        "df",
        "pldf",
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "print",
        "range",
        "repr",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
    }
)

_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "ALL",
        "AND",
        "AS",
        "ASC",
        "BETWEEN",
        "BY",
        "CASE",
        "CAST",
        "CROSS",
        "DESC",
        "DISTINCT",
        "ELSE",
        "END",
        "EXCEPT",
        "EXISTS",
        "FALSE",
        "FROM",
        "FULL",
        "GROUP",
        "HAVING",
        "ILIKE",
        "IN",
        "INNER",
        "INTERSECT",
        "INTO",
        "IS",
        "JOIN",
        "LEFT",
        "LIKE",
        "LIMIT",
        "NOT",
        "NULL",
        "OFFSET",
        "ON",
        "OR",
        "ORDER",
        "OUTER",
        "OVER",
        "PARTITION",
        "RIGHT",
        "SELECT",
        "THEN",
        "TRUE",
        "UNION",
        "USING",
        "WHEN",
        "WHERE",
        "WITH",
    }
)

_SQL_FUNCTIONS: frozenset[str] = frozenset(
    {
        "AVG",
        "COALESCE",
        "CONCAT",
        "COUNT",
        "DENSE_RANK",
        "FIRST",
        "LAG",
        "LAST",
        "LEAD",
        "LOWER",
        "MAX",
        "MIN",
        "NULLIF",
        "RANK",
        "ROUND",
        "ROW_NUMBER",
        "SUBSTR",
        "SUBSTRING",
        "SUM",
        "TRIM",
        "UPPER",
    }
)

# Single-pass regex scanners (tolerant of incomplete tokens mid-typing)
_PY_TOKEN_RE = re.compile(
    r"(?P<COMMENT>#[^\n]*)"
    r'|(?P<TRIPLE>(?:[fFrRbBuU]{0,2})(?:"""[\s\S]*?(?:"""|$)|\'\'\'[\s\S]*?(?:\'\'\'|$)))'
    r'|(?P<STRING>(?:[fFrRbBuU]{0,2})(?:"(?:\\.|[^"\\\n])*(?:"|$)|\'(?:\\.|[^\'\\\n])*(?:\'|$)))'
    r"|(?P<NUMBER>\b(?:0[xXbBoO][0-9a-fA-F_]+|\d+(?:_\d+)*(?:\.\d+(?:_\d+)*)?(?:[eE][+-]?\d+)?j?)\b)"
    r"|(?P<IDENT>\b[A-Za-z_][A-Za-z0-9_]*\b)"
    r"|(?P<BRACE>[{}()\[\]])"
)

_SQL_TOKEN_RE = re.compile(
    r"(?P<COMMENT>--[^\n]*)"
    r"|(?P<STRING>'(?:''|[^'])*(?:'|$))"
    r"|(?P<VAR>@[A-Za-z_][A-Za-z0-9_.]*)"
    r"|(?P<NUMBER>\b\d+(?:\.\d+)?\b)"
    r"|(?P<IDENT>\b[A-Za-z_][A-Za-z0-9_]*\b)"
    r"|(?P<BRACE>[{}()])"
)

_DSL_TOKEN_RE = re.compile(
    r"(?P<COMMENT>(?<!\S)#[^\n]*)"
    r'|(?P<TRIPLE>(?:[rR])?(?:"""[\s\S]*?(?:"""|$)|\'\'\'[\s\S]*?(?:\'\'\'|$)))'
    r'|(?P<STRING>(?:[rR])?(?:"(?:\\.|[^"\\])*(?:"|$)|\'(?:\\.|[^\'\\])*(?:\'|$)))'
    r"|(?P<VAR>@[A-Za-z_][A-Za-z0-9_.]*)"
    r"|(?P<FLAG>(?<!\S)-[A-Za-z_][A-Za-z0-9_-]*)"
    r"|(?P<SAMPLE>\bsample:[A-Za-z0-9_]+\b)"
    r"|(?P<NUMBER>\b\d+(?:\.\d+)?\b)"
    r"|(?P<IDENT>\b[A-Za-z_][A-Za-z0-9_]*\b)"
    r"|(?P<BACKSLASH>\\(?=\s*(?:\n|$)))"
    r"|(?P<BRACE>[{}()\[\]])"
)

_VAR_IN_STR_RE = re.compile(r"@[A-Za-z_][A-Za-z0-9_.]*")


def is_color_enabled() -> bool:
    """Return True if terminal ANSI colors are allowed by environment settings."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return True


def enable_windows_vt_mode() -> None:
    """Best-effort enablement of VT100 ANSI color processing on Windows consoles."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if handle and handle != -1:
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR escape sequences from text."""
    return _ANSI_RE.sub("", text)


def _colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color, resetting cleanly before every newline."""
    if not color or not text:
        return text
    if "\n" not in text:
        return f"{color}{text}{RESET}"
    return "\n".join(f"{color}{part}{RESET}" if part else "" for part in text.split("\n"))


def _colorize_dsl_string(tok: str) -> str:
    """Highlight @variables inside a DSL string literal while keeping the string green."""
    if "@" not in tok:
        return _colorize(tok, _COLOR_STRING)
    out: list[str] = []
    last = 0
    for m in _VAR_IN_STR_RE.finditer(tok):
        if m.start() > last:
            out.append(_colorize(tok[last : m.start()], _COLOR_STRING))
        out.append(_colorize(m.group(0), _COLOR_KEYWORD))
        last = m.end()
    if last < len(tok):
        out.append(_colorize(tok[last:], _COLOR_STRING))
    return "".join(out)


def _highlight_python(
    text: str,
    tables: AbstractSet[str] = frozenset(),
    variables: AbstractSet[str] = frozenset(),
    py_env: AbstractSet[str] = frozenset(),
) -> str:
    """Highlight Python code cleanly even on partial/incomplete input."""
    out: list[str] = []
    last = 0
    for m in _PY_TOKEN_RE.finditer(text):
        if m.start() > last:
            out.append(text[last : m.start()])
        kind = m.lastgroup
        tok = m.group(0)
        if kind == "COMMENT":
            out.append(_colorize(tok, _COLOR_COMMENT))
        elif kind in ("TRIPLE", "STRING"):
            out.append(_colorize(tok, _COLOR_STRING))
        elif kind == "NUMBER":
            out.append(_colorize(tok, _COLOR_NUMBER))
        elif kind == "BRACE":
            out.append(_colorize(tok, _COLOR_BRACE))
        elif kind == "IDENT":
            if tok in _PY_KEYWORDS:
                out.append(_colorize(tok, _COLOR_KEYWORD))
            elif tok in _PY_BUILTINS:
                out.append(_colorize(tok, _COLOR_BUILTIN))
            elif tok in tables or tok in py_env:
                out.append(_colorize(tok, _COLOR_TABLE))
            elif tok in variables:
                out.append(_colorize(tok, _COLOR_KEYWORD))
            else:
                out.append(tok)
        else:
            out.append(tok)
        last = m.end()
    if last < len(text):
        out.append(text[last:])
    return "".join(out)


def _highlight_sql(
    text: str,
    tables: AbstractSet[str] = frozenset(),
) -> str:
    """Highlight ANSI SQL query text cleanly even on partial/incomplete input."""
    out: list[str] = []
    last = 0
    for m in _SQL_TOKEN_RE.finditer(text):
        if m.start() > last:
            out.append(text[last : m.start()])
        kind = m.lastgroup
        tok = m.group(0)
        if kind == "COMMENT":
            out.append(_colorize(tok, _COLOR_COMMENT))
        elif kind == "STRING":
            out.append(_colorize(tok, _COLOR_STRING))
        elif kind == "VAR":
            out.append(_colorize(tok, _COLOR_KEYWORD))
        elif kind == "NUMBER":
            out.append(_colorize(tok, _COLOR_NUMBER))
        elif kind == "BRACE":
            out.append(_colorize(tok, _COLOR_BRACE))
        elif kind == "IDENT":
            upper = tok.upper()
            if upper in _SQL_KEYWORDS:
                out.append(_colorize(tok, _COLOR_SQL_KW))
            elif upper in _SQL_FUNCTIONS:
                out.append(_colorize(tok, _COLOR_BUILTIN))
            elif tok in tables:
                out.append(_colorize(tok, _COLOR_TABLE))
            else:
                out.append(tok)
        else:
            out.append(tok)
        last = m.end()
    if last < len(text):
        out.append(text[last:])
    return "".join(out)


def _highlight_quoted_sql(tok: str, tables: AbstractSet[str]) -> str:
    """Highlight a quoted -sql argument string ('...' or \"...\") with SQL tokens inside."""
    if len(tok) < 2:
        return _colorize(tok, _COLOR_STRING)
    quote = tok[0]
    inner_start = 1
    if tok.startswith(('"""', "'''")):
        quote = tok[:3]
        inner_start = 3
    if len(tok) >= inner_start * 2 and tok.endswith(quote):
        inner = tok[inner_start : len(tok) - len(quote)]
        return (
            _colorize(quote, _COLOR_STRING)
            + _highlight_sql(inner, tables=tables)
            + _colorize(quote, _COLOR_STRING)
        )
    # Unclosed SQL string (mid-typing)
    inner = tok[inner_start:]
    return _colorize(quote, _COLOR_STRING) + _highlight_sql(inner, tables=tables)


def _find_matching_brace_close(text: str, open_brace_idx: int, *, sql_mode: bool = False) -> int | None:
    """Find matching closing '}' for a brace block starting at open_brace_idx, ignoring strings/comments."""
    depth = 1
    idx = open_brace_idx + 1
    n = len(text)
    quote: str | None = None
    in_comment = False
    while idx < n:
        ch = text[idx]
        if in_comment:
            if ch == "\n":
                in_comment = False
            idx += 1
            continue
        if quote is not None:
            if not sql_mode and ch == "\\" and idx + 1 < n:
                idx += 2
                continue
            if sql_mode and quote == "'" and text[idx : idx + 2] == "''":
                idx += 2
                continue
            if text.startswith(quote, idx):
                idx += len(quote)
                quote = None
                continue
            idx += 1
            continue
        if sql_mode and text[idx : idx + 2] == "--":
            in_comment = True
            idx += 2
            continue
        if not sql_mode and ch == "#":
            in_comment = True
            idx += 1
            continue
        if not sql_mode and text[idx : idx + 3] in ('"""', "'''"):
            quote = text[idx : idx + 3]
            idx += 3
            continue
        if ch in ('"', "'"):
            quote = ch
            idx += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx
        idx += 1
    return None


def _highlight_dsl(
    text: str,
    tables: AbstractSet[str] = frozenset(),
    variables: AbstractSet[str] = frozenset(),
    py_env: AbstractSet[str] = frozenset(),
) -> str:
    """Highlight Pytae DSL commands, flags, tables, @vars, inline -sql, sql { ... }, and py { ... }."""
    # Check for 'py { ... }' block at line start (or leading whitespace)
    py_match = re.match(r"^(\s*)(py)(\s*)(\{)", text)
    if py_match:
        ws1, py_kw, ws2, open_b = py_match.groups()
        open_idx = py_match.end() - 1
        close_idx = _find_matching_brace_close(text, open_idx, sql_mode=False)
        prefix = f"{ws1}{_colorize(py_kw, _COLOR_CMD)}{ws2}{_colorize(open_b, _COLOR_BRACE)}"
        if close_idx is not None:
            body = text[open_idx + 1 : close_idx]
            tail = text[close_idx + 1 :]
            return (
                prefix
                + _highlight_python(body, tables=tables, variables=variables, py_env=py_env)
                + _colorize("}", _COLOR_BRACE)
                + _highlight_dsl(tail, tables=tables, variables=variables, py_env=py_env)
            )
        body = text[open_idx + 1 :]
        return prefix + _highlight_python(body, tables=tables, variables=variables, py_env=py_env)

    # Check for 'sql { ... }' or '<var> = sql { ... }' block
    sql_match = re.match(r"^(\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?)(sql)(\s*)(\{)", text, flags=re.IGNORECASE)
    if sql_match:
        lead_part, sql_kw, ws2, open_b = sql_match.groups()
        open_idx = sql_match.end() - 1
        close_idx = _find_matching_brace_close(text, open_idx, sql_mode=True)
        lead_hl = _highlight_dsl(lead_part, tables=tables, variables=variables, py_env=py_env) if lead_part.strip() else lead_part
        prefix = f"{lead_hl}{_colorize(sql_kw, _COLOR_CMD)}{ws2}{_colorize(open_b, _COLOR_BRACE)}"
        if close_idx is not None:
            body = text[open_idx + 1 : close_idx]
            tail = text[close_idx + 1 :]
            return (
                prefix
                + _highlight_sql(body, tables=tables)
                + _colorize("}", _COLOR_BRACE)
                + _highlight_dsl(tail, tables=tables, variables=variables, py_env=py_env)
            )
        body = text[open_idx + 1 :]
        return prefix + _highlight_sql(body, tables=tables)

    out: list[str] = []
    last = 0
    pending_sql = False
    for m in _DSL_TOKEN_RE.finditer(text):
        gap = text[last : m.start()]
        if gap:
            out.append(gap)
            if gap.strip():
                pending_sql = False

        kind = m.lastgroup
        tok = m.group(0)
        if kind == "COMMENT":
            out.append(_colorize(tok, _COLOR_COMMENT))
            pending_sql = False
        elif kind in ("TRIPLE", "STRING"):
            if pending_sql:
                out.append(_highlight_quoted_sql(tok, tables=tables))
                pending_sql = False
            else:
                out.append(_colorize_dsl_string(tok))
        elif kind == "VAR":
            out.append(_colorize(tok, _COLOR_KEYWORD))
            pending_sql = False
        elif kind == "FLAG":
            out.append(_colorize(tok, _COLOR_CMD))
            pending_sql = tok == "-sql"
        elif kind == "SAMPLE":
            out.append(_colorize(tok, _COLOR_TABLE))
            pending_sql = False
        elif kind == "NUMBER":
            out.append(_colorize(tok, _COLOR_NUMBER))
            pending_sql = False
        elif kind == "BACKSLASH":
            out.append(_colorize(tok, _COLOR_COMMENT))
        elif kind == "BRACE":
            out.append(_colorize(tok, _COLOR_BRACE))
            pending_sql = False
        elif kind == "IDENT":
            pending_sql = False
            if tok in tables:
                out.append(_colorize(tok, _COLOR_TABLE))
            elif tok in _REPL_COMMANDS:
                out.append(_colorize(tok, _COLOR_CMD))
            else:
                out.append(tok)
        else:
            pending_sql = False
            out.append(tok)
        last = m.end()

    if last < len(text):
        out.append(text[last:])
    return "".join(out)


def detect_multiline_mode(multi_buffer: list[str]) -> str:
    """Inspect accumulated incomplete multi-line lines to determine highlighting mode."""
    if not multi_buffer:
        return "dsl"
    acc = "\n".join(multi_buffer)
    py_match = re.match(r"^\s*py\s*\{", acc)
    if py_match:
        open_idx = acc.index("{")
        if _find_matching_brace_close(acc, open_idx, sql_mode=False) is None:
            return "py"

    sql_match = re.match(r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?sql\s*\{", acc, flags=re.IGNORECASE)
    if sql_match:
        open_idx = acc.index("{")
        if _find_matching_brace_close(acc, open_idx, sql_mode=True) is None:
            return "sql"

    # Check if there is an unclosed string following -sql
    in_quote: str | None = None
    in_sql_str = False
    i = 0
    n = len(acc)
    while i < n:
        ch = acc[i]
        if in_quote is not None:
            if ch == "\\" and i + 1 < n and in_quote != "'":
                i += 2
                continue
            if acc.startswith(in_quote, i):
                i += len(in_quote)
                in_quote = None
                in_sql_str = False
                continue
            i += 1
            continue
        if acc.startswith("-sql", i) and (i == 0 or acc[i - 1].isspace()):
            j = i + 4
            if j < n and (acc[j].isspace() or acc[j] in ('"', "'")):
                while j < n and acc[j].isspace():
                    j += 1
                if j < n and acc[j] in ('"', "'"):
                    q = acc[j : j + 3] if acc[j : j + 3] in ('"""', "'''") else acc[j]
                    in_quote = q
                    in_sql_str = True
                    i = j + len(q)
                    continue
        if acc[i : i + 3] in ('"""', "'''"):
            in_quote = acc[i : i + 3]
            i += 3
            continue
        if ch in ('"', "'"):
            in_quote = ch
            i += 1
            continue
        i += 1
    if in_sql_str and in_quote is not None:
        if in_quote == '"':
            return "sql_dq"
        if in_quote == "'":
            return "sql_sq"
        if in_quote == '"""':
            return "sql_tdq"
        if in_quote == "'''":
            return "sql_tsq"
    return "dsl"


def highlight_repl_text(
    text: str,
    mode: str = "dsl",
    tables: AbstractSet[str] = frozenset(),
    variables: AbstractSet[str] = frozenset(),
    py_env: AbstractSet[str] = frozenset(),
) -> str:
    """Apply ANSI syntax highlighting to REPL input buffer text while preserving all characters and newlines."""
    if not text:
        return text
    if mode == "py":
        return _highlight_python(text, tables=tables, variables=variables, py_env=py_env)
    if mode.startswith("sql"):
        close_re_map = {
            "sql_dq": r'^((?:[^"\\]|\\.)*?)(")([\s\S]*)$',
            "sql_sq": r"^([^']*?)(')([\s\S]*)$",
            "sql_tdq": r'^([\s\S]*?)(""")([\s\S]*)$',
            "sql_tsq": r"^([\s\S]*?)(''')([\s\S]*)$",
        }
        close_pat = close_re_map.get(mode)
        if close_pat:
            m = re.match(close_pat, text)
            if m:
                sql_part, q_char, rest = m.groups()
                return (
                    _highlight_sql(sql_part, tables=tables)
                    + _colorize(q_char, _COLOR_STRING)
                    + _highlight_dsl(rest, tables=tables, variables=variables, py_env=py_env)
                )
        return _highlight_sql(text, tables=tables)
    return _highlight_dsl(text, tables=tables, variables=variables, py_env=py_env)


def highlight_prompt(prompt: str) -> str:
    """Colorize REPL prompt ('pytae [table: 100x5]> ' or '... ') preserving exact visible characters."""
    if not prompt or "\x1b[" in prompt:
        return prompt
    if prompt == "... ":
        return f"{_COLOR_PROMPT_DIM}... {RESET}"
    m = re.match(r"^([^\s\[]+)(\s*)(\[[^\]]*\])?(>\s*)$", prompt)
    if not m:
        return prompt
    brand, ws, meta, arrow = m.groups()
    out = [f"{_COLOR_CMD}{brand}{RESET}", ws]
    if meta:
        inner = meta[1:-1]
        out.append(f"{_COLOR_PROMPT_DIM}[{RESET}{_COLOR_TABLE}{inner}{RESET}{_COLOR_PROMPT_DIM}]{RESET}")
    out.append(f"{_COLOR_CMD}{arrow}{RESET}")
    return "".join(out)
