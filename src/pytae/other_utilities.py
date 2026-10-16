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
    bar_max_width = 20

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
    bar_max_width = 20
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
