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


def pick(
    df: pd.DataFrame,
    col: str,
    n: int | None = None,
    prop: float | None = None,
    order: str = "max",
    *,
    with_ties: bool = False,
    na_last: bool = True,
    **kwargs: Any,
) -> pd.DataFrame:
    """Select the rows with the largest (or smallest) values of a column, inheriting grouping set via `pt.by()` or `.pt.by()`.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    col : str
        The column to rank by.
    n : int | None, default None
        Number of rows to return (per group if grouped). Defaults to 1 if neither `n` nor `prop` is given.
    prop : float | None, default None
        Proportion of rows to return between 0 and 1 (per group if grouped).
    order : {'max', 'min'}, default 'max'
        Whether to pick highest ('max') or lowest ('min') values.
    with_ties : bool, default False
        If True, keeps all rows tied for the n-th value.
    na_last : bool, default True
        If True, missing values are excluded from the ranking.

    Returns
    -------
    pd.DataFrame
        Picked DataFrame with all original columns and a clean RangeIndex.
    """
    if "by" in kwargs or "_by" in kwargs:
        raise TypeError("pick() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col').")
    if kwargs:
        raise TypeError(f"pick() got unexpected keyword argument(s): {list(kwargs.keys())}")

    clean_order = order.strip().lower() if isinstance(order, str) else ""
    if clean_order not in ("max", "min"):
        raise ValueError(f"pick: order must be 'max' or 'min', got {order!r}")
    ascending = (clean_order == "min")
    res = _slice_ordered(
        df, col, n=n, prop=prop, ascending=ascending, with_ties=with_ties, na_last=na_last, verb="pick"
    )
    if "_pt_by" in df.attrs:
        del df.attrs["_pt_by"]
    if "_pt_by" in res.attrs:
        del res.attrs["_pt_by"]
    return res


def slice_max(
    df: pd.DataFrame,
    col: str,
    n: int | None = None,
    prop: float | None = None,
    *,
    with_ties: bool = False,
    na_last: bool = True,
    **kwargs: Any,
) -> pd.DataFrame:
    """Deprecated alias for `pick(..., order='max')`."""
    import warnings
    warnings.warn("slice_max() is deprecated; use pick() instead.", DeprecationWarning, stacklevel=2)
    return pick(df, col, n=n, prop=prop, order="max", with_ties=with_ties, na_last=na_last, **kwargs)


def slice_min(
    df: pd.DataFrame,
    col: str,
    n: int | None = None,
    prop: float | None = None,
    *,
    with_ties: bool = False,
    na_last: bool = True,
    **kwargs: Any,
) -> pd.DataFrame:
    """Deprecated alias for `pick(..., order='min')`."""
    import warnings
    warnings.warn("slice_min() is deprecated; use pick(..., order='min') instead.", DeprecationWarning, stacklevel=2)
    return pick(df, col, n=n, prop=prop, order="min", with_ties=with_ties, na_last=na_last, **kwargs)


def _slice_ordered(
    df: pd.DataFrame,
    col: str,
    n: int | None = None,
    prop: float | None = None,
    *,
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

    if n is not None and prop is not None:
        raise ValueError(f"{verb}: specify either 'n' or 'prop', not both")

    if n is None and prop is None:
        n = 1

    if prop is not None:
        if not (0 < prop <= 1):
            raise ValueError(f"{verb}: 'prop' must be between 0 and 1, got {prop}")

    by_cols: list[str] = list(df.attrs["_pt_by"]) if "_pt_by" in df.attrs else []
    if by_cols:
        unknown_by = [c for c in by_cols if c not in df.columns]
        if unknown_by:
            raise KeyError(f"{verb}: grouping column(s) {unknown_by} not found in DataFrame. Available columns: {list(df.columns)}")

    na_position = "last" if na_last else "first"

    if prop is not None:
        if by_cols:
            sort_order = by_cols + [clean_col]
            sort_asc = [True] * len(by_cols) + [ascending]
            sorted_df = df.sort_values(by=sort_order, ascending=sort_asc, na_position=na_position)
            if with_ties:
                ranks = sorted_df.groupby(by_cols, observed=False, dropna=False)[clean_col].rank(
                    method="min", ascending=ascending, na_option="bottom" if na_last else "top"
                )
                counts = sorted_df.groupby(by_cols, observed=False, dropna=False)[clean_col].transform("count")
                cutoff = (counts * prop).astype(int).clip(lower=1)
                res = sorted_df[ranks <= cutoff]
            else:
                counts = sorted_df.groupby(by_cols, observed=False, dropna=False)[clean_col].transform("count")
                cutoff = (counts * prop).astype(int).clip(lower=1)
                row_nums = sorted_df.groupby(by_cols, observed=False, dropna=False).cumcount() + 1
                res = sorted_df[row_nums <= cutoff]
            return res.reset_index(drop=True)
        else:
            sorted_df = df.sort_values(by=clean_col, ascending=ascending, na_position=na_position)
            total_valid = int(sorted_df[clean_col].count()) if na_last else len(sorted_df)
            k = max(1, int(total_valid * prop))
            if with_ties:
                ranks = sorted_df[clean_col].rank(
                    method="min", ascending=ascending, na_option="bottom" if na_last else "top"
                )
                res = sorted_df[ranks <= k]
            else:
                res = sorted_df.head(k)
            return res.reset_index(drop=True)

    # When n is specified
    assert n is not None
    if n <= 0:
        return df.iloc[0:0].copy()

    if with_ties:
        if by_cols:
            ranks = df.groupby(by_cols, observed=False, dropna=False)[clean_col].rank(
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
        res = sorted_df.groupby(by_cols, as_index=False, observed=False, sort=False, dropna=False).head(n)
        return res.reset_index(drop=True)
    else:
        sorted_df = df.sort_values(by=clean_col, ascending=ascending, na_position=na_position)
        res = sorted_df.head(n)
        return res.reset_index(drop=True)
