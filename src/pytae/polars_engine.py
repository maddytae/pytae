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

from pytae._text import unquote_name as _unquote_name
from pytae.arrange import _extract_arrange_specs
from pytae.mutate import _rewrite_fallback_col_refs
from pytae.select import select as _select_pandas


def _cond_to_polars_expr(col: str, cond: Any, schema: pl.Schema | None = None) -> pl.Expr:
    """Convert a pytae filter condition tuple/value into a Polars Expression."""
    col_expr = pl.col(col)
    is_numeric = schema is not None and col in schema and schema[col].is_numeric()
    is_string = schema is not None and col in schema and schema[col] == pl.String

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

    # Default direct scalar equality
    return col_expr == _coerce_val(cond)


def filter_polars(df: pl.DataFrame, conditions: list[tuple[str, Any]] | dict) -> pl.DataFrame:
    """Filter a Polars DataFrame using pytae filter specifications."""
    cond_items: list[tuple[str, Any]]
    if isinstance(conditions, dict):
        cond_items = list(conditions.items())
    else:
        cond_items = list(conditions)

    if not cond_items:
        return df

    schema = df.schema
    combined_expr: pl.Expr | None = None
    for col, cond in cond_items:
        expr = _cond_to_polars_expr(col, cond, schema=schema)
        combined_expr = expr if combined_expr is None else (combined_expr & expr)

    assert combined_expr is not None
    return df.filter(combined_expr)


def select_polars(df: pl.DataFrame, names: list[str], kwargs: dict) -> pl.DataFrame:
    """Select and order columns in a Polars DataFrame using pytae selection syntax."""
    # Resolve exact target columns and order using a lightweight 0-row Pandas dummy frame
    dummy = df.head(0).to_pandas()
    target_cols = list(_select_pandas(dummy, *names, **kwargs).columns)
    return df.select(target_cols)


def arrange_polars(df: pl.DataFrame, spec: str, na_last: bool = True) -> pl.DataFrame:
    """Sort rows in a Polars DataFrame by one or more column expressions."""
    cols, asc = _extract_arrange_specs((spec,), available_cols=set(df.columns))
    descending = [not a for a in asc]
    return df.sort(cols, descending=descending, nulls_last=na_last)


def distinct_polars(df: pl.DataFrame, cols: list[str] | None = None, keep: str | bool = "first") -> pl.DataFrame:
    """Drop duplicate rows in a Polars DataFrame."""
    pl_keep: Literal["first", "last", "any", "none"]
    if keep == "first":
        pl_keep = "first"
    elif keep == "last":
        pl_keep = "last"
    elif keep is False or keep == "none":
        pl_keep = "none"
    else:
        pl_keep = "any"
    return df.unique(subset=cols, keep=pl_keep, maintain_order=True)


def dropna_polars(df: pl.DataFrame, cols: list[str] | None = None) -> pl.DataFrame:
    """Drop rows containing null values in specified or all columns."""
    return df.drop_nulls(subset=cols)


def rename_polars(df: pl.DataFrame, mapping: dict[str, str]) -> pl.DataFrame:
    """Rename columns in a Polars DataFrame."""
    return df.rename(mapping)


def pivot_polars(
    df: pl.DataFrame,
    r: str | Sequence[str] | None = None,
    c: str | Sequence[str] | None = None,
    v: str | Sequence[str] | None = None,
    a: str = "sum",
    dropna: bool = False,
    fill_value: Any = None,
    **kwargs: Any,
) -> pl.DataFrame:
    """Pivot a Polars DataFrame matching pytae's pivot semantics."""
    if kwargs:
        raise TypeError(f"pivot_polars() got unexpected keyword argument(s): {list(kwargs.keys())}; only r, c, v, a are accepted")
    if a in ("n", "size") and fill_value is None:
        fill_value = 0

    def _norm(spec: Any) -> list[str]:
        if spec is None:
            return []
        if isinstance(spec, str):
            from pytae._text import tokenize as _tok
            return [_unquote_name(item.strip()) for item in _tok(spec, ",", keep_quotes=True, track_brackets=True) if item.strip()]
        if isinstance(spec, (list, tuple, set)):
            return [_unquote_name(item) if isinstance(item, str) else item for item in spec]
        return [str(spec)]

    r_cols = _norm(r)
    c_cols = _norm(c)
    v_cols = _norm(v)

    if not c_cols:
        raise ValueError("pivot_polars requires column dimension 'c'")

    aggfunc = "len" if a in ("n", "size") else a

    work_df = df
    pivot_on = c_cols
    if len(c_cols) > 1:
        # Combine multiple column dimension keys into a single string formatted key (e.g. 'East_2020')
        col_exprs = [pl.col(col).cast(pl.String) for col in c_cols]
        work_df = work_df.with_columns(pl.concat_str(col_exprs, separator="_").alias("__pt_c_key__"))
        pivot_on = ["__pt_c_key__"]

    val_arg = v_cols[0] if len(v_cols) == 1 else (v_cols if v_cols else None)
    if val_arg is None:
        work_df = work_df.with_columns(pl.lit(1).alias("__pt_n_val__"))
        val_arg = "__pt_n_val__"

    res = work_df.pivot(
        on=pivot_on[0] if len(pivot_on) == 1 else pivot_on,
        index=r_cols if r_cols else None,
        values=val_arg,
        aggregate_function=cast(Any, aggfunc),
        sort_columns=True,
    )

    if fill_value is not None:
        res = res.fill_null(fill_value)

    if r_cols:
        res = res.sort(r_cols)

    return res


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
        raise ValueError(f"Unknown column or variable: {node.id}")
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
            return left ** right
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
                left = (left == right)
            elif isinstance(op, ast.NotEq):
                left = (left != right)
            elif isinstance(op, ast.Lt):
                left = (left < right)
            elif isinstance(op, ast.LtE):
                left = (left <= right)
            elif isinstance(op, ast.Gt):
                left = (left > right)
            elif isinstance(op, ast.GtE):
                left = (left >= right)
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
        if func_name == "if_else" and len(args) == 3:
            return pl.when(args[0]).then(args[1]).otherwise(args[2])
        if func_name == "coalesce":
            return pl.coalesce(args)

    raise ValueError(f"Unsupported AST node: {type(node)}")


def mutate_polars(df: pl.DataFrame, parsed_spec: dict[str, str], by: list[str] | None = None) -> pl.DataFrame:
    """Evaluate mutate expressions on a Polars DataFrame using native Polars vectorization."""
    cur = df
    for col_name, expr_str in parsed_spec.items():
        safe_expr, col_map = _rewrite_fallback_col_refs(expr_str.strip(), set(cur.columns))
        parsed = ast.parse(safe_expr, mode="eval")
        expr = _ast_to_polars_expr(parsed, set(cur.columns), col_map, by=by)
        cur = cur.with_columns(expr.alias(col_name))
    return cur


def pick_polars(
    df: pl.DataFrame,
    col: str,
    n: int | None = None,
    prop: float | None = None,
    order: str = "max",
    by: list[str] | None = None,
) -> pl.DataFrame:
    """Select the rows with the largest (or smallest) values of a column, optionally grouped by 'by'."""
    clean_col = _unquote_name(col.strip())
    if clean_col not in df.columns:
        raise KeyError(f"pick: column '{clean_col}' not found in DataFrame. Available columns: {list(df.columns)}")

    if n is not None and prop is not None:
        raise ValueError("pick: specify either 'n' or 'prop', not both")

    if n is None and prop is None:
        n = 1

    clean_order = order.strip().lower() if isinstance(order, str) else "max"
    if clean_order not in ("max", "min"):
        raise ValueError(f"pick: order must be 'max' or 'min', got {order!r}")
    is_desc = (clean_order == "max")

    if prop is not None:
        if not (0 < prop <= 1):
            raise ValueError(f"pick: 'prop' must be between 0 and 1, got {prop}")

    if by:
        unknown_by = [c for c in by if c not in df.columns]
        if unknown_by:
            raise KeyError(f"pick: grouping column(s) {unknown_by} not found in DataFrame")

        sort_cols = by + [clean_col]
        sort_desc = [False] * len(by) + [is_desc]
        sorted_df = df.sort(sort_cols, descending=sort_desc, nulls_last=True)

        if prop is not None:
            valid_cnt = pl.col(clean_col).drop_nulls().len().over(by)
            cutoff = (valid_cnt * prop).floor().cast(pl.Int64).clip(lower_bound=1)
            row_nr = pl.int_range(1, pl.len() + 1).over(by)
            return sorted_df.filter(row_nr <= cutoff)

        assert n is not None
        if n <= 0:
            return df.head(0)
        return sorted_df.group_by(by, maintain_order=True).head(n)

    sorted_df = df.sort(clean_col, descending=is_desc, nulls_last=True)
    if prop is not None:
        valid_cnt = sorted_df.select(pl.col(clean_col).drop_nulls().len()).item()
        k = max(1, int(valid_cnt * prop))
        return sorted_df.head(k)

    assert n is not None
    if n <= 0:
        return df.head(0)
    return sorted_df.head(n)


def value_counts_polars(
    df: pl.DataFrame,
    cols: list[str] | None = None,
    dropna: bool = False,
) -> pl.DataFrame:
    """Compute value counts across specified or all columns in a Polars DataFrame."""
    target_cols = cols if cols is not None else list(df.columns)
    if "count" in target_cols and "n" in target_cols:
        raise ValueError("-value_counts: columns contain both 'count' and 'n'; rename one to avoid ambiguous count headers")

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

    all_cols = list(df.columns)

    def _norm_spec(spec: str | Sequence[str] | None, param_name: str) -> list[str] | None:
        if spec is None:
            return None
        if isinstance(spec, str):
            from pytae._text import tokenize as _tok
            items = [_unquote_name(item.strip()) for item in _tok(spec, ",", keep_quotes=True, track_brackets=True) if item.strip()]
        elif isinstance(spec, (list, tuple, set)):
            items = [_unquote_name(item) if isinstance(item, str) else item for item in spec]
        else:
            raise TypeError(f"{param_name} must be a column name or sequence of names, got {type(spec).__name__}")
        for item in items:
            if item not in df.columns:
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
        numeric_cols = [col for col, dtype in df.schema.items() if dtype.is_numeric()]
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

    return df.unpivot(on=melt_cols, index=keep_ids, variable_name=c, value_name=v)


def wide_polars(
    df: pl.DataFrame,
    r: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
    **kwargs: Any,
) -> pl.DataFrame:
    """Reshape a long Polars DataFrame into wide format (1-to-1 pivot)."""
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
            from pytae._text import tokenize as _tok
            r_cols = [_unquote_name(col.strip()) for col in _tok(r, ",", keep_quotes=True, track_brackets=True) if col.strip()]
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

    try:
        return df.pivot(
            on=c,
            index=r_cols if r_cols else None,
            values=v,
            sort_columns=True,
        )
    except Exception as exc:
        raise ValueError(
            f"wide() encountered duplicate entries for row 'r' {r_cols} and column '{c}'. "
            "wide() is strictly for 1-to-1 reshaping without aggregation. "
            "Use pt.pivot() / -pivot to summarize or aggregate duplicate entries."
        ) from exc


def handle_missing_polars(
    df: pl.DataFrame,
    fillna: str | None = ".",
    numeric_fill: Any = 0,
    cols: Sequence[str] | None = None,
) -> pl.DataFrame:
    """Fill missing values in a Polars DataFrame with type-appropriate defaults."""
    target_cols = set(cols) if cols is not None else set(df.columns)
    exprs: list[pl.Expr] = []

    for c in df.columns:
        if c not in target_cols:
            exprs.append(pl.col(c))
            continue

        dtype = df.schema[c]
        if dtype.is_numeric():
            if numeric_fill == "mean":
                exprs.append(pl.col(c).fill_null(pl.col(c).mean()))
            elif numeric_fill == "median":
                exprs.append(pl.col(c).fill_null(pl.col(c).median()))
            elif numeric_fill is not None:
                exprs.append(pl.col(c).fill_null(numeric_fill))
            else:
                exprs.append(pl.col(c))
        elif dtype == pl.String:
            fill_str = str(fillna) if fillna is not None else "."
            exprs.append(pl.col(c).fill_null(fill_str).str.strip_chars())
        elif dtype == pl.Categorical:
            fill_str = str(fillna) if fillna is not None else "."
            exprs.append(pl.col(c).cast(pl.String).fill_null(fill_str).cast(pl.Categorical))
        else:
            exprs.append(pl.col(c))

    return df.with_columns(exprs)


def clean_columns_polars(df: pl.DataFrame, **opts: Any) -> pl.DataFrame:
    """Clean column header names in a Polars DataFrame."""
    from pytae.other_utilities import clean_column_names
    old_cols = list(df.columns)
    new_cols = clean_column_names(old_cols, **opts)
    if new_cols == old_cols:
        return df
    if len(set(new_cols)) < len(new_cols):
        raise ValueError("clean_columns resulted in duplicate column names; set dedupe=True to auto-disambiguate")
    mapping = dict(zip(old_cols, new_cols))
    return df.rename(mapping)

