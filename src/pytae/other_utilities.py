from __future__ import annotations

import re

import pandas as pd


def to_clip(df):
    """Copy the DataFrame to the system clipboard (tab-separated, no index)."""
    return df.to_clipboard(index=False)


def handle_missing(df, fillna='.'):
    df = df.copy()

    df_cat_cols = df.columns[df.dtypes == 'category'].tolist()
    for c in df_cat_cols:
        df[c] = df[c].astype("object")

    # Only treat columns actually holding strings as text. pandas' own dedicated
    # string dtype (e.g. pandas >= 3.0's default "str" columns) is homogeneous by
    # construction; legacy object-dtype columns need a value-level check since
    # object can also hold bools/mixed Python objects, which .str.strip() would corrupt.
    def _is_string_col(s):
        if s.dtype == object:
            return s.dropna().map(type).eq(str).all()
        return pd.api.types.is_string_dtype(s)

    df_str_cols = [c for c in df.columns if _is_string_col(df[c])]
    df[df_str_cols] = df[df_str_cols].fillna(fillna)
    df[df_str_cols] = df[df_str_cols].apply(lambda x: x.str.strip())

    # fillna(0) should only touch numeric columns — filling datetime/bool/other
    # non-numeric columns with the literal int 0 silently corrupts them.
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    return df


def cols(df, ascending=True):
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


def group_x(df, group=None, dropna=True, observed=True, a="n", v=None):
    """Broadcast a group aggregate to every row (pandas transform).

    Default a='n' is group size. Pass v= and a= for another aggregate.
    If group is omitted, non-numeric columns are used.
    """
    df = df.copy()

    if group is None:
        group = df.select_dtypes(exclude=["number"]).columns.tolist()
        if not group:
            raise ValueError("group_x: no non-numeric columns to group by; pass group= explicitly")
    elif isinstance(group, str):
        group = [group]

    if a == "n" or v is None:
        if "n" in df.columns:
            raise ValueError("group_x: column 'n' already exists; rename it first or pass a=/v= for a different aggregate.")
        df["n"] = df.groupby(group, dropna=dropna, observed=observed).transform("size")
    else:
        if "x" in df.columns:
            raise ValueError("group_x: column 'x' already exists; rename it first.")
        df["x"] = df.groupby(group, dropna=dropna, observed=observed)[v].transform(a)

    return df



def clean_column_names(
    names,
    *,
    strip=False,
    strip_special=False,
    squeeze=False,
    fill=None,
    case=None,
    dedupe=False,
):
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


def clean_columns(df, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False):
    """Clean column header names (see clean_column_names() for the per-key behavior)."""
    df = df.copy()
    df.columns = clean_column_names(
        list(df.columns), strip=strip, strip_special=strip_special,
        squeeze=squeeze, fill=fill, case=case, dedupe=dedupe,
    )
    return df


def replace_values(df, v, c=None, exact=True):
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