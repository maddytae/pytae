from __future__ import annotations

import ast
import difflib
import operator
import re
from typing import Any

import pandas as pd

from pytae._text import unquote_name as _unquote_name
from pytae.cli_parsing import _split_qry_entries

# Dictionary mapping string operators to their corresponding functions
ops = {
    ">=": operator.ge, "<=": operator.le,
    ">": operator.gt, "<": operator.lt,
    "==": operator.eq, "!=": operator.ne
}

# String-accessor operators for tuple conditions, e.g. ('startswith', 'Ad')
str_ops = {
    "startswith": lambda s, v: s.str.startswith(v, na=False),
    "endswith": lambda s, v: s.str.endswith(v, na=False),
    "contains": lambda s, v: s.str.contains(v, regex=False, na=False),
    "regex": lambda s, v: s.str.contains(v, regex=True, na=False),
}

# No-value tuple operators, e.g. ('isna',)
unary_ops = {
    "isna": lambda s: s.isna(),
    "notna": lambda s: s.notna(),
}


def _parse_filter_string(raw: str) -> list[tuple[str, Any]]:
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        stripped = stripped[1:-1]
    try:
        entries = _split_qry_entries(stripped)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    pairs: list[tuple[str, Any]] = []
    for key_raw, value_raw in entries:
        key = _unquote_name(key_raw)
        if not key:
            raise ValueError("invalid filter conditions: empty column name")
        if not value_raw:
            raise ValueError(f"invalid filter conditions: '{key}' has no value")
        val_strip = value_raw.strip()
        m_int = re.match(r"^([\[(])\s*([^,()\[\]]+)\s*,\s*([^,()\[\]]+)\s*([\])])$", val_strip)
        if m_int:
            left, b1, b2, right = m_int.groups()
            b1_is_quoted = (b1.startswith("'") and b1.endswith("'")) or (b1.startswith('"') and b1.endswith('"'))
            b2_is_quoted = (b2.startswith("'") and b2.endswith("'")) or (b2.startswith('"') and b2.endswith('"'))
            if not (b1_is_quoted and b2_is_quoted and left == "[" and right == "]"):
                pairs.append((key, val_strip))
                continue

        op_match = re.match(r"^(>=|<=|!=|==|>|<)\s*(.+)$", val_strip)
        if op_match:
            op = op_match.group(1)
            sub_raw = op_match.group(2).strip()
            try:
                sub_val = ast.literal_eval(sub_raw)
            except (ValueError, SyntaxError):
                if len(sub_raw) >= 2 and sub_raw[0] in "'\"" and sub_raw[-1] == sub_raw[0]:
                    sub_val = sub_raw[1:-1]
                else:
                    sub_val = sub_raw
            pairs.append((key, (op, sub_val)))
            continue
        try:
            value = ast.literal_eval(val_strip)
        except (ValueError, SyntaxError):
            if len(val_strip) >= 2 and val_strip[0] in "'\"" and val_strip[-1] == val_strip[0]:
                value = val_strip[1:-1]
            else:
                value = val_strip
        pairs.append((key, value))
    if not pairs:
        raise ValueError("filter() expects at least one condition")
    return pairs


def filter(
    df: pd.DataFrame,
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Filters a DataFrame based on callables, string expressions, dictionary mappings, or keyword arguments.

    This method provides a clean, Pythonic way to filter rows in a DataFrame. Conditions can be
    passed as:
    - A bare callable / lambda accepting the DataFrame, e.g. df.pt.filter(lambda d: d['mass'] > 4000)
    - String expressions matching the CLI -filter syntax (e.g. df.pt.filter("body_mass_g > 5000"),
      df.pt.filter("bill length mm > 40"))
    - Plain dictionaries (e.g. df.pt.filter({"bill length mm": "> 40", "species": "Adelie"}))
    - Keyword arguments (e.g. df.pt.filter(species='Adelie', body_mass_g='> 5000'))
    - Any mix of the above (e.g. df.pt.filter("bill length mm > 40", species="Adelie"))

    Conditions can include direct values, lists of values, tuple-based comparisons (e.g., ('>', 100)),
    tuple-based list membership (e.g., ('in', ['a', 'b'])), or interval conditions (e.g., '(a,b)', '[a,b]').
    It supports both numeric and non-numeric columns. Index is preserved for the returned DataFrame.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to filter.
    *args : callable, str, or dict
        Positional filter conditions:
        - Callable / lambda taking df and returning a boolean Series/array: e.g. lambda d: d['body_mass_g'] > 4000.
        - String expressions, e.g. "body_mass_g > 3500", "bill length mm > 40", or comma-separated
          "species = 'Adelie', body_mass_g > 3500".
        - Dictionaries mapping column names to conditions, e.g. {"bill length mm": "> 40"}.
    **kwargs : Any
        Filter conditions specified as keyword arguments where the keyword is the column name
        and the value is the condition to apply.

    Returns:
    --------
    pd.DataFrame
        A filtered DataFrame containing only the rows that satisfy all conditions.
    """
    if len(args) == 1 and not kwargs and callable(args[0]):
        fn = args[0]
        res = fn(df)
        if isinstance(res, (pd.Series, pd.Index)):
            return df.loc[res]
        elif isinstance(res, (list, tuple)) or hasattr(res, "__iter__"):
            return df.loc[list(res)]
        raise TypeError(f"filter(): callable must return a boolean Series or array-like indexer, got {type(res).__name__}")

    cond_pairs: list[tuple[str, Any]] = []
    for arg in args:
        if callable(arg):
            raise TypeError("filter(): callable/lambda predicates cannot be mixed with other conditions. Pass a single callable: df.pt.filter(lambda d: ...)")
        elif isinstance(arg, str):
            cond_pairs.extend(_parse_filter_string(arg))
        elif isinstance(arg, dict):
            for col, cond in arg.items():
                cond_pairs.append((str(col), cond))
        elif isinstance(arg, (list, tuple)):
            for item in arg:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    cond_pairs.append((str(item[0]), item[1]))
                else:
                    raise TypeError(
                        f"qry() expects filter conditions as strings, dicts, or keyword arguments, got {type(arg).__name__}."
                    )
        else:
            raise TypeError(
                f"qry() expects filter conditions as strings, dicts, or keyword arguments, got {type(arg).__name__}."
            )
    for col, cond in kwargs.items():
        cond_pairs.append((col, cond))

    if not cond_pairs:
        raise ValueError("qry() expects at least one condition (e.g. df.pt.filter('col > 5000') or df.pt.filter(col='> 5000'))")

    normalized_conditions: list[tuple[str, Any]] = []
    for col, cond in cond_pairs:
        clean_col = _unquote_name(col)
        if isinstance(cond, str):
            op_match = re.match(r"^(>=|<=|!=|==|>|<)\s*(.+)$", cond.strip())
            if op_match:
                op = op_match.group(1)
                val_str = op_match.group(2).strip()
                try:
                    val = ast.literal_eval(val_str)
                except (ValueError, SyntaxError):
                    val = val_str.strip("'\"")
                normalized_conditions.append((clean_col, (op, val)))
                continue
        normalized_conditions.append((clean_col, cond))

    out = df
    available = list(df.columns)
    for col, cond in normalized_conditions:
        if col not in available:
            close = difflib.get_close_matches(col, available, n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"unknown column '{col}'{hint}")
        is_numeric = pd.api.types.is_numeric_dtype(out[col])

        if isinstance(cond, list):
            out = out.loc[out[col].isin(cond)]
        elif isinstance(cond, tuple) and len(cond) == 1:
            op = cond[0]
            if op not in unary_ops:
                raise ValueError(f"Unsupported 1-element tuple operator '{op}' for '{col}'. Use one of {list(unary_ops.keys())}.")
            out = out.loc[unary_ops[op](out[col])]
        elif isinstance(cond, tuple) and len(cond) == 2:
            op, value = cond
            if op in ['in', 'not in']:
                if not isinstance(value, list):
                    raise ValueError(f"Second element of tuple for '{col}' with '{op}' must be a list, got {type(value)}")
                if op == 'in':
                    out = out.loc[out[col].isin(value)]
                elif op == 'not in':
                    out = out.loc[~out[col].isin(value)]
            elif op in str_ops:
                if op in ('startswith', 'endswith') and isinstance(value, list):
                    value = tuple(value)
                try:
                    out = out.loc[str_ops[op](out[col], value)]
                except AttributeError as exc:
                    raise ValueError(
                        f"filter: '{op}' needs a string column; '{col}' is {out[col].dtype}. "
                        f"Cast it first, e.g. df.astype({{'{col}': str}}).filter(...)."
                    ) from exc
                except TypeError as exc:
                    raise ValueError(f"filter: '{op}' on '{col}': invalid value {value!r} ({exc})") from exc
            elif op in ops:
                if is_numeric and not isinstance(value, (int, float)):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            pass
                out = out.loc[ops[op](out[col], value)]
            else:
                raise ValueError(
                    f"Unsupported tuple operator '{op}' for '{col}'. "
                    f"Use 'in', 'not in', or one of {list(ops.keys()) + list(str_ops.keys())}."
                )
        elif isinstance(cond, str) and re.match(r'^[\[(].*[\])]$', cond):
            interval_pattern = re.compile(r'^([\[(])([^,]+),([^,]+)([\])])$')
            match = interval_pattern.match(cond)
            if match:
                left_bracket, lower_raw, upper_raw, right_bracket = match.groups()
                lower_str = lower_raw.strip()
                upper_str = upper_raw.strip()
                lower: int | float | str
                upper: int | float | str
                if is_numeric:
                    try:
                        lower = int(lower_str)
                    except ValueError:
                        try:
                            lower = float(lower_str)
                        except ValueError as exc:
                            raise ValueError(
                                f"filter: interval lower bound for numeric column '{col}' must be a number, got {lower_str!r}"
                            ) from exc
                    try:
                        upper = int(upper_str)
                    except ValueError:
                        try:
                            upper = float(upper_str)
                        except ValueError as exc:
                            raise ValueError(
                                f"filter: interval upper bound for numeric column '{col}' must be a number, got {upper_str!r}"
                            ) from exc
                else:
                    lower = lower_str
                    upper = upper_str

                if left_bracket == '[':
                    lower_op = operator.ge
                else:
                    lower_op = operator.gt

                if right_bracket == ']':
                    upper_op = operator.le
                else:
                    upper_op = operator.lt

                out = out.loc[lower_op(out[col], lower) & upper_op(out[col], upper)]
            else:
                out = out.loc[out[col] == cond]
        else:
            out = out.loc[out[col] == cond]

    return out


def qry(
    df: pd.DataFrame,
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """Deprecated alias for filter(). Use filter() or df.pt.filter() instead."""
    import warnings
    warnings.warn(
        "qry() is deprecated and will be removed in a future release; use filter() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return filter(df, *args, **kwargs)
