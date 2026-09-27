from __future__ import annotations

import difflib
from collections.abc import Sequence
from typing import Any

import pandas as pd

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name
from pytae.other_utilities import safe_reset_index

_safe_reset_index = safe_reset_index


def long(
    df: pd.DataFrame,
    cols: str | Sequence[str] | None = None,
    id_vars: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
    **kwargs: Any,
) -> pd.DataFrame:
    """Melt columns to rows (unpivot from wide to long format).

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to melt.
    cols : str or sequence of str, optional
        Columns to unpivot into rows. Aliases: `values`, `value_vars`.
        If not specified and `id_vars` is provided, all remaining columns are melted.
        If neither `cols` nor `id_vars` is provided, all numeric columns are melted.
    id_vars : str or sequence of str, optional
        Identifier columns to keep fixed. Aliases: `by`, `id`.
        If not specified, all columns not in `cols` are kept as identifier variables.
    c : str, default 'variable'
        Name for the melted-variable column. Alias: `var_name`.
    v : str, default 'value'
        Name for the melted-value column. Alias: `value_name`.

    Returns:
    --------
    pd.DataFrame
        Unpivoted long DataFrame.
    """
    # Keyword argument aliases
    if cols is None:
        cols = kwargs.pop("values", kwargs.pop("value_vars", None))
    if id_vars is None:
        id_vars = kwargs.pop("by", kwargs.pop("id", None))
    if c == "variable":
        c = kwargs.pop("var_name", c)
    if v == "value":
        v = kwargs.pop("value_name", v)

    all_cols = list(df.columns)

    def _normalize_col_spec(spec: str | Sequence[str] | None, param_name: str) -> list[str] | None:
        if spec is None:
            return None
        if isinstance(spec, str):
            items = [item.strip() for item in spec.split(",") if item.strip()]
        elif isinstance(spec, (list, tuple, set)):
            items = list(spec)
        else:
            raise TypeError(f"{param_name} must be a column name or sequence of names, got {type(spec).__name__}")
        for item in items:
            if item not in df.columns:
                close = difflib.get_close_matches(str(item), [str(col) for col in all_cols], n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                raise KeyError(f"long(): {param_name} column '{item}' not found in DataFrame{hint}")
        return items

    melt_cols = _normalize_col_spec(cols, "cols")
    keep_ids = _normalize_col_spec(id_vars, "id_vars")

    if melt_cols is not None:
        if keep_ids is None:
            keep_ids = [col for col in all_cols if col not in melt_cols]
    elif keep_ids is not None:
        melt_cols = [col for col in all_cols if col not in keep_ids]
        if not melt_cols:
            raise ValueError("long(): no columns left to melt after keeping id_vars")
    else:
        # Default: auto-detect numeric columns
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if not numeric_cols:
            raise ValueError(
                "long(): no numeric columns to melt. "
                "Specify columns to melt via cols= (e.g. df.pt.long(cols=['q1', 'q2'])) "
                "or id_vars= (e.g. df.pt.long(id_vars=['id']))."
            )
        melt_cols = numeric_cols
        keep_ids = [col for col in all_cols if col not in melt_cols]

    return pd.melt(
        df,
        id_vars=keep_ids,
        value_vars=melt_cols,
        var_name=c,
        value_name=v,
    )


def wide(
    df: pd.DataFrame,
    c: str = "variable",
    v: str = "value",
    a: str | None = None,
    dropna: bool = True,
    index: str | Sequence[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Pivot a long column into headers.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to pivot.
    c : str, default 'variable'
        Column whose values become headers (columns).
    v : str, default 'value'
        Values column to populate table cells.
    a : str, optional
        Aggregation function if duplicate index/column pairs exist.
        If set, uses `pivot_table` with this aggfunc; else uses `pivot`, falling back to `sum`.
        'n' is accepted as an alias for pandas 'size' (group row count).
    dropna : bool, default True
        Whether to drop all-NA columns in pivot_table.
    index : str or sequence of str, optional
        Explicit index column(s) to use. If omitted, all columns other than `c` and `v` are used.

    Returns:
    --------
    pd.DataFrame
        Pivoted wide DataFrame.
    """
    c = _unquote_name(c)
    if v is not None:
        v = _unquote_name(v)
    if c not in df.columns:
        raise KeyError(f"wide(): columns 'c' column '{c}' not found in DataFrame")
    if v is not None and v not in df.columns:
        raise KeyError(f"wide(): values 'v' column '{v}' not found in DataFrame")

    if index is None:
        index = kwargs.pop("by", kwargs.pop("id_vars", None))

    if index is not None:
        if isinstance(index, str):
            index_cols = [_unquote_name(col.strip()) for col in _tokenize(index, ",", keep_quotes=True, track_brackets=True) if col.strip()]
        else:
            index_cols = [_unquote_name(col) if isinstance(col, str) else col for col in index]
        for col in index_cols:
            if col not in df.columns:
                raise KeyError(f"wide(): index column '{col}' not found in DataFrame")
    else:
        index_cols = [col for col in df.columns if col not in [c, v]]

    aggfunc = "size" if a == "n" else a

    if aggfunc is None:
        try:
            pivoted = df.pivot(index=index_cols if index_cols else None, columns=c, values=v)
            wide_df = _safe_reset_index(pivoted)
        except ValueError:
            pivoted = df.pivot_table(
                index=index_cols if index_cols else None, columns=c, values=v, aggfunc="sum", dropna=dropna
            )
            wide_df = _safe_reset_index(pivoted)
    else:
        pivoted = df.pivot_table(
            index=index_cols if index_cols else None, columns=c, values=v, aggfunc=aggfunc, dropna=dropna
        )
        wide_df = _safe_reset_index(pivoted)

    wide_df.columns.name = None
    return wide_df
