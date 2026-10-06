"""Row-ordering and group-aware top-N row slicing verbs: arrange, slice_max, slice_min."""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from typing import Any

import pandas as pd

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name


def _parse_col_order(
    token: str,
    default_asc: bool = True,
    available_cols: set[str] | None = None,
) -> tuple[str, bool]:
    """Parse a single column token, e.g. 'species', 'body_mass_g desc', '-body_mass_g',
    '[annual salary] desc', '-[annual salary]'.
    """
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


def arrange(
    df: pd.DataFrame,
    *cols: Any,
    ascending: bool | Sequence[bool] | None = None,
    na_last: bool = True,
) -> pd.DataFrame:
    """Order rows by one or more columns, supporting inline direction ('desc', 'asc', '-col')
    and brackets for spaced column names ('[col with space] desc').

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    *cols : str | Sequence[str]
        Column specifications. Can be passed as separate arguments
        (e.g. ``"species", "body_mass_g desc"``), a single comma-separated string
        (e.g. ``"species, body_mass_g desc"``), or with bracket notation for spaces
        (e.g. ``"[department code], [annual salary] desc"``). Leading '-' signifies descending.
    ascending : bool | Sequence[bool] | None, default None
        Global ascending direction override for columns that do not specify an inline direction.
    na_last : bool, default True
        If True, missing values (NaN) appear at the end; if False, at the beginning.

    Returns
    -------
    pd.DataFrame
        Sorted DataFrame with a clean standard RangeIndex.
    """
    if not cols:
        return df.copy().reset_index(drop=True)

    available = list(df.columns)
    available_set = set(available)

    sort_cols, sort_asc = _extract_arrange_specs(cols, ascending, available_set)
    if not sort_cols:
        return df.copy().reset_index(drop=True)

    unknown = [c for c in sort_cols if c not in available_set]
    if unknown:
        hints = []
        for u in unknown:
            matches = difflib.get_close_matches(str(u), [str(c) for c in available], n=1, cutoff=0.6)
            if matches:
                hints.append(f"'{u}' (did you mean '{matches[0]}')")
            else:
                hints.append(f"'{u}'")
        raise KeyError(
            f"arrange: column(s) {', '.join(hints)} not found in DataFrame. Available columns: {available}"
        )

    na_position = "last" if na_last else "first"
    sorted_df = df.sort_values(by=sort_cols, ascending=sort_asc, na_position=na_position)
    return sorted_df.reset_index(drop=True)


def slice_max(
    df: pd.DataFrame,
    col: str,
    n: int = 1,
    *,
    by: str | Sequence[str] | None = None,
    with_ties: bool = False,
    na_last: bool = True,
) -> pd.DataFrame:
    """Select the rows with the largest values of a column, optionally grouped by one or more columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    col : str
        The column to rank by.
    n : int, default 1
        Number of rows to return (per group if `by` is specified).
    by : str | Sequence[str] | None, default None
        Column(s) to group by before slicing.
    with_ties : bool, default False
        If True, keeps all rows tied for the n-th value.
    na_last : bool, default True
        If True, missing values are excluded from the top-N ranking.

    Returns
    -------
    pd.DataFrame
        Sliced DataFrame with all original columns and a clean RangeIndex.
    """
    return _slice_ordered(df, col, n=n, by=by, ascending=False, with_ties=with_ties, na_last=na_last, verb="slice_max")


def slice_min(
    df: pd.DataFrame,
    col: str,
    n: int = 1,
    *,
    by: str | Sequence[str] | None = None,
    with_ties: bool = False,
    na_last: bool = True,
) -> pd.DataFrame:
    """Select the rows with the smallest values of a column, optionally grouped by one or more columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    col : str
        The column to rank by.
    n : int, default 1
        Number of rows to return (per group if `by` is specified).
    by : str | Sequence[str] | None, default None
        Column(s) to group by before slicing.
    with_ties : bool, default False
        If True, keeps all rows tied for the n-th value.
    na_last : bool, default True
        If True, missing values are excluded from the bottom-N ranking.

    Returns
    -------
    pd.DataFrame
        Sliced DataFrame with all original columns and a clean RangeIndex.
    """
    return _slice_ordered(df, col, n=n, by=by, ascending=True, with_ties=with_ties, na_last=na_last, verb="slice_min")


def _slice_ordered(
    df: pd.DataFrame,
    col: str,
    n: int,
    *,
    by: str | Sequence[str] | None,
    ascending: bool,
    with_ties: bool,
    na_last: bool,
    verb: str,
) -> pd.DataFrame:
    clean_col = _unquote_name(col.strip())
    if clean_col not in df.columns:
        matches = difflib.get_close_matches(str(clean_col), [str(c) for c in df.columns], n=1, cutoff=0.6)
        hint = f" (did you mean '{matches[0]}'?)" if matches else ""
        raise KeyError(f"{verb}: column '{clean_col}' not found in DataFrame{hint}. Available columns: {list(df.columns)}")

    if n <= 0:
        return df.iloc[0:0].copy()

    by_cols: list[str] = []
    if by is not None:
        if isinstance(by, str):
            by_cols = [_unquote_name(c.strip()) for c in _tokenize(by, ",", track_brackets=True) if c.strip()]
        else:
            by_cols = [_unquote_name(str(c).strip()) for c in by]

        unknown_by = [c for c in by_cols if c not in df.columns]
        if unknown_by:
            raise KeyError(f"{verb}: grouping column(s) {unknown_by} not found in DataFrame. Available columns: {list(df.columns)}")

    na_position = "last" if na_last else "first"

    if with_ties:
        if by_cols:
            ranks = df.groupby(by_cols, observed=False)[clean_col].rank(
                method="min", ascending=ascending, na_option="bottom" if na_last else "top"
            )
            filtered = df[ranks <= n]
            sort_order = by_cols + [clean_col]
            sort_asc = [True] * len(by_cols) + [ascending]
            res = filtered.sort_values(by=sort_order, ascending=sort_asc, na_position=na_position)
        else:
            ranks = df[clean_col].rank(
                method="min", ascending=ascending, na_option="bottom" if na_last else "top"
            )
            filtered = df[ranks <= n]
            res = filtered.sort_values(by=clean_col, ascending=ascending, na_position=na_position)
        return res.reset_index(drop=True)

    if by_cols:
        sort_order = by_cols + [clean_col]
        sort_asc = [True] * len(by_cols) + [ascending]
        sorted_df = df.sort_values(by=sort_order, ascending=sort_asc, na_position=na_position)
        res = sorted_df.groupby(by_cols, as_index=False, observed=False, sort=False).head(n)
        return res.reset_index(drop=True)
    else:
        sorted_df = df.sort_values(by=clean_col, ascending=ascending, na_position=na_position)
        res = sorted_df.head(n)
        return res.reset_index(drop=True)
