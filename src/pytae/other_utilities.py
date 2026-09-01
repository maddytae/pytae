import pandas as pd
import numpy as np

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


_GROUP_X_ALIASES = {
    "g": "group",
    "grp": "group",
    "group": "group",
    "v": "value",
    "val": "value",
    "value": "value",
    "a": "aggfunc",
    "agg": "aggfunc",
    "aggfunc": "aggfunc",
    "dropna": "dropna",
    "observed": "observed",
}


def normalize_group_x_kwargs(kwargs: dict) -> dict:
    """Map g, v/val, a/agg onto group, value, aggfunc."""
    out: dict = {}
    seen_from: dict = {}
    for key, val in kwargs.items():
        if key not in _GROUP_X_ALIASES:
            raise ValueError(f"unknown argument {key!r}; expected {', '.join(sorted(_GROUP_X_ALIASES))}")
        canon = _GROUP_X_ALIASES[key]
        if canon in out:
            raise ValueError(f"{canon} given more than once ({seen_from[canon]!r} and {key!r})")
        out[canon] = val
        seen_from[canon] = key
    return out


def group_x(self, **kwargs):
    '''
    penguins.group_x(group=['island','species','sex'], dropna=True, value='body_mass_g', aggfunc='max')
    penguins.group_x(g='species', v='body_mass_g', a='max')
    penguins.group_x()  # group size n, auto-detect non-numeric group columns
    '''
    kwargs = normalize_group_x_kwargs(kwargs)
    group = kwargs.get("group")
    dropna = kwargs.get("dropna", True)
    observed = kwargs.get("observed", True)
    aggfunc = kwargs.get("aggfunc", "n")
    value = kwargs.get("value")

    df = self.copy()

    if group is None:
        group = df.select_dtypes(exclude=['number']).columns.tolist()
    elif isinstance(group, str):
        group = [group]

    if aggfunc == 'n' or value is None:
        df['n'] = df.groupby(group, dropna=dropna, observed=observed).transform('size')
    else:
        df['x'] = df.groupby(group, dropna=dropna, observed=observed)[value].transform(aggfunc)

    return df



pd.DataFrame.to_clip = to_clip
pd.DataFrame.handle_missing = handle_missing
pd.DataFrame.cols = cols
pd.DataFrame.group_x = group_x