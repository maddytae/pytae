import pandas as pd

# Canonical names plus short aliases used by long()/wide() and the CLI.
_RESHAPE_ALIASES = {
    "c": "column",
    "col": "column",
    "column": "column",
    "v": "value",
    "val": "value",
    "value": "value",
    "a": "aggfunc",
    "agg": "aggfunc",
    "aggfunc": "aggfunc",
    "dropna": "dropna",
}
_LONG_CANON = ("column", "value")
_WIDE_CANON = ("column", "value", "aggfunc", "dropna")


def normalize_reshape_kwargs(kwargs, *, allow_agg: bool = False) -> dict:
    """Map c/column, v, a/agg onto col, value, aggfunc. Reject unknown or duplicate names."""
    allowed = _WIDE_CANON if allow_agg else _LONG_CANON
    aliases = {src: dst for src, dst in _RESHAPE_ALIASES.items() if dst in allowed}
    out: dict = {}
    seen_from: dict = {}
    for key, val in kwargs.items():
        if key not in aliases:
            raise ValueError(f"unknown argument {key!r}; expected {', '.join(sorted(aliases))}")
        canon = aliases[key]
        if canon in out:
            raise ValueError(f"{canon} given more than once ({seen_from[canon]!r} and {key!r})")
        out[canon] = val
        seen_from[canon] = key
    return out


def long(self, **kwargs):
    """
    This function converts a wide dataframe to a long format by melting all numeric columns.
    The two new columns are named 'variable' and 'value' by default, but can be changed using
    keyword arguments.

    Parameters:
    - column / c / col (str, optional): name for the melted-name column. Default 'variable'.
    - value / v / val (str, optional): name for the melted-value column. Default 'value'.

    Returns:
    - pd.DataFrame: The melted dataframe with all numeric columns converted to long format.
    """

    
    # Identify numeric columns in the dataframe
    kwargs = normalize_reshape_kwargs(kwargs, allow_agg=False)
    numeric_cols = self.select_dtypes(include=['number']).columns.tolist()
    
    # Melt the dataframe to long format, keeping only numeric columns
    melted_df = pd.melt(self, id_vars=[col for col in self.columns if col not in numeric_cols],
                        value_vars=numeric_cols, var_name=kwargs.get('column', 'variable'), 
                                                 value_name=kwargs.get('value', 'value'))
    
    return melted_df



#note that long and wide are not fungible


def wide(df, **kwargs):
    """
    Converts a long dataframe back to a wide format. It tries to use pivot for straightforward reshaping without aggregation.
    Falls back to pivot_table if there's a uniqueness constraint violation or if an aggregation function is explicitly provided.

    Parameters:
    - df (pd.DataFrame): The dataframe to reshape.
    - column / c / col (str, optional): column whose values become headers. Default 'variable'.
    - value / v / val (str, optional): values column. Default 'value'.
    - aggfunc / a / agg (optional): if set, use pivot_table with this aggregation.
    - dropna (bool, optional): Applies only to pivot_table. Specifies whether to drop columns with all NaN values.
                               Default is True.

    Returns:
    - pd.DataFrame: The pivoted dataframe in a wide format.
    """
    kwargs = normalize_reshape_kwargs(kwargs, allow_agg=True)
    col = kwargs.get('column', 'variable')
    value = kwargs.get('value', 'value')
    aggfunc = kwargs.get('aggfunc', None)
    dropna = kwargs.get('dropna', True)
    
    index_cols = [c for c in df.columns if c not in [col, value]]
    
    if aggfunc is None:
        try:
            wide_df = df.pivot(index=index_cols, columns=col, values=value).reset_index()
    
        except ValueError:
            wide_df = df.pivot_table(index=index_cols, columns=col, values=value, aggfunc='sum', dropna=dropna).reset_index()
    else:
        wide_df = df.pivot_table(index=index_cols, columns=col, values=value, aggfunc=aggfunc, dropna=dropna).reset_index()

    # Reset index and clean column names
    wide_df.columns.name = None
    
    return wide_df





pd.DataFrame.long = long
pd.DataFrame.wide = wide