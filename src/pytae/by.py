from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name


def by(df: pd.DataFrame, *cols: Any) -> pd.DataFrame:
    """Set active grouping columns on the DataFrame for downstream operations.

    Downstream operations such as .pt.mutate(), .pt.agg(), .pt.slice_max(), and
    .pt.slice_min() will automatically inherit these grouping columns unless
    explicitly overridden.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    *cols : str
        Column names to group by as positional arguments (e.g. df.pt.by('species', 'island')).
        Lists or non-string arguments are not accepted.

    Returns
    -------
    pd.DataFrame
        The DataFrame with active grouping context set on .attrs['_pt_by'].
    """
    if not cols:
        raise ValueError("df.pt.by() takes at least one column name as positional arguments: df.pt.by('col1', 'col2'). To clear grouping, use df.pt.ungroup().")

    valid_cols: list[str] = []
    for c in cols:
        if c is None:
            raise TypeError("df.pt.by(None) is not supported. To clear grouping, use df.pt.ungroup().")
        if isinstance(c, (list, tuple, Sequence)) and not isinstance(c, str):
            raise TypeError(
                "df.pt.by() takes column names as positional arguments: df.pt.by('col1', 'col2'). "
                "Lists are not accepted. To clear grouping, use df.pt.ungroup()."
            )
        if not isinstance(c, str):
            raise TypeError(f"df.pt.by() column names must be strings, got {type(c).__name__}: {c!r}")
        
        clean = _unquote_name(c.strip())
        if clean not in df.columns:
            # Check if comma-separated string was passed, but enforce positional arguments
            tokens = [_unquote_name(t.strip()) for t in _tokenize(c, ",", keep_quotes=True, track_brackets=True) if t.strip()]
            if len(tokens) > 1 and all(t in df.columns for t in tokens):
                valid_cols.extend(tokens)
                continue
            raise KeyError(f"df.pt.by(): column '{clean}' not found in DataFrame. Available columns: {list(df.columns)}")
        valid_cols.append(clean)

    df.attrs["_pt_by"] = tuple(valid_cols)
    return df


def ungroup(df: pd.DataFrame) -> pd.DataFrame:
    """Clear active grouping columns from the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.

    Returns
    -------
    pd.DataFrame
        The DataFrame with active grouping context removed.
    """
    if "_pt_by" in df.attrs:
        del df.attrs["_pt_by"]
    return df

