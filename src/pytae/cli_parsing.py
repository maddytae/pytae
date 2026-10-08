"""Parsing helpers for pytae CLI flag values (pure string parsing; no pandas/pipeline state)."""

from __future__ import annotations

import argparse
import ast
import difflib
import glob
import re
from pathlib import Path
from typing import Any

from pytae._text import _is_enclosed_pair
from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name

SELECT_KEYS = ("dtype", "exclude_dtype", "contains", "startswith", "endswith", "regex", "exclude")


def parse_columns(raw: str) -> list[str]:
    """Parse a column list like "'col a','col b'" or "col_a,col_b" or "[col a], [col b]" into a list of names."""
    raw = raw.strip()
    if _is_enclosed_pair(raw, "[", "]") and "," in raw:
        raw = raw[1:-1].strip()
    try:
        parsed = ast.literal_eval(f"[{raw}]")
        cols = list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
        return [_unquote_name(str(c).strip()) for c in cols]
    except (ValueError, SyntaxError):
        tokens = _tokenize(raw, ",", track_brackets=True)
        return [_unquote_name(c.strip()) for c in tokens if c.strip()]



def parse_sort_by(raw: str) -> tuple[list[str], str]:
    """Parse legacy -sort_by SPEC: a comma-separated column list, optionally ending with
    asc or desc as a trailing word (default asc). e.g. "species,body_mass_g desc"."""
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit("-sort_by: expected a column list, optionally followed by asc or desc")
    order = "asc"
    head, sep, tail = raw.rpartition(" ")
    if sep and tail.lower() in ("asc", "desc"):
        raw, order = head.rstrip(",").strip(), tail.lower()
    cols = parse_columns(raw)
    if not cols:
        raise SystemExit("-sort_by: expected a column list, optionally followed by asc or desc")
    return cols, order


def parse_arrange(raw: str) -> tuple[list[str], list[bool]]:
    """Parse -arrange SPEC: a comma-separated column list with optional asc/desc directions,
    leading '-', or brackets for spaced columns. e.g. "species, [annual salary] desc".
    """
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit("-arrange: expected a column list with optional asc/desc directions")
    from pytae.arrange import _extract_arrange_specs
    cols, asc_list = _extract_arrange_specs((raw,))
    if not cols:
        raise SystemExit("-arrange: expected a column list with optional asc/desc directions")
    return cols, asc_list


def parse_pick_spec(raw: str, flag_name: str = "-pick") -> tuple[str, int | None, float | None, str]:
    """Parse -pick SPEC.

    Canonical syntax:
      - 'col,n=N'             e.g. 'body_mass_g,n=3' (order=max by default)
      - 'col,n=N,order=min'   e.g. 'body_mass_g,n=3,order=min'
      - 'col,prop=P'         e.g. 'body_mass_g,prop=0.1'
      - 'col'                e.g. 'body_mass_g' (defaults to n=1, order=max)
      - bracketed spaced names: '[bill length mm],n=3'
    """
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit(f"{flag_name}: expected a column name, e.g. 'col' or 'col,n=N'")

    tokens = [t.strip() for t in _tokenize(raw, ",", track_brackets=True) if t.strip()]
    if not tokens:
        raise SystemExit(f"{flag_name}: expected a column name, e.g. 'col' or 'col,n=N'")

    col_raw = tokens[0]
    col = _unquote_name(col_raw)
    if not col:
        raise SystemExit(f"{flag_name}: expected a column name, e.g. 'col' or 'col,n=N'")

    n: int | None = None
    prop: float | None = None
    order: str = "min" if "min" in flag_name.lower() else "max"

    if len(tokens) == 1:
        return col, 1, None, order

    for param in tokens[1:]:
        if param.startswith("n="):
            val_str = param[2:].strip()
            if not val_str.isdigit() or int(val_str) <= 0:
                raise SystemExit(f"{flag_name}: invalid n value '{val_str}'; must be a positive integer")
            if n is not None or prop is not None:
                raise SystemExit(f"{flag_name}: specify either n= or prop= once")
            n = int(val_str)
        elif param.startswith("prop="):
            val_str = param[5:].strip()
            try:
                p_val = float(val_str)
                if not (0 < p_val <= 1):
                    raise ValueError
            except ValueError:
                raise SystemExit(f"{flag_name}: invalid prop value '{val_str}'; must be a number between 0 and 1")
            if n is not None or prop is not None:
                raise SystemExit(f"{flag_name}: specify either n= or prop= once")
            prop = p_val
        elif param.startswith("order="):
            ord_val = param[6:].strip().lower()
            if ord_val not in ("max", "min"):
                raise SystemExit(f"{flag_name}: invalid order value '{ord_val}'; must be 'max' or 'min'")
            order = ord_val
        else:
            raise SystemExit(f"{flag_name}: unrecognized parameter '{param}'; expected 'n=N', 'prop=P', or 'order=max|min'")

    if n is None and prop is None:
        n = 1
    return col, n, prop, order


def parse_slice_spec(raw: str, flag_name: str = "-slice_max") -> tuple[str, int | None, float | None]:
    """Deprecated parser alias for parse_pick_spec."""
    col, n, prop, _ = parse_pick_spec(raw, flag_name=flag_name)
    return col, n, prop


def _split_tokens(raw: str, sep: str = ",") -> list[str]:
    """Split on sep, respecting quotes and brackets."""
    return [t for t in _tokenize(raw, sep, track_brackets=True) if t]


def _split_groups(raw: str, sep: str = ";") -> list[str]:
    """Split on sep but keep quote characters so inner comma-split still sees them."""
    return [t for t in _tokenize(raw, sep, keep_quotes=True) if t]


def parse_select_spec(raw: str) -> tuple[list[str], dict]:
    """Parse -select into positional names/slices and select() kwargs.

    Tokens without '=' are column names or start:end slices. Tokens like
    dtype=numeric / contains=bill / regex=^flip become kwargs. Repeated keys
    become a list. Union of all tokens, matching pt.select().
    """
    raw = raw.strip()
    if _is_enclosed_pair(raw, "[", "]") and "," in raw:
        raw = raw[1:-1].strip()
    tokens = _split_tokens(raw)

    names: list[str] = []
    kwargs: dict = {}
    for token in tokens:
        if "=" in token:
            key, _, value = token.partition("=")
            key = key.strip()
            value = value.strip()
            if key in SELECT_KEYS:
                if not value:
                    raise SystemExit(f"-select: {key}= needs a value")
                if key in kwargs:
                    prev = kwargs[key]
                    kwargs[key] = (prev if isinstance(prev, list) else [prev]) + [value]
                else:
                    kwargs[key] = value
                continue
        names.append(token)
    if not names and not kwargs:
        raise SystemExit("-select: expected column names and/or key=value tokens")
    if "exclude_dtype" in kwargs and (names or len(kwargs) > 1):
        raise SystemExit("-select: exclude_dtype cannot be combined with other selection criteria")
    return names, kwargs


def _select_unknown_names(tokens: list[str], available: list[str]) -> list[str]:
    """Exact-name tokens (and slice endpoints) that are not in the file."""
    unknown: list[str] = []
    for token in tokens:
        clean = _unquote_name(token)
        if clean in available:
            continue
        if token.startswith(("-", "~")):
            raw = _unquote_name(token[1:].strip())
            if raw in available:
                continue
            if ":" in raw:
                start, end = raw.split(":", 1)
                start, end = _unquote_name(start.strip()), _unquote_name(end.strip())
                if start and start not in available:
                    unknown.append(start)
                if end and end not in available:
                    unknown.append(end)
            else:
                unknown.append(raw)
        elif ":" in token:
            start, end = token.split(":", 1)
            start, end = _unquote_name(start.strip()), _unquote_name(end.strip())
            if start and start not in available:
                unknown.append(start)
            if end and end not in available:
                unknown.append(end)
        else:
            unknown.append(clean)
    return unknown


def unknown_columns_message(flag: str, requested: list[str], available: list[str]) -> str:
    """Build an 'unknown column(s)' error message, suggesting a close match for likely typos."""
    unknown = [c for c in requested if c not in available]
    parts = []
    for c in unknown:
        close = difflib.get_close_matches(c, available, n=1)
        parts.append(f"'{c}'" + (f" (did you mean '{close[0]}'?)" if close else ""))
    return f"{flag}: unknown column(s): {', '.join(parts)}"


def parse_rename(raw: str) -> dict[str, str]:
    """Parse a rename mapping like "old_a:new_a,old_b:new_b" into a dict.
    Quoting either side (e.g. "'old a':'new a'") is optional and stripped if present—
    plain old_a:new_a already handles spaces, quoting just needs to not break things."""
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" in pair:
            old, new = pair.split(":", 1)
        elif "=" in pair:
            raise SystemExit(f"invalid -rename mapping '{pair}'; use ':' (e.g. -rename 'old:new'). '=' is not supported.")
        else:
            raise SystemExit(f"invalid -rename mapping '{pair}'; expected old:new")
        old_clean = _unquote_name(old)
        new_clean = _unquote_name(new)
        if old_clean in mapping and mapping[old_clean] != new_clean:
            raise SystemExit(f"invalid -rename: conflicting mappings for '{old_clean}': '{mapping[old_clean]}' and '{new_clean}'")
        mapping[old_clean] = new_clean
    return mapping


def expand_paths(patterns: str | list[str]) -> list[Path]:
    """Expand glob pattern(s) into matching paths, or wrap plain paths as-is."""
    items = [patterns] if isinstance(patterns, str) else list(patterns)
    results: list[Path] = []
    seen: set[Path] = set()
    for item in items:
        p_literal = Path(item)
        if p_literal.exists():
            if p_literal not in seen:
                results.append(p_literal)
                seen.add(p_literal)
        elif any(ch in item for ch in "*?["):
            matches = sorted(Path(p) for p in glob.glob(item))
            if not matches:
                raise SystemExit(f"no files matched pattern: {item}")
            for m in matches:
                if m not in seen:
                    results.append(m)
                    seen.add(m)
        else:
            if p_literal not in seen:
                results.append(p_literal)
                seen.add(p_literal)
    return results


def _split_qry_entries(raw: str) -> list[tuple[str, str]]:
    """Split a -qry body into raw (key, value) text pairs on top-level commas and equals,
    respecting quotes and nested (), [], {} so tuples/lists/intervals inside a value
    aren't mistaken for entry or key/value separators. Direct comparisons like
    'col > 5' or assignments like 'col = > 3500' or 'col = 3500' are accepted."""
    entries: list[tuple[str, str]] = []
    for raw_entry in _tokenize(raw, ",", keep_quotes=True, track_brackets=True):
        if not raw_entry:
            continue
        # Direct comparison first: col > 5, col >= 5, col <= 5, etc.
        m_cmp = re.match(r"^([^>=<!:]+?)\s*(>=|<=|!=|==|>|<)\s*(.+)$", raw_entry)
        if m_cmp:
            col = m_cmp.group(1).strip()
            op = m_cmp.group(2).strip()
            val = m_cmp.group(3).strip()
            entries.append((col, f"{op} {val}"))
            continue
        # Assignment with '=': col = val, col = > 5, col = ['a', 'b']
        m_eq = re.match(r"^([^>=<!:]+?)\s*=\s*(.+)$", raw_entry)
        if m_eq:
            col = m_eq.group(1).strip()
            val = m_eq.group(2).strip()
            entries.append((col, val))
            continue
        # If colon was used, give a helpful error
        pieces = _tokenize(raw_entry, ":", keep_quotes=True, track_brackets=True)
        if len(pieces) >= 2:
            raise SystemExit(f"invalid -qry condition '{raw_entry}': use '=' (e.g. -qry 'species = Adelie'). Colon ':' is not supported.")
        raise SystemExit(f"invalid -qry conditions: missing '=' in entry '{raw_entry}'")
    return entries


def parse_filter(raw: str) -> list[tuple[str, Any]]:
    """Parse -filter conditions like "col = ('>', 5), other = ['a','b']"; wrapping {} and
    quotes around column names are both optional (matching -select), e.g.
    "sex='Male'" == "'sex'='Male'". Prefix operators (e.g. "col = > 5" or "col > 5") and bare string
    values (e.g. "species = Adelie") are also accepted."""
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        stripped = stripped[1:-1]
    conditions: list[tuple[str, Any]] = []
    for key_raw, value_raw in _split_qry_entries(stripped):
        key = _unquote_name(key_raw)
        if not key:
            raise SystemExit("invalid --filter conditions: empty column name")
        val_strip = value_raw.strip()
        if not val_strip:
            raise SystemExit(f"invalid --filter conditions: '{key}' has no value")

        # Check interval syntax: e.g. [3000, 4500], (3000, 4500), [a, c), (a, c]
        m_int = re.match(r"^([\[(])\s*([^,()\[\]]+)\s*,\s*([^,()\[\]]+)\s*([\])])$", val_strip)
        if m_int:
            left, b1, b2, right = m_int.groups()
            b1_is_quoted = (b1.startswith("'") and b1.endswith("'")) or (b1.startswith('"') and b1.endswith('"'))
            b2_is_quoted = (b2.startswith("'") and b2.endswith("'")) or (b2.startswith('"') and b2.endswith('"'))
            if not (b1_is_quoted and b2_is_quoted and left == "[" and right == "]"):
                conditions.append((key, val_strip))
                continue

        op_match = re.match(r"^(>=|<=|!=|==|>|<)\s*(.+)$", val_strip)
        if op_match:
            op = op_match.group(1)
            sub_raw = op_match.group(2).strip()
            try:
                sub_val = ast.literal_eval(sub_raw)
            except (ValueError, SyntaxError):
                sub_val = _unquote_name(sub_raw)
            conditions.append((key, (op, sub_val)))
            continue

        try:
            value = ast.literal_eval(val_strip)
        except (ValueError, SyntaxError) as exc:
            raise SystemExit(
                f"invalid --filter conditions: value for '{key}' ('{val_strip}') must be quoted "
                "(e.g. 'Male') or a valid literal (number/tuple/list)"
            ) from exc
        conditions.append((key, value))
    if not conditions:
        raise SystemExit("-filter expects keyword entries, e.g. \"col = ('>', 5)\" or \"col > 5\" (quotes around column name optional)")
    return conditions


def parse_qry(raw: str) -> list[tuple[str, Any]]:
    """Deprecated alias for parse_filter."""
    return parse_filter(raw)


def parse_agg(raw: str):
    """Parse -agg: a name (mean), a comma list (mean,sum,n), or a col=aggfunc
    mapping (val = sum, n = n, total = v1:sum). Quote a mapping key only to protect a comma."""
    raw = (raw or "").strip()
    if not raw:
        return "sum"
    if raw.startswith("{") or (raw.startswith("[") and "=" not in raw):
        raise SystemExit(
            "-agg: use a name (mean), a comma list (mean,sum), or a mapping "
            "(col = mean, n = n)"
        )
    entries = [e for e in _tokenize(raw, ",", keep_quotes=True, track_brackets=True) if e]
    if not entries:
        raise SystemExit("-agg: expected a name, a comma list, or a mapping")

    def _is_mapping(entry: str) -> bool:
        return (
            len(_tokenize(entry, "=", keep_quotes=True, track_brackets=True)) >= 2
            or len(_tokenize(entry, ":", keep_quotes=True, track_brackets=True)) >= 2
        )

    mapped = [_is_mapping(e) for e in entries]
    if all(mapped):
        out: dict[str, Any] = {}
        dropna_flag = None
        for entry in entries:
            if "=" in entry:
                parts = _tokenize(entry, "=", keep_quotes=True, track_brackets=True)
                key = _unquote_name(parts[0])
                value = _unquote_name("=".join(parts[1:]))
                if key in ("column", "aggfunc"):
                    raise SystemExit(
                        "-agg: the old 'column=...,aggfunc=...' syntax is retired. "
                        "Use '-by <cols> -agg \"col = aggfunc\"' or '-agg \"total = col:aggfunc\"' instead."
                    )
                if key.lower() == "dropna":
                    dropna_flag = parse_bool_text(value)
                    continue
            elif ":" in entry:
                raise SystemExit(f"-agg: invalid mapping entry '{entry}'; use '=' (e.g. -agg 'col = mean'). Colon ':' is not supported.")
            else:
                raise SystemExit(f"-agg: invalid mapping entry {entry!r}")
            if not key or not value:
                raise SystemExit(f"-agg: invalid mapping entry {entry!r}")
            out[key] = value
        if dropna_flag is not None:
            out["__dropna__"] = dropna_flag
        return out
    if any(mapped):
        raise SystemExit(
            "-agg: mix of names and col=aggfunc mappings; use one or the other"
        )
    names = [_unquote_name(e) for e in entries]
    return names[0] if len(names) == 1 else names


_AGG_KEYS = ("column", "aggfunc", "as")


def parse_group_agg(raw: str) -> list[tuple[str, str, str]]:
    """Parse -agg as key=value specs: column=, aggfunc=, optional as=.

    Several specs are separated by ';'. Several source columns in one spec share
    the same aggfunc: column='value,val_growth',aggfunc=sum. as= needs a single column.
    Returns (source_col, output_name, aggfunc) rows.
    """
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit("-agg: expected key=value specs, e.g. column=value,aggfunc=sum,as=v")
    if raw.startswith("{"):
        raise SystemExit(
            "-agg: use key=value specs, e.g. column=value,aggfunc=sum,as=v "
            "(not a dict literal)"
        )
    rows: list[tuple[str, str, str]] = []
    for group in _split_groups(raw, ";"):
        canon = parse_reshape_kwargs(group, keys=_AGG_KEYS, flag="-agg")
        if "column" not in canon or "aggfunc" not in canon:
            raise SystemExit("-agg: each spec needs column= and aggfunc=")
        cols = parse_columns(canon["column"])
        if not cols:
            raise SystemExit("-agg: column= needs at least one column")
        out = canon.get("as")
        if out and len(cols) != 1:
            raise SystemExit("-agg: as= requires a single column")
        aggfunc = canon["aggfunc"]
        for col in cols:
            rows.append((col, out or col, aggfunc))
    names = [name for _, name, _ in rows]
    if len(names) != len(set(names)):
        raise SystemExit("-agg: duplicate output names")
    return rows


_LONG_KEYS = ("c", "v", "cols", "values", "id_vars", "by")
_WIDE_KEYS = ("c", "v", "index", "by", "r", "rows", "cols", "values")


def parse_reshape_kwargs(raw: str | None, *, keys: tuple[str, ...], flag: str) -> dict:
    """Parse -long/-wide/-pivot as key=value tokens, e.g. c=metric,v=reading,a=mean.
    Comma-separated lists like frames=a,b,c or on=id:id,code:code work with or without quotes."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    kwargs: dict = {}
    current_key: str | None = None
    for token in _split_tokens(raw):
        if "=" in token:
            key, _, value = token.partition("=")
            key = key.strip()
            value = _unquote_name(value)
            if flag == "-wide" and key in ("a", "agg", "aggfunc"):
                raise SystemExit(
                    "-wide: -wide is strictly for 1-to-1 reshaping without aggregation. "
                    "Use -pivot for aggregations (e.g. -pivot 'r=...,c=...,v=...,a=...')."
                )
            if key not in keys:
                raise SystemExit(f"{flag}: unknown key {key!r}; expected {', '.join(keys)}")
            if not value:
                raise SystemExit(f"{flag}: {key}= needs a value")
            if key in kwargs:
                raise SystemExit(f"{flag}: {key}= given more than once")
            current_key = key
            kwargs[key] = value
        else:
            if current_key is None:
                raise SystemExit(f"{flag}: expected key=value tokens ({', '.join(keys)})")
            kwargs[current_key] = f"{kwargs[current_key]},{_unquote_name(token)}"
    for key, value in list(kwargs.items()):
        if key in ("margins", "exact", "dropna"):
            kwargs[key] = parse_bool_text(value)
        elif key in ("fill", "fill_value"):
            if isinstance(value, str):
                v_lower = value.strip().lower()
                if v_lower in ("none", "null"):
                    kwargs[key] = None
                else:
                    try:
                        kwargs[key] = int(value)
                    except ValueError:
                        try:
                            kwargs[key] = float(value)
                        except ValueError:
                            raise SystemExit(f"{flag}: {key}= must be a numeric value or 'none'")
        else:
            kwargs[key] = value
    return kwargs


def parse_long_arg(raw: str | None) -> dict:
    return parse_reshape_kwargs(raw, keys=_LONG_KEYS, flag="-long")


def parse_wide_arg(raw: str | None) -> dict:
    parsed = parse_reshape_kwargs(raw, keys=_WIDE_KEYS, flag="-wide")
    if "cols" in parsed and "c" not in parsed:
        parsed["c"] = parsed.pop("cols")
    if "values" in parsed and "v" not in parsed:
        parsed["v"] = parsed.pop("values")
    return parsed


_PIVOT_KEYS = (
    "r", "c", "v", "a", "dropna", "fill_value", "fill",
    "rows", "row", "index", "by",
    "cols", "col", "columns",
    "values", "value", "val", "vals",
    "agg", "aggfunc",
)


def parse_pivot_arg(raw: str | None) -> dict:
    return parse_reshape_kwargs(raw, keys=_PIVOT_KEYS, flag="-pivot")


_REPLACE_KEYS = ("c", "v", "exact")


def parse_value_map(raw: str) -> dict[str, str]:
    """Parse a -replace_values v= mapping like "old_a:new_a,old_b:new_b" into a dict."""
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" in pair:
            old, new = pair.split(":", 1)
        elif "=" in pair:
            raise SystemExit(f"-replace_values: invalid v= mapping '{pair}'; use ':' (expected old:new). '=' is not supported.")
        else:
            raise SystemExit(f"-replace_values: invalid v= mapping '{pair}'; expected old:new")
        mapping[_unquote_name(old)] = _unquote_name(new)
    if not mapping:
        raise SystemExit("-replace_values: v= needs at least one old:new pair")
    return mapping


def parse_replace_values_arg(raw: str) -> tuple[list[str] | None, dict[str, str], bool]:
    """Parse -replace_values as key=value tokens: c= (optional column scope), v= (required
    old:new mapping), exact= (optional bool, default true — whole-cell match vs
    substring match anywhere in the cell). Returns (cols_or_None, mapping, exact)."""
    kwargs = parse_reshape_kwargs(raw, keys=_REPLACE_KEYS, flag="-replace_values")
    if "v" not in kwargs:
        raise SystemExit("-replace_values: expected v='old:new,...'")
    cols = parse_columns(kwargs["c"]) if "c" in kwargs else None
    mapping = parse_value_map(kwargs["v"])
    exact = kwargs.get("exact", True)
    return cols, mapping, exact


def parse_bool_text(raw: str) -> bool:
    """Parse a required true/false text flag value into bool."""
    lowered = raw.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise argparse.ArgumentTypeError("expected 'true' or 'false'")


def parse_positive_int(raw) -> int:
    """Parse a row-count flag; reject 0 and negatives (e.g. -head 0, -head -5)."""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"invalid integer: {raw!r}") from None
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {n}")
    return n


def parse_fraction(raw) -> float:
    """Parse -frac: a fraction of rows in (0, 1] (e.g. -frac 0.1 for 10%)."""
    try:
        frac = float(raw)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"invalid number: {raw!r}") from None
    if not (0 < frac <= 1):
        raise argparse.ArgumentTypeError(f"must be > 0 and <= 1, got {frac}")
    return frac


def parse_list_order(raw: str) -> str:
    """Parse optional listing order for -cols/-dtype/-nulls: asc or desc.

    'file' is the internal sentinel used when the flag is present with no value
    (argparse 3.14 type-converts const).
    """
    lowered = str(raw).strip().lower()
    if lowered in ("asc", "desc", "file"):
        return lowered
    raise argparse.ArgumentTypeError("expected 'asc' or 'desc'")


_CLEAN_COLUMNS_BOOL_KEYS = ("strip", "squeeze", "strip_special", "dedupe")
_CLEAN_COLUMNS_KEYS = _CLEAN_COLUMNS_BOOL_KEYS + ("fill", "case")
_CLEAN_COLUMNS_CASE_VALUES = ("lower", "upper", "proper")


def parse_clean_columns_arg(raw: str) -> dict:
    """Parse -clean_columns as key[=value] tokens, comma-separated:

    - strip=, squeeze=, strip_special=, dedupe= — bools (default false); a bare
      key with no '=' means true, e.g. "strip" is short for "strip=true".
    - fill[=STR] — replace whitespace in a header with STR; bare "fill" defaults
      to '_'; omit the key entirely for no fill.
    - case=lower|upper|proper — no bare/default form, always needs a value.
    """
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit(
            "-clean_columns: expected at least one key, e.g. \"strip\" or \"case=lower\""
        )
    kwargs: dict = {}
    for token in _split_tokens(raw):
        key, has_value, value = token.partition("=")
        key = key.strip()
        if key not in _CLEAN_COLUMNS_KEYS:
            raise SystemExit(f"-clean_columns: unknown key {key!r}; expected {', '.join(_CLEAN_COLUMNS_KEYS)}")
        if key in kwargs:
            raise SystemExit(f"-clean_columns: {key}= given more than once")
        if key in _CLEAN_COLUMNS_BOOL_KEYS:
            kwargs[key] = parse_bool_text(_unquote_name(value)) if has_value else True
        elif key == "fill":
            kwargs[key] = _unquote_name(value) if has_value else "_"
        else:  # case
            case_value = _unquote_name(value).strip().lower()
            if not has_value or not case_value:
                raise SystemExit("-clean_columns: case= needs a value (lower, upper, or proper)")
            if case_value not in _CLEAN_COLUMNS_CASE_VALUES:
                raise SystemExit(f"-clean_columns: case= must be one of {', '.join(_CLEAN_COLUMNS_CASE_VALUES)}")
            kwargs[key] = case_value
    return kwargs


_FILE_ENTRY_KEYS = ("dlim", "encoding")


def parse_file_arg(raw: str) -> list[dict]:
    """Parse -file as ';'-separated entries (at least two), each PATH=ALIAS optionally
    followed by ,dlim=/,encoding= overrides for reading that file, e.g.
    "data1.parquet=df1,dlim='|'; data2.parquet=df2,encoding='latin-1'".
    Returns a list of {'path', 'alias', 'dlim', 'encoding'} dicts (dlim/encoding are
    None when not given).
    """
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit("-file: expected at least one PATH=ALIAS entry")
    entries: list[dict] = []
    aliases_seen: set[str] = set()
    for group in _split_groups(raw, ";"):
        tokens = _split_tokens(group, ",")
        if not tokens:
            raise SystemExit("-file: expected PATH=ALIAS")
        head, has_value, alias = tokens[0].partition("=")
        if not has_value or not alias.strip():
            raise SystemExit(f"-file: expected PATH=ALIAS, got {tokens[0]!r}")
        alias = alias.strip()
        if alias in aliases_seen:
            raise SystemExit(f"-file: duplicate alias '{alias}'")
        aliases_seen.add(alias)
        entry = {"path": head.strip(), "alias": alias, "dlim": None, "encoding": None}
        for token in tokens[1:]:
            key, has_kv, value = token.partition("=")
            key = key.strip()
            if not has_kv or key not in _FILE_ENTRY_KEYS:
                raise SystemExit(f"-file: unknown option {token!r}; expected dlim= or encoding=")
            entry[key] = _unquote_name(value)
        entries.append(entry)
    if len(entries) < 2:
        raise SystemExit("-file: need at least two PATH=ALIAS entries")
    return entries


_MERGE_KEYS = ("left", "right", "on", "how", "validate")


def parse_merge_on(raw: str) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """Parse -merge's on= value: shared column names (comma list) when names match on
    both sides, or 'left:right' pairs when they differ between sides. Quote the whole
    on= value if it has more than one column/pair (protects the inner commas), e.g.
    on='col a:cola,colb:colb'. Returns (on_cols, left_cols, right_cols) — on_cols is
    set XOR (left_cols, right_cols) are set.
    """
    pairs = [p.strip() for p in raw.split(",") if p.strip()]
    if not pairs:
        raise SystemExit("-merge: on= needs at least one column (or left:right pair)")
    has_colon = [":" in p for p in pairs]
    if any(has_colon) and not all(has_colon):
        raise SystemExit("-merge: on= mixes plain columns and left:right pairs; use one style")
    if all(has_colon):
        left_cols, right_cols = [], []
        for pair in pairs:
            left, _, right = pair.partition(":")
            left_cols.append(left.strip())
            right_cols.append(right.strip())
        return None, left_cols, right_cols
    return pairs, None, None


def parse_merge_arg(raw: str) -> dict:
    """Parse -merge as key=value tokens: left=/right= (required -file aliases, or the
    literal 'df' to reference the pipeline's current result so far — lets repeated
    -merge calls fold in one more file at a time), on= (required; shared column
    name(s), or left:right pairs if they differ between sides), how= (optional,
    default 'inner', passed straight to pandas merge()), validate= (optional, passed
    straight to pandas merge()).
    """
    kwargs = parse_reshape_kwargs(raw, keys=_MERGE_KEYS, flag="-merge")
    how = kwargs.get("how", "inner")
    required = ["left", "right"] if how == "cross" else ["left", "right", "on"]
    missing = [k for k in required if k not in kwargs]
    if missing:
        raise SystemExit(f"-merge: missing required key(s): {', '.join(missing)}")
    if how == "cross":
        if "on" in kwargs:
            raise SystemExit("-merge: on= cannot be used with how=cross (pandas cross joins don't take on=)")
        on_cols, left_cols, right_cols = None, None, None
    else:
        on_cols, left_cols, right_cols = parse_merge_on(kwargs["on"])
    return {
        "left": kwargs["left"],
        "right": kwargs["right"],
        "on": on_cols,
        "left_on": left_cols,
        "right_on": right_cols,
        "how": how,
        "validate": kwargs.get("validate"),
    }


_CONCAT_KEYS = ("frames",)


def parse_concat_arg(raw: str) -> dict:
    """Parse -concat as key=value tokens: frames= (required) — an ordered,
    comma-separated list of -file aliases (or 'df' for the pipeline's current
    result, to stack more files onto something already produced), e.g.
    frames='df1,df2,df3'. Quote the whole value — it has internal commas.
    """
    kwargs = parse_reshape_kwargs(raw, keys=_CONCAT_KEYS, flag="-concat")
    if "frames" not in kwargs:
        raise SystemExit("-concat: expected frames='alias1,alias2,...'")
    names = [n.strip() for n in kwargs["frames"].split(",") if n.strip()]
    if len(names) < 2:
        raise SystemExit("-concat: frames= needs at least two names")
    return {"frames": names}


def parse_kv_spec(raw: str | None, *, flag: str) -> dict[str, Any]:
    """Parse comma-separated key=value tokens into a kwargs dict, type-casting numbers and booleans."""
    if not raw or not raw.strip():
        return {}
    kwargs: dict[str, Any] = {}
    for token in _tokenize(raw, ",", keep_quotes=True, track_brackets=True):
        token = token.strip()
        if not token:
            continue
        if "=" not in token:
            kwargs[token.strip()] = True
            continue
        key, _, raw_val = token.partition("=")
        key = key.strip()
        raw_val = raw_val.strip()
        val: Any
        if (raw_val.startswith("'") and raw_val.endswith("'")) or (raw_val.startswith('"') and raw_val.endswith('"')):
            val = raw_val[1:-1]
        elif raw_val.lower() == "true":
            val = True
        elif raw_val.lower() == "false":
            val = False
        elif raw_val.lower() in ("none", "null"):
            val = None
        else:
            try:
                val = int(raw_val)
            except ValueError:
                try:
                    val = float(raw_val)
                except ValueError:
                    val = raw_val
        kwargs[key] = val
    return kwargs

