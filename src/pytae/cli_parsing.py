"""Parsing helpers for pytae CLI flag values (pure string parsing; no pandas/pipeline state)."""

from __future__ import annotations

import argparse
import ast
import difflib
import glob
import re
from pathlib import Path

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name

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


def parse_sort_by(raw: str) -> tuple[list[str], str]:
    """Parse -sort_by SPEC: a comma-separated column list, optionally ending with
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


def _split_tokens(raw: str, sep: str = ",") -> list[str]:
    """Split on sep, respecting single or double quotes."""
    return [t for t in _tokenize(raw, sep) if t]


def _split_groups(raw: str, sep: str = ";") -> list[str]:
    """Split on sep but keep quote characters so inner comma-split still sees them."""
    return [t for t in _tokenize(raw, sep, keep_quotes=True) if t]


def parse_drop_spec(raw: str) -> list[str]:
    """Parse -drop into exact column names.

    Names only: comma-separated, same quoting as -select names (a space is not
    a separator). key=value tokens and select matchers (dtype=/contains=/regex=/
    slices) are rejected — those stay on -select.
    """
    tokens = _split_tokens(raw)
    if not tokens:
        raise SystemExit("-drop: expected column names")
    names: list[str] = []
    for token in tokens:
        if "=" in token:
            raise SystemExit(
                "-drop: only column names; use -select for dtype=/contains=/regex=/exclude_dtype="
            )
        names.append(token)
    return names


def parse_select_spec(raw: str) -> tuple[list[str], dict]:
    """Parse -select into positional names/slices and select() kwargs.

    Tokens without '=' are column names or start:end slices. Tokens like
    dtype=numeric / contains=bill / regex=^flip become kwargs. Repeated keys
    become a list. Union of all tokens, matching pt.select().
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
    """Parse a rename mapping like "old_a=new_a,old_b=new_b" into a dict.
    Quoting either side (e.g. "'old a'='new a'") is optional and stripped if present—
    plain old_a=new_a already handles spaces, quoting just needs to not break things."""
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            old, new = pair.split("=", 1)
        elif ":" in pair:
            raise SystemExit(f"invalid -rename mapping '{pair}'; use '=' (e.g. -rename 'old=new'). Colon ':' is not supported.")
        else:
            raise SystemExit(f"invalid -rename mapping '{pair}'; expected old=new")
        mapping[_unquote_name(old)] = _unquote_name(new)
    return mapping


def expand_paths(pattern: str) -> list[Path]:
    """Expand a glob pattern (e.g. "data/*.parquet") into matching paths, or wrap a plain path as-is."""
    if any(ch in pattern for ch in "*?["):
        matches = sorted(Path(p) for p in glob.glob(pattern))
        if not matches:
            raise SystemExit(f"no files matched pattern: {pattern}")
        return matches
    return [Path(pattern)]


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
            entries.append((col, f"('{op}', {val})"))
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


def parse_qry(raw: str) -> dict:
    """Parse -qry conditions like "col = ('>', 5), other = ['a','b']"; wrapping {} and
    quotes around column names are both optional (matching -select), e.g.
    "sex='Male'" == "'sex'='Male'". Prefix operators (e.g. "col = > 5" or "col > 5") and bare string
    values (e.g. "species = Adelie") are also accepted."""
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        stripped = stripped[1:-1]
    conditions: dict = {}
    for key_raw, value_raw in _split_qry_entries(stripped):
        key = _unquote_name(key_raw)
        if not key:
            raise SystemExit("invalid --qry conditions: empty column name")
        if not value_raw:
            raise SystemExit(f"invalid --qry conditions: '{key}' has no value")
        
        op_match = re.match(r"^(>=|<=|!=|==|>|<)\s*(.+)$", value_raw)
        if op_match:
            op = op_match.group(1)
            sub_raw = op_match.group(2).strip()
            try:
                sub_val = ast.literal_eval(sub_raw)
            except (ValueError, SyntaxError):
                sub_val = _unquote_name(sub_raw)
            conditions[key] = (op, sub_val)
            continue

        try:
            value = ast.literal_eval(value_raw)
        except (ValueError, SyntaxError) as exc:
            raise SystemExit(
                f"invalid --qry conditions: value for '{key}' ('{value_raw}') must be quoted "
                "(e.g. 'Male') or a valid literal (number/tuple/list)"
            ) from exc
        conditions[key] = value
    if not conditions:
        raise SystemExit("-qry expects keyword entries, e.g. \"col = ('>', 5)\" or \"col > 5\" (quotes around column name optional)")
    return conditions


def parse_agg(raw: str):
    """Parse -agg_df: a name (mean), a comma list (mean,sum,n), or a col=aggfunc
    mapping (body_mass_g = mean, n = n). Quote a mapping key only to protect a comma."""
    raw = (raw or "").strip()
    if not raw:
        return "sum"
    if raw[0] in "{[":
        raise SystemExit(
            "-agg_df: use a name (mean), a comma list (mean,sum), or a mapping "
            "(col: mean, n: n)"
        )
    entries = [e for e in _tokenize(raw, ",", keep_quotes=True) if e]
    if not entries:
        raise SystemExit("-agg_df: expected a name, a comma list, or a mapping")

    def _is_mapping(entry: str) -> bool:
        return len(_tokenize(entry, "=", keep_quotes=True)) >= 2 or len(_tokenize(entry, ":", keep_quotes=True)) >= 2

    mapped = [_is_mapping(e) for e in entries]
    if all(mapped):
        out: dict[str, str] = {}
        for entry in entries:
            if "=" in entry:
                parts = _tokenize(entry, "=", keep_quotes=True)
                key = _unquote_name(parts[0])
                value = _unquote_name("=".join(parts[1:]))
            elif ":" in entry:
                raise SystemExit(f"-agg_df: invalid mapping entry '{entry}'; use '=' (e.g. -agg_df 'col = mean'). Colon ':' is not supported.")
            else:
                raise SystemExit(f"-agg_df: invalid mapping entry {entry!r}")
            if not key or not value:
                raise SystemExit(f"-agg_df: invalid mapping entry {entry!r}")
            out[key] = value
        return out
    if any(mapped):
        raise SystemExit(
            "-agg_df: mix of names and col=aggfunc mappings; use one or the other"
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


_GROUP_X_KEYS = ("group", "v", "a")


def parse_group_x_arg(raw: str | None) -> dict:
    """Parse -group_x as key=value tokens, e.g. group=species,v=body_mass_g,a=max."""
    kwargs = parse_reshape_kwargs(raw, keys=_GROUP_X_KEYS, flag="-group_x")
    if "group" in kwargs and isinstance(kwargs["group"], str):
        kwargs["group"] = parse_columns(kwargs["group"])
    return kwargs




_LONG_KEYS = ("c", "v")
_WIDE_KEYS = ("c", "v", "a")


def parse_reshape_kwargs(raw: str | None, *, keys: tuple[str, ...], flag: str) -> dict:
    """Parse -long/-wide/-group_x as key=value tokens, e.g. c=metric,v=reading,a=mean.
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
        kwargs[key] = parse_bool_text(value) if key in ("margins", "exact") else value
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
    """Parse a -replace_values v= mapping like "old_a=new_a,old_b=new_b" into a dict."""
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            old, new = pair.split("=", 1)
        elif ":" in pair:
            raise SystemExit(f"-replace_values: invalid v= mapping '{pair}'; use '=' (expected old=new). Colon ':' is not supported.")
        else:
            raise SystemExit(f"-replace_values: invalid v= mapping '{pair}'; expected old=new")
        mapping[_unquote_name(old)] = _unquote_name(new)
    if not mapping:
        raise SystemExit("-replace_values: v= needs at least one old=new pair")
    return mapping


def parse_replace_values_arg(raw: str) -> tuple[list[str] | None, dict[str, str], bool]:
    """Parse -replace_values as key=value tokens: c= (optional column scope), v= (required
    old=new mapping), exact= (optional bool, default true — whole-cell match vs
    substring match anywhere in the cell). Returns (cols_or_None, mapping, exact)."""
    kwargs = parse_reshape_kwargs(raw, keys=_REPLACE_KEYS, flag="-replace_values")
    if "v" not in kwargs:
        raise SystemExit("-replace_values: expected v='old=new,...'")
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
