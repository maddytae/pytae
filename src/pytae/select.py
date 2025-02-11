import pandas as pd
import re

def select(self, *args):
    '''
    Select columns based on a list of column names, regex patterns, or a combination of both.
    
    Parameters:
    self (pd.DataFrame): The DataFrame from which to select columns.
    *args: Variable-length arguments. Can be:
        - List of column names
        - Regex pattern (string)
        - Any combination of lists and regex patterns
    
    Returns:
    pd.DataFrame: A DataFrame with the selected columns.
    '''
    selected_cols = set()  # Use a set to avoid duplicate columns
    
    for arg in args:
        if isinstance(arg, list):
            # Handle list of column names
            missing_cols = [col for col in arg if col not in self.columns]
            if missing_cols:
                raise KeyError(f"Columns not found in the DataFrame: {missing_cols}")
            selected_cols.update(arg)  # Add columns from the list
        elif isinstance(arg, str):
            # Handle regex pattern
            regex_cols = self.filter(regex=arg).columns.tolist()
            selected_cols.update(regex_cols)  # Add columns matching the regex
        else:
            raise TypeError("Arguments must be either a list of column names or a regex pattern (string)")
    
    return self[list(selected_cols)]  # Convert set back to list for indexing


pd.DataFrame.select = select