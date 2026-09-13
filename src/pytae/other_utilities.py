import re

import pandas as pd

def to_clip(self):
    """Copy the DataFrame to the system clipboard (tab-separated, no index)."""
    return self.to_clipboard(index=False)


def handle_missing(self, fillna='.'):
    df = self.copy()

    df_cat_cols = df.columns[df.dtypes == 'category'].tolist()
    for c in df_cat_cols:
        df[c] = df[c].astype("object")

    df_str_cols = df.columns[df.dtypes == object]
    df[df_str_cols] = df[df_str_cols].fillna(fillna)
    df[df_str_cols] = df[df_str_cols].apply(lambda x: x.str.strip())
    df = df.fillna(0)

    return df


def cols(self, ascending=True):
    '''
    Return the column names of the DataFrame sorted or in original order.
    
    Parameters:
    self (pd.DataFrame): The DataFrame whose columns are to be returned.
    ascending (bool or None, optional): 
        - True (default): Sort alphabetically A-Z.
        - False: Sort alphabetically Z-A.
        - None: Return columns in their original DataFrame order (unsorted).
    
    Returns:
    list: A list of column names in the specified order.
    
    Raises:
    ValueError: If an invalid ascending parameter is provided.
    '''
    columns = self.columns.to_list()
    
    if ascending is True:
        return sorted(columns)
    elif ascending is False:
        return sorted(columns, reverse=True)
    elif ascending is None:
        return columns
    else:
        raise ValueError(f"Invalid ascending value '{ascending}'. Must be True, False, or None")


def group_x(self, group=None, dropna=True, observed=True, a="n", v=None):
    """Broadcast a group aggregate to every row (pandas transform).

    Default a='n' is group size. Pass v= and a= for another aggregate.
    If group is omitted, non-numeric columns are used.
    """
    df = self.copy()

    if group is None:
        group = df.select_dtypes(exclude=["number"]).columns.tolist()
    elif isinstance(group, str):
        group = [group]

    if a == "n" or v is None:
        df["n"] = df.groupby(group, dropna=dropna, observed=observed).transform("size")
    else:
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
    strip_special: remove anything that isn't a letter, digit, underscore, or
        whitespace (e.g. %, $, #, !, parentheses).
    squeeze: collapse runs of internal whitespace to a single space.
    fill: replace each individual whitespace character with this string (pair
        with squeeze=True to collapse multi-space runs to one separator first).
    case: 'lower', 'upper', or 'proper' (str.title()).
    dedupe: number collisions after cleaning (revenue, revenue_1, revenue_2, ...).
    """
    cleaned = list(names)
    if strip:
        cleaned = [name.strip() for name in cleaned]
    if strip_special:
        cleaned = [re.sub(r"[^\w\s]", "", name) for name in cleaned]
    if squeeze:
        cleaned = [re.sub(r"\s+", " ", name) for name in cleaned]
    if fill is not None:
        cleaned = [re.sub(r"\s", fill, name) for name in cleaned]
    if case == "lower":
        cleaned = [name.lower() for name in cleaned]
    elif case == "upper":
        cleaned = [name.upper() for name in cleaned]
    elif case == "proper":
        cleaned = [name.title() for name in cleaned]
    if dedupe:
        seen = {}
        deduped = []
        for name in cleaned:
            if name not in seen:
                seen[name] = 0
                deduped.append(name)
            else:
                seen[name] += 1
                deduped.append(f"{name}_{seen[name]}")
        cleaned = deduped
    return cleaned


def clean_columns(self, strip=False, strip_special=False, squeeze=False, fill=None, case=None, dedupe=False):
    """Clean column header names (see clean_column_names() for the per-key behavior)."""
    df = self.copy()
    df.columns = clean_column_names(
        list(df.columns), strip=strip, strip_special=strip_special,
        squeeze=squeeze, fill=fill, case=case, dedupe=dedupe,
    )
    return df


def replace_values(self, mapping, cols=None, exact=True):
    """Replace values (pandas replace()), optionally scoped to specific columns.

    mapping: dict of {old: new}.
    cols: a column name, list of column names, or None for the whole DataFrame.
    exact: True (default) matches whole cell values; False matches a substring
        anywhere in the cell (mapping keys are regex-escaped, so they're treated
        as literal text, not patterns).
    """
    df = self.copy()
    to_replace = mapping if exact else {re.escape(k): v for k, v in mapping.items()}
    if cols is not None:
        target_cols = [cols] if isinstance(cols, str) else list(cols)
        df[target_cols] = df[target_cols].replace(to_replace, regex=not exact)
    else:
        df = df.replace(to_replace, regex=not exact)
    return df



pd.DataFrame.to_clip = to_clip
pd.DataFrame.handle_missing = handle_missing
pd.DataFrame.cols = cols
pd.DataFrame.group_x = group_x
pd.DataFrame.clean_columns = clean_columns
pd.DataFrame.replace_values = replace_values