"""Parsing helpers for pytae CLI flag values (pure string parsing; no pandas/pipeline state)."""

from __future__ import annotations

import argparse
import ast
import difflib
import glob
from pathlib import Path

SELECT_KEYS = ("dtype", "exclude_dtype", "contains", "startswith", "endswith", "regex")


def parse_columns(raw: str) -> list[str]:
    """Parse a column list like "'col a','col b'" or "col_a,col_b" into a list of names."""
    raw = raw.strip()
    try:
        parsed = ast.literal_eval(f"[{raw}]")
        cols = list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
        return [str(c).strip() for c in cols]
    except (ValueError, SyntaxError):
        return [c.strip().strip("'\"") for c in raw.split(",") if c.strip()]


def _split_tokens(raw: str, sep: str = ",") -> list[str]:
    """Split on sep, respecting single or double quotes."""
    tokens: list[str] = []
    buf: list[str] = []
    quote = None
    for ch in raw:
        if quote:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in "'\"":
            quote = ch
        elif ch == sep:
            token = "".join(buf).strip()
            if token:
                tokens.append(token)
            buf = []
        else:
            buf.append(ch)
    token = "".join(buf).strip()
    if token:
        tokens.append(token)
    return tokens


def _split_groups(raw: str, sep: str = ";") -> list[str]:
    """Split on sep but keep quote characters so inner comma-split still sees them."""
    tokens: list[str] = []
    buf: list[str] = []
    quote = None
    for ch in raw:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == sep:
            token = "".join(buf).strip()
            if token:
                tokens.append(token)
            buf = []
        else:
            buf.append(ch)
    token = "".join(buf).strip()
    if token:
        tokens.append(token)
    return tokens


def parse_select_spec(raw: str) -> tuple[list[str], dict]:
    """Parse -select into positional names/slices and select() kwargs.

    Tokens without '=' are column names or start:end slices. Tokens like
    dtype=numeric / contains=bill / regex=^flip become kwargs. Repeated keys
    become a list. Union of all tokens, matching df.select().
    """
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
        if ":" in token:
            start, end = token.split(":", 1)
            start, end = start.strip(), end.strip()
            if start and start not in available:
                unknown.append(start)
            if end and end not in available:
                unknown.append(end)
        elif token not in available:
            unknown.append(token)
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
    """Parse a rename mapping like "old_a:new_a,old_b:new_b" into a dict."""
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise SystemExit(f"invalid --rename mapping '{pair}'; expected old:new")
        old, new = pair.split(":", 1)
        mapping[old.strip()] = new.strip()
    return mapping


def expand_paths(pattern: str) -> list[Path]:
    """Expand a glob pattern (e.g. "data/*.parquet") into matching paths, or wrap a plain path as-is."""
    if any(ch in pattern for ch in "*?["):
        matches = sorted(Path(p) for p in glob.glob(pattern))
        if not matches:
            raise SystemExit(f"no files matched pattern: {pattern}")
        return matches
    return [Path(pattern)]


def parse_qry(raw: str) -> dict:
    """Parse --qry conditions like "'col': ('>', 5), 'other': ['a','b']"; wrapping {} is optional."""
    stripped = raw.strip()
    candidate = stripped if stripped.startswith("{") else f"{{{stripped}}}"
    try:
        conditions = ast.literal_eval(candidate)
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f"invalid --qry conditions: {exc}") from exc
    if not isinstance(conditions, dict):
        raise SystemExit("--qry expects dict entries, e.g. \"'col': ('>', 5)\" (braces optional)")
    return conditions


def parse_agg(raw: str):
    """Parse an --agg_df aggfunc value: bare string ('sum'), list literal, or dict of
    quoted key:value pairs, surrounding {} optional, e.g. "'col':'sum','n':'n'"."""
    raw = raw.strip()
    if not (raw.startswith(("{", "[", "'", '"'))):
        return raw
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        if raw.startswith("{"):
            raise SystemExit(f"invalid --agg_df value: {exc}") from exc
        try:
            return ast.literal_eval(f"{{{raw}}}")
        except (ValueError, SyntaxError):
            raise SystemExit(f"invalid --agg_df value: {exc}") from exc


_AGG_KEYS = ("column", "aggfunc", "as")


def parse_group_agg(raw: str) -> list[tuple[str, str, str]]:
    """Parse -agg as key=value specs: column=, aggfunc=, optional as=.

    Several specs are separated by ';'. Several source columns in one spec share
    the same aggfunc: column='value,val_growth',aggfunc='sum'. as= needs a single column.
    Returns (source_col, output_name, aggfunc) rows.
    """
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit("-agg: expected key=value specs, e.g. column='value',aggfunc='sum',as='v'")
    if raw.startswith("{"):
        raise SystemExit(
            "-agg: use key=value specs, e.g. column='value',aggfunc='sum',as='v' "
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


_GROUP_X_KEYS = ("group", "v", "a", "dropna", "observed")


def parse_group_x_arg(raw: str | None) -> dict:
    """Parse -group_x as key=value tokens, e.g. group='species',v='body_mass_g',a='max'."""
    kwargs = parse_reshape_kwargs(raw, keys=_GROUP_X_KEYS, flag="-group_x")
    if "group" in kwargs and isinstance(kwargs["group"], str):
        kwargs["group"] = parse_columns(kwargs["group"])
    return kwargs


def _unquote_name(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    return raw


_LONG_KEYS = ("c", "v")
_WIDE_KEYS = ("c", "v", "a", "dropna")


def parse_reshape_kwargs(raw: str | None, *, keys: tuple[str, ...], flag: str) -> dict:
    """Parse -long/-wide/-group_x as key=value tokens, e.g. c='metric',v='reading',a='mean'."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    kwargs: dict = {}
    for token in _split_tokens(raw):
        if "=" not in token:
            raise SystemExit(f"{flag}: expected key=value tokens ({', '.join(keys)})")
        key, _, value = token.partition("=")
        key = key.strip()
        value = _unquote_name(value)
        if key not in keys:
            raise SystemExit(f"{flag}: unknown key {key!r}; expected {', '.join(keys)}")
        if not value:
            raise SystemExit(f"{flag}: {key}= needs a value")
        if key in kwargs:
            raise SystemExit(f"{flag}: {key}= given more than once")
        kwargs[key] = parse_bool_text(value) if key in ("dropna", "observed", "margins", "exact") else value
    return kwargs


def parse_long_arg(raw: str | None) -> dict:
    return parse_reshape_kwargs(raw, keys=_LONG_KEYS, flag="-long")


def parse_wide_arg(raw: str | None) -> dict:
    return parse_reshape_kwargs(raw, keys=_WIDE_KEYS, flag="-wide")


_CROSSTAB_KEYS = ("index", "columns", "values", "aggfunc", "normalize", "margins", "margins_name")
_CROSSTAB_NORMALIZE_VALUES = ("index", "columns", "all")


def parse_crosstab_arg(raw: str | None) -> dict:
    """Parse -crosstab as key=value tokens: index= (one or more comma-separated columns),
    columns= (single column, required), optional values=+aggfunc= (must be given together),
    normalize=index|columns|all, margins=true|false, margins_name= (requires margins=true).
    """
    kwargs = parse_reshape_kwargs(raw, keys=_CROSSTAB_KEYS, flag="-crosstab")
    if "index" not in kwargs or "columns" not in kwargs:
        raise SystemExit("-crosstab: expected index= and columns=")
    if ("values" in kwargs) != ("aggfunc" in kwargs):
        raise SystemExit("-crosstab: values= and aggfunc= must be given together")
    if "normalize" in kwargs and kwargs["normalize"] not in _CROSSTAB_NORMALIZE_VALUES:
        raise SystemExit(f"-crosstab: normalize= must be one of {', '.join(_CROSSTAB_NORMALIZE_VALUES)}")
    if "margins_name" in kwargs and not kwargs.get("margins"):
        raise SystemExit("-crosstab: margins_name= requires margins=true")
    return kwargs


_REPLACE_KEYS = ("c", "v", "exact")


def parse_value_map(raw: str) -> dict[str, str]:
    """Parse a -replace v= mapping like "old_a:new_a,old_b:new_b" into a dict."""
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise SystemExit(f"-replace: invalid v= mapping '{pair}'; expected old:new")
        old, new = pair.split(":", 1)
        mapping[old.strip()] = new.strip()
    if not mapping:
        raise SystemExit("-replace: v= needs at least one old:new pair")
    return mapping


def parse_replace_arg(raw: str) -> tuple[list[str] | None, dict[str, str], bool]:
    """Parse -replace as key=value tokens: c= (optional column scope), v= (required
    old:new mapping), exact= (optional bool, default true — whole-cell match vs
    substring match anywhere in the cell). Returns (cols_or_None, mapping, exact)."""
    kwargs = parse_reshape_kwargs(raw, keys=_REPLACE_KEYS, flag="-replace")
    if "v" not in kwargs:
        raise SystemExit("-replace: expected v='old:new,...'")
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
