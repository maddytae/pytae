import pandas as pd


def long(self, c="variable", v="value"):
    """Melt all numeric columns to rows.

    Parameters:
    - c: name for the melted-name column (default 'variable')
    - v: name for the melted-value column (default 'value')
    """
    numeric_cols = self.select_dtypes(include=["number"]).columns.tolist()
    return pd.melt(
        self,
        id_vars=[col for col in self.columns if col not in numeric_cols],
        value_vars=numeric_cols,
        var_name=c,
        value_name=v,
    )


def wide(df, c="variable", v="value", a=None, dropna=True):
    """Pivot a long column into headers.

    Parameters:
    - c: column whose values become headers (default 'variable')
    - v: values column (default 'value')
    - a: if set, use pivot_table with this aggfunc; else pivot, falling back to sum
    - dropna: pivot_table only; drop all-NA columns (default True)
    """
    index_cols = [col for col in df.columns if col not in [c, v]]

    if a is None:
        try:
            wide_df = df.pivot(index=index_cols, columns=c, values=v).reset_index()
        except ValueError:
            wide_df = df.pivot_table(
                index=index_cols, columns=c, values=v, aggfunc="sum", dropna=dropna
            ).reset_index()
    else:
        wide_df = df.pivot_table(
            index=index_cols, columns=c, values=v, aggfunc=a, dropna=dropna
        ).reset_index()

    wide_df.columns.name = None
    return wide_df


pd.DataFrame.long = long
pd.DataFrame.wide = wide
