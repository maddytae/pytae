"""Utility functions for REPL input normalization, multiline parsing, and path resolution."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any


def _normalize_unquoted_windows_paths(text: str) -> str:
    """Normalize unquoted Windows drive paths and UNC paths with backslashes so shlex does not eat backslashes."""
    text = re.sub(
        r'(?<!["\'])\b([a-zA-Z]):\\([^\s"\'=]+)',
        lambda m: f"{m.group(1)}:/{m.group(2).replace(chr(92), '/')}",
        text,
    )
    return re.sub(
        r'(?<!["\'])\\\\([^\s"\'=]+)',
        lambda m: f"//{m.group(1).replace(chr(92), '/')}",
        text,
    )


def _collapse_inline_line_continuations(text: str) -> str:
    """Collapse unquoted inline line-continuation backslashes (e.g. 'foo \\ bar' -> 'foo bar').

    Does not modify backslashes inside single or double quotes, nor backslashes in
    file paths or escape sequences where the backslash is immediately followed by non-whitespace.
    """
    res: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if escaped:
            res.append(c)
            escaped = False
            i += 1
            continue
        if c == "\\" and not in_single and not in_double:
            rest = text[i + 1 :]
            if rest == "" or rest[0].isspace():
                j = i + 1
                while j < n and text[j].isspace():
                    j += 1
                if j >= n:
                    while res and res[-1].isspace():
                        res.pop()
                elif res and not res[-1].isspace():
                    res.append(" ")
                i = j
                continue
            else:
                res.append(c)
                i += 1
                continue
        if c == '"' and not in_single:
            in_double = not in_double
        elif c == "'" and not in_double:
            in_single = not in_single
        res.append(c)
        i += 1
    return "".join(res)


def _resolve_to_canonical_path(path_str: str) -> str:
    """Resolve a file path to its canonical absolute path, converting Windows mapped network drives to UNC and using portable forward slashes."""
    from pytae.cli_parsing import normalize_git_bash_path

    raw = path_str.strip().strip("'\"")
    raw = normalize_git_bash_path(raw)
    from pytae.readers import is_db_or_cloud_uri

    if (
        not raw
        or raw.lower() in ("clip", "clipboard")
        or raw.startswith("sample:")
        or raw.startswith("http://")
        or raw.startswith("https://")
        or is_db_or_cloud_uri(raw)
    ):
        return raw

    try:
        p = Path(os.path.expanduser(raw)).resolve()
        if not p.exists():
            from pytae import DATA_PATH

            cand = DATA_PATH / p.name
            if not cand.exists():
                cand = DATA_PATH / f"{p.stem}.parquet"
            if cand.exists():
                p = cand.resolve()
    except Exception:
        return raw

    canon_str = p.as_posix()
    if sys.platform == "win32":
        drive = p.drive  # e.g. "Z:"
        if drive and len(drive) == 2 and drive[1] == ":":
            try:
                import ctypes
                from ctypes import wintypes

                mpr = ctypes.windll.mpr
                buffer = ctypes.create_unicode_buffer(1024)
                buf_len = wintypes.DWORD(1024)
                res = mpr.WNetGetConnectionW(ctypes.c_wchar_p(drive), buffer, ctypes.byref(buf_len))
                if res == 0:  # NO_ERROR
                    unc_remote = buffer.value.rstrip("\\/").replace("\\", "/")
                    sub_path = str(p)[len(drive) :].lstrip("\\/").replace("\\", "/")
                    canon_str = f"{unc_remote}/{sub_path}"
            except Exception:
                pass

    if " " in canon_str and not (canon_str.startswith('"') and canon_str.endswith('"')):
        canon_str = f'"{canon_str}"'

    return canon_str


def _to_relative_path(path_str: str, base_dir: Path | str | None = None) -> str:
    """Convert an absolute file path to a relative POSIX path from base_dir (default: CWD)."""
    clean = path_str.strip().strip("'\"")
    if (
        not clean
        or clean.lower() in ("clip", "clipboard")
        or clean.startswith("sample:")
        or clean.startswith("http://")
        or clean.startswith("https://")
    ):
        return path_str

    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    try:
        target_p = Path(clean).resolve()
        rel = os.path.relpath(target_p, start=base)
        rel_posix = Path(rel).as_posix()
        if " " in rel_posix and not (rel_posix.startswith('"') and rel_posix.endswith('"')):
            return f'"{rel_posix}"'
        return rel_posix
    except Exception:
        return path_str


def _parse_reader_options(tokens: list[str]) -> tuple[list[str], dict[str, Any], int | None]:
    """Parse inline reader flags (-encoding, -dlim, -nrows) from a token list.

    Returns (cleaned_tokens, reader_kwargs, nrows_val).
    """
    cleaned: list[str] = []
    reader_kwargs: dict[str, Any] = {}
    nrows_val: int | None = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-encoding", "--encoding") and i + 1 < len(tokens):
            reader_kwargs["encoding"] = tokens[i + 1]
            i += 2
        elif tok in ("-dlim", "--dlim") and i + 1 < len(tokens):
            reader_kwargs["sep"] = tokens[i + 1]
            i += 2
        elif tok in ("-nrows", "--nrows", "-limit", "--limit") and i + 1 < len(tokens):
            try:
                nrows_val = int(tokens[i + 1])
            except ValueError:
                pass
            i += 2
        elif tok in ("-fmt", "--fmt") and i + 1 < len(tokens):
            i += 2
        elif tok in ("-opts", "--opts") and i + 1 < len(tokens):
            from pytae.cli_parsing import parse_reader_opts

            global_opts, _ = parse_reader_opts(tokens[i + 1])
            reader_kwargs.update(global_opts)
            i += 2
        else:
            cleaned.append(tok)
            i += 1

    truly_cleaned: list[str] = []
    for idx_c, c_tok in enumerate(cleaned):
        if idx_c == 0:
            truly_cleaned.append(c_tok.rstrip(","))
        elif "=" in c_tok:
            from pytae.cli_parsing import parse_reader_opts

            opts_part, _ = parse_reader_opts(c_tok.strip(","))
            reader_kwargs.update(opts_part)
        else:
            truly_cleaned.append(c_tok)
    cleaned = truly_cleaned

    return cleaned, reader_kwargs, nrows_val


def _split_respecting_quotes(s: str, seps: str = ",;") -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    escaped = False
    for ch in s:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            current.append(ch)
            continue
        if ch in ('"', "'"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            current.append(ch)
        elif ch in seps and in_quote is None:
            chunk = "".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = []
        else:
            current.append(ch)
    chunk = "".join(current).strip()
    if chunk:
        chunks.append(chunk)
    return chunks


def _is_multiline_complete(buffer: str) -> bool:
    """Return True if the accumulated input buffer is syntactically complete.

    A buffer is considered incomplete (requiring continuation with prompt '... ') if:
    1. The last non-whitespace character is a trailing backslash '\\'.
    2. It contains an unclosed string quote (single, double, or triple quotes).
    3. It contains unclosed brackets '()', '[]', or '{}'.
    """
    stripped = buffer.rstrip()
    if not stripped:
        return True

    if stripped.endswith("\\"):
        return False

    in_single_quote = False
    in_double_quote = False
    in_triple_single = False
    in_triple_double = False
    escaped = False
    bracket_depth = 0

    i = 0
    n = len(buffer)
    while i < n:
        c = buffer[i]
        if escaped:
            escaped = False
            i += 1
            continue

        if c == "\\":
            escaped = True
            i += 1
            continue

        if not (in_single_quote or in_double_quote):
            if buffer[i : i + 3] == '"""':
                in_triple_double = not in_triple_double
                i += 3
                continue
            if buffer[i : i + 3] == "'''":
                in_triple_single = not in_triple_single
                i += 3
                continue

        if in_triple_double or in_triple_single:
            i += 1
            continue

        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            i += 1
            continue
        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            i += 1
            continue

        if not (in_single_quote or in_double_quote):
            if c in "([{":
                bracket_depth += 1
            elif c in ")]}":
                bracket_depth = max(0, bracket_depth - 1)
        i += 1

    if in_single_quote or in_double_quote or in_triple_single or in_triple_double:
        return False
    if bracket_depth > 0:
        return False

    return True
