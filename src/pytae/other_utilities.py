"""General tabular utilities: clipboard export, missing-value handling, column sorting, header cleaning, and value replacement."""

from __future__ import annotations

import re
from collections.abc import Hashable, Sequence
from typing import Any

import pandas as pd


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


def handle_missing(
    df: pd.DataFrame,
    fillna: str = ".",
    numeric_fill: Any = 0,
    cols: Sequence[str] | None = None,
    preserve_categories: bool = True,
) -> pd.DataFrame:
    """Fill missing values across columns with type-appropriate defaults.

    - String/object columns: filled with `fillna` (default '.') and stripped.
    - Categorical columns: category preserved (adds `fillna` category if needed) and filled.
    - Numeric columns: filled with `numeric_fill` (default 0). Can also be "mean", "median", or None.
    - Bool/datetime columns: left untouched by default to avoid corruption.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to process.
    fillna : str, default '.'
        Fill value for string, object, and categorical columns.
    numeric_fill : number, "mean", "median", or None, default 0
        Fill value for numeric columns. If None, numeric columns are not filled.
    cols : sequence of str, optional
        Specific columns to handle. If None, all applicable columns are processed.
    preserve_categories : bool, default True
        If True, categorical columns keep their categorical dtype instead of being
        converted to object.
    """
    df = df.copy()
    target_cols = set(cols) if cols is not None else set(df.columns)

    # Categorical columns
    cat_cols = [c for c in df.columns if c in target_cols and isinstance(df[c].dtype, pd.CategoricalDtype)]
    for c in cat_cols:
        if preserve_categories:
            if fillna not in df[c].cat.categories:
                df[c] = df[c].cat.add_categories([fillna])
            df[c] = df[c].fillna(fillna)
        else:
            df[c] = df[c].astype("object").fillna(fillna).str.strip()

    # String / object columns (excluding categorical)
    def _is_string_col(s: pd.Series) -> bool:
        if isinstance(s.dtype, pd.CategoricalDtype):
            return False
        if s.dtype == object:
            non_na = s.dropna()
            if len(non_na) == 0:
                return True
            return non_na.map(type).eq(str).all()
        return pd.api.types.is_string_dtype(s)

    str_cols = [c for c in df.columns if c in target_cols and _is_string_col(df[c])]
    for c in str_cols:
        df[c] = df[c].fillna(fillna)
        if hasattr(df[c], "str") and callable(getattr(df[c].str, "strip", None)):
            df[c] = df[c].str.strip()

    # Numeric columns
    if numeric_fill is not None:
        num_cols = [c for c in df.select_dtypes(include="number").columns if c in target_cols]
        for c in num_cols:
            if numeric_fill == "mean":
                df[c] = df[c].fillna(df[c].mean())
            elif numeric_fill == "median":
                df[c] = df[c].fillna(df[c].median())
            else:
                df[c] = df[c].fillna(numeric_fill)

    return df


def cols(df: pd.DataFrame, ascending: bool | None = True) -> list:
    '''
    Return the column names of the DataFrame sorted or in original order.
    
    Parameters:
    df (pd.DataFrame): The DataFrame whose columns are to be returned.
    ascending (bool or None, optional): 
        - True (default): Sort alphabetically A-Z.
        - False: Sort alphabetically Z-A.
        - None: Return columns in their original DataFrame order (unsorted).
    
    Returns:
    list: A list of column names in the specified order.
    
    Raises:
    ValueError: If an invalid ascending parameter is provided.
    '''
    columns = df.columns.to_list()
    
    if ascending is True:
        return sorted(columns)
    elif ascending is False:
        return sorted(columns, reverse=True)
    elif ascending is None:
        return columns
    else:
        raise ValueError(f"Invalid ascending value '{ascending}'. Must be True, False, or None")



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
        list(df.columns), strip=strip, strip_special=strip_special,
        squeeze=squeeze, fill=fill, case=case, dedupe=dedupe,
    )
    return df


def replace_values(
    df: pd.DataFrame,
    v: dict[Any, Any],
    c: str | Sequence[str] | None = None,
    exact: bool = True,
) -> pd.DataFrame:
    """Replace values (pandas replace()), optionally scoped to specific columns.
    Parameter names match the -replace_values CLI flag's v=/c=/exact= keys.

    v: dict of {old: new}.
    c: a column name, list of column names, or None for the whole DataFrame.
    exact: True (default) matches whole cell values; False matches a substring
        anywhere in the cell (v's keys are regex-escaped, so they're treated
        as literal text, not patterns).
    """
    df = df.copy()
    to_replace = v if exact else {re.escape(str(old)): new for old, new in v.items()}
    target_cols = ([c] if isinstance(c, str) else list(c)) if c is not None else list(df.columns)
    if not exact:
        non_string_cols = [col for col in target_cols if not pd.api.types.is_string_dtype(df[col])]
        if non_string_cols:
            raise ValueError(
                f"replace_values: exact=False (substring match) only works on string/object "
                f"columns; non-string column(s): {non_string_cols}"
            )
    if c is not None:
        df[target_cols] = df[target_cols].replace(to_replace, regex=not exact)
    else:
        df = df.replace(to_replace, regex=not exact)
    return df


def format_glimpse(df: pd.DataFrame, width: int | None = None) -> str:
    """Format DataFrame as a transposed glimpse summary (like dplyr::glimpse / Polars).

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame to glimpse.
    width : int, optional
        Maximum line width (defaults to terminal width or 80).
    """
    if width is None:
        import shutil
        width = shutil.get_terminal_size(fallback=(80, 24)).columns

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
        sample_vals: list[str] = []
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
            vals_str = vals_str[:remaining_width - 3].rstrip(", ") + "..."
        lines.append(prefix + vals_str)

    return "\n".join(lines)


def glimpse(df: pd.DataFrame, width: int | None = None) -> pd.DataFrame:
    """Print a transposed overview of DataFrame columns, dtypes, and sample values.

    Returns the original DataFrame for method chaining.
    """
    print(format_glimpse(df, width=width))
    return df


def dedupe(
    df: pd.DataFrame,
    *cols: str | Sequence[str],
    keep: str | bool = "first",
) -> pd.DataFrame:
    """Drop duplicate rows, optionally restricted to specific columns, resetting index.

    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame.
    *cols : str or sequence of str, optional
        Column name(s) to consider for identifying duplicate rows. If omitted,
        all columns are used.
    keep : {'first', 'last', False}, default 'first'
        Determines which duplicates (if any) to keep:
        - 'first' : Drop duplicates except for the first occurrence.
        - 'last' : Drop duplicates except for the last occurrence.
        - False : Drop all duplicates.

    Returns:
    --------
    pd.DataFrame
        Deduplicated DataFrame with a reset 0-indexed RangeIndex.
    """
    flat_cols: list[str] = []
    for c in cols:
        if isinstance(c, str):
            flat_cols.append(c)
        elif isinstance(c, (list, tuple, Sequence)):
            flat_cols.extend(str(x) for x in c)
        else:
            flat_cols.append(str(c))

    subset = flat_cols if flat_cols else None
    if subset is not None:
        unknown = [col for col in subset if col not in df.columns]
        if unknown:
            raise KeyError(
                f"dedupe: column(s) {unknown} not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

    return df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)