import pandas as pd
import numpy as np
import operator
import re

# Dictionary mapping string operators to their corresponding functions
ops = {
    ">=": operator.ge, "<=": operator.le,
    ">": operator.gt, "<": operator.lt,
    "==": operator.eq, "!=": operator.ne
}

def qry(self, conditions):
    """
    Filters a DataFrame based on a dictionary of conditions.

    This method provides a flexible way to filter rows in a DataFrame using a dictionary
    of conditions. Conditions can include direct values, lists of values, tuple-based
    comparisons (e.g., ('>', 100)), tuple-based list membership (e.g., ('in', ['a', 'b'])),
    or interval conditions (e.g., '(a,b)', '[a,b]'). It supports both numeric and non-numeric
    columns. Index is not reset for the returned DataFrame since querying should not alter indexing.

    Parameters:
    -----------
    self : pd.DataFrame
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
        - An interval condition (e.g., '(a,b)', '[a,b]'): Filters for rows where the column
          falls within the specified interval (parentheses for exclusive, brackets for inclusive).

    Returns:
    --------
    pd.DataFrame
        A filtered DataFrame containing only the rows that satisfy all conditions.

    Examples:
    ---------
    >>> import pandas as pd
    >>> data = {
    ...     'species': ['Adelie', 'Gentoo', 'Chinstrap', 'Adelie'],
    ...     'body_mass_g': [74125, 271425, 119925, 89100],
    ...     'code': ['A 1', 'B 2', 'C 3', 'D 4']
    ... }
    >>> df = pd.DataFrame(data)

    >>> # Filter for rows where 'species' is 'Adelie'
    >>> df.qry({'species': 'Adelie'})
       species  body_mass_g code
    0   Adelie      74125.0  A 1
    3   Adelie      89100.0  D 4

    >>> # Filter for rows where 'body_mass_g' is greater than 81500
    >>> df.qry({'body_mass_g': ('>', 81500)})
       species  body_mass_g code
    1   Gentoo     271425.0  B 2
    2  Chinstrap    119925.0  C 3

    >>> # Filter for rows where 'species' is in ['Adelie', 'Gentoo']
    >>> df.qry({'species': ('in', ['Adelie', 'Gentoo'])})
       species  body_mass_g code
    0   Adelie      74125.0  A 1
    1   Gentoo     271425.0  B 2
    3   Adelie      89100.0  D 4

    >>> # Filter for rows where 'species' is not in ['Adelie', 'Gentoo']
    >>> df.qry({'species': ('not in', ['Adelie', 'Gentoo'])})
         species  body_mass_g code
    2  Chinstrap     119925.0  C 3

    >>> # Filter for rows where 'body_mass_g' is in the interval (80000, 120000)
    >>> df.qry({'body_mass_g': '(80000,120000)'})
       species  body_mass_g code
    3   Adelie      89100.0  D 4

    >>> # Filter for rows where 'code' equals 'A 1' (whitespace preserved)
    >>> df.qry({'code': ('==', 'A 1')})
      species  body_mass_g code
    0  Adelie      74125.0  A 1

    Notes:
    ------
    - For numeric columns, tuple-based operator conditions (e.g., ('>', 81500)) will
      automatically convert the comparison value to a float. Since values are typically
      provided as literals, whitespace is handled by Python's parser prior to conversion.
    - For non-numeric columns, tuple-based operator conditions (e.g., ('==', 'A 1')) will
      treat the comparison value as-is, preserving any whitespace in string literals.
    - The method modifies the DataFrame in-place during filtering but returns the final
      filtered DataFrame.
    """
    for col, cond in conditions.items():
        is_numeric = pd.api.types.is_numeric_dtype(self[col])

        if isinstance(cond, list):
            # Handle direct list conditions (e.g., ['Adelie', 'Gentoo'])
            self = self.loc[self[col].isin(cond)]
        elif isinstance(cond, tuple) and len(cond) == 2:
            op, value = cond
            if op in ['in', 'not in']:
                if not isinstance(value, list):
                    raise ValueError(f"Second element of tuple for '{col}' with '{op}' must be a list, got {type(value)}")
                if op == 'in':
                    self = self.loc[self[col].isin(value)]
                elif op == 'not in':
                    self = self.loc[~self[col].isin(value)]
            elif op in ops:
                if is_numeric:
                    value = float(value)  # Convert to float for numeric columns
                self = self.loc[ops[op](self[col], value)]
            else:
                raise ValueError(f"Unsupported tuple operator '{op}' for '{col}'. Use 'in', 'not in', or one of {list(ops.keys())}.")
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

                self = self.loc[lower_op(self[col], lower) & upper_op(self[col], upper)]
        else:
            # Handle single value equality (e.g., 'Adelie')
            self = self.loc[self[col] == cond]

    return self

# Attach the method to the DataFrame class
pd.DataFrame.qry = qry