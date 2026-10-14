from __future__ import annotations

import difflib
from collections.abc import Sequence
from typing import Any

import numpy as np
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
        Columns to unpivot into rows.
        If not specified and `id_vars` is provided, all remaining columns are melted.
        If neither `cols` nor `id_vars` is provided, all numeric columns are melted.
    id_vars : str or sequence of str, optional
        Identifier columns to keep fixed.
        If not specified, all columns not in `cols` are kept as identifier variables.
    c : str, default 'variable'
        Name for the melted-variable column.
    v : str, default 'value'
        Name for the melted-value column.

    Returns:
    --------
    pd.DataFrame
        Unpivoted long DataFrame.
    """
    # Validate kwargs
    if kwargs:
        raise TypeError(f"long() got unexpected keyword argument(s): {list(kwargs.keys())}")

    all_cols = list(df.columns)

    def _normalize_col_spec(spec: str | Sequence[str] | None, param_name: str) -> list[str] | None:
        if spec is None:
            return None
        if isinstance(spec, str):
            items = [_unquote_name(item.strip()) for item in _tokenize(spec, ",", keep_quotes=True, track_brackets=True) if item.strip()]
        elif isinstance(spec, (list, tuple, set)):
            items = [_unquote_name(item) if isinstance(item, str) else item for item in spec]
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

    if melt_cols is not None and keep_ids is not None:
        overlap = set(melt_cols).intersection(keep_ids)
        if overlap:
            raise ValueError(f"long(): column(s) {sorted(overlap)} cannot appear in both 'cols' and 'id_vars'")

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

    if c == v:
        raise ValueError(f"long(): output variable column 'c' ({c!r}) and value column 'v' ({v!r}) cannot have the same name")
    if c in keep_ids:
        raise ValueError(f"long(): output variable column 'c' ({c!r}) collides with kept id column(s)")
    if v in keep_ids:
        raise ValueError(f"long(): output value column 'v' ({v!r}) collides with kept id column(s)")
    if v in melt_cols:
        raise ValueError(f"long(): output value column 'v' ({v!r}) collides with melted column(s)")

    return pd.melt(
        df,
        id_vars=keep_ids,
        value_vars=melt_cols,
        var_name=c,
        value_name=v,
    )


def wide(
    df: pd.DataFrame,
    r: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
    **kwargs: Any,
) -> pd.DataFrame:
    """Pivot a long column into headers (pure 1-to-1 reshape).

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to pivot.
    r : str or sequence of str, optional
        Row identifier column(s) to keep fixed.
        If omitted, all columns other than `c` and `v` are used.
    c : str, default 'variable'
        Column whose values become headers (columns).
    v : str, default 'value'
        Values column to populate table cells.

    Returns:
    --------
    pd.DataFrame
        Pivoted wide DataFrame with standard RangeIndex.
    """
    for bad_arg in ("a", "agg", "aggfunc", "dropna"):
        if bad_arg in kwargs:
            raise ValueError(
                f"wide() does not support '{bad_arg}'. wide() is strictly for 1-to-1 reshaping "
                "without aggregation. Use pt.pivot() / -pivot for multi-dimensional aggregation."
            )

    if "index" in kwargs:
        raise TypeError("wide() parameter 'index' has been removed; use 'r' instead")
    if kwargs:
        raise TypeError(f"wide() got unexpected keyword argument(s): {list(kwargs.keys())}; only r, c, v are accepted")

    c = _unquote_name(c)
    if v is None:
        raise ValueError("wide(): value column 'v' cannot be None. Specify the column to spread via v= (e.g. v='value').")
    v = _unquote_name(v)
    if c == v:
        raise ValueError(f"wide(): 'c' and 'v' cannot be the same column ('{c}')")
    if c not in df.columns:
        raise KeyError(f"wide(): columns 'c' column '{c}' not found in DataFrame")
    if v not in df.columns:
        raise KeyError(f"wide(): values 'v' column '{v}' not found in DataFrame")

    if r is not None:
        if isinstance(r, str):
            r_cols = [_unquote_name(col.strip()) for col in _tokenize(r, ",", keep_quotes=True, track_brackets=True) if col.strip()]
        else:
            r_cols = [_unquote_name(col) if isinstance(col, str) else col for col in r]
        for col in r_cols:
            if col not in df.columns:
                raise KeyError(f"wide(): row 'r' column '{col}' not found in DataFrame")
        if c in r_cols:
            raise ValueError(f"wide(): column 'c' ('{c}') cannot also be in row 'r' columns")
        if v in r_cols:
            raise ValueError(f"wide(): column 'v' ('{v}') cannot also be in row 'r' columns")
    else:
        r_cols = [col for col in df.columns if col not in [c, v]]

    try:
        if not r_cols:
            temp_df = df.copy()
            temp_df["__pt_wide_tmp__"] = 0
            pivoted = temp_df.pivot(index="__pt_wide_tmp__", columns=c, values=v)
        else:
            pivoted = df.pivot(index=r_cols, columns=c, values=v)
    except ValueError as exc:
        raise ValueError(
            f"wide() encountered duplicate entries for row 'r' {r_cols} and column '{c}'. "
            "wide() is strictly for 1-to-1 reshaping without aggregation. "
            "Use pt.pivot() / -pivot to summarize or aggregate duplicate entries."
        ) from exc

    wide_df = _safe_reset_index(pivoted)
    if not r_cols and "__pt_wide_tmp__" in wide_df.columns:
        wide_df = wide_df.drop(columns=["__pt_wide_tmp__"])
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
        Row dimension(s) to group by.
    c : str or sequence of str, optional
        Column dimension(s) to spread as headers.
    v : str or sequence of str
        Value column(s) to aggregate. REQUIRED.
    a : str, default 'sum'
        Aggregation function ('sum', 'mean', 'median', 'min', 'max', 'count', 'std', etc.).
        'n' is accepted for group row count.
    dropna : bool, default False
        Whether to drop NA categories from grouping keys.
    fill_value : any, optional
        Value to replace missing grid intersections with (e.g. 0).

    Returns:
    --------
    pd.DataFrame
        Clean, flattened DataFrame with standard RangeIndex and 1D column names.
    """
    if kwargs:
        raise TypeError(f"pivot() got unexpected keyword argument(s): {list(kwargs.keys())}; only r, c, v, a are accepted")

    all_cols = list(df.columns)

    def _normalize_cols(spec: str | Sequence[str] | None, param_name: str) -> list[str]:
        if spec is None:
            return []
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

    aggfunc = "size" if a == "n" else a
    if aggfunc == "size" and fill_value is None:
        fill_value = 0

    r_cols = _normalize_cols(r, "r (rows)")
    c_cols = _normalize_cols(c, "c (cols)")
    v_cols = _normalize_cols(v, "v (values)")

    dim_counts: dict[str, int] = {}
    for col in r_cols + c_cols:
        dim_counts[col] = dim_counts.get(col, 0) + 1
    dups = [col for col, count in dim_counts.items() if count > 1]
    if dups:
        raise ValueError(f"pivot(): column(s) {dups} cannot appear multiple times in grouping dimensions (r/c)")

    if len(v_cols) != len(set(v_cols)):
        v_dups = [col for col in dict.fromkeys(v_cols) if v_cols.count(col) > 1]
        raise ValueError(f"pivot(): value column(s) {v_dups} cannot appear multiple times in 'v'")

    if not v_cols and aggfunc != "size":
        raise ValueError("pivot(): value column 'v' is required (e.g. v='Sales')")

    overlap = [col for col in v_cols if (r_cols and col in r_cols) or (c_cols and col in c_cols)]
    if overlap:
        if aggfunc == "size":
            raise ValueError(
                f"pivot(): value column(s) {overlap} cannot also be in grouping dimensions (r/c). "
                "For row counts (a='n'), omit 'v' or specify a non-grouping column."
            )
        else:
            raise ValueError(f"pivot(): value column(s) {overlap} cannot also be in grouping dimensions (r/c)")

    observed = kwargs.get("observed", True)

    def _format_part(part: Any) -> str:
        if part is None or (isinstance(part, float) and np.isnan(part)) or pd.isna(part):
            return "nan"
        if isinstance(part, (float, np.floating)) and float(part).is_integer():
            return str(int(part))
        return str(part)

    def _flatten_cols(piv: pd.DataFrame) -> None:
        raw_names: list[str] = []
        if isinstance(piv.columns, pd.MultiIndex):
            for col in piv.columns:
                formatted_parts = [_format_part(part) for part in col if part is not None]
                raw_names.append("_".join(formatted_parts))
        else:
            raw_names = [_format_part(col) for col in piv.columns]

        duplicates = []
        seen = set()
        for name in raw_names:
            if name in seen and name not in duplicates:
                duplicates.append(name)
            seen.add(name)
        if duplicates:
            raise ValueError(
                f"pivot(): resulting column header(s) {duplicates} contain duplicate names. "
                "Ensure pivoted column keys have distinct string representations."
            )
        piv.columns = raw_names

    def _cast_size_ints(df_out: pd.DataFrame) -> pd.DataFrame:
        if aggfunc == "size":
            val_cols = [col for col in df_out.columns if not (r_cols and col in r_cols)]
            for col in val_cols:
                try:
                    if df_out[col].isna().any():
                        df_out[col] = df_out[col].astype("Int64")
                    else:
                        df_out[col] = df_out[col].astype("int64")
                except (TypeError, ValueError):
                    pass
        return df_out

    val_arg = v_cols[0] if len(v_cols) == 1 else v_cols

    if r_cols and c_cols:
        group_keys = list(r_cols) + list(c_cols)
        if aggfunc == "size":
            s = df.groupby(group_keys, dropna=dropna, observed=observed).size()
            pivoted = s.unstack(list(c_cols), fill_value=fill_value if fill_value is not None else 0)
        else:
            g = df.groupby(group_keys, dropna=dropna, observed=observed)[val_arg].agg(aggfunc)
            pivoted = g.unstack(list(c_cols), fill_value=fill_value)
        _flatten_cols(pivoted)
        res = _safe_reset_index(pivoted)
        res.columns.name = None
        return _cast_size_ints(res)
    elif r_cols:
        if aggfunc == "size":
            target_name = v_cols[0] if v_cols else "n"
            if target_name in r_cols:
                raise ValueError(
                    f"pivot(): count column name '{target_name}' collides with row grouping column. "
                    "For row counts (a='n'), omit 'v' or specify a non-colliding column name."
                )
            s = df.groupby(r_cols, dropna=dropna, observed=observed).size()
            res = s.to_frame(name=target_name).reset_index()
            res.columns.name = None
            return _cast_size_ints(res)
        else:
            g = df.groupby(r_cols, dropna=dropna, observed=observed)[val_arg].agg(aggfunc)
            pivoted = g if isinstance(g, pd.DataFrame) else g.to_frame()
            if fill_value is not None:
                pivoted = pivoted.fillna(fill_value)
            _flatten_cols(pivoted)
            res = _safe_reset_index(pivoted)
            res.columns.name = None
            return res
    elif c_cols:
        if aggfunc == "size":
            s = df.groupby(c_cols, dropna=dropna, observed=observed).size()
            pivoted = s.to_frame().T.reset_index(drop=True)
            _flatten_cols(pivoted)
            pivoted.columns.name = None
            return _cast_size_ints(pivoted)
        else:
            g = df.groupby(c_cols, dropna=dropna, observed=observed)[val_arg].agg(aggfunc)
            if len(v_cols) == 1:
                pivoted = g.to_frame().T.reset_index(drop=True)
                if fill_value is not None:
                    pivoted = pivoted.fillna(fill_value)
                _flatten_cols(pivoted)
                pivoted.columns.name = None
                return pivoted
            else:
                pivoted = g.T
                if fill_value is not None:
                    pivoted = pivoted.fillna(fill_value)
                _flatten_cols(pivoted)
                pivoted.index.name = "metric"
                res = _safe_reset_index(pivoted)
                res.columns.name = None
                return res
    else:
        if aggfunc == "size":
            target_cols = v_cols if v_cols else ["n"]
            res = pd.DataFrame({col: [len(df)] for col in target_cols}, dtype="int64")
        else:
            res = df[v_cols].agg(aggfunc).to_frame().T.reset_index(drop=True)
        if fill_value is not None:
            res = res.fillna(fill_value)
        _flatten_cols(res)
        res.columns.name = None
        return _cast_size_ints(res)

