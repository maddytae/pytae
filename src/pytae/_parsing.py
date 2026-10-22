"""Pytae unified AST and string specification parsing utilities.

This module contains pure syntax, tokenization, and AST-parsing routines for
Pytae verbs (mutate, filter, arrange, pivot, select) with zero external engine
dependencies.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pytae._text import _ColRef
from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name

# -----------------------------------------------------------------------------
# Arrange Parsing
# -----------------------------------------------------------------------------


def _parse_col_order(
    token: str,
    default_asc: bool = True,
    available_cols: set[str] | None = None,
) -> tuple[str, bool]:
    """Parse a single column token, e.g. 'species', 'body_mass_g desc', '-body_mass_g'."""
    token = token.strip()
    if available_cols and token in available_cols:
        return token, default_asc

    asc = default_asc
    if token.startswith("-") and len(token) > 1:
        col = token[1:].strip()
        raise ValueError(
            f"arrange(): leading '-' is not supported. In line with 'one and only one obvious way', use '{col} desc' instead (e.g. arrange('{col} desc'))."
        )
    elif token.startswith("+") and len(token) > 1:
        col = token[1:].strip()
        raise ValueError(
            f"arrange(): leading '+' is not supported. Columns sort ascending by default (e.g. arrange('{col}'))."
        )
    else:
        lower = token.lower()
        for suffix, direction in [
            (" descending", False),
            (" desc", False),
            (" ascending", True),
            (" asc", True),
        ]:
            if lower.endswith(suffix):
                asc = direction
                token = token[: len(token) - len(suffix)].strip()
                break

    token = _unquote_name(token)
    return token, asc


def _extract_arrange_specs(
    cols_args: tuple[Any, ...],
    ascending: bool | Sequence[bool] | None = None,
    available_cols: set[str] | None = None,
) -> tuple[list[str], list[bool]]:
    """Extract (columns, ascending_list) from positional args or comma-separated strings."""
    raw_tokens: list[str] = []
    for arg in cols_args:
        if isinstance(arg, (list, tuple)):
            for item in arg:
                if isinstance(item, str):
                    raw_tokens.extend(_tokenize(item, ",", track_brackets=True))
                else:
                    raw_tokens.append(str(item))
        elif isinstance(arg, str):
            raw_tokens.extend(_tokenize(arg, ",", track_brackets=True))
        else:
            raw_tokens.append(str(arg))

    parsed_cols: list[str] = []
    parsed_asc: list[bool] = []

    for idx, token in enumerate(raw_tokens):
        token_clean = token.strip()
        if not token_clean:
            continue
        default_dir = True
        if ascending is not None:
            if isinstance(ascending, (list, tuple)):
                default_dir = bool(ascending[idx]) if idx < len(ascending) else True
            else:
                default_dir = bool(ascending)

        col_name, col_dir = _parse_col_order(token_clean, default_dir, available_cols)
        parsed_cols.append(col_name)
        parsed_asc.append(col_dir)

    return parsed_cols, parsed_asc


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Filter Parsing
# -----------------------------------------------------------------------------


class FilterNode:
    """Base node for boolean filter condition AST."""

    def columns(self) -> list[str]:
        raise NotImplementedError


class BinaryOp(FilterNode):
    """Binary logical conjunction ('and' or 'or') between two filter nodes."""

    def __init__(self, op: str, left: FilterNode, right: FilterNode):
        self.op = op.lower()
        if self.op not in ("and", "or"):
            raise ValueError(f"BinaryOp only supports 'and' or 'or', got {op!r}")
        self.left = left
        self.right = right

    def columns(self) -> list[str]:
        return self.left.columns() + self.right.columns()

    def __repr__(self) -> str:
        return f"BinaryOp({self.op!r}, {self.left!r}, {self.right!r})"


class Predicate(FilterNode):
    """Atomic column predicate (e.g. col == val, col in [...], col.notna())."""

    def __init__(self, col: str, cond: Any):
        self.col = col
        self.cond = cond

    def columns(self) -> list[str]:
        base = self.col
        if ".dt." in base:
            base = base.split(".dt.")[0]
        if ".str." in base:
            base = base.split(".str.")[0]
        return [base.strip("[]").strip()]

    def __repr__(self) -> str:
        return f"Predicate({self.col!r}, {self.cond!r})"


def _is_enclosed_in_parens(s: str) -> bool:
    if not (s.startswith("(") and s.endswith(")")):
        return False
    depth = 0
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
            elif ch == "\\" and i + 1 < len(s):
                continue
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and i < len(s) - 1:
                return False
    return depth == 0


def _split_top_level(text: str, operator_words: list[str]) -> list[str]:
    quote = None
    paren_depth = 0
    bracket_depth = 0
    i = 0
    n = len(text)
    splits: list[str] = []
    last_idx = 0

    while i < n:
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
            elif ch == "\\" and i + 1 < n:
                i += 1
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == "(":
            paren_depth += 1
            i += 1
            continue
        if ch == ")":
            paren_depth -= 1
            i += 1
            continue
        if ch == "[":
            bracket_depth += 1
            i += 1
            continue
        if ch == "]":
            bracket_depth -= 1
            i += 1
            continue
        if paren_depth == 0 and bracket_depth == 0:
            for op in operator_words:
                op_pattern = f" {op} "
                k = len(op_pattern)
                if text[i : i + k].lower() == op_pattern:
                    splits.append(text[last_idx:i].strip())
                    last_idx = i + k
                    i = last_idx - 1
                    break
        i += 1
    splits.append(text[last_idx:].strip())
    return splits


def _parse_predicate(raw_entry: str) -> Predicate:
    raw = raw_entry.strip()
    if not raw:
        raise SystemExit("invalid filter condition: empty expression")

    # 1. Direct comparison first: col > 5, col >= 5, col == 5, col != 5, etc.
    m_cmp = re.match(r"^([^>=<!:]+?)\s*(>=|<=|!=|==|>|<)\s*(.+)$", raw)
    if m_cmp:
        col = _unquote_name(m_cmp.group(1).strip())
        op = m_cmp.group(2).strip()
        val_str = m_cmp.group(3).strip()
        if not col:
            raise SystemExit(f"invalid filter condition '{raw}': empty column name")
        if not val_str:
            raise SystemExit(f"invalid filter condition '{raw}': '{col}' has no value")

        # Disallow interval notation: e.g. [3000, 3200]
        m_int = re.match(r"^([\[(])\s*([^,()\[\]]+)\s*,\s*([^,()\[\]]+)\s*([\])])$", val_str)
        if m_int:
            b1 = m_int.group(2).strip()
            b2 = m_int.group(3).strip()
            raise SystemExit(
                f"invalid filter condition '{raw}': interval notation '[min, max]' is not supported in filter expressions. "
                f"Use '{col} >= {b1} and {col} <= {b2}' or dict syntax {{'{col}': ('between', {b1}, {b2})}}."
            )

        if val_str.lower() == "nan" and op in ("!=", "=="):
            op_nan = "is_not_nan" if op == "!=" else "is_nan"
            return Predicate(col, (op_nan, None))

        if val_str.lower() in ("none", "null") and op in ("!=", "=="):
            op_null = "is_not_null" if op == "!=" else "is_null"
            return Predicate(col, (op_null, None))

        if (val_str.startswith("'") and val_str.endswith("'")) or (val_str.startswith('"') and val_str.endswith('"')):
            sub_val = val_str[1:-1]
        elif val_str.startswith("col(") and val_str.endswith(")"):
            inner = val_str[4:-1].strip().strip("'\"")
            sub_val = _ColRef(_unquote_name(inner))
        else:
            try:
                sub_val = ast.literal_eval(val_str)
            except (ValueError, SyntaxError):
                sub_val = _ColRef(_unquote_name(val_str))
        return Predicate(col, (op, sub_val))

    # 2. In / not in
    m_in = re.match(r"^([^>=<!:]+?)\s+(not\s+in|in)\s+(.+)$", raw, flags=re.IGNORECASE)
    if m_in:
        col = _unquote_name(m_in.group(1).strip())
        op = "not in" if "not" in m_in.group(2).lower() else "in"
        val_str = m_in.group(3).strip()
        try:
            sub_val = ast.literal_eval(val_str)
        except (ValueError, SyntaxError):
            sub_val = [s.strip().strip("'\"") for s in val_str.strip("[]()").split(",") if s.strip()]
        return Predicate(col, (op, sub_val))

    # 3. SQL-style null checks (disallowed: guide to pure Polars .is_null() / .is_not_null())
    m_sql_null = re.match(r"^(.+?)\s+is\s+(not\s+null|null|not\s+na|na)$", raw, flags=re.IGNORECASE)
    if m_sql_null:
        col = _unquote_name(m_sql_null.group(1).strip())
        col_disp = f"[{col}]" if " " in col else col
        m_name = m_sql_null.group(2).strip().lower()
        suggested = f"{col_disp}.is_not_null()" if "not" in m_name else f"{col_disp}.is_null()"
        dict_hint = f" or dict {{{col!r}: None}}" if "not" not in m_name else ""
        raise SystemExit(
            f"invalid filter condition '{raw}': use '{suggested}'{dict_hint}. "
            f"SQL 'is null' syntax is not supported in -filter; use -sql for SQL queries."
        )

    # 4. Functional null check calls
    m_fn_null = re.match(r"^(notna|isna|is_not_null|is_null)\((.+)\)$", raw, flags=re.IGNORECASE)
    if m_fn_null:
        op_name = m_fn_null.group(1).strip().lower()
        col = _unquote_name(m_fn_null.group(2).strip())
        op = "notna" if "not" in op_name else "isna"
        return Predicate(col, (op, None))

    # 5. String method calls
    m_str = re.match(r"^(.+?)\.str\.(contains|startswith|starts_with|endswith|ends_with)\((.+)\)$", raw)
    if m_str:
        col = _unquote_name(m_str.group(1).strip())
        method = m_str.group(2).strip()
        val = m_str.group(3).strip()
        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
            val = val[1:-1]
        op = "startswith" if "start" in method else ("endswith" if "end" in method else "contains")
        return Predicate(col, (op, val))

    # 6. Null and NaN check method calls
    m_null = re.match(r"^(.+?)\.(is_null|isna|is_not_null|notna|is_nan|isnan|is_not_nan|not_nan)\(\)$", raw)
    if m_null:
        col = _unquote_name(m_null.group(1).strip())
        m_name = m_null.group(2).strip()
        if "nan" in m_name:
            op = "is_not_nan" if "not" in m_name else "is_nan"
        else:
            op = "notna" if "not" in m_name else "isna"
        return Predicate(col, (op, None))

    # 7. Single '=' detection (strictly disallow)
    m_eq = re.match(r"^([^>=<!:]+?)\s*=\s*(.+)$", raw)
    if m_eq:
        col = m_eq.group(1).strip()
        val = m_eq.group(2).strip()
        raise SystemExit(
            f"invalid filter condition '{raw}': use '==' for equality comparisons (e.g. {col} == {val}). "
            f"Single '=' is for assignment (-mutate), not comparison (-filter)."
        )

    # 8. Colon ':' detection
    pieces = _tokenize(raw, ":", keep_quotes=True, track_brackets=True)
    if len(pieces) >= 2:
        raise SystemExit(
            f"invalid filter condition '{raw}': use '==' (e.g. species == 'Adelie'). Colon ':' is not supported."
        )

    raise SystemExit(f"invalid filter condition: missing comparison operator in '{raw}'")


def _parse_filter_node(raw_expr: str) -> FilterNode:
    s = raw_expr.strip()
    if not s:
        raise SystemExit("invalid filter condition: empty expression")

    while _is_enclosed_in_parens(s):
        s = s[1:-1].strip()

    # Check for forbidden top-level operators at paren_depth == 0 and bracket_depth == 0
    quote = None
    paren_depth = 0
    bracket_depth = 0
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
            elif ch == "\\" and i + 1 < len(s):
                continue
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == "(":
            paren_depth += 1
            continue
        if ch == ")":
            paren_depth -= 1
            continue
        if ch == "[":
            bracket_depth += 1
            continue
        if ch == "]":
            bracket_depth -= 1
            continue
        if paren_depth == 0 and bracket_depth == 0:
            if ch == ",":
                raise SystemExit(
                    f"invalid filter condition '{s}': comma ',' is not supported as a boolean operator. "
                    f"Use 'and' instead (e.g. {s[:i].strip()} and {s[i+1:].strip()})."
                )
            if ch == "&":
                raise SystemExit(
                    f"invalid filter condition '{s}': '&' is not supported in filter. Use 'and' instead."
                )
            if ch == "|":
                raise SystemExit(
                    f"invalid filter condition '{s}': '|' is not supported in filter. Use 'or' instead."
                )

    # Split OR (lowest precedence)
    or_parts = _split_top_level(s, ["or"])
    if len(or_parts) > 1:
        node = _parse_filter_node(or_parts[0])
        for part in or_parts[1:]:
            node = BinaryOp("or", node, _parse_filter_node(part))
        return node

    # Split AND (higher precedence than OR)
    and_parts = _split_top_level(s, ["and"])
    if len(and_parts) > 1:
        node = _parse_filter_node(and_parts[0])
        for part in and_parts[1:]:
            node = BinaryOp("and", node, _parse_filter_node(part))
        return node

    return _parse_predicate(s)


def _eval_dict_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        lower = node.func.id.lower()
        if lower in ("is_null", "isna"):
            return "is_null()"
        if lower in ("is_not_null", "notna"):
            return "is_not_null()"
        if lower in ("is_nan", "isnan"):
            return "is_nan()"
        if lower in ("is_not_nan", "not_nan"):
            return "is_not_nan()"
    if isinstance(node, ast.Name):
        lower = node.id.lower()
        if lower in ("is_null", "is_not_null", "is_nan", "is_not_nan", "isna", "notna", "isnan", "not_nan"):
            return lower  # Bare word without parens; polars_engine strictly rejects with guidance
        if lower == "nan":
            return float("nan")
        if lower in ("none", "null"):
            return None
        if lower == "true":
            return True
        if lower == "false":
            return False
        return node.id
    if isinstance(node, ast.Tuple):
        return tuple(_eval_dict_node(elt) for elt in node.elts)
    if isinstance(node, ast.List):
        return list(_eval_dict_node(elt) for elt in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _eval_dict_node(node.operand)
        return -val
    return ast.literal_eval(node)


def _parse_dict_literal(raw: str) -> dict[str, Any] | None:
    """Parse a dict literal, accepting both quoted keys and unquoted identifier keys, as well as bare NaN/None/null values."""
    stripped = raw.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    try:
        val = ast.literal_eval(stripped)
        if isinstance(val, dict):
            return val
    except (ValueError, SyntaxError):
        pass
    try:
        tree = ast.parse(stripped, mode="eval")
        if isinstance(tree.body, ast.Dict):
            d: dict[str, Any] = {}
            for k, v in zip(tree.body.keys, tree.body.values):
                if k is None:
                    return None
                key = k.id if isinstance(k, ast.Name) else ast.literal_eval(k)
                val = _eval_dict_node(v)
                d[str(key)] = val
            return d
    except Exception:
        pass
    return None


def _parse_filter_string(raw: str, params: dict[str, Any] | None = None) -> FilterNode | dict[str, Any]:
    """Parse filter conditions from a query string."""
    stripped = raw.strip()
    if "@" in stripped:
        _, at_tokens = _strip_at_refs(stripped)
        for var_name in at_tokens:
            if params and var_name in params:
                val_p = params[var_name]
                stripped = re.sub(rf"@{var_name}\b", repr(val_p), stripped)
            else:
                all_avail = list(params.keys()) if params else []
                import difflib

                close = difflib.get_close_matches(var_name, all_avail, n=1)
                hint = f" (did you mean '@{close[0]}'?)" if close else ""
                raise KeyError(f"local variable '@{var_name}' is not defined{hint}")

    parsed_dict = _parse_dict_literal(stripped)
    if parsed_dict is not None:
        return parsed_dict

    try:
        return _parse_filter_node(stripped)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc


# -----------------------------------------------------------------------------
# Mutate Parsing
# -----------------------------------------------------------------------------


def _split_mutate_entries(raw: str) -> list[tuple[str, str]]:
    lines = [line for line in raw.splitlines() if not line.strip().startswith("#")]
    cleaned = "\n".join(lines)
    entries: list[tuple[str, str]] = []
    for raw_entry in _tokenize(cleaned, ",\n", keep_quotes=True, track_brackets=True):
        if not raw_entry:
            continue
        m_eq = re.match(
            r"^((?:[^\x22\x27\[\]()=]|\x22[^\x22]*\x22|\x27[^\x27]*\x27|\[[^\]]*\]|\([^)]*\))+?)(?<![<>!=])=(?!=)(.+)$",
            raw_entry,
        )
        if m_eq:
            entries.append((m_eq.group(1).strip(), m_eq.group(2).strip()))
            continue
        pieces = _tokenize(raw_entry, ":", keep_quotes=True, track_brackets=True)
        if len(pieces) >= 2:
            raise ValueError(
                f"invalid mutate spec: use '=' for assignment (e.g. 'col = expr'). Colon ':' is not supported in entry '{raw_entry}'"
            )
        raise ValueError(f"invalid mutate spec: missing '=' in entry '{raw_entry}'")
    return entries


def parse_mutate_spec(raw: str) -> dict[str, str]:
    """Parse a mutate spec string like 'bmi = weight / height ** 2' into an ordered dict."""
    stripped = raw.strip()
    if (stripped.startswith("'") and stripped.endswith("'")) or (stripped.startswith('"') and stripped.endswith('"')):
        stripped = stripped[1:-1].strip()
    if stripped.startswith("@"):
        path = stripped[1:].strip()
        if (path.startswith("'") and path.endswith("'")) or (path.startswith('"') and path.endswith('"')):
            path = path[1:-1].strip()
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"mutate spec file not found: '{path}'")
        stripped = file_path.read_text(encoding="utf-8").strip()
    expressions: dict[str, str] = {}
    for key_raw, expr_raw in _split_mutate_entries(stripped):
        key = _unquote_name(key_raw)
        if not key:
            raise ValueError("invalid mutate spec: empty column name")
        expr = expr_raw.strip()
        if not expr:
            raise ValueError(f"invalid mutate spec: '{key}' has no expression")
        expressions[key] = expr
    if not expressions:
        raise ValueError('mutate expects entries like "col = expr"')
    return expressions


def _parse_mutate_spec_entries(raw: str) -> list[tuple[str, str, bool]]:
    """Return an ordered list of (key, expr, is_bracketed) tuples."""
    stripped = raw.strip()
    if (stripped.startswith("'") and stripped.endswith("'")) or (stripped.startswith('"') and stripped.endswith('"')):
        stripped = stripped[1:-1].strip()
    if stripped.startswith("@"):
        path = stripped[1:].strip()
        if (path.startswith("'") and path.endswith("'")) or (path.startswith('"') and path.endswith('"')):
            path = path[1:-1].strip()
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"mutate spec file not found: '{path}'")
        stripped = file_path.read_text(encoding="utf-8").strip()
    entries: list[tuple[str, str, bool]] = []
    for key_raw, expr_raw in _split_mutate_entries(stripped):
        raw_k = key_raw.strip()
        is_bracketed = raw_k.startswith("[") and raw_k.endswith("]")
        key = _unquote_name(key_raw)
        if not key:
            raise ValueError("invalid mutate spec: empty column name")
        expr = expr_raw.strip()
        if not expr:
            raise ValueError(f"invalid mutate spec: '{key}' has no expression")
        entries.append((key, expr, is_bracketed))
    if not entries:
        raise ValueError('mutate expects entries like "col = expr"')
    return entries


def _rewrite_col_refs(expr: str, columns: set[str]) -> tuple[str, dict[str, str]]:
    """Rewrite `col` and [col] for known columns to synthetic identifiers like __col_safe_0__
    for Polars AST compilation, outside string literals."""
    out_chars: list[str] = []
    quote = None
    i, n = 0, len(expr)
    mapping: dict[str, str] = {}
    col_idx = 0
    # Special columns that are not valid Python identifiers (e.g. contain parentheses, spaces, hyphens)
    special_cols = sorted([c for c in columns if not c.isidentifier()], key=len, reverse=True)

    while i < n:
        ch = expr[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == "\\" and i + 1 < n:
                out_chars.append(expr[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch == "`":
            j = expr.find("`", i + 1)
            if j != -1:
                inner = expr[i + 1 : j]
                if inner in columns:
                    alias = f"__col_safe_{col_idx}__"
                    col_idx += 1
                    mapping[alias] = inner
                    out_chars.append(alias)
                    i = j + 1
                    continue
        if ch == "[":
            j = expr.find("]", i + 1)
            if j != -1:
                inner = expr[i + 1 : j]
                if inner in columns:
                    alias = f"__col_safe_{col_idx}__"
                    col_idx += 1
                    mapping[alias] = inner
                    out_chars.append(alias)
                    i = j + 1
                    continue
        if special_cols:
            matched_special = False
            for col_cand in special_cols:
                k = len(col_cand)
                if expr[i : i + k] == col_cand:
                    prev_char = expr[i - 1] if i > 0 else ""
                    next_char = expr[i + k] if i + k < n else ""
                    if (not prev_char.isalnum() and prev_char != "_") and (not next_char.isalnum() and next_char != "_"):
                        alias = f"__col_safe_{col_idx}__"
                        col_idx += 1
                        mapping[alias] = col_cand
                        out_chars.append(alias)
                        i += k
                        matched_special = True
                        break
            if matched_special:
                continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars), mapping


def _strip_at_refs(expr: str) -> tuple[str, set[str]]:
    """Rewrite `@name` local-variable refs to bare `name` for AST compilation,
    and report which names were referenced. `@` inside string literals is left untouched."""
    out_chars: list[str] = []
    names: set[str] = set()
    quote = None
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == "\\" and i + 1 < n:
                out_chars.append(expr[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch == "@" and i + 1 < n and (expr[i + 1].isalpha() or expr[i + 1] == "_"):
            j = i + 1
            while j < n and (expr[j].isalnum() or expr[j] == "_"):
                j += 1
            names.add(expr[i + 1 : j])
            out_chars.append(expr[i + 1 : j])
            i = j
            continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars), names


def _replace_underscore_placeholder(expr: str, col_name: str) -> str:
    """Replace standalone `_` identifier tokens with `col_name`."""
    replacement = col_name if col_name.isidentifier() else f"[{col_name}]"
    out_chars: list[str] = []
    quote: str | None = None
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == "\\" and i + 1 < n:
                out_chars.append(expr[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch in "`[":
            close_ch = "`" if ch == "`" else "]"
            j = expr.find(close_ch, i + 1)
            if j != -1:
                out_chars.append(expr[i : j + 1])
                i = j + 1
                continue
        if ch == "_":
            prev_ch = expr[i - 1] if i > 0 else ""
            next_ch = expr[i + 1] if i + 1 < n else ""
            prev_is_ident = prev_ch.isalnum() or prev_ch in ("_", "@", ".")
            next_is_ident = next_ch.isalnum() or next_ch == "_"
            if not prev_is_ident and not next_is_ident:
                out_chars.append(replacement)
                i += 1
                continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars)


def _resolve_multi_target_cols(df: Any, inner_spec: str, by_cols: list[str] | None) -> list[str]:
    """Resolve inner specification of `(col1, col2)` or `(startswith=bill_)` using resolve_select_columns."""
    from pytae.select import resolve_select_columns

    tokens = [t.strip() for t in _tokenize(inner_spec, ",", track_brackets=True) if t.strip()]
    if not tokens:
        raise ValueError("invalid mutate multi-column target: empty '()' specification")

    _select_keys = {"dtype", "exclude", "contains", "startswith", "endswith", "regex", "exclude_dtype"}
    names: list[str] = []
    kwargs: dict[str, Any] = {}
    for token in tokens:
        if "=" in token:
            k, _, v = token.partition("=")
            k, v = k.strip(), _unquote_name(v.strip())
            if k in _select_keys:
                if not v:
                    raise ValueError(f"mutate multi-column selector '{k}=' requires a value")
                if k in kwargs:
                    prev = kwargs[k]
                    kwargs[k] = (prev if isinstance(prev, list) else [prev]) + [v]
                else:
                    kwargs[k] = v
                continue
        names.append(token if ":" in token or token.startswith(("-", "~", "!")) else _unquote_name(token))

    all_cols = list(df.collect_schema().names()) if hasattr(df, "collect_schema") else list(df.columns)
    schema = df.collect_schema() if hasattr(df, "collect_schema") else getattr(df, "schema", None)
    matched = [str(c) for c in resolve_select_columns(all_cols, schema, *names, **kwargs)]
    if by_cols and kwargs and not names:
        matched = [c for c in matched if c not in by_cols]
    if not matched:
        raise ValueError(f"mutate: multi-column selector '({inner_spec})' matched no columns")
    return matched


# -----------------------------------------------------------------------------
# Pivot Metric Parsing
# -----------------------------------------------------------------------------


@dataclass
class PivotMetric:
    src_col: str | None
    out_name: str
    aggfunc: str
    has_alias: bool = False
    has_explicit_func: bool = False


def _parse_single_metric_expr(item: str, default_a: str) -> list[PivotMetric]:
    item = item.strip()
    if not item:
        return []

    alias: str | None = None
    has_alias = False
    if "=" in item:
        parts = _tokenize(item, "=", track_brackets=True, keep_quotes=True)
        if len(parts) >= 2 and parts[0].strip():
            alias = _unquote_name(parts[0].strip())
            has_alias = True
            rest = "=".join(parts[1:]).strip()
        else:
            rest = item
    else:
        rest = item

    norm_rest = rest.strip()
    if norm_rest.lower() in ("n", "n()", "size", "size()", "count()"):
        out_name = alias if has_alias and alias else "n"
        return [
            PivotMetric(
                src_col=None,
                out_name=out_name,
                aggfunc="size",
                has_alias=has_alias,
                has_explicit_func=True,
            )
        ]

    col_part = rest
    funcs: list[str] = []
    if ":" in rest:
        colon_parts = _tokenize(rest, ":", track_brackets=True, keep_quotes=True)
        if len(colon_parts) >= 2 and colon_parts[0].strip():
            col_part = colon_parts[0].strip()
            func_spec = ":".join(colon_parts[1:]).strip()
            if (func_spec.startswith("[") and func_spec.endswith("]")) or (
                func_spec.startswith("(") and func_spec.endswith(")")
            ):
                inner = func_spec[1:-1].strip()
                funcs = [_unquote_name(f.strip()) for f in _tokenize(inner, ",") if f.strip()]
            else:
                funcs = [_unquote_name(func_spec)]

    src_col = _unquote_name(col_part.strip())
    if not funcs:
        agg = "size" if default_a in ("n", "size") else default_a
        out_name = alias if has_alias and alias else src_col
        return [
            PivotMetric(
                src_col=src_col,
                out_name=out_name,
                aggfunc=agg,
                has_alias=has_alias,
                has_explicit_func=False,
            )
        ]

    res: list[PivotMetric] = []
    for f in funcs:
        agg = "size" if f in ("n", "size") else f
        if has_alias and len(funcs) == 1:
            out_name = alias if alias else f"{src_col}_{f}"
        elif has_alias and len(funcs) > 1:
            out_name = f"{alias}_{f}"
        else:
            out_name = f"{src_col}_{f}"
        res.append(
            PivotMetric(
                src_col=src_col,
                out_name=out_name,
                aggfunc=agg,
                has_alias=has_alias,
                has_explicit_func=True,
            )
        )
    return res


def parse_pivot_metrics(
    v: Any,
    a: str = "sum",
    df_cols: Sequence[str] | None = None,
) -> list[PivotMetric]:
    """Parse rich metric mappings in v for pivot operations."""
    if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, tuple, dict, set)) and len(v) == 0):
        if a in ("n", "size", "count", "sum"):
            return [PivotMetric(src_col=None, out_name="n", aggfunc="size", has_alias=False, has_explicit_func=False)]
        raise ValueError(
            f"pivot(): value column 'v' is required when aggregation function is '{a}'. Omit 'v' for row counts."
        )

    if isinstance(v, str):
        v_strip = v.strip()
        if (v_strip.startswith("{") and v_strip.endswith("}")) or (v_strip.startswith("[") and v_strip.endswith("]")):
            inner = v_strip[1:-1].strip()
            items = [
                item.strip() for item in _tokenize(inner, ",", track_brackets=True, keep_quotes=True) if item.strip()
            ]
        else:
            items = [
                item.strip() for item in _tokenize(v_strip, ",", track_brackets=True, keep_quotes=True) if item.strip()
            ]
        all_metrics: list[PivotMetric] = []
        for item in items:
            all_metrics.extend(_parse_single_metric_expr(item, a))
        return all_metrics

    if isinstance(v, (dict, Mapping)):
        metrics: list[PivotMetric] = []
        for key, val in v.items():
            key_str = _unquote_name(str(key).strip())
            if callable(val):
                raise ValueError(
                    "pivot(): callable in v dictionary is not supported; use function name strings (e.g. 'sum')"
                )
            if isinstance(val, (list, tuple)):
                for f in val:
                    f_str = str(f).strip()
                    agg = "size" if f_str in ("n", "size") else f_str
                    metrics.append(
                        PivotMetric(
                            src_col=key_str,
                            out_name=f"{key_str}_{f_str}",
                            aggfunc=agg,
                            has_alias=False,
                            has_explicit_func=True,
                        )
                    )
            elif isinstance(val, str) and (":" in val or val.strip().lower() in ("n", "size")):
                metrics.extend(_parse_single_metric_expr(f"{key_str} = {val}", default_a=a))
            else:
                f_str = str(val).strip()
                agg = "size" if f_str in ("n", "size") else f_str
                metrics.append(
                    PivotMetric(
                        src_col=key_str,
                        out_name=key_str,
                        aggfunc=agg,
                        has_alias=False,
                        has_explicit_func=True,
                    )
                )
        return metrics

    if isinstance(v, (list, tuple, set)):
        all_metrics = []
        for item in v:
            if not isinstance(item, str):
                item = str(item)
            all_metrics.extend(_parse_single_metric_expr(item, a))
        return all_metrics

    return _parse_single_metric_expr(str(v), a)
