from __future__ import annotations

import pandas as pd


def long(df, c="variable", v="value"):
    """Melt all numeric columns to rows.

    Parameters:
    - c: name for the melted-name column (default 'variable')
    - v: name for the melted-value column (default 'value')
    """
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        raise ValueError("long(): no numeric columns to melt")
    return pd.melt(
        df,
        id_vars=[col for col in df.columns if col not in numeric_cols],
        value_vars=numeric_cols,
        var_name=c,
        value_name=v,
    )


def wide(df, c="variable", v="value", a=None, dropna=True):
    """Pivot a long column into headers.

    Parameters:
    - c: column whose values become headers (default 'variable')
    - v: values column (default 'value')
    - a: if set, use pivot_table with this aggfunc; else pivot, falling back to sum.
      'n' is accepted as an alias for pandas' 'size' (group row count), matching agg_df's convention.
    - dropna: pivot_table only; drop all-NA columns (default True)
    """
    index_cols = [col for col in df.columns if col not in [c, v]]
    aggfunc = "size" if a == "n" else a

    if aggfunc is None:
        try:
            wide_df = df.pivot(index=index_cols, columns=c, values=v).reset_index()
        except ValueError:
            wide_df = df.pivot_table(
                index=index_cols, columns=c, values=v, aggfunc="sum", dropna=dropna
            ).reset_index()
    else:
        wide_df = df.pivot_table(
            index=index_cols, columns=c, values=v, aggfunc=aggfunc, dropna=dropna
        ).reset_index()

    wide_df.columns.name = None
    return wide_df


