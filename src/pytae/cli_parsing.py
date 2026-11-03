"""Parsing helpers for pytae CLI flag values (pure string parsing; no pandas/pipeline state)."""

from __future__ import annotations

import argparse
import ast
import difflib
import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from pytae._parsing import FilterNode, _parse_dict_literal, _parse_filter_node
from pytae._text import _is_enclosed_pair
from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name

SELECT_KEYS = ("dtype", "exclude_dtype", "contains", "startswith", "endswith", "regex")


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


def parse_distinct_spec(raw: str | None) -> tuple[list[str], str | bool]:
    """Parse -distinct SPEC into (cols, keep).

    Canonical syntax:
      - Bare flag / "": all columns, keep='first'
      - "col1,col2": subset of columns, keep='first'
      - "keep=last": all columns, keep='last'
      - "keep=false" or "keep=none": all columns, keep=False (drop all duplicates)
      - "col1,col2,keep=last": subset of columns, keep='last'
    """
    if not raw or not raw.strip():
        return [], "first"

    tokens = [t.strip() for t in _tokenize(raw, ",", track_brackets=True) if t.strip()]
    cols: list[str] = []
    keep: str | bool = "first"

    for token in tokens:
        if token.startswith("keep="):
            val = token[len("keep=") :].strip().strip("'\"").lower()
            if val in ("first", "last"):
                keep = val
            elif val in ("false", "none"):
                keep = False
            else:
                raise SystemExit(f"-distinct: invalid keep value '{val}'. Expected 'first', 'last', 'false', or 'none'")
        else:
            cols.append(_unquote_name(token))

    return cols, keep


def parse_count_spec(raw: str | None) -> tuple[list[str], bool, str]:
    """Parse -count SPEC into (cols, sort, name).

    Canonical syntax:
      - Bare flag / "": all columns (or grouped keys if after -by), sort=True, name='n'
      - "col1,col2": subset of columns, sort=True, name='n'
      - "col1,sort=false": subset of columns, sort=False, name='n'
      - "col1,name=total": subset of columns, sort=True, name='total'
      - "sort=false,name=count": all columns, sort=False, name='count'
    """
    if not raw or not raw.strip():
        return [], True, "n"

    tokens = [t.strip() for t in _tokenize(raw, ",", track_brackets=True) if t.strip()]
    cols: list[str] = []
    sort: bool = True
    name: str = "n"

    for token in tokens:
        if token.startswith("sort="):
            val = token[len("sort=") :].strip().strip("'\"").lower()
            if val in ("true", "1", "yes"):
                sort = True
            elif val in ("false", "0", "no"):
                sort = False
            else:
                raise SystemExit(f"-count: invalid sort value '{val}'. Expected 'true' or 'false'")
        elif token.startswith("name="):
            name = _unquote_name(token[len("name=") :].strip())
        else:
            cols.append(_unquote_name(token))

    return cols, sort, name


def parse_dropna_spec(
    raw: str | None,
    flag_name: str = "-dropna",
    available_cols: Sequence[str] | None = None,
) -> tuple[list[str], str | None, bool]:
    """Parse -dropna SPEC into (cols, how, drop_nans).

    Zero-Data-Loss Safety Defaults:
      - Bare flag / "": cols=[], how=None (defaults to 'all' to prevent accidental data loss), drop_nans=True
      - "col1,col2": cols=['col1', 'col2'], how=None (defaults to 'any' for targeted columns), drop_nans=True
      - "how=any" or "how=all": cols=[], how='any'/'all', drop_nans=True
      - "col1,col2,how=all": cols=['col1', 'col2'], how='all', drop_nans=True
      - "drop_nans=false": drop_nans=False
    """
    if not raw or not raw.strip():
        return [], None, True

    tokens = [t.strip() for t in _tokenize(raw, ",", track_brackets=True) if t.strip()]
    cols: list[str] = []
    how: str | None = None
    drop_nans: bool = True

    for token in tokens:
        if re.match(r"^how\s*[:=]\s*", token, re.IGNORECASE):
            val = re.sub(r"^how\s*[:=]\s*", "", token, flags=re.IGNORECASE).strip().strip("'\"").lower()
            if val in ("any", "all"):
                how = val
            else:
                raise SystemExit(f"{flag_name}: invalid how value '{val}'. Expected 'any' or 'all'")
        elif re.match(r"^(drop_nans|nans)\s*[:=]\s*", token, re.IGNORECASE):
            val = re.sub(r"^(drop_nans|nans)\s*[:=]\s*", "", token, flags=re.IGNORECASE).strip().strip("'\"").lower()
            drop_nans = val not in ("false", "0", "no")
        elif token.lower() in ("any", "all"):
            if available_cols and token in available_cols:
                cols.append(_unquote_name(token))
            else:
                how = token.lower()
        else:
            cols.append(_unquote_name(token))

    return cols, how, drop_nans


def parse_fillna_spec(
    raw: str | None,
    flag_name: str = "-fillna",
    available_cols: Sequence[str] | None = None,
) -> tuple[Any, list[str] | None, bool]:
    """Parse -fillna SPEC into (value, cols, nans).

    Syntax examples:
      - '0': value=0, cols=None, nans=True
      - '.': value='.', cols=None, nans=True
      - 'a:0, b:N/A': value={'a': 0, 'b': 'N/A'}, cols=None, nans=True
      - '0, a, b': value=0, cols=['a', 'b'], nans=True
      - '0, a, b, nans=false': value=0, cols=['a', 'b'], nans=False
    """
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit(f"{flag_name}: expected fill value, column mapping (col:val), or 'val, col1, col2'")

    tokens = [t.strip() for t in _tokenize(raw, ",", keep_quotes=True, track_brackets=True) if t.strip()]
    nans = True
    clean_tokens: list[str] = []
    for t in tokens:
        if re.match(r"^nans\s*[:=]\s*", t, re.IGNORECASE):
            val = re.sub(r"^nans\s*[:=]\s*", "", t, flags=re.IGNORECASE).strip().strip("'\"").lower()
            nans = val not in ("false", "0", "no")
        else:
            clean_tokens.append(t)

    if not clean_tokens:
        raise SystemExit(f"{flag_name}: expected fill value")

    # Check if this is a mapping: "a:0, b:N/A"
    is_mapping = all(":" in t or "=" in t for t in clean_tokens)
    if is_mapping:
        mapping: dict[str, Any] = {}
        for t in clean_tokens:
            sep = ":" if ":" in t else "="
            k, _, v = t.partition(sep)
            k_clean = _unquote_name(k.strip())
            v_strip = v.strip()
            try:
                v_val = ast.literal_eval(v_strip)
            except Exception:
                v_val = _unquote_name(v_strip)
            mapping[k_clean] = v_val
        return mapping, None, nans

    first_token = clean_tokens[0]
    try:
        val = ast.literal_eval(first_token)
    except Exception:
        val = _unquote_name(first_token)

    cols = [_unquote_name(c) for c in clean_tokens[1:]] if len(clean_tokens) > 1 else None
    return val, cols, nans


@dataclass
class SliceSpec:
    n: int | None = None
    prop: float | None = None
    with_ties: bool = False


def parse_head_limit(raw: Any, flag_name: str = "-head") -> SliceSpec:
    """Parse -head or -tail limit argument supporting:
    - 5 (row count, default 5)
    - '10%' (percentage proportion)
    - 0.1 (float proportion)
    - '3, ties=true' (row count with boundary ties)
    - '10%, with_ties=true' (proportion with boundary ties)
    """
    if isinstance(raw, SliceSpec):
        return raw
    if isinstance(raw, int):
        if raw <= 0:
            raise argparse.ArgumentTypeError(f"{flag_name}: row count must be > 0, got {raw}")
        return SliceSpec(n=raw, prop=None, with_ties=False)
    if isinstance(raw, float):
        if not (0 < raw <= 1):
            raise argparse.ArgumentTypeError(f"{flag_name}: proportion must be between 0 and 1, got {raw}")
        return SliceSpec(n=None, prop=raw, with_ties=False)

    s = str(raw).strip()
    if not s:
        return SliceSpec(n=5, prop=None, with_ties=False)

    tokens = [t.strip() for t in s.split(",") if t.strip()]
    n: int | None = None
    prop: float | None = None
    with_ties: bool = False

    for tok in tokens:
        lowered = tok.lower()
        if lowered in ("ties", "with_ties", "ties=true", "with_ties=true", "ties=1", "with_ties=1"):
            with_ties = True
        elif lowered in ("ties=false", "with_ties=false", "ties=0", "with_ties=0"):
            with_ties = False
        elif tok.startswith("n="):
            v_str = tok[2:].strip()
            try:
                val = int(v_str)
                if val <= 0:
                    raise ValueError
                n = val
            except ValueError:
                raise argparse.ArgumentTypeError(f"{flag_name}: invalid n value '{v_str}'; must be a positive integer")
        elif tok.startswith("prop="):
            v_str = tok[5:].strip()
            try:
                p_val = float(v_str.rstrip("%")) / 100.0 if v_str.endswith("%") else float(v_str)
                if not (0 < p_val <= 1):
                    raise ValueError
                prop = p_val
            except ValueError:
                raise argparse.ArgumentTypeError(
                    f"{flag_name}: invalid prop value '{v_str}'; must be a number between 0 and 1"
                )
        elif tok.endswith("%"):
            try:
                p_val = float(tok[:-1]) / 100.0
                if not (0 < p_val <= 1):
                    raise ValueError
                prop = p_val
            except ValueError:
                raise argparse.ArgumentTypeError(
                    f"{flag_name}: invalid percentage '{tok}'; must be between 0% and 100%"
                )
        else:
            try:
                if "." in tok:
                    p_val = float(tok)
                    if not (0 < p_val <= 1):
                        raise argparse.ArgumentTypeError(f"{flag_name}: proportion must be between 0 and 1, got {tok}")
                    prop = p_val
                else:
                    val = int(tok)
                    if val <= 0:
                        raise argparse.ArgumentTypeError(f"{flag_name}: must be > 0, got {val}")
                    n = val
            except ValueError:
                raise argparse.ArgumentTypeError(f"{flag_name}: unrecognized limit/argument '{tok}'")

    if n is not None and prop is not None:
        raise argparse.ArgumentTypeError(f"{flag_name}: specify either row count 'n' or proportion 'prop', not both")
    if n is None and prop is None:
        n = 5
    return SliceSpec(n=n, prop=prop, with_ties=with_ties)


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
            if key == "exclude":
                raise SystemExit(
                    "-select: 'exclude=' is retired in favor of '!' negation. "
                    "Use -select '!col' or -select '!col1,!col2' instead."
                )
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
            raise SystemExit(
                f"-select: '{token[0]}col' negation is retired in favor of '!col'. "
                f"Use -select '!{token[1:]}' instead."
            )
        if token.startswith("!"):
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
            raise SystemExit(
                f"invalid -rename mapping '{pair}'; use ':' (e.g. -rename 'old:new'). '=' is not supported."
            )
        else:
            raise SystemExit(f"invalid -rename mapping '{pair}'; expected old:new")
        old_clean = _unquote_name(old)
        new_clean = _unquote_name(new)
        if old_clean in mapping and mapping[old_clean] != new_clean:
            raise SystemExit(
                f"invalid -rename: conflicting mappings for '{old_clean}': '{mapping[old_clean]}' and '{new_clean}'"
            )
        mapping[old_clean] = new_clean
    return mapping


def expand_paths(patterns: str | list[str]) -> list[Path]:
    """Expand glob pattern(s) into matching paths, or wrap plain paths as-is."""
    items = [patterns] if isinstance(patterns, str) else list(patterns)
    results: list[Path] = []
    seen: set[Path] = set()
    for item in items:
        target = parse_input_target(str(item))
        clean_path_str = target["path"]
        p_literal = Path(clean_path_str)
        if p_literal.exists():
            if p_literal not in seen:
                results.append(p_literal)
                seen.add(p_literal)
        elif any(ch in clean_path_str for ch in "*?["):
            matches = sorted(Path(p) for p in glob.glob(clean_path_str))
            if not matches:
                raise SystemExit(f"no files matched pattern: {clean_path_str}")
            for m in matches:
                if m not in seen:
                    results.append(m)
                    seen.add(m)
        else:
            if p_literal not in seen:
                results.append(p_literal)
                seen.add(p_literal)
    return results


def parse_filter(raw: str) -> FilterNode | dict[str, Any]:
    """Parse -filter conditions like "col == 5 and other in ['a','b']", or dict literal '{"col": 5}'."""
    stripped = raw.strip()
    parsed_dict = _parse_dict_literal(stripped)
    if parsed_dict is not None:
        return parsed_dict
    return _parse_filter_node(stripped)


def parse_agg(raw: str):
    """Parse -agg: a name (mean), a comma list (mean,sum,count), or a col=aggfunc
    mapping (val = sum, n = count, total = v1:sum). Quote a mapping key only to protect a comma."""
    raw = (raw or "").strip()
    if not raw:
        return "sum"
    if raw.startswith("{") or (raw.startswith("[") and "=" not in raw):
        raise SystemExit("-agg: use a name (mean), a comma list (mean,sum), or a mapping (col = mean, total = count)")
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
                raise SystemExit(
                    f"-agg: invalid mapping entry '{entry}'; use '=' (e.g. -agg 'col = mean'). Colon ':' is not supported."
                )
            else:
                raise SystemExit(f"-agg: invalid mapping entry {entry!r}")
            if not key or not value:
                raise SystemExit(f"-agg: invalid mapping entry {entry!r}")
            if key in out:
                raise ValueError(f"agg(): output column name '{key}' is duplicated in aggregation specification")
            out[key] = value
        if dropna_flag is not None:
            out["__dropna__"] = dropna_flag
        return out
    if any(mapped):
        raise SystemExit("-agg: mix of names and col=aggfunc mappings; use one or the other")
    names = [_unquote_name(e) for e in entries]
    return names[0] if len(names) == 1 else names


_LONG_KEYS = ("cols", "id_vars", "c", "v", "r")
_WIDE_KEYS = ("r", "c", "v")


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
            if key in keys:
                if not value:
                    raise SystemExit(f"{flag}: {key}= needs a value")
                if key in kwargs:
                    raise SystemExit(f"{flag}: {key}= given more than once")
                current_key = key
                kwargs[key] = value
            elif current_key is not None:
                kwargs[current_key] = f"{kwargs[current_key]},{_unquote_name(token)}"
            else:
                raise SystemExit(f"{flag}: unknown key {key!r}; expected {', '.join(keys)}")
        else:
            if current_key is None:
                raise SystemExit(f"{flag}: expected key=value tokens ({', '.join(keys)})")
            kwargs[current_key] = f"{kwargs[current_key]},{_unquote_name(token)}"
    for key, value in list(kwargs.items()):
        if key in ("margins", "exact", "dropna"):
            kwargs[key] = parse_bool_text(value)
        elif key == "f_v":
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
    kwargs = parse_reshape_kwargs(raw, keys=_LONG_KEYS, flag="-long")
    if "r" in kwargs:
        if "id_vars" in kwargs:
            raise SystemExit("-long: cannot specify both r= and id_vars=")
        kwargs["id_vars"] = kwargs.pop("r")
    return kwargs


def parse_wide_arg(raw: str | None) -> dict:
    return parse_reshape_kwargs(raw, keys=_WIDE_KEYS, flag="-wide")


_PIVOT_KEYS = ("r", "c", "v", "a", "dropna", "f_v")


def parse_pivot_arg(raw: str | None) -> dict:
    return parse_reshape_kwargs(raw, keys=_PIVOT_KEYS, flag="-pivot")


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


def parse_sample_arg(raw: Any) -> tuple[int | None, float | None]:
    """Parse -sample argument: integer count (e.g. 5, 100), float fraction (e.g. 0.05), or percentage (e.g. 5%).

    Returns (count, frac) where exactly one is non-None.
    """
    if raw is None or raw == "" or raw == (5, None) or raw == 5:
        return (5, None)
    if isinstance(raw, tuple) and len(raw) == 2:
        return raw  # already parsed tuple
    raw_str = str(raw).strip()
    if raw_str.endswith("%"):
        try:
            pct = float(raw_str[:-1].strip())
        except ValueError:
            raise argparse.ArgumentTypeError(f"invalid percentage for -sample: {raw!r}") from None
        if not (0 < pct <= 100):
            raise argparse.ArgumentTypeError(f"percentage must be > 0 and <= 100, got {pct}%")
        return (None, pct / 100.0)
    try:
        val = float(raw_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid sample size or fraction: {raw!r}") from None

    if "." in raw_str:
        if not (0 < val <= 1):
            raise argparse.ArgumentTypeError(f"fraction must be > 0 and <= 1, got {val}")
        return (None, val)

    n = int(val)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"sample count must be > 0, got {n}")
    return (n, None)


def parse_fraction(raw: Any) -> float:
    """Parse -frac (deprecated)."""
    raise argparse.ArgumentTypeError(
        "-frac is deprecated and removed; use '-sample <val>' (e.g. -sample 0.05 or -sample 5%)"
    )


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
        raise SystemExit('-clean_columns: expected at least one key, e.g. "strip" or "case=lower"')
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


def normalize_git_bash_path(path: str, *, _force_nt: bool = False) -> str:
    """Normalize Git Bash / MSYS POSIX-style drive mounts (e.g. '/c/Users/...'), WSL mounts ('/mnt/c/...'), and Cygwin mounts ('/cygdrive/c/...') to Windows paths ('C:/Users/...').

    On Windows (os.name == 'nt') or when _force_nt is True:
    If the path begins with '/<drive>/', '/mnt/<drive>/', or '/cygdrive/<drive>/' and does not exist as-is, translate to 'C:/...'.
    On non-Windows platforms (Linux/macOS), the path is returned untouched unless forced for testing.
    Surrounding quotes are preserved.
    """
    import os

    if not path or not isinstance(path, str):
        return path

    quote_char = ""
    stripped = path.strip()
    if len(stripped) >= 2 and stripped[0] in ('"', "'") and stripped[-1] == stripped[0]:
        quote_char = stripped[0]
        unquoted = stripped[1:-1]
    else:
        unquoted = stripped

    if os.name == "nt" or _force_nt:
        # WSL: /mnt/c/...
        m_wsl = re.match(r"^/mnt/([a-zA-Z])(/.*)$", unquoted)
        if m_wsl:
            if not _force_nt and Path(unquoted).exists():
                return path
            drive = m_wsl.group(1).upper()
            converted = f"{drive}:{m_wsl.group(2)}"
            return f"{quote_char}{converted}{quote_char}" if quote_char else converted

        # Cygwin: /cygdrive/c/...
        m_cyg = re.match(r"^/cygdrive/([a-zA-Z])(/.*)$", unquoted)
        if m_cyg:
            if not _force_nt and Path(unquoted).exists():
                return path
            drive = m_cyg.group(1).upper()
            converted = f"{drive}:{m_cyg.group(2)}"
            return f"{quote_char}{converted}{quote_char}" if quote_char else converted

        # Git Bash / MSYS: /c/...
        m = re.match(r"^/([a-zA-Z])(/.*)$", unquoted)
        if m:
            if not _force_nt and Path(unquoted).exists():
                return path
            drive = m.group(1).upper()
            converted = f"{drive}:{m.group(2)}"
            return f"{quote_char}{converted}{quote_char}" if quote_char else converted

    return path


def normalize_session_path(
    raw_path: str | Path,
    *,
    base_dir: Path | None = None,
    _force_nt: bool = False,
) -> Path:
    """Normalize and resolve any session path across Windows (CMD, PowerShell, Git Bash, WSL, Cygwin) and POSIX.

    Supported formats:
      - Windows backslash paths: r'C:\\Users\\...\\rwa_analysis'
      - Windows forward-slash paths: 'C:/Users/.../rwa_analysis'
      - Git Bash / MSYS paths: '/c/Users/.../rwa_analysis' -> 'C:/Users/.../rwa_analysis'
      - WSL paths: '/mnt/c/Users/.../rwa_analysis' -> 'C:/Users/.../rwa_analysis'
      - Cygwin paths: '/cygdrive/c/Users/.../rwa_analysis' -> 'C:/Users/.../rwa_analysis'
      - file:// URLs: 'file:///C:/Users/...' -> 'C:/Users/...'
      - Tilde home expansion: '~/...' -> expands to user home
      - Relative paths: './rwa_analysis', r'.\\rwa_analysis', 'rwa_analysis'
      - Strips wrapping quotes and trailing slashes.
    """
    if isinstance(raw_path, Path):
        return raw_path.expanduser().resolve()

    clean = str(raw_path).strip()
    while len(clean) >= 2 and clean[0] in ('"', "'") and clean[-1] == clean[0]:
        clean = clean[1:-1].strip()

    if clean.startswith("file:///"):
        clean = clean[8:]
    elif clean.startswith("file://"):
        clean = clean[7:]

    # Strip trailing slashes, preserving root slashes like "/" or "C:\"
    if len(clean) > 3 and clean.endswith(("/", "\\")):
        clean = clean.rstrip("/\\")

    clean = normalize_git_bash_path(clean, _force_nt=_force_nt)
    if os.name != "nt" and "\\" in clean and not Path(clean).exists():
        clean = clean.replace("\\", "/")
    p = Path(clean).expanduser()

    if p.is_absolute():
        return p.resolve()

    # Relative path resolution: check CWD first
    cwd_candidate = (Path.cwd() / p).resolve()
    if cwd_candidate.exists() and cwd_candidate.is_dir():
        return cwd_candidate

    # Check base_dir fallback (e.g. configured sessions_dir)
    if base_dir is not None:
        base_candidate = (base_dir / p).resolve()
        if base_candidate.exists() and base_candidate.is_dir():
            return base_candidate

    return cwd_candidate


def parse_input_target(token: str) -> dict[str, Any]:
    """Parse a positional input target into (alias, path_str).

    Supported forms:
      - 'alias=path.ext' -> alias='alias', path='path.ext'
      - 'path.ext'       -> alias=stem,    path='path.ext'

    Note:
      Colon sheet syntax (e.g. 'path.xlsx:Sheet1') is strictly not supported.
      Sheet names must be specified via -opts (e.g. -opts "sheet=Sheet1").
    """
    token = token.strip()
    alias: str | None = None
    rest = token

    if "=" in token:
        lhs, _, rhs = token.partition("=")
        alias = lhs.strip()
        rest = rhs.strip()

    rest = normalize_git_bash_path(rest)

    # Guard against mistaken colon sheet syntax (e.g. data.xlsx:Sheet1)
    if ":" in rest and not rest.startswith("sample:"):
        p_part, _, s_part = rest.rpartition(":")
        # Check if p_part is not just a Windows drive letter (e.g. 'C' or 'D')
        if not (len(p_part) == 1 and p_part.isalpha()):
            low_p = p_part.lower()
            if any(low_p.endswith(ext) for ext in (".xlsx", ".xls", ".xlsm", ".xlsb")):
                suggest_alias = f"{alias}:" if alias else ""
                raise ValueError(
                    f"colon sheet syntax '{token}' is not supported; specify sheet via -opts "
                    f'(e.g. -opts "{suggest_alias}sheet={s_part}")'
                )

    path_str = rest.strip().strip("\"'")
    if not alias:
        if path_str.startswith("sample:"):
            alias = path_str[7:].removesuffix(".parquet")
        else:
            alias = Path(path_str).stem

    return {"alias": alias, "path": path_str}


def parse_reader_opts(raw: str | None) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Parse -opts string into global options and per-alias targeted overrides.

    Example:
      'skiprows=1, cust:skiprows=3, usecols="A:E"'
      Returns:
        global_opts: {'skiprows': 1, 'usecols': 'A:E'}
        targeted_opts: {'cust': {'skiprows': 3}}
    """
    if not raw or not raw.strip():
        return {}, {}
    global_opts: dict[str, Any] = {}
    targeted_opts: dict[str, dict[str, Any]] = {}

    import ast

    def _eval(val: str) -> Any:
        v = val.strip()
        if not v:
            return ""
        try:
            return ast.literal_eval(v)
        except Exception:
            low = v.lower()
            if low == "true":
                return True
            if low == "false":
                return False
            if low in ("none", "null"):
                return None
            return v.strip("\"'")

    tokens = _split_tokens(raw, ",")
    for tok in tokens:
        if "=" not in tok:
            continue
        key, _, val = tok.partition("=")
        key = key.strip()
        parsed_val = _eval(val)
        if ":" in key:
            alias, _, opt_name = key.partition(":")
            alias = alias.strip()
            opt_name = opt_name.strip()
            if opt_name == "sheet":
                opt_name = "sheet_name"
            targeted_opts.setdefault(alias, {})[opt_name] = parsed_val
        else:
            if key == "sheet":
                key = "sheet_name"
            global_opts[key] = parsed_val

    return global_opts, targeted_opts


_JOIN_KEYS = ("left", "right", "on", "how", "validate")


def parse_join_on(raw: str) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """Parse -join's on= value: shared column names (comma list) when names match on
    both sides, or 'left:right' pairs when they differ between sides. Quote the whole
    on= value if it has more than one column/pair (protects the inner commas), e.g.
    on='col a:cola,colb:colb'. Returns (on_cols, left_cols, right_cols) — on_cols is
    set XOR (left_cols, right_cols) are set.
    """
    pairs = [p.strip() for p in raw.split(",") if p.strip()]
    if not pairs:
        raise SystemExit("-join: on= needs at least one column (or left:right pair)")
    has_colon = [":" in p for p in pairs]
    if any(has_colon) and not all(has_colon):
        raise SystemExit("-join: on= mixes plain columns and left:right pairs; use one style")
    if all(has_colon):
        left_cols, right_cols = [], []
        for pair in pairs:
            left, _, right = pair.partition(":")
            left_cols.append(left.strip())
            right_cols.append(right.strip())
        return None, left_cols, right_cols
    return pairs, None, None


def parse_join_arg(raw: str) -> dict:
    """Parse -join as key=value tokens: left=/right= (optional table aliases, or the
    literal 'data' to reference the pipeline's current result so far; when omitted,
    left/right default to the first two input tables), on= (required; shared column
    name(s), or left:right pairs if they differ between sides), how= (optional,
    default 'inner', passed to Polars join()), validate= (optional, passed
    to Polars join()).
    """
    kwargs = parse_reshape_kwargs(raw, keys=_JOIN_KEYS, flag="-join")
    how = kwargs.get("how", "inner")
    if how != "cross" and "on" not in kwargs:
        raise SystemExit("-join: missing required key 'on'")
    if how == "cross":
        if "on" in kwargs:
            raise SystemExit("-join: on= cannot be used with how=cross (cross joins don't take on=)")
        on_cols, left_cols, right_cols = None, None, None
    else:
        on_cols, left_cols, right_cols = parse_join_on(kwargs["on"])
    return {
        "left": kwargs.get("left"),
        "right": kwargs.get("right"),
        "on": on_cols,
        "left_on": left_cols,
        "right_on": right_cols,
        "how": how,
        "validate": kwargs.get("validate"),
    }


_CONCAT_KEYS = ("frames",)


def parse_concat_arg(raw: str | None) -> dict:
    """Parse -concat as optional comma-separated list of table aliases (or 'data' for
    the pipeline's current result). When omitted, concatenates all input tables in order.
    """
    if not raw or not raw.strip():
        return {"frames": None}
    raw = raw.strip()
    if raw.startswith("frames="):
        kwargs = parse_reshape_kwargs(raw, keys=_CONCAT_KEYS, flag="-concat")
        val = kwargs.get("frames", "")
    else:
        val = raw.strip("\"' ")
    names = [n.strip() for n in val.split(",") if n.strip()]
    if names and len(names) < 2:
        raise SystemExit("-concat: frames needs at least two names")
    return {"frames": names if names else None}


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


def normalize_sql(query: str) -> str:
    """Normalize SQL queries for CLI -sql: resolve @file references, convert backticks
    `col` and brackets [col] to double-quoted identifiers "col" for standard SQL."""
    q = query.strip()
    if (q.startswith("'") and q.endswith("'")) or (q.startswith('"') and q.endswith('"')):
        q = q[1:-1].strip()
    if q.startswith("@"):
        path = q[1:].strip()
        if (path.startswith("'") and path.endswith("'")) or (path.startswith('"') and path.endswith('"')):
            path = path[1:-1].strip()
        from pathlib import Path

        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"sql: query file not found: '{path}'")
        q = file_path.read_text(encoding="utf-8").strip()
    out_chars: list[str] = []
    i, n = 0, len(q)
    quote = None
    while i < n:
        ch = q[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == quote:
                if i + 1 < n and q[i + 1] == quote:
                    out_chars.append(q[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch == "`":
            j = q.find("`", i + 1)
            if j != -1:
                ident = q[i + 1 : j]
                out_chars.append(f'"{ident}"')
                i = j + 1
                continue
        if ch == "[":
            j = q.find("]", i + 1)
            if j != -1:
                inner = q[i + 1 : j]
                is_index = i > 0 and (q[i - 1].isalnum() or q[i - 1] in "_)]")
                is_list_literal = "," in inner or "'" in inner or '"' in inner
                has_ident = any(c.isalpha() or c == "_" for c in inner)
                all_valid = all(c.isalnum() or c in " _-" for c in inner)
                if not is_index and not is_list_literal and has_ident and all_valid:
                    out_chars.append(f'"{inner}"')
                    i = j + 1
                    continue

        out_chars.append(ch)
        i += 1
    return "".join(out_chars)


def parse_bar_spec(raw: str | None) -> dict[str, Any]:
    """Parse -bar specification: e.g. bare (None/""), "col", "cat:val",
    "cat:val,limit=(min,max),pct=true,width=30", "limit=(0,5000),pct=true"."""
    result: dict[str, Any] = {
        "cat": None,
        "val": None,
        "limit": None,
        "pct": False,
        "width": 20,
    }
    if not raw or not raw.strip():
        return result

    tokens = _tokenize(raw.strip(), ",", keep_quotes=True, track_brackets=True)
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            key, _, val_str = token.partition("=")
            key = key.strip().lower()
            val_str = val_str.strip()
            if key == "limit":
                v = val_str.strip("()[]")
                lim_parts = [p.strip() for p in (v.split(":") if ":" in v else v.split(",")) if p.strip()]
                if len(lim_parts) == 2:
                    try:
                        result["limit"] = (float(lim_parts[0]), float(lim_parts[1]))
                    except ValueError:
                        raise SystemExit(f"-bar: invalid limit='{val_str}'; expected (min, max)")
                else:
                    raise SystemExit(f"-bar: invalid limit='{val_str}'; expected (min, max)")
            elif key == "pct":
                result["pct"] = parse_bool_text(val_str)
            elif key == "width":
                try:
                    result["width"] = int(val_str)
                except ValueError:
                    raise SystemExit(f"-bar: invalid width='{val_str}'; expected positive integer")
            elif key in ("val", "value"):
                result["val"] = _unquote_name(val_str)
            elif key in ("cat", "category"):
                result["cat"] = _unquote_name(val_str)
            else:
                raise SystemExit(f"-bar: unrecognized option '{key}'")
        else:
            if ":" in token:
                cp, _, vp = token.partition(":")
                result["cat"] = _unquote_name(cp.strip())
                result["val"] = _unquote_name(vp.strip())
            else:
                result["val"] = _unquote_name(token)
    return result


def parse_scatter_spec(raw: str | None) -> dict[str, Any]:
    """Parse -scatter specification: e.g. bare (None/""), "x:y",
    "x:y,width=60,height=20,limit_x=(min,max),limit_y=(min,max)"."""
    result: dict[str, Any] = {
        "x": None,
        "y": None,
        "width": 50,
        "height": 15,
        "limit_x": None,
        "limit_y": None,
    }
    if not raw or not raw.strip():
        return result

    tokens = _tokenize(raw.strip(), ",", keep_quotes=True, track_brackets=True)
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            key, _, val_str = token.partition("=")
            key = key.strip().lower()
            val_str = val_str.strip()
            if key in ("limit_x", "xlim"):
                v = val_str.strip("()[]")
                lim_parts = [p.strip() for p in (v.split(":") if ":" in v else v.split(",")) if p.strip()]
                if len(lim_parts) == 2:
                    try:
                        result["limit_x"] = (float(lim_parts[0]), float(lim_parts[1]))
                    except ValueError:
                        raise SystemExit(f"-scatter: invalid limit_x='{val_str}'; expected (min, max)")
                else:
                    raise SystemExit(f"-scatter: invalid limit_x='{val_str}'; expected (min, max)")
            elif key in ("limit_y", "ylim"):
                v = val_str.strip("()[]")
                lim_parts = [p.strip() for p in (v.split(":") if ":" in v else v.split(",")) if p.strip()]
                if len(lim_parts) == 2:
                    try:
                        result["limit_y"] = (float(lim_parts[0]), float(lim_parts[1]))
                    except ValueError:
                        raise SystemExit(f"-scatter: invalid limit_y='{val_str}'; expected (min, max)")
                else:
                    raise SystemExit(f"-scatter: invalid limit_y='{val_str}'; expected (min, max)")
            elif key == "width":
                try:
                    result["width"] = int(val_str)
                except ValueError:
                    raise SystemExit(f"-scatter: invalid width='{val_str}'; expected positive integer")
            elif key == "height":
                try:
                    result["height"] = int(val_str)
                except ValueError:
                    raise SystemExit(f"-scatter: invalid height='{val_str}'; expected positive integer")
            elif key == "x":
                result["x"] = _unquote_name(val_str)
            elif key == "y":
                result["y"] = _unquote_name(val_str)
            else:
                raise SystemExit(f"-scatter: unrecognized option '{key}'")
        else:
            if ":" in token:
                xp, _, yp = token.partition(":")
                result["x"] = _unquote_name(xp.strip())
                result["y"] = _unquote_name(yp.strip())
            else:
                result["x"] = _unquote_name(token)
    return result


def parse_corr_spec(raw: str | None) -> dict[str, Any]:
    """Parse -corr specification: e.g. bare (None/""), "pairs", "target=col",
    "method=spearman", "pairs,method=spearman"."""
    result: dict[str, Any] = {
        "target": None,
        "pairs": False,
        "method": "pearson",
    }
    if not raw or not raw.strip():
        return result

    tokens = _tokenize(raw.strip(), ",", keep_quotes=True, track_brackets=True)
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            key, _, val_str = token.partition("=")
            key = key.strip().lower()
            val_str = val_str.strip()
            if key in ("target", "y"):
                result["target"] = _unquote_name(val_str)
            elif key == "method":
                m = val_str.lower().strip()
                if m not in ("pearson", "spearman"):
                    raise SystemExit(f"-corr: invalid method '{val_str}'; expected 'pearson' or 'spearman'")
                result["method"] = m
            elif key == "pairs":
                result["pairs"] = parse_bool_text(val_str)
            else:
                raise SystemExit(f"-corr: unrecognized option '{key}'")
        else:
            t_lower = token.lower()
            if t_lower == "pairs":
                result["pairs"] = True
            elif t_lower in ("pearson", "spearman"):
                result["method"] = t_lower
            else:
                result["target"] = _unquote_name(token)
    return result
