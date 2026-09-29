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
    dropna: bool = False,
    index: str | Sequence[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Pivot a long column into headers (pure reshape).

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
    dropna : bool, default False
        Whether to drop all-NA columns in pivot_table.
    index : str or sequence of str, optional
        Explicit index column(s) to use. Aliases: `r`, `rows`, `by`, `id_vars`.
        If omitted, all columns other than `c` and `v` are used.

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
        index = kwargs.pop("r", kwargs.pop("rows", kwargs.pop("by", kwargs.pop("id_vars", None))))

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


def pivot(
    df: pd.DataFrame,
    r: str | Sequence[str] | None = None,
    c: str | Sequence[str] | None = None,
    v: str | Sequence[str] | None = None,
    a: str = "sum",
    dropna: bool = False,
    fill_value: Any = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Summarize and aggregate a DataFrame across dimensions (Excel-style pivot table).

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to pivot.
    r : str or sequence of str, optional
        Row dimension(s) to group by. Aliases: `rows`, `row`, `index`, `by`.
    c : str or sequence of str, optional
        Column dimension(s) to spread as headers. Aliases: `cols`, `col`, `columns`.
    v : str or sequence of str
        Value column(s) to aggregate. REQUIRED. Aliases: `values`, `value`, `val`, `vals`.
    a : str, default 'sum'
        Aggregation function ('sum', 'mean', 'median', 'min', 'max', 'count', 'std', etc.).
        'n' is accepted as an alias for 'size' (group row count). Aliases: `agg`, `aggfunc`.
    dropna : bool, default False
        Whether to drop NA categories from grouping keys.
    fill_value : any, optional
        Value to replace missing grid intersections with (e.g. 0).

    Returns:
    --------
    pd.DataFrame
        Clean, flattened DataFrame with standard RangeIndex and 1D column names.
    """
    if r is None:
        r = kwargs.pop("rows", kwargs.pop("row", kwargs.pop("index", kwargs.pop("by", None))))
    if c is None:
        c = kwargs.pop("cols", kwargs.pop("col", kwargs.pop("columns", None)))
    if v is None:
        v = kwargs.pop("values", kwargs.pop("value", kwargs.pop("val", kwargs.pop("vals", None))))
    if a == "sum":
        a = kwargs.pop("agg", kwargs.pop("aggfunc", a))
    if fill_value is None:
        fill_value = kwargs.pop("fill", None)

    all_cols = list(df.columns)

    def _normalize_cols(spec: str | Sequence[str] | None, param_name: str) -> list[str] | None:
        if spec is None:
            return None
        if isinstance(spec, str):
            cols = [_unquote_name(item.strip()) for item in _tokenize(spec, ",", keep_quotes=True, track_brackets=True) if item.strip()]
        elif isinstance(spec, (list, tuple, set)):
            cols = [_unquote_name(item) if isinstance(item, str) else item for item in spec]
        else:
            raise TypeError(f"pivot(): {param_name} must be a column name or sequence of names, got {type(spec).__name__}")
        for col in cols:
            if col not in df.columns:
                close = difflib.get_close_matches(str(col), [str(x) for x in all_cols], n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                raise KeyError(f"pivot(): {param_name} column '{col}' not found in DataFrame{hint}")
        return cols

    v_cols = _normalize_cols(v, "v (values)")
    if not v_cols:
        raise ValueError("pivot(): value column 'v' is required (e.g. v='Sales')")
    r_cols = _normalize_cols(r, "r (rows)")
    c_cols = _normalize_cols(c, "c (cols)")

    aggfunc = "size" if a == "n" else a
    if aggfunc == "size" and fill_value is None:
        fill_value = 0
    val_arg = v_cols if len(v_cols) > 1 else v_cols[0]

    def _flatten_cols(piv: pd.DataFrame) -> None:
        if isinstance(piv.columns, pd.MultiIndex):
            piv.columns = [
                "_".join(str(part) for part in col if part is not None and str(part) != "")
                for col in piv.columns
            ]
        else:
            piv.columns = [str(col) for col in piv.columns]

    def _cast_size_ints(df_out: pd.DataFrame) -> pd.DataFrame:
        if aggfunc == "size":
            val_cols = [col for col in df_out.columns if not (r_cols and col in r_cols)]
            for col in val_cols:
                try:
                    if df_out[col].isna().any():
                        df_out[col] = df_out[col].astype("Int64")
                    else:
                        df_out[col] = df_out[col].astype("int64")
                except Exception:
                    pass
        return df_out

    if r_cols and c_cols:
        pivoted = df.pivot_table(
            index=r_cols,
            columns=c_cols,
            values=val_arg,
            aggfunc=aggfunc,
            dropna=dropna,
            fill_value=fill_value,
        )
        _flatten_cols(pivoted)
        res = _safe_reset_index(pivoted)
        res.columns.name = None
        return _cast_size_ints(res)
    elif r_cols:
        if aggfunc == "size":
            s = df.groupby(r_cols, dropna=dropna).size()
            res = s.to_frame(name=v_cols[0] if len(v_cols) == 1 else "count").reset_index()
            res.columns.name = None
            return _cast_size_ints(res)
        else:
            pivoted = df.pivot_table(
                index=r_cols,
                values=val_arg,
                aggfunc=aggfunc,
                dropna=dropna,
                fill_value=fill_value,
            )
            _flatten_cols(pivoted)
            res = _safe_reset_index(pivoted)
            res.columns.name = None
            return res
    elif c_cols:
        if aggfunc == "size":
            s = df.groupby(c_cols, dropna=dropna).size()
            res = s.to_frame().T.reset_index(drop=True)
            _flatten_cols(res)
            res.columns.name = None
            return _cast_size_ints(res)
        else:
            pivoted = df.pivot_table(
                columns=c_cols,
                values=val_arg,
                aggfunc=aggfunc,
                dropna=dropna,
                fill_value=fill_value,
            )
            _flatten_cols(pivoted)
            res = pivoted.reset_index(drop=True)
            res.columns.name = None
            return res
    else:
        if aggfunc == "size":
            res = pd.DataFrame({col: [len(df)] for col in v_cols}, dtype="int64")
        else:
            res = df[v_cols].agg(aggfunc).to_frame().T.reset_index(drop=True)
        if fill_value is not None:
            res = res.fillna(fill_value)
        res.columns = [str(col) for col in res.columns]
        res.columns.name = None
        return _cast_size_ints(res)

