"""General tabular utilities: clipboard export, missing-value handling, column sorting, header cleaning, and value replacement."""

from __future__ import annotations

import re
from collections.abc import Hashable, Sequence
from typing import Any

import pandas as pd

from pytae._text import unquote_name as _unquote_name


def to_clip(df: pd.DataFrame | pd.Series) -> None:
    """Copy the DataFrame or Series to the system clipboard (tab-separated, no index)."""
    return df.to_clipboard(index=False)


pd.DataFrame.to_clip = to_clip
pd.Series.to_clip = to_clip


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
            if isinstance(underlying, pl.LazyFrame):
                try:
                    n_rows = underlying.select(pl.len()).collect().item()
                except Exception:
                    n_rows = len(underlying.collect())
                schema = underlying.collect_schema()
                preview = underlying.limit(25).collect()
            else:
                n_rows = underlying.height
                schema = underlying.schema
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
    import polars as pl

    from pytae.dataframe import DataFrame

    if isinstance(df, pl.LazyFrame):
        pldf = df.collect()
    elif isinstance(df, pl.DataFrame):
        pldf = df
    elif hasattr(df, "_df"):
        inner = df._df
        pldf = inner.collect() if isinstance(inner, pl.LazyFrame) else inner
    else:
        try:
            if isinstance(df, pd.DataFrame):
                pldf = pl.from_pandas(df)
            else:
                pldf = pl.DataFrame(df)
        except Exception:
            pldf = pl.DataFrame(df)

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

    total = counted["Count"].sum() if len(counted) > 0 else 0
    max_cnt = counted["Count"].max() if len(counted) > 0 else 1
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
    import polars as pl

    from pytae.dataframe import DataFrame

    raw = col.strip() if isinstance(col, str) else ""
    target_col: str | None = None

    if isinstance(df, pl.LazyFrame):
        pldf = df.collect()
    elif isinstance(df, pl.DataFrame):
        pldf = df
    elif hasattr(df, "_df"):
        inner = df._df
        pldf = inner.collect() if isinstance(inner, pl.LazyFrame) else inner
    else:
        try:
            if isinstance(df, pd.DataFrame):
                pldf = pl.from_pandas(df)
            else:
                pldf = pl.DataFrame(df)
        except Exception:
            pldf = pl.DataFrame(df)

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

    min_val = float(s_clean.min())  # type: ignore[arg-type]
    max_val = float(s_clean.max())  # type: ignore[arg-type]
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
    bin_counts = [0] * bins
    vals = s_clean.to_list()
    for v in vals:
        if v == max_val:
            idx = bins - 1
        else:
            idx = int((v - min_val) / step)
            if idx >= bins:
                idx = bins - 1
            elif idx < 0:
                idx = 0
        bin_counts[idx] += 1

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

    import polars as pl

    from pytae.dataframe import DataFrame

    if isinstance(df, pl.LazyFrame):
        pldf = df.collect()
    elif isinstance(df, pl.DataFrame):
        pldf = df
    elif hasattr(df, "_df"):
        inner = df._df
        pldf = inner.collect() if isinstance(inner, pl.LazyFrame) else inner
    else:
        try:
            if isinstance(df, pd.DataFrame):
                pldf = pl.from_pandas(df)
            else:
                pldf = pl.DataFrame(df)
        except Exception:
            pldf = pl.DataFrame(df)

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

    import polars as pl

    if isinstance(df, pl.LazyFrame):
        pldf = df.collect()
    elif isinstance(df, pl.DataFrame):
        pldf = df
    elif hasattr(df, "_df"):
        inner = df._df
        pldf = inner.collect() if isinstance(inner, pl.LazyFrame) else inner
    else:
        try:
            if isinstance(df, pd.DataFrame):
                pldf = pl.from_pandas(df)
            else:
                pldf = pl.DataFrame(df)
        except Exception:
            pldf = pl.DataFrame(df)

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

    import polars as pl

    from pytae.dataframe import DataFrame

    if isinstance(df, pl.LazyFrame):
        pldf = df.collect()
    elif isinstance(df, pl.DataFrame):
        pldf = df
    elif hasattr(df, "_df"):
        inner = df._df
        pldf = inner.collect() if isinstance(inner, pl.LazyFrame) else inner
    else:
        try:
            if isinstance(df, pd.DataFrame):
                pldf = pl.from_pandas(df)
            else:
                pldf = pl.DataFrame(df)
        except Exception:
            pldf = pl.DataFrame(df)

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
            clean = pldf.select(
                [
                    pl.col(target_col).cast(pl.Float64, strict=False).alias("y"),
                    pl.col(feat).cast(pl.Float64, strict=False).alias("x"),
                ]
            ).filter(
                pl.col("y").is_not_null()
                & pl.col("x").is_not_null()
                & pl.col("y").is_not_nan()
                & pl.col("x").is_not_nan()
            )
            if clean.height < 2:
                r_val = 0.0
            else:
                try:
                    r = clean.select(pl.corr("x", "y", method=method_clean)).item()
                    r_val = float(r) if (r is not None and not math.isnan(r)) else 0.0
                except Exception:
                    r_val = 0.0

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
                clean = pldf.select(
                    [
                        pl.col(c1).cast(pl.Float64, strict=False).alias("x"),
                        pl.col(c2).cast(pl.Float64, strict=False).alias("y"),
                    ]
                ).filter(
                    pl.col("x").is_not_null()
                    & pl.col("y").is_not_null()
                    & pl.col("x").is_not_nan()
                    & pl.col("y").is_not_nan()
                )
                if clean.height < 2:
                    r_val = 0.0
                else:
                    try:
                        r = clean.select(pl.corr("x", "y", method=method_clean)).item()
                        r_val = float(r) if (r is not None and not math.isnan(r)) else 0.0
                    except Exception:
                        r_val = 0.0

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

        paired = sorted(zip(col_a_list, col_b_list, corr_vals, strengths, abs_vals), key=lambda t: t[4], reverse=True)
        out_pl = pl.DataFrame(
            {
                "Column A": [p[0] for p in paired],
                "Column B": [p[1] for p in paired],
                "Corr": [p[2] for p in paired],
                "Strength": [p[3] for p in paired],
            }
        )
        return DataFrame(out_pl)

    # Matrix view (default)
    matrix_data: dict[str, list[Any]] = {"column": num_cols}
    for c2 in num_cols:
        col_vals = []
        for c1 in num_cols:
            if c1 == c2:
                col_vals.append(1.0)
            else:
                clean = pldf.select(
                    [
                        pl.col(c1).cast(pl.Float64, strict=False).alias("x"),
                        pl.col(c2).cast(pl.Float64, strict=False).alias("y"),
                    ]
                ).filter(
                    pl.col("x").is_not_null()
                    & pl.col("y").is_not_null()
                    & pl.col("x").is_not_nan()
                    & pl.col("y").is_not_nan()
                )
                if clean.height < 2:
                    r_val = 0.0
                else:
                    try:
                        r = clean.select(pl.corr("x", "y", method=method_clean)).item()
                        r_val = float(r) if (r is not None and not math.isnan(r)) else 0.0
                    except Exception:
                        r_val = 0.0
                col_vals.append(round(r_val, 2))
        matrix_data[c2] = col_vals

    return DataFrame(pl.DataFrame(matrix_data))
