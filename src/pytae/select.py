import pandas as pd
import re

def select(self, *args, dtype=None, exclude_dtype=None, contains=None, startswith=None, endswith=None):
    '''
    Select columns based on a combination of column names, regex patterns, and data types.
    
    Parameters:
    self (pd.DataFrame): The DataFrame from which to select columns.
    *args: Variable-length arguments. Can be:
        - A list of column names
        - A regex pattern (string)
    dtype: A string, type, or list of strings/types representing the data type of columns to select. 
           Special values:
           - 'numeric': Selects all numeric columns (int, float).
           - 'non_numeric': Selects all non-numeric columns.
           - 'datetime': Selects all datetime columns.
           - 'category': Selects all categorical columns.
           - 'bool': Selects all boolean columns.
    exclude_dtype: A string, type, or list of strings/types representing the data type of columns to exclude.
                  If provided, all other selection criteria (*args, dtype, contains, etc.) are ignored.
    contains: A string or list of strings to select columns whose names contain any of these substrings.
    startswith: A string or list of strings to select columns whose names start with any of these substrings.
    endswith: A string or list of strings to select columns whose names end with any of these substrings.
    
    Returns:
    pd.DataFrame: A DataFrame with the selected columns.
    
    Raises:
    ValueError: If exclude_dtype is combined with other selection criteria.
    KeyError: If specified columns are not found in the DataFrame.
    TypeError: If invalid arguments are provided.
    '''
    # Check if exclude_dtype is combined with other criteria
    if exclude_dtype is not None and (args or dtype is not None or contains is not None or startswith is not None or endswith is not None):
        raise ValueError("exclude_dtype cannot be combined with other selection criteria.")
    
    selected_cols = set()  # Use a set to avoid duplicate columns
    ordered_cols = [] 
    
    # Handle exclude_dtype (works independently)
    if exclude_dtype is not None:
        if isinstance(exclude_dtype, (str, type)):
            # Single exclude_dtype filtering
            exclude_cols = self.select_dtypes(exclude=[exclude_dtype]).columns.tolist()
        elif isinstance(exclude_dtype, list):
            # List of exclude_dtypes filtering
            exclude_cols = self.select_dtypes(exclude=exclude_dtype).columns.tolist()
        return self[exclude_cols]  # Return only columns not in the excluded dtypes
    
    # Handle *args
    for arg in args:
        if isinstance(arg, list):
            # Handle list of column names
            missing_cols = [col for col in arg if col not in self.columns]
            if missing_cols:
                raise KeyError(f"Columns not found in the DataFrame: {missing_cols}")
            selected_cols.update(arg)  # Add columns from the list
            ordered_cols.extend([col for col in arg if col not in ordered_cols])  # Preserve order
        elif isinstance(arg, str):
            # Handle regex pattern
            regex_cols = self.filter(regex=arg).columns.tolist()
            selected_cols.update(regex_cols)  # Add columns matching the regex
        else:
            raise TypeError("Arguments must be either a list of column names or a regex pattern (string)")
    
    # Handle dtype (single value or list)
    if dtype is not None:
        if isinstance(dtype, str) and dtype == 'numeric':
            # Custom dtype 'numeric' selects all numeric columns
            dtype_cols = self.select_dtypes(include=['int', 'float']).columns.tolist()
        elif isinstance(dtype, str) and dtype == 'non_numeric':
            # Custom dtype 'non_numeric' selects all non-numeric columns
            dtype_cols = self.select_dtypes(exclude=['int', 'float']).columns.tolist()
        elif isinstance(dtype, (str, type)):
            # Single dtype filtering
            dtype_cols = self.select_dtypes(include=[dtype]).columns.tolist()
        elif isinstance(dtype, list):
            # List of dtypes filtering
            dtype_cols = self.select_dtypes(include=dtype).columns.tolist()
        selected_cols.update(dtype_cols)  # Add columns matching the dtype
    
    # Handle contains (single value or list)
    if contains is not None:
        if isinstance(contains, str):
            # Single substring
            contains_cols = [col for col in self.columns if contains in col]
        elif isinstance(contains, list):
            # List of substrings
            contains_cols = [col for col in self.columns if any(sub in col for sub in contains)]
        selected_cols.update(contains_cols)  # Add columns containing the substring(s)
    
    # Handle startswith (single value or list)
    if startswith is not None:
        if isinstance(startswith, str):
            # Single substring
            startswith_cols = [col for col in self.columns if col.startswith(startswith)]
        elif isinstance(startswith, list):
            # List of substrings
            startswith_cols = [col for col in self.columns if any(col.startswith(sub) for sub in startswith)]
        selected_cols.update(startswith_cols)  # Add columns starting with the substring(s)
    
    # Handle endswith (single value or list)
    if endswith is not None:
        if isinstance(endswith, str):
            # Single substring
            endswith_cols = [col for col in self.columns if col.endswith(endswith)]
        elif isinstance(endswith, list):
            # List of substrings
            endswith_cols = [col for col in self.columns if any(col.endswith(sub) for sub in endswith)]
        selected_cols.update(endswith_cols)  # Add columns ending with the substring(s)

    # If ordered_cols exists (from *args), use it as the base and append other selected cols
    if ordered_cols:
        final_cols = ordered_cols + [col for col in selected_cols if col not in ordered_cols]
    else:
        final_cols = list(selected_cols)
    
    
    return self[final_cols]  # Convert set back to list for indexing

# Attach the function to pandas DataFrame
pd.DataFrame.select = select