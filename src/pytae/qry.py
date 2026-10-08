"""Deprecated module: row filtering via qry(). Use pytae.filter instead."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .filter import _parse_filter_string as _parse_qry_string
from .filter import filter, ops, str_ops, unary_ops


def qry(
    df: pd.DataFrame,
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """Deprecated alias for filter(). Use filter() or df.pt.filter() instead."""
    import warnings
    warnings.warn(
        "qry() is deprecated; use filter() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return filter(df, *args, **kwargs)


__all__ = ["qry", "ops", "str_ops", "unary_ops", "_parse_qry_string"]