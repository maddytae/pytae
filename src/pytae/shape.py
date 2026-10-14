from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name
from pytae.other_utilities import safe_reset_index

_safe_reset_index = safe_reset_index


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
        return [PivotMetric(
            src_col=None,
            out_name=out_name,
            aggfunc="size",
            has_alias=has_alias,
            has_explicit_func=True,
        )]

    col_part = rest
    funcs: list[str] = []
    if ":" in rest:
        colon_parts = _tokenize(rest, ":", track_brackets=True, keep_quotes=True)
        if len(colon_parts) >= 2 and colon_parts[0].strip():
            col_part = colon_parts[0].strip()
            func_spec = ":".join(colon_parts[1:]).strip()
            if (func_spec.startswith("[") and func_spec.endswith("]")) or (func_spec.startswith("(") and func_spec.endswith(")")):
                inner = func_spec[1:-1].strip()
                funcs = [_unquote_name(f.strip()) for f in _tokenize(inner, ",") if f.strip()]
            else:
                funcs = [_unquote_name(func_spec)]

    src_col = _unquote_name(col_part.strip())
    if not funcs:
        agg = "size" if default_a in ("n", "size") else default_a
        out_name = alias if has_alias and alias else src_col
        return [PivotMetric(
            src_col=src_col,
            out_name=out_name,
            aggfunc=agg,
            has_alias=has_alias,
            has_explicit_func=False,
        )]

    res: list[PivotMetric] = []
    for f in funcs:
        agg = "size" if f in ("n", "size") else f
        if has_alias and len(funcs) == 1:
            out_name = alias if alias else f"{src_col}_{f}"
        elif has_alias and len(funcs) > 1:
            out_name = f"{alias}_{f}"
        else:
            out_name = f"{src_col}_{f}"
        res.append(PivotMetric(
            src_col=src_col,
            out_name=out_name,
            aggfunc=agg,
            has_alias=has_alias,
            has_explicit_func=True,
        ))
    return res


def parse_pivot_metrics(
    v: Any,
    a: str = "sum",
    df_cols: Sequence[str] | None = None,
) -> list[PivotMetric]:
    """Parse rich metric mappings in v for pivot operations."""
    if v is None:
        if a in ("n", "size"):
            return [PivotMetric(src_col=None, out_name="n", aggfunc="size", has_alias=False, has_explicit_func=True)]
        return []

    if isinstance(v, Mapping):
        metrics: list[PivotMetric] = []
        for key, val in v.items():
            key_str = _unquote_name(str(key).strip())
            if isinstance(val, (list, tuple)):
                for f in val:
                    f_str = str(f).strip()
                    agg = "size" if f_str in ("n", "size") else f_str
                    metrics.append(PivotMetric(
                        src_col=key_str,
                        out_name=f"{key_str}_{f_str}",
                        aggfunc=agg,
                        has_alias=False,
                        has_explicit_func=True,
                    ))
            elif isinstance(val, str) and (":" in val or val.strip().lower() in ("n", "size")):
                metrics.extend(_parse_single_metric_expr(f"{key_str} = {val}", default_a=a))
            else:
                f_str = str(val).strip()
                agg = "size" if f_str in ("n", "size") else f_str
                metrics.append(PivotMetric(
                    src_col=key_str,
                    out_name=key_str,
                    aggfunc=agg,
                    has_alias=False,
                    has_explicit_func=True,
                ))
        return metrics

    if isinstance(v, (list, tuple, set)):
        metrics = []
        for item in v:
            metrics.extend(_parse_single_metric_expr(str(item), default_a=a))
        return metrics

    if isinstance(v, str):
        raw_items = [t for t in _tokenize(v, ",", track_brackets=True, keep_quotes=True) if t.strip()]
        metrics = []
        for item in raw_items:
            metrics.extend(_parse_single_metric_expr(item, default_a=a))
        return metrics

    return _parse_single_metric_expr(str(v), default_a=a)



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

    r_cols = _normalize_cols(r, "r (rows)")
    c_cols = _normalize_cols(c, "c (cols)")

    dim_counts: dict[str, int] = {}
    for col in r_cols + c_cols:
        dim_counts[col] = dim_counts.get(col, 0) + 1
    dups = [col for col, count in dim_counts.items() if count > 1]
    if dups:
        raise ValueError(f"pivot(): column(s) {dups} cannot appear multiple times in grouping dimensions (r/c)")

    metrics = parse_pivot_metrics(v, a=a, df_cols=all_cols)
    if not metrics:
        raise ValueError("pivot(): value column 'v' is required (e.g. v='Sales')")

    for m in metrics:
        if m.src_col is not None and m.src_col not in df.columns:
            close = difflib.get_close_matches(str(m.src_col), [str(x) for x in all_cols], n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"pivot(): value column '{m.src_col}' not found in DataFrame{hint}")

    overlap = [m.src_col for m in metrics if m.src_col is not None and ((r_cols and m.src_col in r_cols) or (c_cols and m.src_col in c_cols))]
    if overlap:
        if all(m.aggfunc == "size" for m in metrics if m.src_col in overlap):
            raise ValueError(
                f"pivot(): value column(s) {overlap} cannot also be in grouping dimensions (r/c). "
                "For row counts (a='n'), omit 'v' or specify a non-grouping column."
            )
        else:
            raise ValueError(f"pivot(): value column(s) {overlap} cannot also be in grouping dimensions (r/c)")

    out_names = [m.out_name for m in metrics]
    if len(out_names) != len(set(out_names)):
        v_dups = [name for name in dict.fromkeys(out_names) if out_names.count(name) > 1]
        raise ValueError(f"pivot(): value column(s) {v_dups} cannot appear multiple times in 'v'")

    if r_cols and not c_cols:
        for m in metrics:
            if m.out_name in r_cols:
                if m.aggfunc == "size":
                    raise ValueError(
                        f"pivot(): count column name '{m.out_name}' collides with row grouping column. "
                        "For row counts (a='n'), omit 'v' or specify a non-colliding column name."
                    )
                else:
                    raise ValueError(f"pivot(): resulting column header '{m.out_name}' collides with row grouping column.")

    observed = kwargs.get("observed", True)

    def _format_part(part: Any) -> str:
        if part is None or (isinstance(part, float) and np.isnan(part)) or pd.isna(part):
            return "nan"
        if isinstance(part, (float, np.floating)) and float(part).is_integer():
            return str(int(part))
        return str(part)

    def _flatten_cols(piv: pd.DataFrame, prefix: str | None = None) -> list[str]:
        raw_names: list[str] = []
        if isinstance(piv.columns, pd.MultiIndex):
            for col in piv.columns:
                formatted_parts = [_format_part(part) for part in col if part is not None]
                base_name = "_".join(formatted_parts)
                raw_names.append(f"{prefix}_{base_name}" if prefix else base_name)
        else:
            for col in piv.columns:
                base_name = _format_part(col)
                raw_names.append(f"{prefix}_{base_name}" if prefix else base_name)
        return raw_names

    if r_cols and c_cols:
        group_keys = list(r_cols) + list(c_cols)
        need_prefix = len(metrics) > 1
        pivoted_dfs: list[pd.DataFrame] = []
        for m in metrics:
            m_prefix_needed = need_prefix or m.has_alias or (m.has_explicit_func and m.src_col is not None)
            prefix = m.out_name if m_prefix_needed else None
            if m.src_col is None or m.aggfunc == "size":
                s = df.groupby(group_keys, dropna=dropna, observed=observed).size()
                fv = fill_value if fill_value is not None else 0
                piv_m = s.unstack(list(c_cols), fill_value=fv)
            else:
                g = df.groupby(group_keys, dropna=dropna, observed=observed)[m.src_col].agg(m.aggfunc)
                piv_m = g.unstack(list(c_cols), fill_value=fill_value)
            new_cols = _flatten_cols(piv_m, prefix=prefix)
            piv_m.columns = new_cols
            pivoted_dfs.append(piv_m)

        concatenated = pd.concat(pivoted_dfs, axis=1)
        all_col_names = list(concatenated.columns)
        duplicates = [c for c in dict.fromkeys(all_col_names) if all_col_names.count(c) > 1]
        if duplicates:
            raise ValueError(
                f"pivot(): resulting column header(s) {duplicates} contain duplicate names. "
                "Ensure pivoted column keys have distinct string representations."
            )
        res = _safe_reset_index(concatenated)
        res.columns.name = None
        for m in metrics:
            if m.aggfunc == "size":
                m_prefix_needed = need_prefix or m.has_alias or (m.has_explicit_func and m.src_col is not None)
                prefix = m.out_name if m_prefix_needed else ""
                val_cols = [c for c in res.columns if not (r_cols and c in r_cols) and (not prefix or c.startswith(prefix))]
                for c in val_cols:
                    try:
                        if res[c].isna().any():
                            res[c] = res[c].astype("Int64")
                        else:
                            res[c] = res[c].astype("int64")
                    except (TypeError, ValueError):
                        pass
        return res
    elif r_cols:
        col_dfs: list[pd.DataFrame] = []
        for m in metrics:
            if m.src_col is None or m.aggfunc == "size":
                s = df.groupby(r_cols, dropna=dropna, observed=observed).size()
                col_df = s.to_frame(name=m.out_name)
            else:
                g = df.groupby(r_cols, dropna=dropna, observed=observed)[m.src_col].agg(m.aggfunc)
                col_df = g.to_frame(name=m.out_name)
            if fill_value is not None:
                col_df = col_df.fillna(fill_value)
            col_dfs.append(col_df)

        combined = pd.concat(col_dfs, axis=1)
        res = _safe_reset_index(combined)
        res.columns.name = None
        for m in metrics:
            if m.aggfunc == "size" and m.out_name in res.columns:
                try:
                    if res[m.out_name].isna().any():
                        res[m.out_name] = res[m.out_name].astype("Int64")
                    else:
                        res[m.out_name] = res[m.out_name].astype("int64")
                except (TypeError, ValueError):
                    pass
        return res
    elif c_cols:
        need_prefix = len(metrics) > 1
        if len(metrics) == 1:
            m = metrics[0]
            m_prefix_needed = m.has_alias or (m.has_explicit_func and m.src_col is not None)
            prefix = m.out_name if m_prefix_needed else None
            if m.src_col is None or m.aggfunc == "size":
                s = df.groupby(c_cols, dropna=dropna, observed=observed).size()
                pivoted = s.to_frame().T.reset_index(drop=True)
            else:
                g = df.groupby(c_cols, dropna=dropna, observed=observed)[m.src_col].agg(m.aggfunc)
                pivoted = g.to_frame().T.reset_index(drop=True)
            if fill_value is not None:
                pivoted = pivoted.fillna(fill_value)
            pivoted.columns = _flatten_cols(pivoted, prefix=prefix)
            pivoted.columns.name = None
            if m.aggfunc == "size":
                for col in pivoted.columns:
                    try:
                        pivoted[col] = pivoted[col].astype("int64")
                    except (TypeError, ValueError):
                        pass
            return pivoted
        else:
            rows: list[pd.DataFrame] = []
            for m in metrics:
                if m.src_col is None or m.aggfunc == "size":
                    s = df.groupby(c_cols, dropna=dropna, observed=observed).size()
                    row_df = s.to_frame().T
                else:
                    g = df.groupby(c_cols, dropna=dropna, observed=observed)[m.src_col].agg(m.aggfunc)
                    row_df = g.to_frame().T
                if fill_value is not None:
                    row_df = row_df.fillna(fill_value)
                row_df.index = [m.out_name]
                rows.append(row_df)
            pivoted = pd.concat(rows)
            pivoted.columns = _flatten_cols(pivoted)
            pivoted.index.name = "metric"
            res = _safe_reset_index(pivoted)
            res.columns.name = None
            return res
    else:
        data: dict[str, Any] = {}
        for m in metrics:
            if m.src_col is None or m.aggfunc == "size":
                val = len(df)
            else:
                val = df[m.src_col].agg(m.aggfunc)
            data[m.out_name] = [val]
        res = pd.DataFrame(data)
        if fill_value is not None:
            res = res.fillna(fill_value)
        for m in metrics:
            if m.aggfunc == "size" and m.out_name in res.columns:
                try:
                    res[m.out_name] = res[m.out_name].astype("int64")
                except (TypeError, ValueError):
                    pass
        res.columns.name = None
        return res

