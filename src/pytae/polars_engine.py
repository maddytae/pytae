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
    _replace_underscore_placeholder,
    _resolve_multi_target_cols,
    _rewrite_fallback_col_refs,
    _strip_at_refs,
)
from pytae._text import _ColRef
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
    if schema is not None and col not in schema and ("." in col or "(" in col):
        cur_cols = set(schema.names())
        safe_expr, col_map = _rewrite_fallback_col_refs(col, cur_cols)
        parsed = ast.parse(safe_expr, mode="eval")
        col_expr = _ast_to_polars_expr(parsed, cur_cols, col_map, schema=schema)
        is_numeric = False
        is_string = False
        is_date = False
        is_datetime = False
    else:
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
        elif is_string and not isinstance(val, (str, bytes)):
            if val is not None:
                raise TypeError(
                    f"filter(): column '{col}' has String type, but received {type(val).__name__} {val!r}. "
                    f"String values must be enclosed in quotes (e.g. {col} = '{val}')."
                )
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
            raise ValueError(
                f"filter(): 1-tuple pattern {cond!r} on column {col!r} is not supported. "
                f"In line with 'one and only one obvious way', use predicate expressions instead, "
                f"e.g. filter('{col}.notna()') or filter('{col}.isna()')."
            )
        elif len(cond) == 2:
            op, val = cond
            if op == "isna":
                return col_expr.is_null()
            if op == "notna":
                return col_expr.is_not_null()
            if op == "in":
                vals = [_coerce_val(v) for v in val] if isinstance(val, (list, tuple)) else val
                return col_expr.is_in(vals)
            if op == "not in":
                vals = [_coerce_val(v) for v in val] if isinstance(val, (list, tuple)) else val
                return ~col_expr.is_in(vals)
            if op == "startswith":
                if isinstance(val, (list, tuple)):
                    for v in val:
                        _coerce_val(v)
                    if not val:
                        return pl.lit(False)
                    return pl.any_horizontal([col_expr.cast(pl.String).str.starts_with(str(v)) for v in val])
                _coerce_val(val)
                return col_expr.cast(pl.String).str.starts_with(str(val))
            if op == "endswith":
                if isinstance(val, (list, tuple)):
                    for v in val:
                        _coerce_val(v)
                    if not val:
                        return pl.lit(False)
                    return pl.any_horizontal([col_expr.cast(pl.String).str.ends_with(str(v)) for v in val])
                _coerce_val(val)
                return col_expr.cast(pl.String).str.ends_with(str(val))
            if op == "contains":
                if isinstance(val, (list, tuple)):
                    for v in val:
                        _coerce_val(v)
                    if not val:
                        return pl.lit(False)
                    return pl.any_horizontal([col_expr.cast(pl.String).str.contains(str(v), literal=True) for v in val])
                _coerce_val(val)
                return col_expr.cast(pl.String).str.contains(str(val), literal=True)
            if op == "regex":
                if isinstance(val, (list, tuple)):
                    for v in val:
                        _coerce_val(v)
                    if not val:
                        return pl.lit(False)
                    return pl.any_horizontal([col_expr.cast(pl.String).str.contains(str(v)) for v in val])
                _coerce_val(val)
                return col_expr.cast(pl.String).str.contains(str(val))

            if isinstance(val, _ColRef):
                if schema is not None and val in schema:
                    rhs = pl.col(str(val))
                else:
                    import difflib

                    avail = list(schema.names()) if schema is not None else []
                    close = difflib.get_close_matches(str(val), avail, n=1)
                    hint = f" (did you mean '{close[0]}'?)" if close else ""
                    raise KeyError(
                        f"column '{val}' not found in DataFrame{hint}. "
                        f"if you intended a string literal, quote it like '{val}'"
                    )
                if op == "==":
                    return col_expr == rhs
                if op == "!=":
                    return col_expr != rhs
                if op == ">":
                    return col_expr > rhs
                if op == ">=":
                    return col_expr >= rhs
                if op == "<":
                    return col_expr < rhs
                if op == "<=":
                    return col_expr <= rhs
            elif isinstance(val, pl.Expr):
                if op == "==":
                    return col_expr == val
                if op == "!=":
                    return col_expr != val
                if op == ">":
                    return col_expr > val
                if op == ">=":
                    return col_expr >= val
                if op == "<":
                    return col_expr < val
                if op == "<=":
                    return col_expr <= val

            cval = _coerce_val(val)
            if op == "==":
                if cval is None or str(cval).lower() in ("none", "null"):
                    return col_expr.is_null()
                return col_expr == cval
            if op == "!=":
                if cval is None or str(cval).lower() in ("none", "null"):
                    return col_expr.is_not_null()
                return col_expr != cval
            if op == ">":
                return col_expr > cval
            if op == ">=":
                return col_expr >= cval
            if op == "<":
                return col_expr < cval
            if op == "<=":
                return col_expr <= cval

    if isinstance(cond, str):
        cond_clean = cond.strip().lower()
        if cond_clean in ("notna", "is_not_null", "not_null", "not null"):
            return col_expr.is_not_null()
        if cond_clean in ("isna", "is_null", "null"):
            return col_expr.is_null()

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
            if len(sub_raw) >= 2 and sub_raw[0] in "'\"" and sub_raw[-1] == sub_raw[0]:
                sub_val = sub_raw[1:-1]
            else:
                try:
                    sub_val = ast.literal_eval(sub_raw)
                except (ValueError, SyntaxError):
                    sub_val = _ColRef(_unquote_name(sub_raw))
            return _cond_to_polars_expr(col, (op, sub_val), schema=schema)

    # Default direct scalar equality or column reference
    if isinstance(cond, _ColRef):
        if schema is not None and cond in schema:
            return col_expr == pl.col(str(cond))
        else:
            import difflib

            avail = list(schema.names()) if schema is not None else []
            close = difflib.get_close_matches(str(cond), avail, n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(
                f"column '{cond}' not found in DataFrame{hint}. "
                f"if you intended a string literal, quote it like '{cond}'"
            )
    if isinstance(cond, pl.Expr):
        return col_expr == cond

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


def count_polars(
    df: Any,
    cols: Sequence[str] | None = None,
    sort: bool = True,
    name: str = "n",
) -> Any:
    """Count occurrences of unique combinations of columns (or total rows)."""
    import polars as pl

    col_list = list(cols) if cols else []
    if col_list:
        if name in col_list:
            raise ValueError(
                f"count(): count column '{name}' collides with group column '{name}'. "
                f"Use name='...' to specify a distinct output column name."
            )
        schema = _df_schema(df)
        for c in col_list:
            if c not in schema:
                raise KeyError(f"count(): unknown column '{c}'")
        counted = df.group_by(col_list, maintain_order=True).agg(
            pl.len().cast(pl.Int64).alias(name)
        )
        if sort:
            counted = counted.sort(name, descending=True)
        return counted
    else:
        if isinstance(df, pl.LazyFrame):
            return df.select(pl.len().cast(pl.Int64).alias(name))
        return pl.DataFrame({name: pl.Series(name, [len(df)], dtype=pl.Int64)})


def dropna_polars(
    df: Any,
    cols: list[str] | Sequence[str] | None = None,
    *,
    how: str | None = None,
    drop_nans: bool = True,
) -> Any:
    """Drop rows containing missing values (Arrow null and/or float NaN).

    Zero-Data-Loss Safety Defaults:
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


def fillna_polars(
    df: Any,
    value: Any = None,
    *cols: Any,
    subset: Any = None,
    nans: bool = True,
    **kwargs: Any,
) -> Any:
    """Fill missing values (Arrow null and/or float NaN) in a Polars DataFrame or LazyFrame."""
    import polars as pl

    if value is None and kwargs:
        value = dict(kwargs)

    if value is None:
        raise TypeError("fillna() missing required argument: 'value'")

    schema = _df_schema(df)
    target_cols = list(subset) if subset is not None else (list(cols) if cols else None)

    def _fill_col_expr(c: str, dt: pl.DataType, fill_val: Any) -> pl.Expr:
        if dt.is_float() and nans and isinstance(fill_val, (int, float)) and not isinstance(fill_val, bool):
            return pl.col(c).fill_nan(fill_val).fill_null(fill_val)
        if dt == pl.Categorical and isinstance(fill_val, str):
            return pl.col(c).cast(pl.String).fill_null(fill_val).cast(pl.Categorical)
        if dt == pl.Null:
            target_dt = (
                pl.String
                if isinstance(fill_val, str)
                else (
                    pl.Boolean
                    if isinstance(fill_val, bool)
                    else (pl.Float64 if isinstance(fill_val, float) else pl.Int64)
                )
            )
            return pl.col(c).cast(target_dt).fill_null(fill_val)
        return pl.col(c).fill_null(fill_val)

    # If value is a string with col:val or col=val pairs matching schema columns
    if isinstance(value, str) and not target_cols and (":" in value or "=" in value):
        from pytae._text import tokenize as _tok

        tokens = [t.strip() for t in _tok(value, ",", keep_quotes=True, track_brackets=True) if t.strip()]
        parsed_map: dict[str, Any] = {}
        is_mapping = bool(tokens)
        for tok in tokens:
            sep = ":" if ":" in tok else ("=" if "=" in tok else None)
            if not sep:
                is_mapping = False
                break
            k_raw, v_raw = tok.split(sep, 1)
            k_clean = _unquote_name(k_raw.strip())
            if k_clean not in schema:
                is_mapping = False
                break
            v_strip = v_raw.strip()
            try:
                v_val = ast.literal_eval(v_strip)
            except Exception:
                v_val = _unquote_name(v_strip)
            parsed_map[k_clean] = v_val
        if is_mapping:
            value = parsed_map

    # 1. Dictionary fill: {col_name: fill_value}
    if isinstance(value, dict):
        missing = [str(c) for c in value if str(c) not in schema]
        if missing:
            raise KeyError(f"fillna: column(s) {missing} not found in DataFrame")
        exprs = [_fill_col_expr(str(col_name), schema[str(col_name)], fill_val) for col_name, fill_val in value.items()]
        return df.with_columns(exprs) if exprs else df

    # 2. Targeted subset/cols with a scalar value
    if target_cols:
        missing = [str(c) for c in target_cols if str(c) not in schema]
        if missing:
            raise KeyError(f"fillna: column(s) {missing} not found in DataFrame")
        exprs = [_fill_col_expr(str(c), schema[str(c)], value) for c in target_cols]
        return df.with_columns(exprs) if exprs else df

    # 3. Whole-table fill with scalar value (scoped to compatible column types)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        exprs = [_fill_col_expr(c, dt, value) for c, dt in schema.items() if dt.is_numeric()]
        return df.with_columns(exprs) if exprs else df

    if isinstance(value, str):
        exprs = [
            _fill_col_expr(c, dt, value)
            for c, dt in schema.items()
            if dt in (pl.String, pl.Utf8, pl.Null, pl.Categorical)
        ]
        return df.with_columns(exprs) if exprs else df

    if isinstance(value, bool):
        exprs = [_fill_col_expr(c, dt, value) for c, dt in schema.items() if dt == pl.Boolean]
        return df.with_columns(exprs) if exprs else df

    return df.fill_null(value)


def rename_polars(df: Any, mapping: dict[str, str]) -> Any:
    """Rename columns in a Polars DataFrame or LazyFrame."""
    return df.rename(mapping)


def sql_polars(df: Any, query: str) -> Any:
    """Execute a SQL query against a Polars DataFrame or LazyFrame (registered as 'data' and 'self')."""
    from pytae.cli_parsing import normalize_sql

    normalized_query = normalize_sql(query)
    polars_query = re.sub(r"\bin\s*\[(.*?)\]", r"in (\1)", normalized_query, flags=re.IGNORECASE)
    ctx = pl.SQLContext(frames={"data": df, "self": df})
    res_lazy = ctx.execute(polars_query)
    return res_lazy if isinstance(df, pl.LazyFrame) else res_lazy.collect()


def _polars_agg_expr(col: pl.Expr, func: str) -> pl.Expr:
    fn = func.lower()
    if fn == "sum":
        return col.sum()
    elif fn in ("mean", "avg"):
        return col.mean()
    elif fn in ("median",):
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
    if kwargs:
        raise TypeError(
            f"{_func_name}() got unexpected keyword argument(s): {list(kwargs.keys())}; only r, c, v, a, dropna, f_v are accepted"
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
                "For row counts (a='count'), omit 'v' or specify a non-grouping column."
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
                        "For row counts (a='count'), omit 'v' or specify a non-colliding column name."
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


def _is_float_or_numeric_expr(node: ast.AST, schema: Any | None) -> bool:
    if schema is None:
        return True
    if isinstance(node, ast.Name):
        col_type = schema.get(node.id)
        if col_type is not None:
            return getattr(col_type, "is_float", lambda: False)() or getattr(col_type, "is_numeric", lambda: False)()
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Div):
            return True
        return _is_float_or_numeric_expr(node.left, schema) or _is_float_or_numeric_expr(node.right, schema)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in ("sqrt", "log", "exp", "mean", "std", "var"):
            return True
    return True


_DTYPE_MAP: dict[str, pl.DataType] = {
    "int": pl.Int64(),
    "int64": pl.Int64(),
    "i64": pl.Int64(),
    "integer": pl.Int64(),
    "bigint": pl.Int64(),
    "int32": pl.Int32(),
    "i32": pl.Int32(),
    "int16": pl.Int16(),
    "i16": pl.Int16(),
    "smallint": pl.Int16(),
    "int8": pl.Int8(),
    "i8": pl.Int8(),
    "tinyint": pl.Int8(),
    "uint64": pl.UInt64(),
    "u64": pl.UInt64(),
    "uint32": pl.UInt32(),
    "u32": pl.UInt32(),
    "uint16": pl.UInt16(),
    "u16": pl.UInt16(),
    "uint8": pl.UInt8(),
    "u8": pl.UInt8(),
    "float": pl.Float64(),
    "float64": pl.Float64(),
    "f64": pl.Float64(),
    "double": pl.Float64(),
    "float32": pl.Float32(),
    "f32": pl.Float32(),
    "str": pl.String(),
    "string": pl.String(),
    "varchar": pl.String(),
    "text": pl.String(),
    "bool": pl.Boolean(),
    "boolean": pl.Boolean(),
    "date": pl.Date(),
    "datetime": pl.Datetime(),
    "timestamp": pl.Datetime(),
}


def _ast_to_polars_expr(
    node: ast.AST,
    col_names: set[str],
    col_map: dict[str, str],
    by: list[str] | None = None,
    schema: Any | None = None,
    params: dict[str, Any] | None = None,
) -> pl.Expr:
    """Recursively convert a Python AST expression node to a Polars Expression."""
    if isinstance(node, ast.Expression):
        return _ast_to_polars_expr(node.body, col_names, col_map, by, schema, params)
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
        left = _ast_to_polars_expr(node.left, col_names, col_map, by, schema, params)
        right = _ast_to_polars_expr(node.right, col_names, col_map, by, schema, params)
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
        if isinstance(node.op, ast.BitOr):
            return left | right
        if isinstance(node.op, ast.BitAnd):
            return left & right
        if isinstance(node.op, ast.BitXor):
            return left ^ right
        raise ValueError(f"Unsupported binary operator: {type(node.op)}")
    if isinstance(node, ast.UnaryOp):
        oprnd = _ast_to_polars_expr(node.operand, col_names, col_map, by, schema, params)
        if isinstance(node.op, ast.USub):
            return -oprnd
        if isinstance(node.op, ast.UAdd):
            return oprnd
        if isinstance(node.op, (ast.Not, ast.Invert)):
            return ~oprnd
        raise ValueError(f"Unsupported unary operator: {type(node.op)}")
    if isinstance(node, ast.Compare):
        left = _ast_to_polars_expr(node.left, col_names, col_map, by, schema, params)
        for op, comp in zip(node.ops, node.comparators):
            right = _ast_to_polars_expr(comp, col_names, col_map, by, schema, params)
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
        vals = [_ast_to_polars_expr(v, col_names, col_map, by, schema, params) for v in node.values]
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
        test = _ast_to_polars_expr(node.test, col_names, col_map, by, schema, params)
        body = _ast_to_polars_expr(node.body, col_names, col_map, by, schema, params)
        orelse = _ast_to_polars_expr(node.orelse, col_names, col_map, by, schema, params)
        return pl.when(test).then(body).otherwise(orelse)
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Attribute) and node.value.attr == "dt":
            obj_expr = _ast_to_polars_expr(node.value.value, col_names, col_map, by, schema, params)
            dt_prop = node.attr
            dt_map = {
                "year": lambda e: e.dt.year(),
                "quarter": lambda e: e.dt.quarter(),
                "month": lambda e: e.dt.month(),
                "day": lambda e: e.dt.day(),
                "weekday": lambda e: e.dt.weekday(),
                "ordinal_day": lambda e: e.dt.ordinal_day(),
                "dayofyear": lambda e: e.dt.ordinal_day(),
                "hour": lambda e: e.dt.hour(),
                "minute": lambda e: e.dt.minute(),
                "second": lambda e: e.dt.second(),
                "date": lambda e: e.dt.date(),
            }
            if dt_prop in dt_map:
                return dt_map[dt_prop](obj_expr)
            raise ValueError(f"Unsupported .dt attribute: '{dt_prop}'")
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "map":
            raise ValueError(
                "In mutate, '.map()' method syntax is not supported. "
                "Use functional map(column, mapping, [default]) instead, e.g. map(species, {'Adelie': 'AD'})"
            )
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # 1. Attribute method calls (e.g. name.str.upper(), order_date.dt.strftime('%Y-%m'), val.cumsum(), val.fillna(0))
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "dt":
                obj_expr = _ast_to_polars_expr(node.func.value.value, col_names, col_map, by, schema, params)
                dt_map = {
                    "year": lambda e: e.dt.year(),
                    "quarter": lambda e: e.dt.quarter(),
                    "month": lambda e: e.dt.month(),
                    "day": lambda e: e.dt.day(),
                    "weekday": lambda e: e.dt.weekday(),
                    "ordinal_day": lambda e: e.dt.ordinal_day(),
                    "dayofyear": lambda e: e.dt.ordinal_day(),
                    "hour": lambda e: e.dt.hour(),
                    "minute": lambda e: e.dt.minute(),
                    "second": lambda e: e.dt.second(),
                    "date": lambda e: e.dt.date(),
                }
                if attr_name in dt_map:
                    return dt_map[attr_name](obj_expr)
                if (
                    attr_name in ("strftime", "to_string")
                    and len(node.args) >= 1
                    and isinstance(node.args[0], ast.Constant)
                ):
                    return obj_expr.dt.strftime(str(node.args[0].value))
                if attr_name == "truncate" and len(node.args) >= 1 and isinstance(node.args[0], ast.Constant):
                    return obj_expr.dt.truncate(str(node.args[0].value))
                raise ValueError(f"Unsupported .dt method: '{attr_name}'")
            elif isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "str":
                obj_expr = _ast_to_polars_expr(node.func.value.value, col_names, col_map, by, schema, params)
                if attr_name in ("upper", "to_uppercase"):
                    return obj_expr.str.to_uppercase()
                elif attr_name in ("lower", "to_lowercase"):
                    return obj_expr.str.to_lowercase()
                elif attr_name in ("title", "to_titlecase"):
                    return obj_expr.str.to_titlecase()
                elif attr_name in ("strip", "strip_chars"):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        return obj_expr.str.strip_chars(str(node.args[0].value))
                    return obj_expr.str.strip_chars()
                elif attr_name in ("len", "len_chars"):
                    return obj_expr.str.len_chars()
                elif attr_name in ("replace", "replace_all") and len(node.args) >= 2:
                    literal = True
                    for kw in node.keywords:
                        if kw.arg == "literal" and isinstance(kw.value, ast.Constant):
                            literal = bool(kw.value.value)
                        elif kw.arg == "regex" and isinstance(kw.value, ast.Constant):
                            literal = not bool(kw.value.value)
                    pat = (
                        str(node.args[0].value)
                        if isinstance(node.args[0], ast.Constant)
                        else _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
                    )
                    repl = (
                        str(node.args[1].value)
                        if isinstance(node.args[1], ast.Constant)
                        else _ast_to_polars_expr(node.args[1], col_names, col_map, by, schema, params)
                    )
                    return obj_expr.str.replace_all(pat, repl, literal=literal)
                elif attr_name == "slice" and len(node.args) >= 1:
                    offset = (
                        int(node.args[0].value)
                        if isinstance(node.args[0], ast.Constant)
                        else _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
                    )
                    if len(node.args) >= 2:
                        length = (
                            int(node.args[1].value)
                            if isinstance(node.args[1], ast.Constant)
                            else _ast_to_polars_expr(node.args[1], col_names, col_map, by, schema, params)
                        )
                        return obj_expr.str.slice(offset, length)
                    return obj_expr.str.slice(offset)
                elif attr_name == "extract" and len(node.args) >= 1:
                    pat = str(node.args[0].value) if isinstance(node.args[0], ast.Constant) else ""
                    grp = (
                        int(node.args[1].value) if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) else 1
                    )
                    return obj_expr.str.extract(pat, group_index=grp)
                elif attr_name == "zfill" and len(node.args) >= 1 and isinstance(node.args[0], ast.Constant):
                    return obj_expr.str.zfill(int(node.args[0].value))
                elif attr_name == "contains" and len(node.args) >= 1:
                    literal = False
                    for kw in node.keywords:
                        if kw.arg == "literal" and isinstance(kw.value, ast.Constant):
                            literal = bool(kw.value.value)
                    if isinstance(node.args[0], ast.Constant):
                        pat_val = str(node.args[0].value)
                        return obj_expr.str.contains(pat_val, literal=literal)
                    pat_expr = _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
                    return obj_expr.str.contains(pat_expr, literal=literal)
                elif attr_name in ("startswith", "starts_with") and len(node.args) >= 1:
                    if isinstance(node.args[0], ast.Constant):
                        return obj_expr.str.starts_with(str(node.args[0].value))
                    pat_expr = _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
                    return obj_expr.str.starts_with(pat_expr)
                elif attr_name in ("endswith", "ends_with") and len(node.args) >= 1:
                    if isinstance(node.args[0], ast.Constant):
                        return obj_expr.str.ends_with(str(node.args[0].value))
                    pat_expr = _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
                    return obj_expr.str.ends_with(pat_expr)
            elif isinstance(node.func.value, (ast.Name, ast.Call, ast.BinOp, ast.Attribute)) and attr_name in (
                "is_null",
                "is_not_null",
                "is_nan",
                "is_not_nan",
                "cumsum",
                "cumprod",
                "cummin",
                "cummax",
                "fillna",
                "first",
                "last",
            ):
                obj_expr = _ast_to_polars_expr(node.func.value, col_names, col_map, by, schema, params)
                if attr_name == "is_null":
                    expr = obj_expr.is_null()
                    return expr.over(by) if by else expr
                elif attr_name == "is_not_null":
                    expr = obj_expr.is_not_null()
                    return expr.over(by) if by else expr
                elif attr_name == "is_nan":
                    expr = obj_expr.is_nan()
                    return expr.over(by) if by else expr
                elif attr_name == "is_not_nan":
                    expr = obj_expr.is_not_nan()
                    return expr.over(by) if by else expr
                elif attr_name == "cumsum":
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
                elif attr_name == "first":
                    expr = obj_expr.first()
                    return expr.over(by) if by else expr
                elif attr_name == "last":
                    expr = obj_expr.last()
                    return expr.over(by) if by else expr
                elif attr_name == "fillna":
                    val_expr = (
                        _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
                        if node.args
                        else pl.lit(0)
                    )
                    nans = True
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        nans = bool(node.args[1].value)
                    for kw in node.keywords:
                        if kw.arg == "nans" and isinstance(kw.value, ast.Constant):
                            nans = bool(kw.value.value)
                    is_float = _is_float_or_numeric_expr(node.func.value, schema)
                    if nans and is_float:
                        expr = obj_expr.fill_nan(val_expr).fill_null(val_expr)
                    else:
                        expr = obj_expr.fill_null(val_expr)
                    return expr.over(by) if by else expr

        # col(...) dynamic column resolution
        if func_name == "col" and len(node.args) >= 1:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                cname = str(first_arg.value)
            elif isinstance(first_arg, ast.Name):
                cname = col_map.get(first_arg.id, first_arg.id)
            else:
                try:
                    eval_res = ast.literal_eval(first_arg)
                    cname = str(eval_res)
                except Exception:
                    cname = ""
            cname = col_map.get(cname, cname)
            if schema is not None and cname not in schema:
                import difflib

                avail = list(schema.names()) if schema is not None else []
                close = difflib.get_close_matches(cname, avail, n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                raise KeyError(f"column '{cname}' not found in DataFrame{hint}")
            return pl.col(cname)

        # 2. Functional map(...)
        if func_name == "map" and len(node.args) >= 2:
            col_expr = _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
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

            default_node = None
            if len(node.args) > 2:
                default_node = node.args[2]
            else:
                for kw in node.keywords:
                    if kw.arg == "default":
                        default_node = kw.value
                        break

            # Analyze value types in mapping
            val_types = {type(v) for v in mapping.values()}
            has_bool_val = bool in val_types
            has_non_bool_val = any(t is not bool for t in val_types)

            def_val = None
            def_is_constant = False
            if default_node is not None and isinstance(default_node, ast.Constant):
                def_val = default_node.value
                def_is_constant = True

            # If mapping dictionary is empty and default is boolean, treat as boolean mapping
            if not mapping and def_is_constant and isinstance(def_val, bool):
                has_bool_val = True

            if has_bool_val and has_non_bool_val:
                raise TypeError(
                    "map() cannot mix boolean and non-boolean values in mapping dictionary. "
                    "Polars requires homogeneous column dtypes; mixing them coerces booleans "
                    "to strings ('true'/'false'), which are both truthy in Python."
                )

            if has_bool_val:
                if def_is_constant and def_val is not None and not isinstance(def_val, bool):
                    raise TypeError(
                        f"map() cannot mix boolean mapping values with non-boolean default {def_val!r}. "
                        "Polars requires homogeneous column dtypes; coercing booleans to strings "
                        "would evaluate 'false' as truthy in Python."
                    )
            elif def_is_constant and isinstance(def_val, bool):
                raise TypeError(
                    f"map() cannot mix non-boolean mapping values with boolean default {def_val!r}. "
                    "Polars requires homogeneous column dtypes; coercing booleans to strings "
                    "would evaluate 'false' as truthy in Python."
                )

            if has_bool_val:
                if default_node is not None:
                    default_expr = _ast_to_polars_expr(default_node, col_names, col_map, by, schema, params)
                    expr = col_expr.replace_strict(mapping, default=default_expr, return_dtype=pl.Boolean)
                else:
                    expr = col_expr.replace_strict(mapping, default=None, return_dtype=pl.Boolean)
            elif default_node is not None:
                default_expr = _ast_to_polars_expr(default_node, col_names, col_map, by, schema, params)
                if hasattr(pl.Expr, "replace_strict"):
                    expr = col_expr.replace_strict(mapping, default=default_expr)
                else:
                    expr = col_expr.replace(mapping, default=default_expr)  # type: ignore[call-arg]
            else:
                # 2-argument map(col, mapping) preserves unmapped values by default
                expr = col_expr.replace(mapping)
            return expr.over(by) if by else expr

        # 3. case_when
        if func_name == "case_when":
            if not node.args and not node.keywords:
                raise ValueError("case_when expects at least one (condition, value) pair")
            default_expr = pl.lit(None)
            for kw in node.keywords:
                if kw.arg == "default":
                    default_expr = _ast_to_polars_expr(kw.value, col_names, col_map, by, schema, params)
            pairs: list[tuple[pl.Expr, pl.Expr]] = []
            has_tuple = any(isinstance(a, ast.Tuple) for a in node.args)
            if has_tuple:
                for i, a in enumerate(node.args):
                    if isinstance(a, ast.Tuple) and len(a.elts) == 2:
                        c = _ast_to_polars_expr(a.elts[0], col_names, col_map, by, schema, params)
                        v = _ast_to_polars_expr(a.elts[1], col_names, col_map, by, schema, params)
                        pairs.append((c, v))
                    elif i == len(node.args) - 1:
                        default_expr = _ast_to_polars_expr(a, col_names, col_map, by, schema, params)
                    else:
                        raise ValueError("case_when default (non-tuple) must be the last argument")
            else:
                flat_args = list(node.args)
                if len(flat_args) % 2 == 1:
                    default_expr = _ast_to_polars_expr(flat_args.pop(), col_names, col_map, by, schema, params)
                for i in range(0, len(flat_args), 2):
                    c = _ast_to_polars_expr(flat_args[i], col_names, col_map, by, schema, params)
                    v = _ast_to_polars_expr(flat_args[i + 1], col_names, col_map, by, schema, params)
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
            c = _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
            t = _ast_to_polars_expr(node.args[1], col_names, col_map, by, schema, params)
            f = _ast_to_polars_expr(node.args[2], col_names, col_map, by, schema, params)
            if (isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)) or (
                isinstance(node.args[2], ast.Constant) and isinstance(node.args[2].value, str)
            ):
                t = t.cast(pl.String) if hasattr(t, "cast") else t
                f = f.cast(pl.String) if hasattr(f, "cast") else f
            expr = pl.when(c).then(t).otherwise(f)
            return expr.over(by) if by else expr

        args = [_ast_to_polars_expr(a, col_names, col_map, by, schema, params) for a in node.args]

        agg_map = {
            "sum": lambda e: e.sum(),
            "mean": lambda e: e.mean(),
            "median": lambda e: e.median(),
            "min": lambda e: e.min(),
            "max": lambda e: e.max(),
            "std": lambda e: e.std(),
            "var": lambda e: e.var(),
            "rank": lambda e: e.rank(),
            "first": lambda e: e.first(),
            "last": lambda e: e.last(),
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
        if func_name == "fillna" and len(node.args) >= 2:
            target_expr = _ast_to_polars_expr(node.args[0], col_names, col_map, by, schema, params)
            val_expr = _ast_to_polars_expr(node.args[1], col_names, col_map, by, schema, params)
            nans = True
            if len(node.args) > 2 and isinstance(node.args[2], ast.Constant):
                nans = bool(node.args[2].value)
            for kw in node.keywords:
                if kw.arg == "nans" and isinstance(kw.value, ast.Constant):
                    nans = bool(kw.value.value)
            is_float = _is_float_or_numeric_expr(node.args[0], schema)
            if nans and is_float:
                expr = target_expr.fill_nan(val_expr).fill_null(val_expr)
            else:
                expr = target_expr.fill_null(val_expr)
            return expr.over(by) if by else expr
        if func_name == "n" and len(args) == 0:
            expr = pl.len()
            return expr.over(by) if by else expr
        if func_name == "date" and len(args) >= 1:
            arg_type = schema.get(node.args[0].id) if schema and isinstance(node.args[0], ast.Name) else None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                expr = args[0].str.to_date(str(node.args[1].value))
            elif arg_type == pl.Date:
                expr = args[0]
            elif isinstance(arg_type, pl.Datetime) or arg_type == pl.Datetime:
                expr = args[0].dt.date()
            else:
                expr = pl.coalesce(
                    args[0].str.to_date(strict=False),
                    args[0].str.to_datetime(strict=False).dt.date(),
                )
            return expr.over(by) if by else expr
        if func_name in ("datetime", "timestamp") and len(args) >= 1:
            arg_type = schema.get(node.args[0].id) if schema and isinstance(node.args[0], ast.Name) else None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                expr = args[0].str.to_datetime(str(node.args[1].value))
            elif isinstance(arg_type, pl.Datetime) or arg_type == pl.Datetime:
                expr = args[0]
            elif arg_type == pl.Date:
                expr = args[0].cast(pl.Datetime())
            else:
                expr = pl.coalesce(
                    args[0].str.to_datetime(strict=False),
                    args[0].str.to_date(strict=False).cast(pl.Datetime()),
                )
            return expr.over(by) if by else expr
        if func_name in _DTYPE_MAP and len(args) == 1:
            expr = args[0].cast(_DTYPE_MAP[func_name])
            return expr.over(by) if by else expr
        if func_name in ("is_null", "isna") and len(args) == 1:
            expr = args[0].is_null()
            return expr.over(by) if by else expr
        if func_name in ("is_not_null", "notna") and len(args) == 1:
            expr = args[0].is_not_null()
            return expr.over(by) if by else expr
        if func_name in ("is_nan", "isnan") and len(args) == 1:
            expr = args[0].is_nan()
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
            if isinstance(val, pl.Expr):
                cur = cur.with_columns(val.alias(col_name))
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
                        if callable(val_p):
                            expr_str = re.sub(rf"@{var_name}\b", var_name, expr_str)
                        else:
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
                expr = _ast_to_polars_expr(parsed, cur_cols, col_map, by=by, schema=_df_schema(cur), params=params)
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


def slice_head_polars(
    df: Any,
    n: int | None = None,
    prop: float | None = None,
    with_ties: bool = False,
    by: list[str] | None = None,
    sort_cols: list[str] | None = None,
    sort_desc: list[bool] | None = None,
) -> Any:
    """Slice the first n rows or proportion of rows, optionally per group and with boundary ties."""
    return _slice_bound_polars(
        df,
        n=n,
        prop=prop,
        with_ties=with_ties,
        by=by,
        sort_cols=sort_cols,
        sort_desc=sort_desc,
        is_head=True,
    )


def slice_tail_polars(
    df: Any,
    n: int | None = None,
    prop: float | None = None,
    with_ties: bool = False,
    by: list[str] | None = None,
    sort_cols: list[str] | None = None,
    sort_desc: list[bool] | None = None,
) -> Any:
    """Slice the last n rows or proportion of rows, optionally per group and with boundary ties."""
    return _slice_bound_polars(
        df,
        n=n,
        prop=prop,
        with_ties=with_ties,
        by=by,
        sort_cols=sort_cols,
        sort_desc=sort_desc,
        is_head=False,
    )


def _slice_bound_polars(
    df: Any,
    n: int | None = None,
    prop: float | None = None,
    with_ties: bool = False,
    by: list[str] | None = None,
    sort_cols: list[str] | None = None,
    sort_desc: list[bool] | None = None,
    is_head: bool = True,
) -> Any:
    op_name = "head" if is_head else "tail"
    if n is not None and prop is not None:
        raise ValueError(f"{op_name}: specify either 'n' or 'prop', not both")

    if n is None and prop is None:
        n = 5

    if prop is not None:
        if not (0 < prop <= 1):
            raise ValueError(f"{op_name}: 'prop' must be between 0 and 1, got {prop}")

    if n is not None:
        if n < 0:
            raise ValueError(f"{op_name}: 'n' cannot be negative, got {n}")
        if n == 0:
            return df.head(0)

    if with_ties and not sort_cols:
        raise ValueError("with_ties=True requires calling df.arrange() beforehand to determine tie-breaking order.")

    df_cols = _df_columns(df)
    if by:
        unknown_by = [c for c in by if c not in df_cols]
        if unknown_by:
            raise KeyError(f"{op_name}: grouping column(s) {unknown_by} not found in DataFrame")

    if with_ties:
        assert sort_cols is not None
        assert sort_desc is not None
        if len(sort_cols) == 1:
            target = pl.col(sort_cols[0])
            desc = sort_desc[0] if is_head else not sort_desc[0]
        else:
            target = pl.struct(sort_cols)
            desc = sort_desc[0] if is_head else not sort_desc[0]

        rank_expr = target.rank(method="min", descending=desc)
        if by:
            rank_expr = rank_expr.over(by)

        if prop is not None:
            len_expr = pl.len().over(by) if by else pl.len()
            cutoff = (len_expr * prop).floor().cast(pl.Int64).clip(lower_bound=1)
            return df.filter(rank_expr <= cutoff)
        else:
            assert n is not None
            return df.filter(rank_expr <= n)

    if by:
        if prop is not None:
            grp_len = pl.len().over(by)
            cutoff = (grp_len * prop).floor().cast(pl.Int64).clip(lower_bound=1)
            row_nr = pl.int_range(1, pl.len() + 1).over(by)
            if is_head:
                return df.filter(row_nr <= cutoff)
            else:
                return df.filter(row_nr > (grp_len - cutoff))
        else:
            assert n is not None
            if is_head:
                return df.group_by(by, maintain_order=True).head(n)
            else:
                return df.group_by(by, maintain_order=True).tail(n)

    # Ungrouped
    if prop is not None:
        total_len = pl.len()
        cutoff = (total_len * prop).floor().cast(pl.Int64).clip(lower_bound=1)
        row_nr = pl.int_range(1, pl.len() + 1)
        if is_head:
            return df.filter(row_nr <= cutoff)
        else:
            return df.filter(row_nr > (total_len - cutoff))
    else:
        assert n is not None
        if is_head:
            return df.head(n)
        else:
            return df.tail(n)


def pick_polars(*args: Any, **kwargs: Any) -> Any:
    raise AttributeError("pick() has been removed; use arrange().head(n) instead (or by().arrange().head(n) for grouped slicing).")


def long_polars(
    df: pl.DataFrame,
    cols: str | Sequence[str] | None = None,
    id_vars: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
    r: str | Sequence[str] | None = None,
    **kwargs: Any,
) -> pl.DataFrame:
    """Unpivot a Polars DataFrame from wide to long format."""
    if kwargs:
        raise TypeError(f"long_polars() got unexpected keyword argument(s): {list(kwargs.keys())}")
    if r is not None:
        if id_vars is not None:
            raise ValueError("long(): cannot specify both 'r' and 'id_vars'")
        id_vars = r

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
    if "dropna" in active_kwargs:
        dropna = active_kwargs.pop("dropna")
        if by_cols and dropna:
            work_df = work_df.drop_nulls(subset=by_cols)

    if active_kwargs and remaining_specs and specs:
        raise ValueError("agg(): cannot mix whole-frame aggregation with keyword arguments")

    if active_kwargs:
        for out_name, val in active_kwargs.items():
            clean_out = _unquote_name(out_name)
            val_str = val.strip() if isinstance(val, str) else ""
            val_norm = re.sub(r"\(\s*\)$", "", val_str).lower() if val_str else ""

            if val_norm in ("n", "count", "size", "len") or val in (["n"], ["count"], ("n",), ("count",)):
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
                fn_call_m = re.match(r"^(\w+)\(([^)]+)\)$", val.strip())
                if fn_call_m:
                    fn_name = fn_call_m.group(1).strip()
                    src = _unquote_name(fn_call_m.group(2).strip())
                    _add_expr(_polars_agg_expr(pl.col(src), fn_name), clean_out)
                else:
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
                    sub_str = str(sub).strip()
                    sub_norm = re.sub(r"\(\s*\)$", "", sub_str).strip()
                    if "," in sub_norm:
                        flat_fns.extend([p.strip() for p in sub_norm.split(",") if p.strip()])
                    else:
                        flat_fns.append(sub_norm)
            elif isinstance(item, str):
                item_norm = re.sub(r"\(\s*\)$", "", item).strip()
                if "," in item_norm:
                    flat_fns.extend([p.strip() for p in item_norm.split(",") if p.strip()])
                else:
                    flat_fns.append(item_norm)
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


def _to_polars_frame(obj: Any) -> pl.DataFrame | pl.LazyFrame:
    """Convert any tabular input (Pytae DataFrame, Pandas DataFrame, Polars DataFrame/LazyFrame, dict) to Polars."""
    if isinstance(obj, (pl.DataFrame, pl.LazyFrame)):
        return obj
    if hasattr(obj, "_df") and isinstance(obj._df, (pl.DataFrame, pl.LazyFrame)):
        return obj._df
    if hasattr(obj, "to_polars"):
        return obj.to_polars()
    if hasattr(obj, "to_pandas"):
        import pandas as pd

        return pl.from_pandas(obj.to_pandas())
    try:
        import pandas as pd

        if isinstance(obj, pd.DataFrame):
            return pl.from_pandas(obj)
    except Exception:
        pass
    return pl.DataFrame(obj)


def join_polars(
    left: Any,
    other: Any,
    on: str | Sequence[str] | None = None,
    how: str = "inner",
    *,
    left_on: str | Sequence[str] | None = None,
    right_on: str | Sequence[str] | None = None,
    suffix: str = "_right",
    suffixes: tuple[str, str] | None = None,
    validate: str = "m:m",
    coalesce: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Join two tabular datasets using Polars multithreaded SIMD vectorization.

    Retains lazy execution plan if both frames are LazyFrames (or converts eager to lazy
    when joining lazy with eager).
    """
    left_pl = _to_polars_frame(left)
    right_pl = _to_polars_frame(other)

    # If one is LazyFrame and other is DataFrame, unify to LazyFrame for lazy execution
    if isinstance(left_pl, pl.LazyFrame) and not isinstance(right_pl, pl.LazyFrame):
        right_pl = right_pl.lazy()
    elif not isinstance(left_pl, pl.LazyFrame) and isinstance(right_pl, pl.LazyFrame):
        left_pl = left_pl.lazy()

    left_cols = _df_columns(left_pl)
    right_cols = _df_columns(right_pl)

    how_norm = str(how).lower()
    if how_norm == "outer":
        how_norm = "full"
    valid_hows = {"inner", "left", "right", "full", "semi", "anti", "cross"}
    if how_norm not in valid_hows:
        raise ValueError(
            f"join(): unsupported join type '{how}'. "
            f"Supported join types: 'inner', 'left', 'right', 'full', 'semi', 'anti', 'cross'."
        )

    def _split_cols(c: str | Sequence[str]) -> list[str]:
        if isinstance(c, str):
            return [x.strip() for x in c.split(",") if x.strip()]
        return [str(x).strip() for x in c if str(x).strip()]

    on_cols: list[str] | None = None
    l_cols_key: list[str] | None = None
    r_cols_key: list[str] | None = None

    if how_norm == "cross":
        if on is not None or left_on is not None or right_on is not None:
            raise ValueError("join(): 'on', 'left_on', and 'right_on' cannot be used with how='cross'")
    elif on is not None:
        if left_on is not None or right_on is not None:
            raise ValueError("join(): Cannot specify both 'on' and 'left_on'/'right_on'")
        raw_items = _split_cols(on)
        has_colon = any(":" in item for item in raw_items)
        if has_colon:
            left_keys = []
            right_keys = []
            for item in raw_items:
                if ":" in item:
                    parts = item.split(":", 1)
                    left_keys.append(parts[0].strip())
                    right_keys.append(parts[1].strip())
                else:
                    left_keys.append(item.strip())
                    right_keys.append(item.strip())
            l_cols_key = left_keys
            r_cols_key = right_keys
        else:
            on_cols = raw_items
    elif left_on is not None or right_on is not None:
        if left_on is None or right_on is None:
            raise ValueError("join(): Both 'left_on' and 'right_on' must be specified")
        l_keys = _split_cols(left_on)
        r_keys = _split_cols(right_on)
        if len(l_keys) != len(r_keys):
            raise ValueError(f"join(): 'left_on' ({len(l_keys)}) and 'right_on' ({len(r_keys)}) must have same length")
        if l_keys == r_keys:
            on_cols = l_keys
        else:
            l_cols_key = l_keys
            r_cols_key = r_keys
    else:
        # Auto-detect common columns
        common = [c for c in left_cols if c in right_cols]
        if not common:
            raise ValueError(
                "join(): No common columns found between left and right tables. "
                "Specify join keys via 'on' or 'left_on'/'right_on'."
            )
        on_cols = common

    # Validate columns
    if on_cols is not None:
        missing_l = [c for c in on_cols if c not in left_cols]
        missing_r = [c for c in on_cols if c not in right_cols]
        if missing_l or missing_r:
            missing_both = list(dict.fromkeys(missing_l + missing_r))
            raise ValueError(f"join(): 'on' column(s) not found in both tables: {missing_both}")
    elif l_cols_key is not None and r_cols_key is not None:
        missing_l = [c for c in l_cols_key if c not in left_cols]
        if missing_l:
            raise ValueError(f"join(): 'left_on' column(s) not found in left table: {missing_l}")
        missing_r = [c for c in r_cols_key if c not in right_cols]
        if missing_r:
            raise ValueError(f"join(): 'right_on' column(s) not found in right table: {missing_r}")

    val_map = {
        "1:1": "1:1",
        "one_to_one": "1:1",
        "1:m": "1:m",
        "one_to_many": "1:m",
        "m:1": "m:1",
        "many_to_one": "m:1",
        "m:m": "m:m",
        "many_to_many": "m:m",
    }
    validate_arg: Any = val_map.get(str(validate).lower(), "m:m")

    eff_suffix = suffix
    if suffixes is not None:
        if not (isinstance(suffixes, (tuple, list)) and len(suffixes) == 2):
            raise ValueError("join(): 'suffixes' must be a tuple or list of two strings, e.g. ('_x', '_y')")
        l_suf, r_suf = suffixes
        if on_cols is not None:
            key_set = set(on_cols)
        elif l_cols_key is not None and r_cols_key is not None:
            key_set = set(l_cols_key) | set(r_cols_key)
        else:
            key_set = set()
        conflicts = [c for c in left_cols if c in right_cols and c not in key_set]
        if conflicts:
            if l_suf:
                left_pl = left_pl.rename({c: f"{c}{l_suf}" for c in conflicts})
            if r_suf:
                right_pl = right_pl.rename({c: f"{c}{r_suf}" for c in conflicts})
        eff_suffix = ""

    if coalesce is not None:
        coalesce_val = coalesce
    elif on_cols is not None or (l_cols_key == r_cols_key):
        coalesce_val = True
    else:
        coalesce_val = False

    if how_norm == "cross":
        return left_pl.join(right_pl, how="cross", suffix=eff_suffix, **kwargs)
    elif on_cols is not None:
        return left_pl.join(
            right_pl,
            on=on_cols,
            how=how_norm,
            suffix=eff_suffix,
            validate=validate_arg,
            coalesce=coalesce_val,
            **kwargs,
        )
    else:
        return left_pl.join(
            right_pl,
            left_on=l_cols_key,
            right_on=r_cols_key,
            how=how_norm,
            suffix=eff_suffix,
            validate=validate_arg,
            coalesce=coalesce_val,
            **kwargs,
        )


def concat_polars(
    items: Sequence[Any],
    how: str = "vertical",
    axis: int | str | None = None,
    **kwargs: Any,
) -> Any:
    """Concatenate multiple DataFrames vertically or horizontally with Polars.

    Automatically handles LazyFrames lazily, and falls back to diagonal_relaxed
    if schemas differ in column sets during vertical concatenation.
    """
    if not items:
        raise ValueError("concat(): requires at least one DataFrame")

    pl_dfs = [_to_polars_frame(d) for d in items]
    has_lazy = any(isinstance(d, pl.LazyFrame) for d in pl_dfs)
    if has_lazy:
        pl_dfs = [d.lazy() if not isinstance(d, pl.LazyFrame) else d for d in pl_dfs]

    if axis in (1, "columns", "horizontal") or how == "horizontal":
        # Disambiguate duplicate column names across frames if present
        seen_cols: set[str] = set()
        renamed_dfs = []
        for i, d in enumerate(pl_dfs):
            cols = _df_columns(d)
            clashes = {c: f"{c}_{i}" for c in cols if c in seen_cols}
            if clashes:
                d = d.rename(clashes)
            seen_cols.update(_df_columns(d))
            renamed_dfs.append(d)
        return pl.concat(renamed_dfs, how="horizontal", **kwargs)

    if how in ("diagonal", "diagonal_relaxed"):
        return pl.concat(pl_dfs, how=how, **kwargs)

    try:
        return pl.concat(pl_dfs, how="vertical", **kwargs)
    except (pl.exceptions.SchemaError, pl.exceptions.ShapeError, Exception):
        return pl.concat(pl_dfs, how="diagonal_relaxed", **kwargs)
