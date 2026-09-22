from __future__ import annotations

import ast
import difflib
import operator
import re
from typing import Any

import pandas as pd

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

def qry(
    df: pd.DataFrame,
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Filters a DataFrame based on a dictionary of conditions.

    This method provides a flexible way to filter rows in a DataFrame using a dictionary
    of conditions. Conditions can include direct values, lists of values, tuple-based
    comparisons (e.g., ('>', 100)), tuple-based list membership (e.g., ('in', ['a', 'b'])),
    or interval conditions (e.g., '(a,b)', '[a,b]'). It supports both numeric and non-numeric
    columns. Index is not reset for the returned DataFrame since querying should not alter indexing.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to filter.
    conditions : dict
        A dictionary where keys are column names and values are conditions to apply.
        Conditions can be:
        - A single value (e.g., 'Adelie'): Filters for rows where the column equals the value.
        - A list of values (e.g., ['Adelie', 'Gentoo']): Filters for rows where the column
          matches any value in the list.
        - A tuple with 'in' and list (e.g., ('in', ['Adelie', 'Gentoo'])): Filters for rows
          where the column matches any value in the list.
        - A tuple with 'not in' and list (e.g., ('not in', ['Adelie', 'Gentoo'])): Filters
          for rows where the column does not match any value in the list.
        - A tuple with an operator and value (e.g., ('>', 81500)): Filters for rows where
          the column satisfies the operator-based condition. Supported operators are
          >=, <=, >, <, ==, !=.
        - A tuple with a string operator and value (e.g., ('startswith', 'Ad')): Filters
          using pandas' `.str` accessor. Supported: 'startswith', 'endswith' (value may
          also be a list of prefixes/suffixes), 'contains', 'regex' (both search anywhere
          in the string, like re.search; 'regex' is 'contains' with regex=True). Missing
          values never match (na=False); requires a string-dtype column.
        - A one-element tuple ('isna',) or ('notna',): Filters for rows where the column
          is/isn't null. Takes no value since these are unary checks.
        - An interval condition (e.g., '(a,b)', '[a,b]'): Filters for rows where the column
          falls within the specified interval (parentheses for exclusive, brackets for inclusive).

    Returns:
    --------
    pd.DataFrame
        A filtered DataFrame containing only the rows that satisfy all conditions.

    Examples:
    ---------
    >>> import pandas as pd
    >>> import pytae as pt
    >>> data = {
    ...     'species': ['Adelie', 'Gentoo', 'Chinstrap', 'Adelie'],
    ...     'body_mass_g': [74125, 271425, 119925, 89100],
    ...     'code': ['A 1', 'B 2', 'C 3', 'D 4']
    ... }
    >>> df = pd.DataFrame(data)

    >>> # Filter for rows where 'species' is 'Adelie'
    >>> df.pt.qry(species='Adelie')
      species  body_mass_g code
    0  Adelie        74125  A 1
    3  Adelie        89100  D 4

    >>> # Filter for rows where 'body_mass_g' is greater than 81500
    >>> df.pt.qry(body_mass_g='> 81500')
         species  body_mass_g code
    1     Gentoo       271425  B 2
    2  Chinstrap       119925  C 3
    3     Adelie        89100  D 4

    >>> # Filter for rows where 'species' is in ['Adelie', 'Gentoo']
    >>> df.pt.qry(species=['Adelie', 'Gentoo'])
      species  body_mass_g code
    0  Adelie        74125  A 1
    1  Gentoo       271425  B 2
    3  Adelie        89100  D 4

    >>> # Filter for rows where 'species' is not in ['Adelie', 'Gentoo']
    >>> df.pt.qry(species=('not in', ['Adelie', 'Gentoo']))
         species  body_mass_g code
    2  Chinstrap       119925  C 3

    >>> # Filter for rows where 'body_mass_g' is in the interval (80000, 120000)
    >>> df.pt.qry(body_mass_g='(80000,120000)')
         species  body_mass_g code
    2  Chinstrap       119925  C 3
    3     Adelie        89100  D 4

    >>> # Filter for rows where 'code' equals 'A 1' (whitespace preserved)
    >>> df.pt.qry(code=('==', 'A 1'))
      species  body_mass_g code
    0  Adelie        74125  A 1

    >>> # Filter for rows where 'species' starts with 'Ad'
    >>> df.pt.qry(species=('startswith', 'Ad'))
      species  body_mass_g code
    0  Adelie        74125  A 1
    3  Adelie        89100  D 4

    >>> # Filter for rows where 'code' matches a regex pattern anywhere in the string
    >>> df.pt.qry(code=('regex', r'^[AB]'))
      species  body_mass_g code
    0  Adelie        74125  A 1
    1  Gentoo       271425  B 2

    >>> # Filter for rows where 'species' is not null
    >>> df.pt.qry(species=('notna',))
         species  body_mass_g code
    0     Adelie        74125  A 1
    1     Gentoo       271425  B 2
    2  Chinstrap       119925  C 3
    3     Adelie        89100  D 4

    Notes:
    ------
    - For numeric columns, tuple-based operator conditions (e.g., ('>', 81500)) will
      automatically convert the comparison value to a float. Since values are typically
      provided as literals, whitespace is handled by Python's parser prior to conversion.
    - For non-numeric columns, tuple-based operator conditions (e.g., ('==', 'A 1')) will
      treat the comparison value as-is, preserving any whitespace in string literals.
    - String-accessor operators ('startswith', 'endswith', 'contains', 'regex') use pandas'
      `.str` accessor and treat missing values as non-matching (`na=False`) rather than
      raising or propagating NaN. 'contains'/'regex' both do a search-anywhere match
      (like `re.search`); 'regex' is the same as 'contains' with `regex=True`.
    - 'isna'/'notna' are one-element tuples (e.g. ('isna',)) since they take no value.
    - Filtering does not modify the original DataFrame. Each condition is applied with
      `.loc[...]` and a new filtered frame is returned; the caller's object is unchanged.
    """
    if args:
        first_arg = args[0]
        raise TypeError(
            "qry() expects filter conditions as keyword arguments, e.g. df.pt.qry(species='Adelie', body_mass_g='> 5000'). "
            f"Positional {type(first_arg).__name__} is not supported."
        )

    if not kwargs:
        raise ValueError("qry() expects at least one condition keyword argument (e.g. df.pt.qry(col='> 5000'))")

    cond_dict: dict[str, Any] = dict(kwargs)

    normalized_conditions: dict[str, Any] = {}
    for col, cond in cond_dict.items():
        if isinstance(cond, str):
            op_match = re.match(r"^(>=|<=|!=|==|>|<)\s*(.+)$", cond.strip())
            if op_match:
                op = op_match.group(1)
                val_str = op_match.group(2).strip()
                try:
                    val = ast.literal_eval(val_str)
                except (ValueError, SyntaxError):
                    val = val_str.strip("'\"")
                normalized_conditions[col] = (op, val)
                continue
        normalized_conditions[col] = cond

    out = df
    available = list(df.columns)
    for col, cond in normalized_conditions.items():
        if col not in available:
            close = difflib.get_close_matches(col, available, n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"unknown column '{col}'{hint}")
        is_numeric = pd.api.types.is_numeric_dtype(out[col])

        if isinstance(cond, list):
            # Handle direct list conditions (e.g., ['Adelie', 'Gentoo'])
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
                    value = tuple(value)  # pandas' str.startswith()/endswith() take a tuple of prefixes, not a list
                try:
                    out = out.loc[str_ops[op](out[col], value)]
                except AttributeError as exc:
                    raise ValueError(
                        f"qry: '{op}' needs a string column; '{col}' is {out[col].dtype}. "
                        f"Cast it first, e.g. df.astype({{'{col}': str}}).qry(...)."
                    ) from exc
                except TypeError as exc:
                    raise ValueError(f"qry: '{op}' on '{col}': invalid value {value!r} ({exc})") from exc
            elif op in ops:
                if is_numeric:
                    value = float(value)  # Convert to float for numeric columns
                out = out.loc[ops[op](out[col], value)]
            else:
                raise ValueError(
                    f"Unsupported tuple operator '{op}' for '{col}'. "
                    f"Use 'in', 'not in', or one of {list(ops.keys()) + list(str_ops.keys())}."
                )
        elif isinstance(cond, str) and re.match(r'^[\[(].*[)\]]$', cond):
            # Handle interval conditions (e.g., '(a,b)', '[a,b]')
            interval_pattern = re.compile(r'^([\[(])(.*),(.*)([\])])$')
            match = interval_pattern.match(cond)
            if match:
                left_bracket, lower, upper, right_bracket = match.groups()
                lower = float(lower) if is_numeric else lower
                upper = float(upper) if is_numeric else upper

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
            # Handle single value equality (e.g., 'Adelie')
            out = out.loc[out[col] == cond]

    return out