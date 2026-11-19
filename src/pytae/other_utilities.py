"""General tabular utilities: clipboard export, missing-value handling, column sorting, header cleaning, and value replacement."""

from __future__ import annotations

import re
from collections.abc import Hashable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl

from pytae._text import unquote_name as _unquote_name
from pytae.polars_engine import _df_columns, _df_schema, _ensure_eager


def safe_reset_index(df: pd.DataFrame) -> pd.DataFrame:
    """Reset index, ensuring no index level name collides with existing columns."""
    if isinstance(df.index, pd.RangeIndex) and df.index.name is None:
        return df
    idx_names = list(df.index.names)
    col_names = [str(col) for col in df.columns]
    colliding = []
    used_names = set(col_names)
    for i, name in enumerate(idx_names):
        target_name = str(name) if name is not None else ("index" if len(idx_names) == 1 else f"level_{i}")
        if target_name in used_names:
            colliding.append(target_name)
    if colliding:
        raise ValueError(
            f"Resetting index failed: index level name(s) {colliding} collide with existing column name(s). "
            "Rename the column or index before resetting."
        )
    return df.reset_index()


def cols(df: Any, ascending: bool | None = True) -> list[str]:
    """Return the column names of the DataFrame sorted or in original order."""
    from pytae.dataframe import DataFrame

    return DataFrame(df).cols(ascending=ascending)


def clean_column_names(
    names: Sequence[Hashable],
    *,
    strip: bool = False,
    strip_special: bool = False,
    squeeze: bool = False,
    fill: str | None = None,
    case: str | None = None,
    dedupe: bool = False,
) -> list:
    """Clean a list of header names, in a fixed order: strip -> strip_special
    -> squeeze -> fill -> case -> dedupe.

    strip: trim leading/trailing whitespace.
    strip_special: remove anything that isn't a letter, digit, underscore,
        whitespace, or the fill character (e.g. %, $, #, !, parentheses,
        quotes) — if fill is set, that character is kept in place rather
        than stripped, since it's the intended separator.
    squeeze: collapse runs of internal whitespace to a single space.
    fill: replace each individual whitespace character with this string (pair
        with squeeze=True to collapse multi-space runs to one separator first).
    case: 'lower', 'upper', or 'proper' (str.title()).
    dedupe: number collisions after cleaning (revenue, revenue_1, revenue_2, ...).
    """
    cleaned = list(names)
    if strip:
        cleaned = [str(name).strip() for name in cleaned]
    if strip_special:
        keep = "".join(re.escape(ch) for ch in fill) if fill else ""
        pattern = re.compile(rf"[^\w\s{keep}]")
        cleaned = [pattern.sub("", str(name)) for name in cleaned]
    if squeeze:
        cleaned = [re.sub(r"\s+", " ", str(name)) for name in cleaned]
    if fill is not None:
        cleaned = [re.sub(r"\s", fill, str(name)) for name in cleaned]
    if case == "lower":
        cleaned = [str(name).lower() for name in cleaned]
    elif case == "upper":
        cleaned = [str(name).upper() for name in cleaned]
    elif case == "proper":
        cleaned = [str(name).title() for name in cleaned]
    if dedupe:
        seen = {}
        used = set(cleaned)  # original names, so a generated suffix never collides with a real one
        deduped = []
        for name in cleaned:
            if name not in seen:
                seen[name] = 0
                deduped.append(name)
            else:
                seen[name] += 1
                candidate = f"{name}_{seen[name]}"
                while candidate in used:
                    seen[name] += 1
                    candidate = f"{name}_{seen[name]}"
                used.add(candidate)
                deduped.append(candidate)
        cleaned = deduped
    return cleaned


def clean_columns(
    df: pd.DataFrame,
    strip: bool = False,
    strip_special: bool = False,
    squeeze: bool = False,
    fill: str | None = None,
    case: str | None = None,
    dedupe: bool = False,
) -> pd.DataFrame:
    """Clean column header names (see clean_column_names() for the per-key behavior)."""
    df = df.copy()
    df.columns = clean_column_names(
        list(df.columns),
        strip=strip,
        strip_special=strip_special,
        squeeze=squeeze,
        fill=fill,
        case=case,
        dedupe=dedupe,
    )
    return df


def format_glimpse(df: Any, width: int | None = None) -> str:
    """Format DataFrame as a transposed glimpse summary (like dplyr::glimpse / Polars).

    Parameters:
    -----------
    df : Any
        DataFrame, Polars DataFrame, or Polars LazyFrame to glimpse.
    width : int, optional
        Maximum line width (defaults to terminal width or 80).
    """
    import shutil

    if width is None:
        width = shutil.get_terminal_size(fallback=(80, 24)).columns

    try:
        import polars as pl

        from pytae.dataframe import DataFrame

        underlying = df._df if isinstance(df, DataFrame) else df
        if isinstance(underlying, (pl.DataFrame, pl.LazyFrame)):
            schema = _df_schema(underlying)
            if isinstance(underlying, pl.LazyFrame):
                try:
                    n_rows = underlying.select(pl.len()).collect().item()
                except Exception:
                    n_rows = len(underlying.collect())
                preview = underlying.limit(25).collect()
            else:
                n_rows = underlying.height
                preview = underlying.head(25)

            col_names = [str(c) for c in schema.names()]
            lines = [
                f"Rows: {n_rows:,}",
                f"Columns: {len(col_names):,}",
            ]
            if not col_names:
                return "\n".join(lines)

            max_col_len = min(max((len(c) for c in col_names), default=0), 30)
            dtypes = [f"<{schema[c]}>" for c in col_names]
            max_dtype_len = min(max((len(d) for d in dtypes), default=0), 20)

            for col, dtype_str in zip(col_names, dtypes):
                prefix = f"$ {col.ljust(max_col_len)} {dtype_str.ljust(max_dtype_len)} "
                sample_vals: list[str] = []
                for val in preview[col].to_list():
                    if val is None:
                        sample_vals.append("NA")
                    elif isinstance(val, str):
                        sample_vals.append(repr(val))
                    else:
                        sample_vals.append(str(val))

                remaining_width = max(width - len(prefix), 10)
                vals_str = ", ".join(sample_vals)
                if len(vals_str) > remaining_width:
                    vals_str = vals_str[: remaining_width - 3].rstrip(", ") + "..."
                lines.append(prefix + vals_str)

            return "\n".join(lines)
    except Exception:
        pass

    lines = [
        f"Rows: {len(df):,}",
        f"Columns: {len(df.columns):,}",
    ]
    if len(df.columns) == 0:
        return "\n".join(lines)

    col_names = [str(c) for c in df.columns]
    max_col_len = min(max((len(c) for c in col_names), default=0), 30)

    dtypes = [f"<{df[col].dtype}>" for col in df.columns]
    max_dtype_len = min(max((len(d) for d in dtypes), default=0), 20)

    for col, dtype_str in zip(df.columns, dtypes):
        col_str = str(col)
        prefix = f"$ {col_str.ljust(max_col_len)} {dtype_str.ljust(max_dtype_len)} "
        sample_vals = []
        for val in df[col].head(25):
            if pd.isna(val):
                sample_vals.append("NA")
            elif isinstance(val, str):
                sample_vals.append(repr(val))
            else:
                sample_vals.append(str(val))

        remaining_width = max(width - len(prefix), 10)
        vals_str = ", ".join(sample_vals)
        if len(vals_str) > remaining_width:
            vals_str = vals_str[: remaining_width - 3].rstrip(", ") + "..."
        lines.append(prefix + vals_str)

    return "\n".join(lines)


def schema_dataframe(df: Any) -> Any:
    """Extract DataFrame schema summary as a 4-column Polars DataFrame: Column, Type, Nulls, Unique."""

    pldf = _ensure_eager(df)

    total = len(pldf)
    if total == 0:
        nulls: tuple[Any, ...] = tuple([0] * len(pldf.columns))
        uniques: tuple[Any, ...] = tuple([0] * len(pldf.columns))
    else:
        nulls = pldf.null_count().row(0)
        uniques = pldf.select(pl.all().n_unique()).row(0)

    rows = []
    for col, n_null, n_uniq in zip(pldf.columns, nulls, uniques):
        pct = (n_null / total * 100) if total else 0.0
        dtype_str = str(pldf.schema[col])
        rows.append({
            "Column": col,
            "Type": dtype_str,
            "Nulls": f"{n_null:,} ({pct:.1f}%)",
            "Unique": f"{n_uniq:,}",
        })
    return pl.DataFrame(rows)


def _extract_schema_info(df: Any) -> tuple[list[tuple[str, str, int]], int]:
    """Return ([(col_name, polars_dtype_str, null_count), ...], total_rows) for a dataset."""

    pldf = _ensure_eager(df)

    total = len(pldf)
    if total == 0:
        nulls: tuple[Any, ...] = tuple([0] * len(pldf.columns))
    else:
        nulls = pldf.null_count().row(0)

    info: list[tuple[str, str, int]] = []
    for col, n_null in zip(pldf.columns, nulls):
        info.append((str(col), str(pldf.schema[col]), int(n_null)))
    return info, total


def _generate_schema_ddl(df: Any, fmt: str, table_name: str = "data") -> str:
    """Generate schema DDL or model definition in 'sql', 'bq', 'pydantic', or 'json' format."""
    import json

    fmt_clean = fmt.strip().lower()
    info, total = _extract_schema_info(df)
    clean_tbl = re.sub(r"[^A-Za-z0-9_]", "_", Path(str(table_name)).stem or "data").strip("_") or "data"
    if clean_tbl[0].isdigit():
        clean_tbl = f"t_{clean_tbl}"

    if fmt_clean == "sql":
        col_lines: list[str] = []
        for col, dtype_str, n_null in info:
            dt_upper = dtype_str.upper()
            if dt_upper in ("INT64", "UINT64"):
                sql_type = "BIGINT"
            elif dt_upper in ("INT32", "UINT32"):
                sql_type = "INTEGER"
            elif dt_upper in ("INT16", "INT8", "UINT16", "UINT8"):
                sql_type = "SMALLINT"
            elif dt_upper == "FLOAT64":
                sql_type = "DOUBLE PRECISION"
            elif dt_upper == "FLOAT32":
                sql_type = "REAL"
            elif dt_upper.startswith("DECIMAL"):
                sql_type = "NUMERIC"
            elif dt_upper in ("BOOLEAN", "BOOL"):
                sql_type = "BOOLEAN"
            elif dt_upper == "DATE":
                sql_type = "DATE"
            elif dt_upper.startswith("DATETIME"):
                sql_type = "TIMESTAMP"
            elif dt_upper == "TIME":
                sql_type = "TIME"
            elif dt_upper == "BINARY":
                sql_type = "BYTEA"
            else:
                sql_type = "VARCHAR"

            null_clause = " NOT NULL" if (total > 0 and n_null == 0) else ""
            col_ident = col if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", col) else f'"{col}"'
            col_lines.append(f"    {col_ident} {sql_type}{null_clause}")
        body = ",\n".join(col_lines)
        return f"CREATE TABLE {clean_tbl} (\n{body}\n);"

    if fmt_clean in ("bq", "bigquery"):
        fields = []
        for col, dtype_str, n_null in info:
            dt_upper = dtype_str.upper()
            if dt_upper.startswith(("INT", "UINT")):
                bq_type = "INT64"
            elif dt_upper.startswith("FLOAT"):
                bq_type = "FLOAT64"
            elif dt_upper.startswith("DECIMAL"):
                bq_type = "NUMERIC"
            elif dt_upper in ("BOOLEAN", "BOOL"):
                bq_type = "BOOL"
            elif dt_upper == "DATE":
                bq_type = "DATE"
            elif dt_upper.startswith("DATETIME"):
                bq_type = "TIMESTAMP"
            elif dt_upper == "TIME":
                bq_type = "TIME"
            elif dt_upper == "BINARY":
                bq_type = "BYTES"
            else:
                bq_type = "STRING"
            mode = "REQUIRED" if (total > 0 and n_null == 0) else "NULLABLE"
            fields.append({"name": col, "type": bq_type, "mode": mode})
        return json.dumps(fields, indent=2)

    if fmt_clean == "pydantic":
        needs_optional = any(total == 0 or n_null > 0 for _, _, n_null in info)
        needs_date = any(dt.upper() == "DATE" for _, dt, _ in info)
        needs_datetime = any(dt.upper().startswith("DATETIME") for _, dt, _ in info)
        needs_time = any(dt.upper() == "TIME" for _, dt, _ in info)
        needs_any = any(dt.upper().startswith(("LIST", "STRUCT", "OBJECT", "NULL")) for _, dt, _ in info)

        imports: list[str] = []
        dt_imports: list[str] = []
        if needs_date:
            dt_imports.append("date")
        if needs_datetime:
            dt_imports.append("datetime")
        if needs_time:
            dt_imports.append("time")
        if dt_imports:
            imports.append(f"from datetime import {', '.join(dt_imports)}")

        typing_imports: list[str] = []
        if needs_any:
            typing_imports.append("Any")
        if needs_optional:
            typing_imports.append("Optional")
        if typing_imports:
            imports.append(f"from typing import {', '.join(typing_imports)}")

        imports.append("from pydantic import BaseModel")

        class_name = "".join(part.capitalize() for part in clean_tbl.split("_") if part) + "Record"
        lines = ["\n".join(imports), "", "", f"class {class_name}(BaseModel):"]
        if not info:
            lines.append("    pass")
            return "\n".join(lines)

        for col, dtype_str, n_null in info:
            dt_upper = dtype_str.upper()
            if dt_upper.startswith(("INT", "UINT")):
                py_type = "int"
            elif dt_upper.startswith(("FLOAT", "DECIMAL")):
                py_type = "float"
            elif dt_upper in ("BOOLEAN", "BOOL"):
                py_type = "bool"
            elif dt_upper == "DATE":
                py_type = "date"
            elif dt_upper.startswith("DATETIME"):
                py_type = "datetime"
            elif dt_upper == "TIME":
                py_type = "time"
            elif dt_upper == "BINARY":
                py_type = "bytes"
            elif dt_upper.startswith("LIST"):
                py_type = "list[Any]"
            elif dt_upper.startswith("STRUCT"):
                py_type = "dict[str, Any]"
            elif dt_upper in ("OBJECT", "NULL", "UNKNOWN"):
                py_type = "Any"
            else:
                py_type = "str"

            py_ident = re.sub(r"[^A-Za-z0-9_]", "_", col).strip("_") or "field"
            if py_ident[0].isdigit():
                py_ident = f"f_{py_ident}"

            is_nullable = total == 0 or n_null > 0
            if is_nullable:
                lines.append(f"    {py_ident}: Optional[{py_type}] = None")
            else:
                lines.append(f"    {py_ident}: {py_type}")
        return "\n".join(lines)

    if fmt_clean in ("json", "jsonschema"):
        properties: dict[str, Any] = {}
        required: list[str] = []
        for col, dtype_str, n_null in info:
            dt_upper = dtype_str.upper()
            prop: dict[str, Any] = {}
            if dt_upper.startswith(("INT", "UINT")):
                js_type = "integer"
            elif dt_upper.startswith(("FLOAT", "DECIMAL")):
                js_type = "number"
            elif dt_upper in ("BOOLEAN", "BOOL"):
                js_type = "boolean"
            elif dt_upper == "DATE":
                js_type = "string"
                prop["format"] = "date"
            elif dt_upper.startswith("DATETIME"):
                js_type = "string"
                prop["format"] = "date-time"
            elif dt_upper.startswith("LIST"):
                js_type = "array"
            elif dt_upper.startswith("STRUCT"):
                js_type = "object"
            else:
                js_type = "string"

            is_nullable = total == 0 or n_null > 0
            if is_nullable:
                prop["type"] = [js_type, "null"]
            else:
                prop["type"] = js_type
                required.append(col)
            properties[col] = prop

        class_title = "".join(part.capitalize() for part in clean_tbl.split("_") if part) + "Record"
        schema_obj: dict[str, Any] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": class_title,
            "type": "object",
            "properties": properties,
        }
        if required:
            schema_obj["required"] = required
        return json.dumps(schema_obj, indent=2)

    raise ValueError(f"Unsupported schema format '{fmt}'. Expected 'table', 'sql', 'bq', 'pydantic', or 'json'.")


def format_schema(
    df: Any,
    is_tty: bool | None = None,
    *,
    fmt: str | None = None,
    table_name: str = "data",
) -> str:
    """Format DataFrame as a concise schema summary table or DDL/code generation."""
    if fmt is not None and fmt.strip().lower() not in ("", "table", "default", "summary"):
        return _generate_schema_ddl(df, fmt=fmt, table_name=table_name)


    from pytae.cli_run import _format_table
    from pytae.dataframe import DataFrame as PytaeDataFrame

    underlying = df._df if isinstance(df, PytaeDataFrame) else df
    total = underlying.select(pl.len()).collect().item() if isinstance(underlying, pl.LazyFrame) else len(underlying)
    num_cols = len(_df_columns(underlying))
    schema_df = schema_dataframe(df)

    header = f"Columns: {num_cols} | Rows: {total:,}\n"
    return header + _format_table(schema_df, tbl_rows=max(len(schema_df), 10), is_tty=is_tty)


def glimpse(df: Any, width: int | None = None) -> Any:
    """Print a transposed overview of DataFrame columns, dtypes, and sample values.

    Returns the original DataFrame for method chaining.
    """
    print(format_glimpse(df, width=width))
    return df


def distinct(
    df: Any,
    *cols: Any,
    keep: str = "first",
) -> Any:
    """Drop duplicate rows, optionally restricted to specific key columns."""
    from pytae.dataframe import DataFrame

    return DataFrame(df).distinct(*cols, keep=keep)


def dups(
    df: Any,
    *cols: Any,
) -> Any:
    """Filter to duplicate rows, optionally restricted to specific key columns."""
    from pytae.dataframe import DataFrame

    return DataFrame(df).dups(*cols)


def outliers(
    df: Any,
    *cols: Any,
    method: str = "iqr",
    threshold: float | None = None,
    k: float | None = None,
    drop: bool = False,
    which: str = "any",
) -> Any:
    """Filter to statistical outlier rows, optionally restricted to specific numeric columns."""
    from pytae.dataframe import DataFrame, GroupedDataFrame

    if isinstance(df, GroupedDataFrame):
        return df.outliers(*cols, method=method, threshold=threshold, k=k, drop=drop, which=which)
    return DataFrame(df).outliers(*cols, method=method, threshold=threshold, k=k, drop=drop, which=which)


def freq(
    df: Any,
    col: str | None = None,
    *,
    dropna: bool = False,
    width: int = 20,
) -> Any:
    """Compute a frequency table with ASCII distribution bars and percentages for a column.

    Parameters:
    -----------
    df : Any
        Input DataFrame, Polars DataFrame, or Pandas DataFrame.
    col : str, optional
        Column name to inspect. Required unless `df` has only a single column.
    dropna : bool, default False
        Whether to exclude NA/null values from the frequency counts.
    width : int, default 20
        Maximum character width of the bars.

    Returns:
    --------
    DataFrame
        DataFrame with columns `[col, 'Count', 'Distribution']`.
    """

    from pytae.dataframe import DataFrame

    pldf = _ensure_eager(df)

    cols = list(pldf.columns)
    if col is None or (isinstance(col, str) and not col.strip()):
        if len(cols) == 1:
            target_col = str(cols[0])
        else:
            raise ValueError("freq() requires a column name (or a single-column DataFrame)")
    else:
        target_col = _unquote_name(str(col).strip())

    if target_col not in cols:
        raise KeyError(f"freq: column '{target_col}' not found in DataFrame. Available columns: {cols}")

    s_df = pldf.select(pl.col(target_col))
    if dropna:
        s_df = s_df.filter(pl.col(target_col).is_not_null())

    counted = s_df.group_by(target_col).agg(pl.len().alias("Count")).sort("Count", descending=True)

    from typing import cast

    total = int(cast(Any, counted["Count"].sum())) if len(counted) > 0 else 0
    max_cnt = int(cast(Any, counted["Count"].max() or 1)) if len(counted) > 0 else 1
    bar_max_width = width

    cats: list[str] = []
    counts_list: list[int] = []
    dists: list[str] = []
    for row in counted.iter_rows(named=True):
        val = row[target_col]
        cat_str = "None" if val is None else str(val)
        cnt = int(row["Count"])
        bar_len = int(round((cnt / max_cnt) * bar_max_width)) if max_cnt > 0 else 0
        bar_str = "█" * bar_len
        pct_str = f"({(cnt / total * 100):.1f}%)" if total > 0 else "(0.0%)"
        dist_str = f"{bar_str} {pct_str}".strip()

        cats.append(cat_str)
        counts_list.append(cnt)
        dists.append(dist_str)

    res_pl = pl.DataFrame(
        {
            target_col: cats,
            "Count": counts_list,
            "Distribution": dists,
        }
    )
    return DataFrame(res_pl)


def hist(
    df: Any,
    col: str | None = None,
    bins: int = 10,
    *,
    width: int = 20,
) -> Any:
    """Compute a binned distribution histogram with ASCII bars and percentages for a numeric column.

    Parameters:
    -----------
    df : Any
        Input DataFrame, Polars DataFrame, or Pandas DataFrame.
    col : str, optional
        Column name or `'col:bins'` specification (e.g. `'body_mass_g'` or `'body_mass_g:10'`).
        Required unless `df` has only a single column.
    bins : int, default 10
        Number of equal-width bins (overridden if `:bins` or `,bins=` is specified in `col`).
    width : int, default 20
        Maximum character width of the bars.

    Returns:
    --------
    DataFrame
        DataFrame with columns `['Range', 'Count', 'Distribution']`.
    """

    from pytae.dataframe import DataFrame

    raw = col.strip() if isinstance(col, str) else ""
    target_col: str | None = None

    pldf = _ensure_eager(df)

    cols = list(pldf.columns)
    if ":" in raw:
        col_part, _, b_str = raw.rpartition(":")
        if col_part.strip() and b_str.strip() and col_part.strip() not in cols:
            target_col = _unquote_name(col_part.strip())
            try:
                bins = int(b_str.strip())
            except ValueError as exc:
                raise ValueError(f"hist: invalid bins value '{b_str.strip()}'; must be a positive integer") from exc
        elif col_part.strip() in cols and b_str.strip().isdigit():
            target_col = col_part.strip()
            bins = int(b_str.strip())
        else:
            target_col = _unquote_name(raw)
    elif "," in raw and "bins=" in raw:
        col_part, _, b_part = raw.partition(",")
        target_col = _unquote_name(col_part.strip())
        b_str = b_part.replace("bins=", "").strip()
        try:
            bins = int(b_str)
        except ValueError as exc:
            raise ValueError(f"hist: invalid bins value '{b_str}'; must be a positive integer") from exc
    elif raw:
        target_col = _unquote_name(raw)
    elif col is not None and not isinstance(col, str):
        target_col = str(col)
    else:
        if len(cols) == 1:
            target_col = str(cols[0])
        else:
            raise ValueError("hist() requires a column name (e.g. 'mass' or 'mass:10')")

    if not isinstance(bins, int) or isinstance(bins, bool) or bins <= 0:
        raise ValueError(f"hist: bins must be a positive integer, got {bins!r}")

    if target_col not in cols:
        raise KeyError(f"hist: column '{target_col}' not found in DataFrame. Available columns: {cols}")

    s_col = pldf[target_col]
    s_clean = s_col.cast(pl.Float64, strict=False).drop_nulls().drop_nans()
    if len(s_clean) == 0:
        return DataFrame(pl.DataFrame(schema={"Range": pl.String, "Count": pl.Int64, "Distribution": pl.String}))

    min_val = float(s_clean.min())
    max_val = float(s_clean.max())
    total = len(s_clean)

    if min_val == max_val:
        left_fmt = f"{min_val:.2f}".rstrip("0").rstrip(".")
        range_str = f"[{left_fmt}, {left_fmt}]"
        bar_str = "█" * 20
        dist_str = f"{bar_str} (100.0%)"
        data = [{"Range": range_str, "Count": total, "Distribution": dist_str}]
        return DataFrame(pl.DataFrame(data))

    step = (max_val - min_val) / bins
    edges = [min_val + i * step for i in range(bins + 1)]
    idx_expr = (
        pl.when(pl.col("v") == max_val)
        .then(pl.lit(bins - 1))
        .otherwise(((pl.col("v") - min_val) / step).cast(pl.Int64).clip(0, bins - 1))
        .alias("idx")
    )
    vc = s_clean.to_frame("v").select(idx_expr).group_by("idx").len()
    bin_counts = [0] * bins
    for row_idx, cnt_val in vc.iter_rows():
        if row_idx is not None and 0 <= row_idx < bins:
            bin_counts[int(row_idx)] = int(cnt_val)

    max_cnt = max(bin_counts) if bin_counts else 1
    bar_max_width = width
    ranges = []
    counts = []
    distributions = []

    for i in range(bins):
        left = edges[i]
        right = edges[i + 1]
        left_fmt = f"{left:.2f}".rstrip("0").rstrip(".")
        right_fmt = f"{right:.2f}".rstrip("0").rstrip(".")
        range_str = f"[{left_fmt}, {right_fmt}]"
        cnt = bin_counts[i]
        bar_len = int(round((cnt / max_cnt) * bar_max_width)) if max_cnt > 0 else 0
        bar_str = "█" * bar_len
        pct_str = f"({(cnt / total * 100):.1f}%)" if total > 0 else "(0.0%)"
        dist_str = f"{bar_str} {pct_str}".strip()
        ranges.append(range_str)
        counts.append(cnt)
        distributions.append(dist_str)

    res_df = pl.DataFrame(
        {
            "Range": ranges,
            "Count": counts,
            "Distribution": distributions,
        }
    )
    return DataFrame(res_df)


def bar(
    df: Any,
    cat: str | None = None,
    val: str | None = None,
    *,
    limit: tuple[float, float] | list[float] | None = None,
    pct: bool = False,
    width: int = 20,
) -> Any:
    """Compute an in-terminal bar representation for a numeric column across categories.

    Parameters:
    -----------
    df : Any
        Input DataFrame, Polars DataFrame, or Pandas DataFrame.
    cat : str, optional
        Category column name, or `'cat:val'` / `'val'` specification.
    val : str, optional
        Numeric value column to visualize with bars.
    limit : tuple of (float, float), optional
        Custom (min, max) limits for scaling bar lengths.
    pct : bool, default False
        Whether to append the percentage of total to each bar.
    width : int, default 20
        Maximum character width of the bars.

    Returns:
    --------
    DataFrame
        DataFrame with an added 'Bar' column.
    """
    import math

    from pytae.dataframe import DataFrame

    pldf = _ensure_eager(df)

    cols = list(pldf.columns)
    if not cols:
        return DataFrame(pldf)

    cat_col: str | None = None
    val_col: str | None = None
    explicit_pair = False

    if cat is not None and not isinstance(cat, str):
        cat = str(cat)
    if val is not None and not isinstance(val, str):
        val = str(val)

    if cat and ":" in cat and val is None:
        c_part, _, v_part = cat.partition(":")
        cat_col = _unquote_name(c_part.strip())
        val_col = _unquote_name(v_part.strip())
        explicit_pair = True
    elif cat and val:
        cat_col = _unquote_name(cat.strip())
        val_col = _unquote_name(val.strip())
        explicit_pair = True
    elif cat and val is None:
        cand = _unquote_name(cat.strip())
        if cand in cols and pldf[cand].dtype.is_numeric():
            val_col = cand
            cat_col = None
        elif cand in cols:
            cat_col = cand
            val_col = None
        else:
            val_col = cand
    elif val and cat is None:
        val_col = _unquote_name(val.strip())
        cat_col = None
    else:
        # Bare -bar: auto-detect
        if "Distribution" in cols and "Count" in cols:
            # Already formatted by freq() with inline bars
            return DataFrame(pldf)
        if len(cols) == 2:
            num_cols = [c for c in cols if pldf[c].dtype.is_numeric()]
            non_num_cols = [c for c in cols if not pldf[c].dtype.is_numeric()]
            if len(num_cols) == 1 and len(non_num_cols) == 1:
                val_col = num_cols[0]
                cat_col = non_num_cols[0]
                explicit_pair = True
            else:
                cat_col = cols[0]
                val_col = cols[1]
                explicit_pair = True
        elif len(cols) == 1:
            val_col = cols[0]
            cat_col = None
        else:
            num_cols = [c for c in cols if pldf[c].dtype.is_numeric()]
            if len(num_cols) == 1:
                val_col = num_cols[0]
                cat_col = None
            else:
                raise ValueError(
                    "bar() requires a column specification (e.g. bar('mass') or bar('species:mass')) when DataFrame has multiple numeric columns"
                )

    if val_col is None:
        num_cols = [c for c in cols if pldf[c].dtype.is_numeric()]
        if len(num_cols) == 1:
            val_col = num_cols[0]
        else:
            raise ValueError("bar() requires a numeric value column to plot")

    if val_col not in cols:
        raise KeyError(f"bar: column '{val_col}' not found in DataFrame. Available columns: {cols}")

    if cat_col is not None and cat_col not in cols:
        raise KeyError(f"bar: category column '{cat_col}' not found in DataFrame. Available columns: {cols}")

    s_val = pldf[val_col].cast(pl.Float64, strict=False)
    vals = s_val.drop_nulls().drop_nans().to_list()

    if not vals:
        min_limit, max_limit = 0.0, 1.0
    elif limit is not None:
        min_limit, max_limit = float(limit[0]), float(limit[1])
    else:
        min_data = min(vals)
        max_data = max(vals)
        if min_data >= 0:
            min_limit = 0.0
            max_limit = max_data if max_data > 0 else 1.0
        else:
            min_limit = min_data
            max_limit = max_data if max_data > min_data else min_data + 1.0

    denom = max_limit - min_limit if max_limit != min_limit else 1.0
    total_pos = sum(v for v in vals if v > 0)
    bars_list: list[str] = []

    for v in s_val.to_list():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            bars_list.append("")
            continue
        clamped_v = max(min_limit, min(max_limit, v))
        fraction = (clamped_v - min_limit) / denom
        fraction = max(0.0, min(1.0, fraction))
        bar_len = int(round(fraction * width))
        bar_str = "█" * bar_len
        if pct:
            pct_val = (v / total_pos * 100) if total_pos > 0 else 0.0
            pct_str = f"({pct_val:.1f}%)"
            bars_list.append(f"{bar_str} {pct_str}".strip() if bar_str else pct_str)
        else:
            bars_list.append(bar_str)

    if explicit_pair and cat_col is not None:
        out_pl = pldf.select([cat_col, val_col]).with_columns(pl.Series("Bar", bars_list))
    else:
        out_pl = pldf.with_columns(pl.Series("Bar", bars_list))

    return DataFrame(out_pl)


def scatter(
    df: Any,
    x: str | None = None,
    y: str | None = None,
    *,
    width: int = 50,
    height: int = 15,
    limit_x: tuple[float, float] | list[float] | None = None,
    limit_y: tuple[float, float] | list[float] | None = None,
) -> str:
    """Render an in-terminal 2D Unicode Braille scatter plot for two numeric columns.

    Parameters:
    -----------
    df : Any
        Input DataFrame, Polars DataFrame, or Pandas DataFrame.
    x : str, optional
        X-axis column name, or `'x:y'` specification.
    y : str, optional
        Y-axis column name.
    width : int, default 50
        Width of the plot canvas in terminal characters (each char has 2 subpixels).
    height : int, default 15
        Height of the plot canvas in terminal lines (each line has 4 subpixels).
    limit_x : tuple of (float, float), optional
        Custom (min, max) limits for X-axis.
    limit_y : tuple of (float, float), optional
        Custom (min, max) limits for Y-axis.

    Returns:
    --------
    str
        Formatted 2D Braille scatter plot string with axes and footer stats.
    """
    import math


    pldf = _ensure_eager(df)

    cols = list(pldf.columns)
    x_col: str | None = None
    y_col: str | None = None

    if x is not None and ":" in str(x) and y is None:
        xp, _, yp = str(x).partition(":")
        x_col = _unquote_name(xp.strip())
        y_col = _unquote_name(yp.strip())
    elif x is not None and y is not None:
        x_col = _unquote_name(str(x).strip())
        y_col = _unquote_name(str(y).strip())
    elif x is not None and y is None:
        x_col = _unquote_name(str(x).strip())
        other_nums = [c for c in cols if c != x_col and pldf[c].dtype.is_numeric()]
        if len(other_nums) == 1:
            y_col = other_nums[0]
        else:
            raise ValueError(f"scatter() requires two numeric columns; specify 'x:y' (e.g. scatter('{x_col}:col2'))")
    else:
        num_cols = [c for c in cols if pldf[c].dtype.is_numeric()]
        if len(num_cols) == 2:
            x_col = num_cols[0]
            y_col = num_cols[1]
        else:
            raise ValueError(
                f"scatter() requires column specification (e.g. scatter('x:y')) when DataFrame has {len(num_cols)} numeric columns"
            )

    if x_col not in cols:
        raise KeyError(f"scatter: column '{x_col}' not found in DataFrame. Available columns: {cols}")
    if y_col not in cols:
        raise KeyError(f"scatter: column '{y_col}' not found in DataFrame. Available columns: {cols}")

    total_rows = pldf.height
    clean = pldf.select(
        [
            pl.col(x_col).cast(pl.Float64, strict=False).alias("x"),
            pl.col(y_col).cast(pl.Float64, strict=False).alias("y"),
        ]
    ).filter(
        pl.col("x").is_not_null() & pl.col("y").is_not_null() & pl.col("x").is_not_nan() & pl.col("y").is_not_nan()
    )
    valid_points = clean.height
    null_points = total_rows - valid_points

    if valid_points == 0:
        return f"Empty scatter plot: no valid numeric pairs in '{x_col}' and '{y_col}'"

    corr_str = "N/A"
    if valid_points >= 2:
        try:
            r = clean.select(pl.corr("x", "y")).item()
            corr_str = f"{r:+.3f}" if r is not None and not math.isnan(r) else "N/A"
        except Exception:
            corr_str = "N/A"

    xs = clean["x"].to_list()
    ys = clean["y"].to_list()

    min_x = float(limit_x[0]) if limit_x is not None else min(xs)
    max_x = float(limit_x[1]) if limit_x is not None else max(xs)
    min_y = float(limit_y[0]) if limit_y is not None else min(ys)
    max_y = float(limit_y[1]) if limit_y is not None else max(ys)

    pw = max(width * 2, 2)
    ph = max(height * 4, 4)
    canvas = [[0] * width for _ in range(height)]
    dot_map = {
        (0, 0): 0x01,
        (0, 1): 0x02,
        (0, 2): 0x04,
        (0, 3): 0x40,
        (1, 0): 0x08,
        (1, 1): 0x10,
        (1, 2): 0x20,
        (1, 3): 0x80,
    }

    denom_x = max_x - min_x if max_x != min_x else 1.0
    denom_y = max_y - min_y if max_y != min_y else 1.0

    for x_val, y_val in zip(xs, ys):
        if not (min_x <= x_val <= max_x and min_y <= y_val <= max_y):
            continue
        nx = int((x_val - min_x) / denom_x * (pw - 1))
        ny = int((max_y - y_val) / denom_y * (ph - 1))
        nx = max(0, min(pw - 1, nx))
        ny = max(0, min(ph - 1, ny))
        c_col, s_x = divmod(nx, 2)
        c_row, s_y = divmod(ny, 4)
        canvas[c_row][c_col] |= dot_map[(s_x, s_y)]

    lines: list[str] = []
    lines.append(f" {y_col}")

    mid_y = (min_y + max_y) / 2.0
    mid_x = (min_x + max_x) / 2.0

    for r in range(height):
        if r == 0:
            prefix = f"{max_y:>8.1f} ┤ "
        elif r == height // 2:
            prefix = f"{mid_y:>8.1f} ┤ "
        elif r == height - 1:
            prefix = f"{min_y:>8.1f} ┤ "
        else:
            prefix = "         │ "
        row_chars = "".join(chr(0x2800 + cell) if cell else " " for cell in canvas[r])
        lines.append(prefix + row_chars)

    lines.append("         ┼" + "─" * width)

    tick_spacing = max(width - 24, 4)
    half_space = tick_spacing // 2
    x_ticks_line = f"          {min_x:<8.1f}{' ' * half_space}{mid_x:^8.1f}{' ' * (tick_spacing - half_space)}{max_x:>8.1f}  {x_col}"
    lines.append(x_ticks_line)
    lines.append("")
    null_suffix = f" ({null_points} nulls excluded)" if null_points > 0 else ""
    lines.append(f"  Points: {valid_points}{null_suffix} | Corr (r): {corr_str}")

    return "\n".join(lines)


def corr(
    df: Any,
    target: str | None = None,
    *,
    cols: list[str] | None = None,
    pairs: bool = False,
    method: str = "pearson",
) -> Any:
    """Compute pairwise correlation matrix or ranked pairs for numeric columns.

    Parameters:
    -----------
    df : Any
        Input DataFrame, Polars DataFrame, or Pandas DataFrame.
    target : str, optional
        Screen correlations of all other numeric columns against this target column.
    cols : list of str, optional
        Subset of numeric columns to evaluate.
    pairs : bool, default False
        If True, return a ranked pairwise list sorted descending by absolute correlation.
    method : str, default 'pearson'
        Correlation method: 'pearson' or 'spearman'.

    Returns:
    --------
    DataFrame
        Correlation matrix or ranked pairs DataFrame.
    """
    import math

    from pytae.dataframe import DataFrame

    pldf = _ensure_eager(df)

    all_num_cols = [c for c in pldf.columns if pldf[c].dtype.is_numeric()]
    if cols is not None:
        num_cols = [c for c in cols if c in all_num_cols]
    else:
        num_cols = all_num_cols

    if len(num_cols) < 2 and target is None:
        raise ValueError("corr() requires at least two numeric columns")

    method_clean = method.lower().strip()
    if method_clean not in ("pearson", "spearman"):
        raise ValueError(f"corr: invalid method '{method}'; must be 'pearson' or 'spearman'")

    needed_cols = list(
        dict.fromkeys(
            num_cols
            + (
                [_unquote_name(str(target).strip())]
                if target is not None and _unquote_name(str(target).strip()) in all_num_cols
                else []
            )
        )
    )
    clean_pldf = pldf.select(
        [pl.col(c).cast(pl.Float64, strict=False).fill_nan(None).alias(c) for c in needed_cols]
    )

    corr_cache: dict[tuple[str, str], float] = {}

    def _pair_corr(col_x: str, col_y: str) -> float:
        if col_x == col_y:
            return 1.0
        key = (col_x, col_y) if col_x <= col_y else (col_y, col_x)
        if key in corr_cache:
            return corr_cache[key]
        pair_df = clean_pldf.select([col_x, col_y]).drop_nulls()
        if pair_df.height < 2:
            corr_cache[key] = 0.0
            return 0.0
        try:
            corr_method = "pearson" if method_clean == "pearson" else "spearman"
            r = pair_df.select(pl.corr(col_x, col_y, method=corr_method)).item()  # type: ignore[call-overload]
            val = float(r) if (r is not None and not math.isnan(r)) else 0.0
        except Exception:
            val = 0.0
        corr_cache[key] = val
        return val

    if target is not None:
        target_col = _unquote_name(str(target).strip())
        if target_col not in all_num_cols:
            raise KeyError(
                f"corr: target column '{target_col}' not found or is not numeric. Numeric columns: {all_num_cols}"
            )
        features = [c for c in num_cols if c != target_col]
        if not features:
            features = [c for c in all_num_cols if c != target_col]
        if not features:
            raise ValueError(f"corr: no other numeric columns to correlate with target '{target_col}'")

        feature_names: list[str] = []
        corr_vals: list[float] = []
        bars: list[str] = []
        abs_vals: list[float] = []

        for feat in features:
            r_val = _pair_corr(feat, target_col)
            abs_r = abs(r_val)
            bar_len = int(round(abs_r * 15))
            bar_char = "█" if r_val >= 0 else "▒"
            feature_names.append(feat)
            corr_vals.append(round(r_val, 2))
            bars.append(bar_char * bar_len)
            abs_vals.append(abs_r)

        paired = sorted(zip(feature_names, corr_vals, bars, abs_vals), key=lambda t: t[3], reverse=True)
        out_pl = pl.DataFrame(
            {
                "Feature": [p[0] for p in paired],
                "Corr": [p[1] for p in paired],
                "Bar": [p[2] for p in paired],
            }
        )
        return DataFrame(out_pl)

    if pairs:
        col_a_list: list[str] = []
        col_b_list: list[str] = []
        corr_vals = []
        strengths: list[str] = []
        abs_vals = []

        for i in range(len(num_cols)):
            for j in range(i + 1, len(num_cols)):
                c1, c2 = num_cols[i], num_cols[j]
                r_val = _pair_corr(c1, c2)
                abs_r = abs(r_val)
                if abs_r >= 0.8:
                    label = "Very Strong"
                elif abs_r >= 0.6:
                    label = "Strong"
                elif abs_r >= 0.4:
                    label = "Moderate"
                elif abs_r >= 0.2:
                    label = "Weak"
                else:
                    label = "Very Weak"

                bar_char = "█" if r_val >= 0 else "▒"
                suffix = "" if r_val >= 0 else " (-)"
                bar_len = int(round(abs_r * 10))
                strength_bar = f"{bar_char * bar_len} {label}{suffix}".strip()

                col_a_list.append(c1)
                col_b_list.append(c2)
                corr_vals.append(round(r_val, 2))
                strengths.append(strength_bar)
                abs_vals.append(abs_r)

        paired_pairs = sorted(zip(col_a_list, col_b_list, corr_vals, strengths, abs_vals), key=lambda t: t[4], reverse=True)
        out_pl = pl.DataFrame(
            {
                "Column A": [p[0] for p in paired_pairs],
                "Column B": [p[1] for p in paired_pairs],
                "Corr": [p[2] for p in paired_pairs],
                "Strength": [p[3] for p in paired_pairs],
            }
        )
        return DataFrame(out_pl)

    # Matrix view (default)
    matrix_data: dict[str, list[Any]] = {"column": num_cols}
    for c2 in num_cols:
        col_vals = [1.0 if c1 == c2 else round(_pair_corr(c1, c2), 2) for c1 in num_cols]
        matrix_data[c2] = col_vals

    return DataFrame(pl.DataFrame(matrix_data))
