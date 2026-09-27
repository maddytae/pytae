from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from typing import Any

import pandas as pd


class _EverythingMeta(type):
    def __repr__(cls) -> str:
        return "everything"


class everything(metaclass=_EverythingMeta):
    """Sentinel class/instance representing all remaining unselected columns in pt.select().

    Can be passed either as the class `pt.everything` or called as `pt.everything()`.
    """
    _instance: everything | None = None

    def __new__(cls) -> everything:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "everything()"


def select(
    df: pd.DataFrame,
    *args: Any,
    exclude: str | Sequence[str] | None = None,
    dtype: str | type | Sequence[str | type] | None = None,
    exclude_dtype: str | type | Sequence[str | type] | None = None,
    contains: str | Sequence[str] | None = None,
    startswith: str | Sequence[str] | None = None,
    endswith: str | Sequence[str] | None = None,
    regex: str | Sequence[str] | None = None,
) -> pd.DataFrame:
    """
    Select columns from a DataFrame based on names, regex patterns, slices, data types,
    string matching, or exclusions.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame from which to select columns.
    *args : variable-length arguments
        Can be:
        - Exact column name(s) or slice (e.g. 'species', 'bill_length_mm:body_mass_g').
        - Negative column names to exclude (e.g. '-species', '~island', '-start:end').
        - `everything` or `everything()` to capture all remaining columns.
        - List of column names.
        - Callable `f(col_name) -> bool`.
    exclude : str or list of str, optional
        Column name(s) or slice to exclude from the selection.
    dtype : str, type, or list, optional
        Data type(s) to select (e.g., 'numeric', 'datetime').
    exclude_dtype : str, type, or list, optional
        Data type(s) to exclude by dtype.
    contains : str or list of str, optional
        Substring(s) to match in column names.
    startswith : str or list of str, optional
        Prefix(es) to match in column names.
    endswith : str or list of str, optional
        Suffix(es) to match in column names.
    regex : str or list of str, optional
        Regular expression(s) to match in column names.

    Returns:
    --------
    pd.DataFrame
        Selected columns, with explicit/regex/slice selections first, followed by everything()
        if specified, with any excluded columns removed.
    """
    if exclude_dtype is not None and (args or exclude or dtype or contains or startswith or endswith or regex):
        raise ValueError("exclude_dtype cannot be combined with other selection criteria.")

    all_cols = df.columns.tolist()  # List of all columns for slice positioning

    if exclude_dtype is not None:
        _shorthands = {
            "numeric": ["number"],
            "datetime": ["datetime", "datetimetz"],
            "category": ["category"],
            "bool": ["bool"],
        }
        if exclude_dtype == "non_numeric":
            exclude_cols = df.select_dtypes(include="number").columns.tolist()
        elif isinstance(exclude_dtype, str) and exclude_dtype in _shorthands:
            exclude_cols = df.select_dtypes(exclude=_shorthands[exclude_dtype]).columns.tolist()
        elif isinstance(exclude_dtype, (str, type)):
            exclude_cols = df.select_dtypes(exclude=[exclude_dtype]).columns.tolist()
        elif isinstance(exclude_dtype, (list, tuple)):
            exclude_cols = df.select_dtypes(exclude=list(exclude_dtype)).columns.tolist()
        else:
            raise TypeError("exclude_dtype must be a string, type, or list of strings/types")
        return df[exclude_cols]

    selected_cols: set[Any] = set()
    ordered_cols: list[Any] = []
    excluded_cols: set[Any] = set()
    everything_requested = False

    def _resolve_negation(neg_spec: str) -> list[str]:
        raw = neg_spec.strip()
        if raw in all_cols:
            return [raw]
        elif ":" in raw:
            start_raw, end_raw = raw.split(":", 1)
            start: str | None = start_raw.strip() or None
            end: str | None = end_raw.strip() or None
            if start and start not in all_cols:
                raise KeyError(f"Start column '{start}' not found")
            if end and end not in all_cols:
                raise KeyError(f"End column '{end}' not found")
            start_idx = all_cols.index(start) if start in all_cols else 0
            end_idx = all_cols.index(end) if end in all_cols else len(all_cols) - 1
            return all_cols[start_idx : end_idx + 1]
        else:
            close = difflib.get_close_matches(raw, [str(c) for c in all_cols], n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"Column to exclude not found: '{raw}'{hint}")

    if exclude is not None:
        if isinstance(exclude, str):
            for token in exclude.split(","):
                token = token.strip()
                if token:
                    excluded_cols.update(_resolve_negation(token))
        elif isinstance(exclude, (list, tuple, set)):
            for item in exclude:
                if isinstance(item, str):
                    excluded_cols.update(_resolve_negation(item))
                elif item in df.columns:
                    excluded_cols.add(item)
                else:
                    raise KeyError(f"Column to exclude not found: '{item}'")
        else:
            raise TypeError(f"exclude must be a string or sequence of strings, got {type(exclude)}")

    for arg in args:
        if arg is everything or isinstance(arg, everything):
            everything_requested = True
        elif isinstance(arg, list):
            for col in arg:
                if col in df.columns:
                    selected_cols.add(col)
                    if col not in ordered_cols:
                        ordered_cols.append(col)
                elif isinstance(col, str) and col.startswith(("-", "~")):
                    excluded_cols.update(_resolve_negation(col[1:]))
                else:
                    close = difflib.get_close_matches(str(col), [str(c) for c in all_cols], n=1)
                    hint = f" (did you mean '{close[0]}'?)" if close else ""
                    raise KeyError(f"Column not found: '{col}'{hint}")
        elif isinstance(arg, str):
            if arg in df.columns:  # Exact match first — a literal ':' or '-' in a real column name wins
                selected_cols.add(arg)
                if arg not in ordered_cols:
                    ordered_cols.append(arg)
            elif arg.startswith(("-", "~")):
                excluded_cols.update(_resolve_negation(arg[1:]))
            elif ":" in arg:  # Handle slice notation
                start_raw, end_raw = arg.split(":", 1)
                start = start_raw.strip() or None  # Empty start means from beginning
                end = end_raw.strip() or None     # Empty end means to end
                start_idx = all_cols.index(start) if start in all_cols else 0
                end_idx = all_cols.index(end) if end in all_cols else len(all_cols) - 1
                if start and start not in all_cols:
                    raise KeyError(f"Start column '{start}' not found")
                if end and end not in all_cols:
                    raise KeyError(f"End column '{end}' not found")
                slice_cols = all_cols[start_idx : end_idx + 1]
                selected_cols.update(slice_cols)
                ordered_cols.extend([col for col in slice_cols if col not in ordered_cols])
            else:
                close = difflib.get_close_matches(arg, [str(c) for c in all_cols], n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                regex_hint = "; for a regex use select(regex=...)" if any(ch in arg for ch in "^$|*+?[]()") else ""
                raise KeyError(f"Column not found: '{arg}'{hint}{regex_hint}")
        elif callable(arg):
            func_cols = [col for col in df.columns if arg(col)]
            selected_cols.update(func_cols)
            ordered_cols.extend([col for col in func_cols if col not in ordered_cols])
        else:
            raise TypeError(f"Unsupported argument type: {type(arg)}.")

    if dtype is not None:
        if isinstance(dtype, str):
            if dtype == "numeric":
                dtype_cols = df.select_dtypes(include="number").columns.tolist()
            elif dtype == "non_numeric":
                dtype_cols = df.select_dtypes(exclude="number").columns.tolist()
            elif dtype == "datetime":
                dtype_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
            elif dtype == "category":
                dtype_cols = df.select_dtypes(include=["category"]).columns.tolist()
            elif dtype == "bool":
                dtype_cols = df.select_dtypes(include=["bool"]).columns.tolist()
            else:
                dtype_cols = df.select_dtypes(include=[dtype]).columns.tolist()
        elif isinstance(dtype, (type, list, tuple)):
            dtype_cols = df.select_dtypes(include=list(dtype) if isinstance(dtype, tuple) else dtype).columns.tolist()
        else:
            raise TypeError(f"dtype must be a string, type, list, or tuple, got {type(dtype)}")
        selected_cols.update(dtype_cols)
        ordered_cols.extend([col for col in dtype_cols if col not in ordered_cols])

    if contains is not None:
        if isinstance(contains, str):
            contains_cols = [col for col in df.columns if contains in str(col)]
        elif isinstance(contains, list):
            contains_cols = [col for col in df.columns if any(sub in str(col) for sub in contains)]
        selected_cols.update(contains_cols)
        ordered_cols.extend([col for col in contains_cols if col not in ordered_cols])

    if startswith is not None:
        if isinstance(startswith, str):
            startswith_cols = [col for col in df.columns if str(col).startswith(startswith)]
        elif isinstance(startswith, list):
            startswith_cols = [col for col in df.columns if any(str(col).startswith(sub) for sub in startswith)]
        selected_cols.update(startswith_cols)
        ordered_cols.extend([col for col in startswith_cols if col not in ordered_cols])

    if endswith is not None:
        if isinstance(endswith, str):
            endswith_cols = [col for col in df.columns if str(col).endswith(endswith)]
        elif isinstance(endswith, list):
            endswith_cols = [col for col in df.columns if any(str(col).endswith(sub) for sub in endswith)]
        selected_cols.update(endswith_cols)
        ordered_cols.extend([col for col in endswith_cols if col not in ordered_cols])

    if regex is not None:
        patterns = [regex] if isinstance(regex, str) else list(regex)
        try:
            compiled = [re.compile(p) for p in patterns]
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        regex_cols = [col for col in df.columns if any(p.search(str(col)) for p in compiled)]
        selected_cols.update(regex_cols)
        ordered_cols.extend([col for col in regex_cols if col not in ordered_cols])

    # Final assembly:
    if not ordered_cols:
        if everything_requested or excluded_cols:
            final_cols = [col for col in all_cols if col not in excluded_cols]
            return df[final_cols]
        return df[[]]

    if everything_requested:
        remaining_cols = [col for col in all_cols if col not in selected_cols and col not in excluded_cols]
        ordered_cols.extend(remaining_cols)

    final_cols = [col for col in ordered_cols if col not in excluded_cols]
    return df[final_cols]
