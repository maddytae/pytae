import pandas as pd


def long(self, column="variable", value="value"):
    """Melt all numeric columns to rows.

    Parameters:
    - column: name for the melted-name column (default 'variable')
    - value: name for the melted-value column (default 'value')
    """
    numeric_cols = self.select_dtypes(include=["number"]).columns.tolist()
    return pd.melt(
        self,
        id_vars=[c for c in self.columns if c not in numeric_cols],
        value_vars=numeric_cols,
        var_name=column,
        value_name=value,
    )


def wide(df, column="variable", value="value", aggfunc=None, dropna=True):
    """Pivot a long column into headers.

    Parameters:
    - column: column whose values become headers (default 'variable')
    - value: values column (default 'value')
    - aggfunc: if set, use pivot_table; else pivot, falling back to sum
    - dropna: pivot_table only; drop all-NA columns (default True)
    """
    index_cols = [c for c in df.columns if c not in [column, value]]

    if aggfunc is None:
        try:
            wide_df = df.pivot(index=index_cols, columns=column, values=value).reset_index()
        except ValueError:
            wide_df = df.pivot_table(
                index=index_cols, columns=column, values=value, aggfunc="sum", dropna=dropna
            ).reset_index()
    else:
        wide_df = df.pivot_table(
            index=index_cols, columns=column, values=value, aggfunc=aggfunc, dropna=dropna
        ).reset_index()

    wide_df.columns.name = None
    return wide_df


pd.DataFrame.long = long
pd.DataFrame.wide = wide
