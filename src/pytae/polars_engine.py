"""High-performance Polars execution engine for the pytae CLI.

Accelerates scanning, filtering, selecting, sorting, reshaping, mutating, and exporting
tabular data with multithreaded SIMD vectorization and lazy query pushdown, while maintaining
100% semantic and formatting compatibility with pytae's Pandas library.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from typing import Any, Literal, cast

import polars as pl

from pytae._parsing import (
    _extract_arrange_specs,
    _Lit,
    _replace_underscore_placeholder,
    _resolve_multi_target_cols,
    _rewrite_fallback_col_refs,
    _strip_at_refs,
)
from pytae._text import unquote_name as _unquote_name
from pytae.select import resolve_select_columns


def _df_columns(df: Any) -> list[str]:
    if isinstance(df, pl.LazyFrame):
        return df.collect_schema().names()
    return list(df.columns)


def _df_schema(df: Any) -> pl.Schema:
    if isinstance(df, pl.LazyFrame):
        return df.collect_schema()
    return df.schema


def _cond_to_polars_expr(col: str, cond: Any, schema: pl.Schema | None = None) -> pl.Expr:
    """Convert a pytae filter condition tuple/value into a Polars Expression."""
    col_expr = pl.col(col)
    is_numeric = schema is not None and col in schema and schema[col].is_numeric()
    is_string = schema is not None and col in schema and schema[col] in (pl.String, pl.Utf8)
    is_date = schema is not None and col in schema and schema[col] == pl.Date
    is_datetime = (
        schema is not None
        and col in schema
        and (schema[col] == pl.Datetime or getattr(schema[col], "base_type", None) == pl.Datetime)
    )

    def _coerce_val(val: Any) -> Any:
        if is_numeric and isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                try:
                    return float(val)
                except ValueError:
                    pass
        elif is_string and not isinstance(val, str):
            return str(val)
        elif is_date and isinstance(val, str):
            from datetime import datetime

            try:
                return datetime.fromisoformat(val).date()
            except ValueError:
                pass
        elif is_datetime and isinstance(val, str):
            from datetime import datetime

            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
        return val

    if isinstance(cond, list):
        coerced_list = [_coerce_val(v) for v in cond]
        return col_expr.is_in(coerced_list)

    if isinstance(cond, tuple):
        if len(cond) == 1:
            op = cond[0]
            if op == "isna":
                return col_expr.is_null()
            if op == "notna":
                return col_expr.is_not_null()
        elif len(cond) == 2:
            op, val = cond
            if op == "in":
                vals = [_coerce_val(v) for v in val] if isinstance(val, (list, tuple)) else val
                return col_expr.is_in(vals)
            if op == "not in":
                vals = [_coerce_val(v) for v in val] if isinstance(val, (list, tuple)) else val
                return ~col_expr.is_in(vals)
            cval = _coerce_val(val)
            if op == "==":
                return col_expr == cval
            if op == "!=":
                return col_expr != cval
            if op == ">":
                return col_expr > cval
            if op == ">=":
                return col_expr >= cval
            if op == "<":
                return col_expr < cval
            if op == "<=":
                return col_expr <= cval
            if op == "startswith":
                return col_expr.cast(pl.String).str.starts_with(str(val))
            if op == "endswith":
                return col_expr.cast(pl.String).str.ends_with(str(val))
            if op == "contains":
                return col_expr.cast(pl.String).str.contains(str(val), literal=True)
            if op == "regex":
                return col_expr.cast(pl.String).str.contains(str(val))

    if isinstance(cond, str):
        # interval pattern: [lo, hi], (lo, hi), [lo, hi), (lo, hi]
        m = re.match(r"^([\[(])([^,]+),([^,]+)([\])])$", cond.strip())
        if m:
            l_br, lo_raw, hi_raw, r_br = m.groups()
            try:
                lo = ast.literal_eval(lo_raw.strip())
            except Exception:
                lo = lo_raw.strip()
            try:
                hi = ast.literal_eval(hi_raw.strip())
            except Exception:
                hi = hi_raw.strip()

            lo = _coerce_val(lo)
            hi = _coerce_val(hi)
            c1 = col_expr >= lo if l_br == "[" else col_expr > lo
            c2 = col_expr <= hi if r_br == "]" else col_expr < hi
            return c1 & c2

        op_match = re.match(r"^(>=|<=|!=|==|>|<)\s*(.+)$", cond.strip())
        if op_match:
            op = op_match.group(1)
            sub_raw = op_match.group(2).strip()
            try:
                sub_val = ast.literal_eval(sub_raw)
            except (ValueError, SyntaxError):
                if len(sub_raw) >= 2 and sub_raw[0] in "'\"" and sub_raw[-1] == sub_raw[0]:
                    sub_val = sub_raw[1:-1]
                else:
                    sub_val = sub_raw
            return _cond_to_polars_expr(col, (op, sub_val), schema=schema)

    # Default direct scalar equality
    return col_expr == _coerce_val(cond)


def filter_polars(df: Any, conditions: list[tuple[str, Any]] | dict) -> Any:
    """Filter a Polars DataFrame or LazyFrame using pytae filter specifications."""
    cond_items: list[tuple[str, Any]]
    if isinstance(conditions, dict):
        cond_items = list(conditions.items())
    else:
        cond_items = list(conditions)

    if not cond_items:
        return df

    schema = _df_schema(df)
    combined_expr: pl.Expr | None = None
    for col, cond in cond_items:
        expr = _cond_to_polars_expr(col, cond, schema=schema)
        combined_expr = expr if combined_expr is None else (combined_expr & expr)

    assert combined_expr is not None
    return df.filter(combined_expr)


def select_polars(df: Any, names: list[str], kwargs: dict) -> Any:
    """Select and order columns in a Polars DataFrame or LazyFrame using pytae selection syntax."""
    target_cols = resolve_select_columns(_df_columns(df), _df_schema(df), *names, **kwargs)
    return df.select(target_cols)


def arrange_polars(df: Any, spec: str, na_last: bool = True) -> Any:
    """Sort rows in a Polars DataFrame or LazyFrame by one or more column expressions."""
    cols, asc = _extract_arrange_specs((spec,), available_cols=set(_df_columns(df)))
    descending = [not a for a in asc]
    return df.sort(cols, descending=descending, nulls_last=na_last)


def distinct_polars(df: Any, cols: list[str] | None = None, keep: str | bool = "first") -> Any:
    """Drop duplicate rows in a Polars DataFrame or LazyFrame."""
    pl_keep: Literal["first", "last", "any", "none"]
    if keep == "first":
        pl_keep = "first"
    elif keep == "last":
        pl_keep = "last"
    elif keep is False or keep == "none":
        pl_keep = "none"
    else:
        pl_keep = "any"
    return df.unique(subset=cols if cols else None, keep=pl_keep, maintain_order=True)


def dropna_polars(
    df: Any,
    cols: list[str] | Sequence[str] | None = None,
    *,
    how: str | None = None,
    drop_nans: bool = True,
) -> Any:
    """Drop rows containing missing values (Arrow null and/or float NaN).

    Option B Zero Data Loss Philosophy:
    - If `cols` is None/empty: defaults to how='all' (only drop completely empty rows).
    - If `cols` is specified: defaults to how='any' (drop rows missing any of the specified columns).
    - `how` can be explicitly 'any' or 'all' to override.
    - `drop_nans=True` (default) drops float NaNs in addition to Arrow nulls.
    """
    import polars as pl

    schema = _df_schema(df)
    target_cols = [c for c in cols if c in schema] if cols else list(schema.names())
    if not target_cols:
        return df

    effective_how = how.lower() if how else ("all" if cols is None else "any")
    if effective_how not in ("any", "all"):
        raise ValueError(f"dropna: invalid 'how' argument '{how}'. Must be 'any' or 'all'")

    is_null_exprs = []
    for c in target_cols:
        dt = schema[c]
        if drop_nans and dt.is_float():
            is_null_exprs.append(pl.col(c).is_null() | pl.col(c).is_nan())
        else:
            is_null_exprs.append(pl.col(c).is_null())

    if len(is_null_exprs) == 1:
        cond = ~is_null_exprs[0]
    elif effective_how == "all":
        cond = ~pl.all_horizontal(is_null_exprs)
    else:
        cond = ~pl.any_horizontal(is_null_exprs)

    return df.filter(cond)


def rename_polars(df: Any, mapping: dict[str, str]) -> Any:
    """Rename columns in a Polars DataFrame or LazyFrame."""
    return df.rename(mapping)


def _polars_agg_expr(col: pl.Expr, func: str) -> pl.Expr:
    fn = func.lower()
    if fn == "sum":
        return col.sum()
    elif fn in ("mean", "avg"):
        return col.mean()
    elif fn == "median":
        return col.median()
    elif fn == "min":
        return col.min()
    elif fn == "max":
        return col.max()
    elif fn == "std":
        return col.std()
    elif fn == "var":
        return col.var()
    elif fn in ("len", "size", "n"):
        return pl.len().cast(pl.Int64)
    elif fn == "count":
        return col.count().cast(pl.Int64)
    elif fn == "first":
        return col.first()
    elif fn == "last":
        return col.last()
    elif fn in ("n_unique", "nunique"):
        return col.n_unique()
    else:
        raise ValueError(f"pivot_polars: unsupported aggregation function '{func}'")


def pivot_polars(
    df: pl.DataFrame,
    r: str | Sequence[str] | None = None,
    c: str | Sequence[str] | None = None,
    v: Any = None,
    a: str = "sum",
    dropna: bool = False,
    f_v: Any = None,
    _func_name: str = "pivot_polars",
    **kwargs: Any,
) -> pl.DataFrame:
    """Pivot a Polars DataFrame matching pytae's pivot semantics across all 4 geometric configurations."""
    if "drop_nulls" in kwargs:
        dropna = kwargs.pop("drop_nulls")
    if kwargs:
        raise TypeError(
            f"{_func_name}() got unexpected keyword argument(s): {list(kwargs.keys())}; only r, c, v, a, dropna, drop_nulls, f_v are accepted"
        )

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    all_cols = list(df.columns)

    def _norm(spec: Any) -> list[str]:
        if spec is None:
            return []
        if isinstance(spec, str):
            from pytae._text import tokenize as _tok

            return [
                _unquote_name(item.strip())
                for item in _tok(spec, ",", keep_quotes=True, track_brackets=True)
                if item.strip()
            ]
        if isinstance(spec, (list, tuple, set)):
            return [_unquote_name(item) if isinstance(item, str) else item for item in spec]
        return [str(spec)]

    r_cols = _norm(r)
    c_cols = _norm(c)

    if c_cols:
        for c_col in c_cols:
            if c_col in df.columns:
                vals = df[c_col].to_list()
                str_vals = ["nan" if x is None or (isinstance(x, float) and str(x) == "nan") else str(x) for x in vals]
                if len(set(vals)) != len(set(str_vals)):
                    raise ValueError("Pivoting would result in column headers that contain duplicate names")

    for col in r_cols:
        if col not in df.columns:
            import difflib

            close = difflib.get_close_matches(str(col), [str(x) for x in all_cols], n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"pivot(): r (rows) column '{col}' not found in DataFrame{hint}")

    for col in c_cols:
        if col not in df.columns:
            import difflib

            close = difflib.get_close_matches(str(col), [str(x) for x in all_cols], n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"pivot(): c (cols) column '{col}' not found in DataFrame{hint}")

    dim_counts: dict[str, int] = {}
    for col in r_cols + c_cols:
        dim_counts[col] = dim_counts.get(col, 0) + 1
    dups = [col for col, count in dim_counts.items() if count > 1]
    if dups:
        raise ValueError(f"pivot(): column(s) {dups} cannot appear multiple times in grouping dimensions (r/c)")

    from pytae._parsing import parse_pivot_metrics

    metrics = parse_pivot_metrics(v, a=a, df_cols=all_cols)
    if not metrics:
        raise ValueError("pivot(): value column 'v' is required (e.g. v='Sales')")

    for m in metrics:
        if m.src_col is not None and m.src_col not in df.columns:
            import difflib

            close = difflib.get_close_matches(str(m.src_col), [str(x) for x in all_cols], n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"pivot(): value column '{m.src_col}' not found in DataFrame{hint}")

    overlap = [
        m.src_col
        for m in metrics
        if m.src_col is not None and ((r_cols and m.src_col in r_cols) or (c_cols and m.src_col in c_cols))
    ]
    if overlap:
        if all(m.aggfunc in ("size", "len") for m in metrics if m.src_col in overlap):
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
                if m.aggfunc in ("size", "len"):
                    raise ValueError(
                        f"pivot(): count column name '{m.out_name}' collides with row grouping column. "
                        "For row counts (a='n'), omit 'v' or specify a non-colliding column name."
                    )
                else:
                    raise ValueError(
                        f"pivot(): resulting column header '{m.out_name}' collides with row grouping column."
                    )

    def _clean_null_col(r_df: pl.DataFrame) -> pl.DataFrame:
        if "null" in r_df.columns:
            return r_df.rename({"null": "nan"})
        return r_df

    work_df = df
    if dropna:
        dim_cols = r_cols + c_cols
        if dim_cols:
            work_df = work_df.drop_nulls(subset=dim_cols)

    if r_cols and c_cols:
        pivot_on = c_cols
        if len(c_cols) > 1:
            col_exprs = [pl.col(col).cast(pl.String) for col in c_cols]
            work_df = work_df.with_columns(pl.concat_str(col_exprs, separator="_").alias("__pt_c_key__"))
            pivot_on = ["__pt_c_key__"]

        need_prefix = len(metrics) > 1
        pivoted_dfs: list[pl.DataFrame] = []

        for m in metrics:
            prefix = m.out_name if need_prefix else None

            if m.src_col is None:
                m_df = work_df.with_columns(pl.lit(1).alias("__pt_n__"))
                val_col = "__pt_n__"
                agg_fn = "len"
            else:
                m_df = work_df
                val_col = m.src_col
                agg_fn = "len" if m.aggfunc in ("size", "len") else m.aggfunc

            native_aggs = ("min", "max", "first", "last", "mean", "median")
            if agg_fn in native_aggs:
                piv_m = m_df.pivot(
                    on=pivot_on[0] if len(pivot_on) == 1 else pivot_on,
                    index=r_cols,
                    values=val_col,
                    aggregate_function=cast(Any, agg_fn),
                    sort_columns=True,
                )
            else:
                grouped = m_df.group_by([*r_cols, *pivot_on]).agg(
                    _polars_agg_expr(pl.col(val_col), agg_fn).alias(val_col)
                )
                piv_m = grouped.pivot(
                    on=pivot_on[0] if len(pivot_on) == 1 else pivot_on,
                    index=r_cols,
                    values=val_col,
                    aggregate_function="first",
                    sort_columns=True,
                )

            data_cols = [c for c in piv_m.columns if c not in r_cols]
            if prefix:
                piv_m = piv_m.rename({c: f"{prefix}_{c}" for c in data_cols})
                data_cols = [f"{prefix}_{c}" for c in data_cols]

            if f_v is not None and not (isinstance(f_v, float) and str(f_v) == "nan"):
                piv_m = piv_m.with_columns([pl.col(c).fill_null(f_v) for c in data_cols])
            elif agg_fn in ("len", "count", "size") and f_v is None:
                piv_m = piv_m.with_columns([pl.col(c).fill_null(0) for c in data_cols])

            if agg_fn in ("len", "count", "size"):
                piv_m = piv_m.with_columns([pl.col(c).cast(pl.Int64) for c in data_cols])

            pivoted_dfs.append(piv_m)

        res = pivoted_dfs[0]
        for next_df in pivoted_dfs[1:]:
            res = res.join(next_df, on=r_cols, how="full", coalesce=True)

        res = res.sort(r_cols)
        return _clean_null_col(res)

    elif r_cols:
        exprs: list[pl.Expr] = []
        for m in metrics:
            if m.src_col is None or m.aggfunc in ("size", "len", "n"):
                expr = pl.len().cast(pl.Int64).alias(m.out_name)
            else:
                expr = _polars_agg_expr(pl.col(m.src_col), m.aggfunc).alias(m.out_name)
            exprs.append(expr)

        res = work_df.group_by(r_cols).agg(exprs).sort(r_cols)
        if f_v is not None and not (isinstance(f_v, float) and str(f_v) == "nan"):
            res = res.fill_null(f_v)
        return _clean_null_col(res)

    elif c_cols:
        pivot_on = c_cols
        if len(c_cols) > 1:
            col_exprs = [pl.col(col).cast(pl.String) for col in c_cols]
            work_df = work_df.with_columns(pl.concat_str(col_exprs, separator="_").alias("__pt_c_key__"))
            pivot_on = ["__pt_c_key__"]

        need_prefix = len(metrics) > 1
        if len(metrics) == 1:
            m = metrics[0]
            prefix = None

            if m.src_col is None:
                m_df = work_df.with_columns([pl.lit(1).alias("__pt_n__"), pl.lit(1).alias("__dummy__")])
                val_col = "__pt_n__"
                agg_fn = "len"
            else:
                m_df = work_df.with_columns(pl.lit(1).alias("__dummy__"))
                val_col = m.src_col
                agg_fn = "len" if m.aggfunc in ("size", "len") else m.aggfunc

            native_aggs = ("min", "max", "first", "last", "mean", "median")
            if agg_fn in native_aggs:
                piv_m = m_df.pivot(
                    on=pivot_on[0] if len(pivot_on) == 1 else pivot_on,
                    index="__dummy__",
                    values=val_col,
                    aggregate_function=cast(Any, agg_fn),
                    sort_columns=True,
                ).drop("__dummy__")
            else:
                grouped = m_df.group_by(["__dummy__", *pivot_on]).agg(
                    _polars_agg_expr(pl.col(val_col), agg_fn).alias(val_col)
                )
                piv_m = grouped.pivot(
                    on=pivot_on[0] if len(pivot_on) == 1 else pivot_on,
                    index="__dummy__",
                    values=val_col,
                    aggregate_function="first",
                    sort_columns=True,
                ).drop("__dummy__")

            data_cols = list(piv_m.columns)
            if prefix:
                piv_m = piv_m.rename({c: f"{prefix}_{c}" for c in data_cols})
                data_cols = [f"{prefix}_{c}" for c in data_cols]

            if f_v is not None and not (isinstance(f_v, float) and str(f_v) == "nan"):
                piv_m = piv_m.with_columns([pl.col(c).fill_null(f_v) for c in data_cols])
            elif agg_fn in ("len", "count", "size") and f_v is None:
                piv_m = piv_m.with_columns([pl.col(c).fill_null(0) for c in data_cols])

            if agg_fn in ("len", "count", "size"):
                piv_m = piv_m.with_columns([pl.col(c).cast(pl.Int64) for c in data_cols])

            return _clean_null_col(piv_m)
        else:
            rows: list[pl.DataFrame] = []
            for m in metrics:
                if m.src_col is None:
                    m_df = work_df.with_columns([pl.lit(1).alias("__pt_n__"), pl.lit(m.out_name).alias("metric")])
                    val_col = "__pt_n__"
                    agg_fn = "len"
                else:
                    m_df = work_df.with_columns(pl.lit(m.out_name).alias("metric"))
                    val_col = m.src_col
                    agg_fn = "len" if m.aggfunc in ("size", "len") else m.aggfunc

                native_aggs = ("min", "max", "first", "last", "mean", "median")
                if agg_fn in native_aggs:
                    piv_m = m_df.pivot(
                        on=pivot_on[0] if len(pivot_on) == 1 else pivot_on,
                        index="metric",
                        values=val_col,
                        aggregate_function=cast(Any, agg_fn),
                        sort_columns=True,
                    )
                else:
                    grouped = m_df.group_by(["metric", *pivot_on]).agg(
                        _polars_agg_expr(pl.col(val_col), agg_fn).alias(val_col)
                    )
                    piv_m = grouped.pivot(
                        on=pivot_on[0] if len(pivot_on) == 1 else pivot_on,
                        index="metric",
                        values=val_col,
                        aggregate_function="first",
                        sort_columns=True,
                    )
                rows.append(piv_m)

            res = pl.concat(rows, how="vertical")
            data_cols = [c for c in res.columns if c != "metric"]
            if f_v is not None and not (isinstance(f_v, float) and str(f_v) == "nan"):
                res = res.with_columns([pl.col(c).fill_null(f_v) for c in data_cols])
            return _clean_null_col(res)

    else:
        exprs = []
        for m in metrics:
            if m.src_col is None or m.aggfunc in ("size", "len", "n"):
                expr = pl.len().cast(pl.Int64).alias(m.out_name)
            else:
                expr = _polars_agg_expr(pl.col(m.src_col), m.aggfunc).alias(m.out_name)
            exprs.append(expr)

        res = work_df.select(exprs)
        if f_v is not None and not (isinstance(f_v, float) and str(f_v) == "nan"):
            res = res.fill_null(f_v)
        return _clean_null_col(res)


def _ast_to_polars_expr(
    node: ast.AST,
    col_names: set[str],
    col_map: dict[str, str],
    by: list[str] | None = None,
) -> pl.Expr:
    """Recursively convert a Python AST expression node to a Polars Expression."""
    if isinstance(node, ast.Expression):
        return _ast_to_polars_expr(node.body, col_names, col_map, by)
    if isinstance(node, ast.Constant):
        return pl.lit(node.value)
    if isinstance(node, ast.Name):
        if node.id in col_map:
            return pl.col(col_map[node.id])
        if node.id in col_names:
            return pl.col(node.id)
        if node.id == "n":
            expr = pl.len()
            return expr.over(by) if by else expr
        import difflib

        close = difflib.get_close_matches(str(node.id), [str(c) for c in col_names], n=1)
        hint = f" (did you mean '{close[0]}'?)" if close else ""
        raise KeyError(
            f"column '{node.id}' not found in DataFrame{hint}. "
            f"if you intended a string literal, quote it like '{node.id}'"
        )
    if isinstance(node, ast.BinOp):
        left = _ast_to_polars_expr(node.left, col_names, col_map, by)
        right = _ast_to_polars_expr(node.right, col_names, col_map, by)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise ValueError(f"Unsupported binary operator: {type(node.op)}")
    if isinstance(node, ast.UnaryOp):
        oprnd = _ast_to_polars_expr(node.operand, col_names, col_map, by)
        if isinstance(node.op, ast.USub):
            return -oprnd
        if isinstance(node.op, ast.UAdd):
            return oprnd
        if isinstance(node.op, (ast.Not, ast.Invert)):
            return ~oprnd
        raise ValueError(f"Unsupported unary operator: {type(node.op)}")
    if isinstance(node, ast.Compare):
        left = _ast_to_polars_expr(node.left, col_names, col_map, by)
        for op, comp in zip(node.ops, node.comparators):
            right = _ast_to_polars_expr(comp, col_names, col_map, by)
            if isinstance(op, ast.Eq):
                left = left == right
            elif isinstance(op, ast.NotEq):
                left = left != right
            elif isinstance(op, ast.Lt):
                left = left < right
            elif isinstance(op, ast.LtE):
                left = left <= right
            elif isinstance(op, ast.Gt):
                left = left > right
            elif isinstance(op, ast.GtE):
                left = left >= right
            else:
                raise ValueError(f"Unsupported comparison operator: {type(op)}")
        return left
    if isinstance(node, ast.BoolOp):
        vals = [_ast_to_polars_expr(v, col_names, col_map, by) for v in node.values]
        res = vals[0]
        for v in vals[1:]:
            if isinstance(node.op, ast.And):
                res = res & v
            elif isinstance(node.op, ast.Or):
                res = res | v
            else:
                raise ValueError(f"Unsupported bool op: {type(node.op)}")
        return res
    if isinstance(node, ast.IfExp):
        test = _ast_to_polars_expr(node.test, col_names, col_map, by)
        body = _ast_to_polars_expr(node.body, col_names, col_map, by)
        orelse = _ast_to_polars_expr(node.orelse, col_names, col_map, by)
        return pl.when(test).then(body).otherwise(orelse)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "map":
            raise ValueError(
                "In mutate, '.map()' method syntax is not supported. "
                "Use functional map(column, mapping, [default]) instead, e.g. map(species, {'Adelie': 'AD'}, 'OTHER')"
            )
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # 0. lit(...) or pt.lit(...) or pytae.lit(...)
        if (isinstance(node.func, ast.Name) and node.func.id == "lit") or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "lit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("pt", "pytae")
        ):
            if len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Constant):
                    return pl.lit(arg.value)
                if isinstance(arg, ast.Name):
                    return pl.lit(arg.id)
                try:
                    return pl.lit(ast.literal_eval(arg))
                except Exception:
                    pass
            elif len(node.args) == 0:
                return pl.lit(None)

        # 1. Attribute method calls (e.g. name.str.upper(), val.cumsum())
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "str":
                obj_expr = _ast_to_polars_expr(node.func.value.value, col_names, col_map, by)
                if attr_name in ("upper", "to_uppercase"):
                    return obj_expr.str.to_uppercase()
                elif attr_name in ("lower", "to_lowercase"):
                    return obj_expr.str.to_lowercase()
                elif attr_name in ("strip", "strip_chars"):
                    return obj_expr.str.strip_chars()
                elif attr_name in ("len", "len_chars"):
                    return obj_expr.str.len_chars()
            elif isinstance(node.func.value, (ast.Name, ast.Call, ast.BinOp, ast.Attribute)):
                obj_expr = _ast_to_polars_expr(node.func.value, col_names, col_map, by)
                if attr_name == "cumsum":
                    expr = obj_expr.cum_sum()
                    return expr.over(by) if by else expr
                elif attr_name == "cumprod":
                    expr = obj_expr.cum_prod()
                    return expr.over(by) if by else expr
                elif attr_name == "cummin":
                    expr = obj_expr.cum_min()
                    return expr.over(by) if by else expr
                elif attr_name == "cummax":
                    expr = obj_expr.cum_max()
                    return expr.over(by) if by else expr

        # 2. Functional map(...)
        if func_name == "map" and len(node.args) >= 2:
            col_expr = _ast_to_polars_expr(node.args[0], col_names, col_map, by)
            mapping_node = node.args[1]
            if isinstance(mapping_node, ast.Dict):
                mapping: dict[Any, Any] = {}
                for k_node, v_node in zip(mapping_node.keys, mapping_node.values):
                    if k_node is not None and isinstance(k_node, ast.Constant) and isinstance(v_node, ast.Constant):
                        mapping[k_node.value] = v_node.value
                    elif k_node is not None:
                        mapping[ast.literal_eval(k_node)] = ast.literal_eval(v_node)
            else:
                mapping = ast.literal_eval(mapping_node)

            default_val = None
            if len(node.args) > 2:
                def_node = node.args[2]
                if isinstance(def_node, ast.Constant):
                    default_val = def_node.value
                else:
                    default_val = ast.literal_eval(def_node)

            if hasattr(pl.Expr, "replace_strict"):
                expr = col_expr.replace_strict(mapping, default=cast(Any, default_val))
            else:
                expr = col_expr.replace(mapping, default=cast(Any, default_val))  # type: ignore[call-arg]
            return expr.over(by) if by else expr

        # 3. lit / pt.lit
        if func_name in ("lit", "pt.lit") and len(node.args) >= 1:
            arg = node.args[0]
            if isinstance(arg, ast.Constant):
                val = arg.value
            elif isinstance(arg, ast.Name):
                val = arg.id
            else:
                try:
                    val = ast.literal_eval(arg)
                except Exception:
                    val = getattr(arg, "value", getattr(arg, "id", str(arg)))
            return pl.lit(val)

        # 4. case_when
        if func_name == "case_when":
            if not node.args and not node.keywords:
                raise ValueError("case_when expects at least one (condition, value) pair")
            default_expr = pl.lit(None)
            for kw in node.keywords:
                if kw.arg == "default":
                    default_expr = _ast_to_polars_expr(kw.value, col_names, col_map, by)
            pairs: list[tuple[pl.Expr, pl.Expr]] = []
            has_tuple = any(isinstance(a, ast.Tuple) for a in node.args)
            if has_tuple:
                for i, a in enumerate(node.args):
                    if isinstance(a, ast.Tuple) and len(a.elts) == 2:
                        c = _ast_to_polars_expr(a.elts[0], col_names, col_map, by)
                        v = _ast_to_polars_expr(a.elts[1], col_names, col_map, by)
                        pairs.append((c, v))
                    elif i == len(node.args) - 1:
                        default_expr = _ast_to_polars_expr(a, col_names, col_map, by)
                    else:
                        raise ValueError("case_when default (non-tuple) must be the last argument")
            else:
                flat_args = list(node.args)
                if len(flat_args) % 2 == 1:
                    default_expr = _ast_to_polars_expr(flat_args.pop(), col_names, col_map, by)
                for i in range(0, len(flat_args), 2):
                    c = _ast_to_polars_expr(flat_args[i], col_names, col_map, by)
                    v = _ast_to_polars_expr(flat_args[i + 1], col_names, col_map, by)
                    pairs.append((c, v))

            if not pairs:
                raise ValueError("case_when expects at least one (condition, value) pair")

            any_str = any(
                (
                    isinstance(a, ast.Tuple)
                    and len(a.elts) == 2
                    and isinstance(a.elts[1], ast.Constant)
                    and isinstance(a.elts[1].value, str)
                )
                for a in node.args
            ) or any(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args)
            if any_str:
                pairs = [(c, v.cast(pl.String) if hasattr(v, "cast") else v) for c, v in pairs]
                if hasattr(default_expr, "cast"):
                    default_expr = default_expr.cast(pl.String)

            first_c, first_v = pairs[0]
            when_chain = pl.when(first_c).then(first_v)
            for c, v in pairs[1:]:
                when_chain = when_chain.when(c).then(v)
            expr = when_chain.otherwise(default_expr)
            return expr.over(by) if by else expr

        # 5. if_else
        if func_name == "if_else":
            if len(node.args) != 3:
                raise TypeError(
                    f"if_else requires exactly 3 arguments (condition, if_true, if_false), got {len(node.args)}"
                )
            c = _ast_to_polars_expr(node.args[0], col_names, col_map, by)
            t = _ast_to_polars_expr(node.args[1], col_names, col_map, by)
            f = _ast_to_polars_expr(node.args[2], col_names, col_map, by)
            if (isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)) or (
                isinstance(node.args[2], ast.Constant) and isinstance(node.args[2].value, str)
            ):
                t = t.cast(pl.String) if hasattr(t, "cast") else t
                f = f.cast(pl.String) if hasattr(f, "cast") else f
            expr = pl.when(c).then(t).otherwise(f)
            return expr.over(by) if by else expr

        args = [_ast_to_polars_expr(a, col_names, col_map, by) for a in node.args]

        agg_map = {
            "sum": lambda e: e.sum(),
            "mean": lambda e: e.mean(),
            "median": lambda e: e.median(),
            "min": lambda e: e.min(),
            "max": lambda e: e.max(),
            "std": lambda e: e.std(),
            "var": lambda e: e.var(),
            "rank": lambda e: e.rank(),
        }
        if func_name in agg_map and len(args) == 1:
            expr = agg_map[func_name](args[0])
            return expr.over(by) if by else expr
        if func_name in ("len", "count") and len(args) <= 1:
            expr = pl.len()
            return expr.over(by) if by else expr
        if func_name == "shift" and len(args) >= 1:
            shift_n = 1
            if len(node.args) > 1:
                arg1 = node.args[1]
                if isinstance(arg1, ast.Constant) and isinstance(arg1.value, (int, float)):
                    shift_n = int(arg1.value)
                elif (
                    isinstance(arg1, ast.UnaryOp)
                    and isinstance(arg1.op, ast.USub)
                    and isinstance(arg1.operand, ast.Constant)
                ):
                    shift_n = -int(arg1.operand.value)  # type: ignore[attr-defined]
            expr = args[0].shift(shift_n)
            return expr.over(by) if by else expr
        if func_name == "lead" and len(args) >= 1:
            shift_val = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else 1
            shift_n = int(shift_val) if isinstance(shift_val, (int, float)) else 1
            expr = args[0].shift(-shift_n)
            return expr.over(by) if by else expr
        if func_name == "lag" and len(args) >= 1:
            shift_val = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else 1
            shift_n = int(shift_val) if isinstance(shift_val, (int, float)) else 1
            expr = args[0].shift(shift_n)
            return expr.over(by) if by else expr
        if func_name == "round":
            dec_val = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else 0
            dec = int(dec_val) if isinstance(dec_val, (int, float)) else 0
            return args[0].round(dec)
        if func_name == "abs" and len(args) == 1:
            return args[0].abs()
        if func_name == "sqrt" and len(args) == 1:
            return args[0].sqrt()
        if func_name == "log" and len(args) == 1:
            return args[0].log()
        if func_name == "exp" and len(args) == 1:
            return args[0].exp()
        if func_name == "floor" and len(args) == 1:
            return args[0].floor()
        if func_name == "ceil" and len(args) == 1:
            return args[0].ceil()
        if func_name == "coalesce":
            return pl.coalesce(args)
        if func_name == "n" and len(args) == 0:
            expr = pl.len()
            return expr.over(by) if by else expr

    raise ValueError(f"Unsupported AST node: {type(node)}")


def mutate_polars(
    df: pl.DataFrame,
    parsed_spec: dict[str, Any],
    by: list[str] | None = None,
    params: dict[str, Any] | None = None,
    dropna: bool = False,
) -> pl.DataFrame:
    """Evaluate mutate expressions on a Polars DataFrame using native Polars vectorization."""
    cur = df
    for raw_col, raw_val in parsed_spec.items():
        cur_cols = set(_df_columns(cur))
        m_multi = re.match(r"^([^()]*)\(([^()]*)\)([^()]*)$", raw_col)
        if m_multi and isinstance(raw_val, str) and raw_col not in cur_cols:
            prefix, inner_spec, suffix = m_multi.groups()
            target_cols = _resolve_multi_target_cols(cur, inner_spec, by)
            expanded_pairs = [
                (f"{prefix}{tc}{suffix}", _replace_underscore_placeholder(raw_val, tc)) for tc in target_cols
            ]
        else:
            expanded_pairs = [(raw_col, raw_val)]

        for col_name, val in expanded_pairs:
            if isinstance(val, _Lit):
                cur = cur.with_columns(pl.lit(val.value).alias(col_name))
                continue
            if not isinstance(val, str):
                cur = cur.with_columns(pl.lit(val).alias(col_name))
                continue

            expr_str = val.strip()
            if "@" in expr_str:
                _, at_tokens = _strip_at_refs(expr_str)
                for var_name in at_tokens:
                    if params and var_name in params:
                        val_p = params[var_name]
                        expr_str = re.sub(rf"@{var_name}\b", repr(val_p), expr_str)
                    else:
                        all_avail = list(params.keys()) if params else []
                        import difflib

                        close = difflib.get_close_matches(var_name, all_avail, n=1)
                        hint = f" (did you mean '@{close[0]}'?)" if close else ""
                        raise KeyError(f"local variable '@{var_name}' is not defined{hint}")

            cur_cols = set(_df_columns(cur))
            safe_expr, col_map = _rewrite_fallback_col_refs(expr_str, cur_cols)
            try:
                parsed = ast.parse(safe_expr, mode="eval")
                expr = _ast_to_polars_expr(parsed, cur_cols, col_map, by=by)
                if dropna and by:
                    null_mask = pl.any_horizontal([pl.col(c).is_null() for c in by])
                    expr = pl.when(null_mask).then(pl.lit(None)).otherwise(expr)
                cur = cur.with_columns(expr.alias(col_name))
            except (pl.exceptions.InvalidOperationError, pl.exceptions.ComputeError) as exc:
                msg = str(exc).lower()
                if any(
                    term in msg
                    for term in (
                        "unsupported",
                        "cannot",
                        "arithmetic",
                        "operator",
                        "divide",
                        "division",
                        "add",
                        "sub",
                        "mul",
                    )
                ):
                    raise TypeError(str(exc)) from exc
                raise
    return cur


def pick_polars(
    df: pl.DataFrame,
    col: str,
    n: int | None = None,
    prop: float | None = None,
    order: str = "max",
    with_ties: bool = False,
    na_last: bool = True,
    by: list[str] | None = None,
) -> Any:
    """Select the rows with the largest (or smallest) values of a column, optionally grouped by 'by'."""
    clean_col = _unquote_name(col.strip())
    df_cols = _df_columns(df)
    if clean_col not in df_cols:
        raise KeyError(f"pick: column '{clean_col}' not found in DataFrame. Available columns: {df_cols}")

    if n is not None and prop is not None:
        raise ValueError("pick: specify either 'n' or 'prop', not both")

    if n is None and prop is None:
        n = 1

    clean_order = order.strip().lower() if isinstance(order, str) else "max"
    if clean_order not in ("max", "min"):
        raise ValueError(f"pick: order must be 'max' or 'min', got {order!r}")
    is_desc = clean_order == "max"

    if prop is not None:
        if not (0 < prop <= 1):
            raise ValueError(f"pick: 'prop' must be between 0 and 1, got {prop}")

    if by:
        unknown_by = [c for c in by if c not in df_cols]
        if unknown_by:
            raise KeyError(f"pick: grouping column(s) {unknown_by} not found in DataFrame")

        sort_cols = by + [clean_col]
        sort_desc = [False] * len(by) + [is_desc]
        sorted_df = df.sort(sort_cols, descending=sort_desc, nulls_last=na_last)

        if prop is not None:
            valid_cnt = pl.col(clean_col).drop_nulls().len().over(by)
            cutoff = (valid_cnt * prop).floor().cast(pl.Int64).clip(lower_bound=1)
            if with_ties:
                rank_expr = pl.col(clean_col).rank(method="min", descending=is_desc).over(by)
                return sorted_df.filter(rank_expr <= cutoff)
            row_nr = pl.int_range(1, pl.len() + 1).over(by)
            return sorted_df.filter(row_nr <= cutoff)

        assert n is not None
        if n <= 0:
            return df.head(0)
        if with_ties:
            rank_expr = pl.col(clean_col).rank(method="min", descending=is_desc).over(by)
            return sorted_df.filter(rank_expr <= n)
        return sorted_df.group_by(by, maintain_order=True).head(n)

    sorted_df = df.sort(clean_col, descending=is_desc, nulls_last=na_last)
    if prop is not None:
        cnt_expr = sorted_df.select(pl.col(clean_col).drop_nulls().len())
        valid_cnt = cnt_expr.collect().item() if isinstance(cnt_expr, pl.LazyFrame) else cnt_expr.item()
        k = max(1, int(valid_cnt * prop))
        if with_ties:
            return sorted_df.filter(pl.col(clean_col).rank(method="min", descending=is_desc) <= k)
        return sorted_df.head(k)

    assert n is not None
    if n <= 0:
        return df.head(0)
    if with_ties:
        return sorted_df.filter(pl.col(clean_col).rank(method="min", descending=is_desc) <= n)
    return sorted_df.head(n)


def value_counts_polars(
    df: Any,
    cols: list[str] | None = None,
    dropna: bool = False,
) -> Any:
    """Compute value counts across specified or all columns in a Polars DataFrame or LazyFrame."""
    df_cols = _df_columns(df)
    target_cols = cols if cols is not None else df_cols
    if "count" in target_cols and "n" in target_cols:
        raise ValueError(
            "-value_counts: columns contain both 'count' and 'n'; rename one to avoid ambiguous count headers"
        )

    count_name = "count" if "count" not in target_cols else "n"

    work_df = df
    if dropna:
        work_df = work_df.drop_nulls(subset=target_cols)

    return work_df.group_by(target_cols).len().rename({"len": count_name}).sort(count_name, descending=True)


def long_polars(
    df: pl.DataFrame,
    cols: str | Sequence[str] | None = None,
    id_vars: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
    **kwargs: Any,
) -> pl.DataFrame:
    """Unpivot a Polars DataFrame from wide to long format."""
    if kwargs:
        raise TypeError(f"long_polars() got unexpected keyword argument(s): {list(kwargs.keys())}")

    all_cols = _df_columns(df)

    def _norm_spec(spec: str | Sequence[str] | None, param_name: str) -> list[str] | None:
        if spec is None:
            return None
        if isinstance(spec, str):
            from pytae._text import tokenize as _tok

            items = [
                _unquote_name(item.strip())
                for item in _tok(spec, ",", keep_quotes=True, track_brackets=True)
                if item.strip()
            ]
        elif isinstance(spec, (list, tuple, set)):
            items = [_unquote_name(item) if isinstance(item, str) else item for item in spec]
        else:
            raise TypeError(f"{param_name} must be a column name or sequence of names, got {type(spec).__name__}")
        for item in items:
            if item not in all_cols:
                import difflib

                close = difflib.get_close_matches(str(item), [str(col) for col in all_cols], n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                raise KeyError(f"long(): {param_name} column '{item}' not found in DataFrame{hint}")
        return items

    melt_cols = _norm_spec(cols, "cols")
    keep_ids = _norm_spec(id_vars, "id_vars")

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
        schema = _df_schema(df)
        numeric_cols = [col for col, dtype in schema.items() if dtype.is_numeric()]
        if not numeric_cols:
            raise ValueError(
                "long(): no numeric columns to melt. "
                "Specify columns to melt via cols= (e.g. df.pt.long(cols=['q1', 'q2'])) "
                "or id_vars= (e.g. df.pt.long(id_vars=['id']))."
            )
        melt_cols = numeric_cols
        keep_ids = [col for col in all_cols if col not in melt_cols]

    if c == v:
        raise ValueError(
            f"long(): output variable column 'c' ({c!r}) and value column 'v' ({v!r}) cannot have the same name"
        )
    if c in keep_ids:
        raise ValueError(f"long(): output variable column 'c' ({c!r}) collides with kept id column(s)")
    if v in keep_ids:
        raise ValueError(f"long(): output value column 'v' ({v!r}) collides with kept id column(s)")
    if v in melt_cols:
        raise ValueError(f"long(): output value column 'v' ({v!r}) collides with melted column(s)")

    return df.unpivot(on=melt_cols, index=keep_ids, variable_name=c, value_name=v)


def wide_polars(
    df: Any,
    r: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
    **kwargs: Any,
) -> pl.DataFrame:
    """Reshape a long Polars DataFrame into wide format (1-to-1 pivot)."""
    if isinstance(df, pl.LazyFrame):
        df = df.collect()
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
        raise ValueError(
            "wide(): value column 'v' cannot be None. Specify the column to spread via v= (e.g. v='value')."
        )
    v = _unquote_name(v)
    if c == v:
        raise ValueError(f"wide(): 'c' and 'v' cannot be the same column ('{c}')")
    if c not in df.columns:
        raise KeyError(f"wide(): columns 'c' column '{c}' not found in DataFrame")
    if v not in df.columns:
        raise KeyError(f"wide(): values 'v' column '{v}' not found in DataFrame")

    if r is not None:
        if isinstance(r, str):
            from pytae._text import tokenize as _tok

            r_cols = [
                _unquote_name(col.strip()) for col in _tok(r, ",", keep_quotes=True, track_brackets=True) if col.strip()
            ]
        else:
            r_cols = [_unquote_name(col) if isinstance(col, str) else col for col in r]
        for col in r_cols:
            if col not in df.columns:
                raise KeyError(f"wide(): row 'r' column '{col}' not found in DataFrame")
        if c in r_cols:
            raise ValueError(f"wide(): column 'c' ('{c}') cannot also be in row 'r' columns")
        if v is not None and v in r_cols:
            raise ValueError(f"wide(): column 'v' ('{v}') cannot also be in row 'r' columns")
    else:
        r_cols = [col for col in df.columns if col not in [c, v]]

    distinct_c_vals = set(str(x) for x in df[c].unique().to_list())
    colliding = [col for col in r_cols if str(col) in distinct_c_vals]
    if colliding:
        raise ValueError(
            f"Resetting index failed: index level name(s) {colliding} collide with existing column name(s). "
            "Rename the column or index before resetting."
        )

    try:
        res = df.pivot(
            on=c,
            index=r_cols if r_cols else None,
            values=v,
            sort_columns=True,
        )
        if r_cols:
            res = res.sort(r_cols)
        return res
    except Exception as exc:
        raise ValueError(
            f"wide() encountered duplicate entries for row 'r' {r_cols} and column '{c}'. "
            "wide() is strictly for 1-to-1 reshaping without aggregation. "
            "Use pt.pivot() / -pivot to summarize or aggregate duplicate entries."
        ) from exc


def handle_missing_polars(
    df: Any,
    fillna: str | None = ".",
    numeric_fill: Any = 0,
    cols: Sequence[str] | None = None,
    preserve_categories: bool = True,
    **kwargs: Any,
) -> Any:
    """Fill missing values in a Polars DataFrame or LazyFrame with type-appropriate defaults."""
    df_cols = _df_columns(df)
    schema = _df_schema(df)
    target_cols = set(cols) if cols is not None else set(df_cols)
    exprs: list[pl.Expr] = []

    for c in df_cols:
        if c not in target_cols:
            exprs.append(pl.col(c))
            continue

        dtype = schema[c]
        if dtype.is_numeric():
            if numeric_fill == "mean":
                exprs.append(pl.col(c).fill_null(pl.col(c).mean()))
            elif numeric_fill == "median":
                exprs.append(pl.col(c).fill_null(pl.col(c).median()))
            elif numeric_fill is not None:
                exprs.append(pl.col(c).fill_null(numeric_fill))
            else:
                exprs.append(pl.col(c))
        elif dtype in (pl.String, pl.Null):
            fill_str = str(fillna) if fillna is not None else "."
            exprs.append(pl.col(c).cast(pl.String).fill_null(fill_str).str.strip_chars())
        elif dtype == pl.Categorical:
            fill_str = str(fillna) if fillna is not None else "."
            expr = pl.col(c).cast(pl.String).fill_null(fill_str)
            if preserve_categories:
                expr = expr.cast(pl.Categorical)
            exprs.append(expr)
        else:
            exprs.append(pl.col(c))

    return df.with_columns(exprs)


def replace_values_polars(
    df: Any,
    v: dict[Any, Any],
    c: str | Sequence[str] | None = None,
    exact: bool = True,
) -> Any:
    """Replace values in a Polars DataFrame or LazyFrame (exact or substring)."""
    df_cols = _df_columns(df)
    schema = _df_schema(df)
    target_cols = ([c] if isinstance(c, str) else list(c)) if c is not None else list(df_cols)
    if not exact:
        non_string_cols = [col for col in target_cols if schema[col] not in (pl.String, pl.Utf8)]
        if non_string_cols:
            raise ValueError(
                f"replace_values: exact=False (substring match) only works on string/object "
                f"columns; non-string column(s): {non_string_cols}"
            )
        exprs: list[pl.Expr] = []
        for col in df_cols:
            if col in target_cols:
                col_expr = pl.col(col)
                for old_val, new_val in v.items():
                    col_expr = col_expr.str.replace_all(re.escape(str(old_val)), str(new_val))
                exprs.append(col_expr)
            else:
                exprs.append(pl.col(col))
        return df.with_columns(exprs)

    exprs = []
    for col in df_cols:
        if col in target_cols:
            mapping = {k: v_val for k, v_val in v.items()}
            exprs.append(pl.col(col).replace(mapping))
        else:
            exprs.append(pl.col(col))
    return df.with_columns(exprs)


def clean_columns_polars(df: Any, **opts: Any) -> Any:
    """Clean column header names in a Polars DataFrame or LazyFrame."""
    from pytae.other_utilities import clean_column_names

    old_cols = _df_columns(df)
    new_cols = clean_column_names(old_cols, **opts)
    if new_cols == old_cols:
        return df
    if len(set(new_cols)) < len(new_cols):
        raise ValueError("clean_columns resulted in duplicate column names; set dedupe=True to auto-disambiguate")
    mapping = dict(zip(old_cols, new_cols))
    return df.rename(mapping)


def agg_polars(
    df: Any,
    *specs: Any,
    by: list[str] | Sequence[str] | None = None,
    a: Any = None,
    dropna: bool = False,
    **kwargs: Any,
) -> Any:
    """Aggregate a Polars DataFrame or LazyFrame by group or across the whole table."""
    if "by" in kwargs or "_by" in kwargs:
        raise TypeError(
            "agg() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col')."
        )

    if isinstance(a, dict):
        raise TypeError("agg() no longer accepts dictionaries. Use kwargs (col='sum') or strings.")
    for s in specs:
        if isinstance(s, dict):
            raise TypeError("agg() no longer accepts dictionaries. Use kwargs (col='sum') or strings.")

    if a is not None and specs:
        raise TypeError("agg(): multiple values for aggregation spec: both positional args and 'a' were provided")

    if "drop_nulls" in kwargs:
        dropna = kwargs.pop("drop_nulls")
    by_cols: list[str] = list(by) if by else []
    work_df = df
    if by_cols and dropna:
        work_df = work_df.drop_nulls(subset=by_cols)

    exprs: list[pl.Expr] = []
    output_names: list[str] = []

    def _add_expr(e: pl.Expr, name: str) -> None:
        if name in by_cols:
            raise ValueError(f"agg(): output column name '{name}' collides with group column '{name}'")
        if name in output_names:
            raise ValueError(f"agg(): output column name '{name}' is duplicated in aggregation specification")
        output_names.append(name)
        exprs.append(e.alias(name))

    active_kwargs: dict[str, Any] = {}
    remaining_specs: list[Any] = []

    raw_items = list(specs)
    if a is not None:
        if specs:
            raise TypeError("agg(): multiple values for aggregation spec: both positional args and 'a' were provided")
        raw_items = [a] if not isinstance(a, (list, tuple)) else list(a)

    for item in raw_items:
        if isinstance(item, str) and ("=" in item or ":" in item):
            from pytae.cli_parsing import parse_agg

            parsed = parse_agg(item)
            if isinstance(parsed, dict):
                active_kwargs.update(parsed)
            else:
                remaining_specs.append(item)
        else:
            remaining_specs.append(item)

    if kwargs:
        active_kwargs.update(kwargs)

    if "__dropna__" in active_kwargs:
        dropna = active_kwargs.pop("__dropna__")
        if by_cols and dropna:
            work_df = work_df.drop_nulls(subset=by_cols)
    if "drop_nulls" in active_kwargs:
        dropna = active_kwargs.pop("drop_nulls")
        if by_cols and dropna:
            work_df = work_df.drop_nulls(subset=by_cols)
    if "dropna" in active_kwargs:
        dropna = active_kwargs.pop("dropna")
        if by_cols and dropna:
            work_df = work_df.drop_nulls(subset=by_cols)

    if active_kwargs and remaining_specs and specs:
        raise ValueError("agg(): cannot mix whole-frame aggregation with keyword arguments")

    if active_kwargs:
        for out_name, val in active_kwargs.items():
            clean_out = _unquote_name(out_name)
            if val in ("n", "count", "size") or val == ["n"] or val == ("n",):
                if "n" in by_cols and clean_out == "n":
                    raise ValueError("agg(): count 'n' collides with group column 'n'")
                _add_expr(pl.len().cast(pl.Int64), clean_out)
            elif isinstance(val, str) and ":" in val:
                src, fn_str = val.split(":", 1)
                src = _unquote_name(src.strip())
                fn_list = [f.strip() for f in fn_str.split(",") if f.strip()]
                if len(fn_list) > 1:
                    for f in fn_list:
                        _add_expr(_polars_agg_expr(pl.col(src), f), f"{clean_out}_{f}")
                else:
                    _add_expr(_polars_agg_expr(pl.col(src), fn_list[0]), clean_out)
            elif isinstance(val, str):
                fn_list = [f.strip() for f in val.split(",") if f.strip()]
                if len(fn_list) > 1:
                    for f in fn_list:
                        _add_expr(_polars_agg_expr(pl.col(clean_out), f), f"{clean_out}_{f}")
                else:
                    _add_expr(_polars_agg_expr(pl.col(clean_out), fn_list[0]), clean_out)
            elif isinstance(val, (list, tuple)):
                fn_list = list(val)
                if len(fn_list) > 1:
                    for f in fn_list:
                        _add_expr(_polars_agg_expr(pl.col(clean_out), f), f"{clean_out}_{f}")
                else:
                    _add_expr(_polars_agg_expr(pl.col(clean_out), fn_list[0]), clean_out)
            else:
                raise ValueError(f"agg(): unsupported kwargs specification {clean_out}={val!r}")
    else:
        items_to_process = remaining_specs if remaining_specs else ["sum"]
        flat_fns: list[str] = []
        for item in items_to_process:
            if isinstance(item, (list, tuple)):
                for sub in item:
                    if isinstance(sub, str) and "," in sub:
                        flat_fns.extend([p.strip() for p in sub.split(",") if p.strip()])
                    else:
                        flat_fns.append(str(sub).strip())
            elif isinstance(item, str):
                if "," in item:
                    flat_fns.extend([p.strip() for p in item.split(",") if p.strip()])
                else:
                    flat_fns.append(item.strip())
            else:
                flat_fns.append(str(item).strip())

        known_aggs = {
            "sum",
            "mean",
            "median",
            "min",
            "max",
            "std",
            "var",
            "first",
            "last",
            "n",
            "count",
            "size",
            "nunique",
            "n_unique",
        }
        for fn in flat_fns:
            if fn not in known_aggs:
                raise ValueError(f"agg(): unsupported aggregation function or invalid syntax '{fn}'")

        unique_fns = list(dict.fromkeys(flat_fns))
        has_n = any(f in ("n", "count", "size") for f in unique_fns)
        rem_fns = [f for f in unique_fns if f not in ("n", "count", "size")]
        num_cols = [c for c, dt in _df_schema(work_df).items() if dt.is_numeric() and c not in by_cols]

        if has_n and "n" in num_cols:
            raise ValueError(
                "agg(): cannot compute 'n' (row count) because the input already has a numeric column named 'n'"
            )
        if has_n and "n" in by_cols:
            raise ValueError("agg(): count 'n' collides with group column 'n'")

        if has_n:
            _add_expr(pl.len().cast(pl.Int64), "n")

        for c in num_cols:
            for fn in rem_fns:
                col_name = f"{c}_{fn}" if len(rem_fns) > 1 else c
                _add_expr(_polars_agg_expr(pl.col(c), fn), col_name)

    if not exprs:
        raise ValueError("agg(): no aggregation expressions could be constructed")

    if by_cols:
        res = work_df.group_by(by_cols).agg(exprs).sort(by_cols, nulls_last=True)
    else:
        res = work_df.select(exprs)
    return res
