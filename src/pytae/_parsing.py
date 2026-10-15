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

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name
from pytae.cli_parsing import _split_qry_entries

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
        asc = False
        token = token[1:].strip()
    elif token.startswith("+") and len(token) > 1:
        asc = True
        token = token[1:].strip()
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
# Filter Parsing
# -----------------------------------------------------------------------------


def _parse_filter_string(raw: str) -> list[tuple[str, Any]]:
    """Parse filter conditions from a query string."""
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        stripped = stripped[1:-1]
    try:
        entries = _split_qry_entries(stripped)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    pairs: list[tuple[str, Any]] = []
    for key_raw, value_raw in entries:
        key = _unquote_name(key_raw)
        if not key:
            raise ValueError("invalid filter conditions: empty column name")
        if isinstance(value_raw, tuple):
            pairs.append((key, value_raw))
            continue
        if not value_raw:
            raise ValueError(f"invalid filter conditions: '{key}' has no value")
        val_strip = value_raw.strip()
        m_int = re.match(r"^([\[(])\s*([^,()\[\]]+)\s*,\s*([^,()\[\]]+)\s*([\])])$", val_strip)
        if m_int:
            left, b1, b2, right = m_int.groups()
            b1_is_quoted = (b1.startswith("'") and b1.endswith("'")) or (b1.startswith('"') and b1.endswith('"'))
            b2_is_quoted = (b2.startswith("'") and b2.endswith("'")) or (b2.startswith('"') and b2.endswith('"'))
            if not (b1_is_quoted and b2_is_quoted and left == "[" and right == "]"):
                pairs.append((key, val_strip))
                continue

        m_in = re.match(r"^(not\s+in|in)\s*(.+)$", val_strip, flags=re.IGNORECASE)
        if m_in:
            op = "not in" if "not" in m_in.group(1).lower() else "in"
            sub_raw = m_in.group(2).strip()
            try:
                sub_val = ast.literal_eval(sub_raw)
            except (ValueError, SyntaxError):
                sub_val = [s.strip().strip("'\"") for s in sub_raw.strip("[]()").split(",") if s.strip()]
            pairs.append((key, (op, sub_val)))
            continue

        op_match = re.match(r"^(>=|<=|!=|==|>|<)\s*(.+)$", val_strip)
        if op_match:
            op = op_match.group(1)
            sub_raw = op_match.group(2).strip()
            try:
                sub_val = ast.literal_eval(sub_raw)
            except (ValueError, SyntaxError):
                if len(sub_raw) >= 2 and sub_raw[0] in "'\"" and sub_raw[-1] == sub_raw[0]:
                    sub_val = sub_raw[1:-1]
                else:
                    sub_val = sub_raw
            pairs.append((key, (op, sub_val)))
            continue
        try:
            value = ast.literal_eval(val_strip)
        except (ValueError, SyntaxError):
            if len(val_strip) >= 2 and val_strip[0] in "'\"" and val_strip[-1] == val_strip[0]:
                value = val_strip[1:-1]
            else:
                value = val_strip
        pairs.append((key, value))
    if not pairs:
        raise ValueError("filter() expects at least one condition")
    return pairs


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


def _rewrite_fallback_col_refs(expr: str, columns: set[str]) -> tuple[str, dict[str, str]]:
    """Rewrite `col` and [col] for known columns to synthetic identifiers like __col_safe_0__
    for the plain Python eval() fallback, outside string literals."""
    out_chars: list[str] = []
    quote = None
    i, n = 0, len(expr)
    mapping: dict[str, str] = {}
    col_idx = 0
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
        out_chars.append(ch)
        i += 1
    return "".join(out_chars), mapping


def _strip_at_refs(expr: str) -> tuple[str, set[str]]:
    """Rewrite pandas-eval `@name` local-variable refs to bare `name` for the
    plain Python eval() fallback (which has no `@` syntax), and report which
    names were referenced. `@` inside string literals is left untouched."""
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
        names.append(token if ":" in token or token.startswith(("-", "~")) else _unquote_name(token))

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
