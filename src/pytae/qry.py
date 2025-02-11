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
    of conditions. Conditions can include direct values, lists of values, string-based
    comparisons (e.g., '>= 100', '== "value"'), or interval conditions (e.g., '(a,b)', '[a,b]').
    It supports both numeric and non-numeric columns.
    Index is not reset for returning df since query should not change indexing.

    Parameters:
    -----------
    self : pd.DataFrame
        The DataFrame to filter.
    conditions : dict
        A dictionary where keys are column names and values are conditions to apply.
        Conditions can be:
        - A single value (e.g., 74125): Filters for rows where the column equals the value.
        - A list of values (e.g., ['Adelie', 'Gentoo']): Filters for rows where the column
          matches any value in the list.
        - A string with an operator (e.g., '>= 100', '== "value"'): Filters for rows where
          the column satisfies the operator-based condition.
        - An interval condition (e.g., '(a,b)', '[a,b]'): Filters for rows where the column
          falls within the specified interval.

    Returns:
    --------
    pd.DataFrame
        A filtered DataFrame containing only the rows that satisfy all conditions.

    Examples:
    ---------
    >>> import pandas as pd
    >>> data = {
    ...     'species': ['Adelie', 'Adelie', 'Chinstrap', 'Gentoo'],
    ...     'body_mass_g': [74125, 89100, 119925, 271425]
    ... }
    >>> df = pd.DataFrame(data)

    >>> # Filter for rows where 'species' is 'Adelie'
    >>> df.qry({'species': 'Adelie'})
       species  body_mass_g
    0   Adelie      74125.0
    1   Adelie      89100.0

    >>> # Filter for rows where 'body_mass_g' is greater than or equal to 100000
    >>> df.qry({'body_mass_g': '>= 100000'})
        species  body_mass_g
    2  Chinstrap     119925.0
    3     Gentoo     271425.0

    >>> # Filter for rows where 'species' is either 'Adelie' or 'Gentoo'
    >>> df.qry({'species': ['Adelie', 'Gentoo']})
       species  body_mass_g
    0   Adelie      74125.0
    1   Adelie      89100.0
    3    Gentoo     271425.0

    >>> # Filter for rows where 'body_mass_g' is in the interval (80000, 120000)
    >>> df.qry({'body_mass_g': '(80000,120000)'})
       species  body_mass_g
    1   Adelie      89100.0
    2  Chinstrap     119925.0

    Notes:
    ------
    - For numeric columns, conditions with operators (e.g., '>= 100') will automatically
      convert the comparison value to a float. For numeric float will automatically take 
      care of any white space.
    - For non-numeric columns, conditions with operators (e.g., '== "value"') will treat
      the comparison value as a string. Whitespaces will not be automatically removed 
      and they will treated as part of conditions.
    - The method modifies the DataFrame in-place during filtering but returns the final
      filtered DataFrame.
    - The `for-else` construct is used to handle direct equality conditions when no operator
      is found in the condition string. The `else` block only executes if the loop completes
      without encountering a `break`.
    """


        
    for col, cond in conditions.items():
        is_numeric = pd.api.types.is_numeric_dtype(self[col])

        if isinstance(cond, list):
            # Handle list conditions (e.g., ['Adelie', 'Gentoo'])
            self = self.loc[self[col].isin(cond)]
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
            # Handle string conditions (e.g., '==74125')
            for symbol, op_func in ops.items():
                if str(cond).startswith(symbol):
                    # Extract the value after the operator
                    value = cond[len(symbol):]  # No .strip() to preserve whitespace if needed
                
                    if is_numeric:
                        value = float(value)  # Convert to numeric if the column is numeric
                    # Apply the operator and filter the DataFrame
                    self = self.loc[op_func(self[col], value)]
                    break  # Stop checking once a match is found
            else:
                # Handle direct equality (e.g., cond is a single value, not a string with an operator)
                # This else block runs only if no operator match is found (no break triggered).
                self = self.loc[self[col] == cond]

    return self

# Attach the method to the DataFrame class
pd.DataFrame.qry = qry