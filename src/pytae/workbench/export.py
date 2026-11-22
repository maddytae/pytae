"""Session export pruning, `%pt` fluent Python transpilation, and AST dead-code removal."""

from __future__ import annotations

import ast
import datetime
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

from pytae.workbench.system import is_dataframe

_INSPECTION_MAGICS = frozenset(
    {
        "status",
        "checkpoint",
        "checkpoints",
        "restore",
        "free",
        "export",
        "set",
        "exit",
        "quit",
        "whos",
        "who",
        "load_ext",
        "reload_ext",
        "unload_ext",
        "clear",
        "cls",
        "history",
        "hist",
        "lsmagic",
        "colors",
        "theme",
        "magic",
        "pinfo",
        "pdoc",
        "pwd",
        "ls",
    }
)


def _has_output_flag(cmd: str) -> bool:
    return bool(re.search(r"(?:^|\s)-o(?:\s|=)", cmd))


_PURE_INSPECTION_METHODS = frozenset(
    {
        "head",
        "tail",
        "glimpse",
        "schema",
        "describe",
        "cols",
        "nulls",
        "freq",
        "hist",
        "bar",
        "scatter",
        "corr",
        "info",
        "sample",
        "explain",
    }
)


def _is_pure_python_inspection(code: str) -> bool:
    """Return True if valid Python code contains only side-effect-free interactive previews."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    if not tree.body:
        return True
    for stmt in tree.body:
        if not isinstance(stmt, ast.Expr):
            return False
        val = stmt.value
        if isinstance(val, (ast.Name, ast.Attribute, ast.Subscript, ast.Constant)):
            continue
        if isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute):
            if val.func.attr in _PURE_INSPECTION_METHODS:
                continue
        return False
    return True


def _is_skippable_cell(code: str) -> bool:
    """Return True if a cell is purely an inspection/meta magic or unassigned read-only preview."""
    lines = [ln.strip() for ln in code.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return True

    # Cell magic `%%pt` with no target var and no `-o` output flag is a read-only preview
    if lines[0].startswith("%%"):
        header_parts = lines[0][2:].split()
        magic_name = header_parts[0].lower() if header_parts else ""
        if magic_name in _INSPECTION_MAGICS:
            return True
        if magic_name == "pt":
            non_flag_targets = [tok for tok in header_parts[1:] if tok.isidentifier()]
            has_target = bool(non_flag_targets)
            body = " ".join(lines[1:])
            if not has_target and not _has_output_flag(body):
                return True
            return False
        return False

    all_magic_skippable = True
    for ln in lines:
        if ln.startswith("%"):
            rest = ln.lstrip("%")
            magic_name = rest.split(None, 1)[0].lower() if rest else ""
            if magic_name in _INSPECTION_MAGICS:
                continue
            if magic_name == "pt":
                # Unassigned `%pt ...` without `-o` is read-only exploration
                if not _has_output_flag(rest[2:]):
                    continue
                all_magic_skippable = False
                break
            all_magic_skippable = False
            break
        # Bare automagic commands (e.g. `exit -s maddy.py`, `status`, `checkpoint raw`, `restore`)
        first_tok = ln.split(None, 1)[0].lower()
        if first_tok in _INSPECTION_MAGICS and not ln.startswith(f"{first_tok}=") and not ln.startswith(f"{first_tok} ="):
            continue
        all_magic_skippable = False
        break

    if all_magic_skippable:
        return True

    return _is_pure_python_inspection(code)


_FLUENT_REQ_ARG_FLAGS: dict[str, str] = {
    "-filter": "filter",
    "-mutate": "mutate",
    "-select": "select",
    "-rename": "rename",
    "-by": "by",
    "-arrange": "arrange",
    "-explode": "explode",
    "-assert": "assert_",
    "-o": "to",
}

_FLUENT_OPT_ARG_FLAGS: dict[str, str] = {
    "-agg": "agg",
    "-distinct": "distinct",
    "-dups": "dups",
    "-outliers": "outliers",
    "-count": "count",
    "-dropna": "dropna",
    "-fillna": "fillna",
    "-head": "head",
    "-tail": "tail",
    "-sample": "sample",
}

_FLUENT_INT_FLAGS: dict[str, str] = {
    "-round": "round",
}


def _unquote_token(tok: str) -> str:
    if len(tok) >= 2 and ((tok[0] == '"' and tok[-1] == '"') or (tok[0] == "'" and tok[-1] == "'")):
        return tok[1:-1]
    return tok


def _resolve_export_path(raw_path: str, *, relative_to: Path | None = None) -> str:
    """Resolve a local input path to a full absolute path (or relative to `relative_to`).

    Leaves URIs (s3://, https://, sqlite://, ...), `sample:*`, `clip`, and already-absolute
    Windows drive/UNC paths intact.
    """
    p_str = raw_path.strip()
    if not p_str:
        return raw_path
    low = p_str.lower()
    if low == "clip" or low.startswith("sample:") or "://" in p_str:
        return p_str
    # Preserve Windows drive / UNC paths cleanly when running on non-Windows hosts
    if re.match(r"^[A-Za-z]:[\\/]", p_str) or p_str.startswith("\\\\"):
        if sys.platform != "win32":
            return p_str

    has_glob = any(ch in p_str for ch in "*?[]")
    if has_glob:
        # Resolve the static parent portion so glob patterns stay valid from any cwd
        parts = Path(os.path.expanduser(p_str)).parts
        static_parts: list[str] = []
        glob_parts: list[str] = []
        in_glob = False
        for part in parts:
            if not in_glob and any(ch in part for ch in "*?[]"):
                in_glob = True
            if in_glob:
                glob_parts.append(part)
            else:
                static_parts.append(part)
        base = Path(*static_parts).resolve() if static_parts else Path.cwd().resolve()
        resolved = base.joinpath(*glob_parts)
    else:
        resolved = Path(os.path.expanduser(p_str)).resolve()

    if relative_to is not None:
        try:
            return os.path.relpath(str(resolved), str(relative_to))
        except ValueError:
            return str(resolved)
    return str(resolved)


def _resolve_python_io_paths(py_code: str, *, relative_to: Path | None = None) -> str:
    """Resolve string path literals inside input calls (`pt.read(...)` / `pt.scan(...)`); leave outputs as typed."""
    if "read(" not in py_code and "scan(" not in py_code:
        return py_code

    def _repl_in(match: re.Match[str]) -> str:
        prefix, _quote, inner = match.group(1), match.group(2), match.group(3)
        resolved = _resolve_export_path(inner, relative_to=relative_to)
        return f"{prefix}{resolved!r}"

    return re.sub(
        r"""(\b(?:pt|pytae)\.(?:read|scan)\(\s*)(['"])([^'"]+)\2""",
        _repl_in,
        py_code,
    )


def _transpile_pt_to_fluent(cmd: str, *, relative_to: Path | None = None) -> str | None:
    """Transpile standard `%pt` CLI pipelines into idiomatic fluent Python, or return None to fall back."""
    try:
        raw_tokens = shlex.split(cmd, posix=False)
    except ValueError:
        return None
    if not raw_tokens:
        return None

    tokens = [_unquote_token(t) for t in raw_tokens]
    first = tokens[0]
    if first.startswith("-"):
        return None

    # Source expression
    m_sample = re.match(r"^sample:([A-Za-z0-9_.-]+)$", first)
    if m_sample:
        source_expr = f"pt.sample({m_sample.group(1)!r})"
    elif first.isidentifier() and first.lower() != "clip":
        source_expr = first
    else:
        resolved_first = _resolve_export_path(first, relative_to=relative_to)
        source_expr = f"pt.read({resolved_first!r})"

    if len(tokens) == 1:
        return source_expr

    steps: list[str] = []
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("-"):
            return None
        flag = tok.lower()
        val: str | None = None
        if "=" in flag:
            flag, _, eq_val = flag.partition("=")
            # Preserve original case for eq_val from tok
            val = tok.partition("=")[2]
            i += 1
        elif flag in _FLUENT_REQ_ARG_FLAGS or flag in _FLUENT_INT_FLAGS:
            if i + 1 >= len(tokens):
                return None
            val = tokens[i + 1]
            i += 2
        elif flag in _FLUENT_OPT_ARG_FLAGS:
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                val = tokens[i + 1]
                i += 2
            else:
                i += 1
        else:
            return None

        if flag in _FLUENT_REQ_ARG_FLAGS:
            assert val is not None
            steps.append(f".{_FLUENT_REQ_ARG_FLAGS[flag]}({val!r})")
        elif flag in _FLUENT_INT_FLAGS:
            assert val is not None
            try:
                n = int(val)
            except ValueError:
                return None
            steps.append(f".{_FLUENT_INT_FLAGS[flag]}({n})")
        elif flag in _FLUENT_OPT_ARG_FLAGS:
            method = _FLUENT_OPT_ARG_FLAGS[flag]
            if val is None:
                steps.append(f".{method}()")
            elif flag in ("-head", "-tail", "-sample") and val.isdigit():
                steps.append(f".{method}({int(val)})")
            else:
                steps.append(f".{method}({val!r})")
        else:
            return None

    if len(steps) == 1:
        return f"{source_expr}{steps[0]}"
    joined = "\n    ".join([source_expr] + steps)
    return f"(\n    {joined}\n)"


def _rewrite_pt_cmd_to_python(
    cmd: str,
    target_var: str | None = None,
    *,
    relative_to: Path | None = None,
) -> str:
    """Convert a `%pt` / `%%pt` invocation into standalone valid Python."""
    stripped = cmd.strip()
    fluent = _transpile_pt_to_fluent(stripped, relative_to=relative_to)
    expr = fluent if fluent is not None else f"pt.eval_cli({stripped!r}, locals())"
    if target_var:
        return f"{target_var} = {expr}"
    return expr


def _rewrite_cell_for_python(code: str, *, relative_to: Path | None = None) -> str:
    """Rewrite IPython `%pt` / `%%pt` magics into standalone valid Python for `.py` export."""
    lines = code.splitlines()
    if not lines:
        return ""
    first = lines[0].strip()
    if first.startswith("%%pt"):
        parts = first[4:].strip().split()
        is_sql = any(p in ("-sql", "--sql") for p in parts)
        target_var = next((p for p in parts if p.isidentifier()), None)
        if is_sql:
            sql_body = " ".join(ln.strip() for ln in lines[1:] if ln.strip())
            cmd_str = f"-sql {shlex.quote(sql_body)}"
            expr = f"pt.eval_cli({cmd_str!r}, locals())"
            return f"{target_var} = {expr}" if target_var else expr
        body = " ".join(
            ln.strip() for ln in lines[1:] if ln.strip() and not ln.strip().startswith("#")
        )
        return _rewrite_pt_cmd_to_python(body, target_var=target_var, relative_to=relative_to)

    out_lines: list[str] = []
    for raw_ln in lines:
        ln = raw_ln.strip()
        m_assign = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*%pt\s+(.+)$", ln)
        if m_assign:
            indent = raw_ln[: len(raw_ln) - len(raw_ln.lstrip())]
            out_lines.append(
                indent
                + _rewrite_pt_cmd_to_python(
                    m_assign.group(2), target_var=m_assign.group(1), relative_to=relative_to
                )
            )
            continue
        m_bare = re.match(r"^%pt\s+(.+)$", ln)
        if m_bare:
            indent = raw_ln[: len(raw_ln) - len(raw_ln.lstrip())]
            out_lines.append(indent + _rewrite_pt_cmd_to_python(m_bare.group(1), relative_to=relative_to))
            continue
        if ln.startswith("%"):
            # Comment out any other IPython magic so exported .py is always valid Python
            out_lines.append(f"# {raw_ln}")
            continue
        out_lines.append(_resolve_python_io_paths(raw_ln, relative_to=relative_to))
    return "\n".join(out_lines)


def _substitute_ns_vars(token: str, ns: dict[str, Any]) -> str:
    """Substitute `@var` references in CLI flag strings using scalar/list values in `ns`."""
    if "@" not in token:
        return token

    def _repl(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name not in ns:
            return match.group(0)
        val = ns[var_name]
        if is_dataframe(val) or callable(val):
            return match.group(0)
        if isinstance(val, str):
            return repr(val)
        if isinstance(val, (int, float, bool)):
            return str(val)
        if isinstance(val, (list, tuple)):
            return "[" + ", ".join(repr(x) for x in val) + "]"
        return match.group(0)

    return re.sub(r"(?<![A-Za-z0-9_])@([A-Za-z_][A-Za-z0-9_]*)", _repl, token)


_AUTO_IMPORT_MAP: tuple[tuple[str, str], ...] = (
    ("pt", "import pytae as pt"),
    ("pd", "import pandas as pd"),
    ("pl", "import polars as pl"),
    ("np", "import numpy as np"),
    ("Path", "from pathlib import Path"),
)


def _infer_missing_imports(py_cells: list[str], *, always_include_pt: bool = True) -> list[str]:
    """Detect common startup-imported aliases (pt, pd, pl, np, Path) used without explicit imports."""
    loaded: set[str] = set()
    defined: set[str] = set()
    for cell in py_cells:
        try:
            tree = ast.parse(cell)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    defined.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    loaded.add(node.id)
                elif isinstance(node.ctx, ast.Store):
                    defined.add(node.id)

    missing: list[str] = []
    for sym, stmt in _AUTO_IMPORT_MAP:
        if sym in defined:
            continue
        if sym in loaded or (sym == "pt" and always_include_pt):
            missing.append(stmt)
    return missing


def _build_python_script(cells: list[str]) -> str:
    header = [
        "# Exported from Pytae IPython Workbench",
        f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    missing_imports = _infer_missing_imports(cells, always_include_pt=True)
    if missing_imports:
        header.extend(missing_imports)
        header.append("")

    body = "\n\n".join(cells)
    return "\n".join(header) + ("\n" if header[-1] == "" and body else "") + body + ("\n" if body else "")


def _build_notebook_json(cells: list[str]) -> dict[str, Any]:
    nb_cells: list[dict[str, Any]] = []
    for code in cells:
        src_lines = [ln + "\n" for ln in code.splitlines()]
        if src_lines:
            src_lines[-1] = src_lines[-1].rstrip("\n")
        nb_cells.append(
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": src_lines,
            }
        )
    return {
        "cells": nb_cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# ---------------------------------------------------------------------------
# AST dead-assignment & duplicate pruning + CLI post-hoc export from SQLite
# ---------------------------------------------------------------------------

_SIDE_EFFECT_CALLS = frozenset({"to", "write", "write_parquet", "write_csv", "write_ipc", "print", "finalize", "save"})


def _analyze_python_cell(py_code: str) -> tuple[str | None, set[str], bool]:
    """Return `(single_assigned_var, referenced_names, has_side_effect)` for a valid Python cell."""
    try:
        tree = ast.parse(py_code)
    except SyntaxError:
        return None, set(), True

    used: set[str] = set()
    has_side_effect = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in _SIDE_EFFECT_CALLS:
                    has_side_effect = True
                if node.func.attr == "eval_cli" and node.args and isinstance(node.args[0], ast.Constant):
                    cmd_str = str(node.args[0].value)
                    if _has_output_flag(cmd_str):
                        has_side_effect = True
                    # Tokens inside eval_cli('df -filter "x > @k"', locals()) may reference variables
                    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cmd_str):
                        used.add(tok)
            elif isinstance(node.func, ast.Name) and node.func.id in _SIDE_EFFECT_CALLS:
                has_side_effect = True

    single_def: str | None = None
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Assign):
        assign = tree.body[0]
        if len(assign.targets) == 1 and isinstance(assign.targets[0], ast.Name):
            single_def = assign.targets[0].id

    return single_def, used, has_side_effect


def _prune_dead_and_duplicate_cells(pairs: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], int]:
    """Drop duplicate consecutive cells, duplicate `import pytae` lines, and dead overwritten assignments."""
    # 1. Deduplicate consecutive identical cells & repeated `import pytae as pt`
    deduped: list[tuple[str, str]] = []
    seen_pt_import = False
    pruned = 0
    for orig, py_code in pairs:
        norm = py_code.strip()
        if deduped and deduped[-1][1].strip() == norm:
            pruned += 1
            continue
        if re.fullmatch(r"import\s+pytae(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?", norm):
            if seen_pt_import:
                pruned += 1
                continue
            seen_pt_import = True
        deduped.append((orig, py_code))

    # 2. Prune dead overwritten single-variable assignments
    analyzed = [_analyze_python_cell(py) for _orig, py in deduped]
    dead_indices: set[int] = set()
    n = len(deduped)
    for i in range(n):
        def_var, _used_i, has_side_effect = analyzed[i]
        if def_var is None or has_side_effect:
            continue
        # Scan forward until `def_var` is either read or unconditionally overwritten
        for j in range(i + 1, n):
            next_def, next_used, _next_se = analyzed[j]
            if def_var in next_used:
                break
            if next_def == def_var:
                dead_indices.add(i)
                break

    final = [pair for idx, pair in enumerate(deduped) if idx not in dead_indices]
    return final, pruned + len(dead_indices)


def _infer_restore_events(history_cells: list[tuple[int, str]]) -> list[tuple[int, int]]:
    """Infer `(checkpoint_cell_idx, restore_cell_idx)` ranges from raw history lines."""
    cp_indices: dict[str, int] = {}
    cp_order: list[str] = []
    restores: list[tuple[int, int]] = []
    for idx, raw in history_cells:
        ln = raw.strip()
        m_cp = re.match(r"^%?checkpoint\s+([A-Za-z0-9_.-]+)", ln)
        if m_cp:
            name = m_cp.group(1)
            if name.lower() not in ("list", "rm", "drop", "delete", "diff"):
                cp_indices[name] = idx
                if name in cp_order:
                    cp_order.remove(name)
                cp_order.append(name)
            continue
        m_res = re.match(r"^%?restore(?:\s+([A-Za-z0-9_.-]+))?\s*$", ln)
        if m_res:
            target = m_res.group(1) or (cp_order[-1] if cp_order else None)
            if target and target in cp_indices:
                restores.append((cp_indices[target], idx))
    return restores


