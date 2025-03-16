import pandas as pd
import re

# Define the sentinel class
class everything:
    pass

def select(self, *args, dtype=None, exclude_dtype=None, contains=None, startswith=None, endswith=None):
    '''
    Select columns from a DataFrame based on names, regex patterns, slices, data types, or string matching.
    
    Parameters:
    -----------
    self : pd.DataFrame
        The DataFrame from which to select columns.
    *args : variable-length arguments
        Can be: list of column names, string (exact name, regex, or slice like 'start:end'), everything(), or callable.
    dtype : str, type, or list, optional
        Data type(s) to select (e.g., 'numeric', 'datetime').
    exclude_dtype : str, type, or list, optional
        Data type(s) to exclude.
    contains : str or list of str, optional
        Substring(s) to match in column names.
    startswith : str or list of str, optional
        Prefix(es) to match in column names.
    endswith : str or list of str, optional
        Suffix(es) to match in column names.
    
    Returns:
    --------
    pd.DataFrame
        Selected columns, with explicit/regex/slice selections first, followed by everything() if specified.
    '''
    if exclude_dtype is not None and (args or dtype or contains or startswith or endswith):
        raise ValueError("exclude_dtype cannot be combined with other selection criteria.")
    
    selected_cols = set()
    ordered_cols = []
    all_cols = self.columns.tolist()  # List of all columns for slice positioning
    
    if exclude_dtype is not None:
        if isinstance(exclude_dtype, (str, type)):
            exclude_cols = self.select_dtypes(exclude=[exclude_dtype]).columns.tolist()
        elif isinstance(exclude_dtype, list):
            exclude_cols = self.select_dtypes(exclude=exclude_dtype).columns.tolist()
        else:
            raise TypeError("exclude_dtype must be a string, type, or list of strings/types")
        return self[exclude_cols]
    
    for arg in args:
        if isinstance(arg, list):
            missing_cols = [col for col in arg if col not in self.columns]
            if missing_cols:
                raise KeyError(f"Columns not found: {missing_cols}")
            selected_cols.update(arg)
            ordered_cols.extend([col for col in arg if col not in ordered_cols])
        elif isinstance(arg, str):
            if ':' in arg:  # Handle slice notation
                start, end = arg.split(':', 1)
                start = start.strip() or None  # Empty start means from beginning
                end = end.strip() or None     # Empty end means to end
                start_idx = all_cols.index(start) if start in all_cols else 0
                end_idx = all_cols.index(end) if end in all_cols else len(all_cols) - 1
                if start and start not in all_cols:
                    raise KeyError(f"Start column '{start}' not found")
                if end and end not in all_cols:
                    raise KeyError(f"End column '{end}' not found")
                slice_cols = all_cols[start_idx:end_idx + 1]
                selected_cols.update(slice_cols)
                ordered_cols.extend([col for col in slice_cols if col not in ordered_cols])
            elif arg in self.columns:  # Exact match
                selected_cols.add(arg)
                if arg not in ordered_cols:
                    ordered_cols.append(arg)
            else:  # Treat as regex
                regex_cols = self.filter(regex=arg).columns.tolist()
                selected_cols.update(regex_cols)
                ordered_cols.extend([col for col in regex_cols if col not in ordered_cols])
        elif isinstance(arg, everything):
            remaining_cols = [col for col in self.columns if col not in selected_cols]
            selected_cols.update(remaining_cols)
            ordered_cols.extend([col for col in remaining_cols if col not in ordered_cols])
        elif callable(arg):
            func_cols = [col for col in self.columns if arg(col)]
            selected_cols.update(func_cols)
            ordered_cols.extend([col for col in func_cols if col not in ordered_cols])
        else:
            raise TypeError(f"Unsupported argument type: {type(arg)}.")

    if dtype is not None:
        if isinstance(dtype, str):
            if dtype == 'numeric':
                dtype_cols = self.select_dtypes(include=['int8', 'int16', 'int32', 'int64', 'float16', 'float32', 'float64']).columns.tolist()
            elif dtype == 'non_numeric':
                dtype_cols = self.select_dtypes(exclude=['int8', 'int16', 'int32', 'int64', 'float16', 'float32', 'float64']).columns.tolist()
            elif dtype == 'datetime':
                dtype_cols = self.select_dtypes(include=['datetime64[ns]']).columns.tolist()
            elif dtype == 'category':
                dtype_cols = self.select_dtypes(include=['category']).columns.tolist()
            elif dtype == 'bool':
                dtype_cols = self.select_dtypes(include=['bool']).columns.tolist()
            else:
                dtype_cols = self.select_dtypes(include=[dtype]).columns.tolist()
        elif isinstance(dtype, (type, list)):
            dtype_cols = self.select_dtypes(include=dtype).columns.tolist()
        selected_cols.update(dtype_cols)
        ordered_cols.extend([col for col in dtype_cols if col not in ordered_cols])

    if contains is not None:
        if isinstance(contains, str):
            contains_cols = [col for col in self.columns if contains in col]
        elif isinstance(contains, list):
            contains_cols = [col for col in self.columns if any(sub in col for sub in contains)]
        selected_cols.update(contains_cols)
        ordered_cols.extend([col for col in contains_cols if col not in ordered_cols])

    if startswith is not None:
        if isinstance(startswith, str):
            startswith_cols = [col for col in self.columns if col.startswith(startswith)]
        elif isinstance(startswith, list):
            startswith_cols = [col for col in self.columns if any(col.startswith(sub) for sub in startswith)]
        selected_cols.update(startswith_cols)
        ordered_cols.extend([col for col in startswith_cols if col not in ordered_cols])

    if endswith is not None:
        if isinstance(endswith, str):
            endswith_cols = [col for col in self.columns if col.endswith(endswith)]
        elif isinstance(endswith, list):
            endswith_cols = [col for col in self.columns if any(col.endswith(sub) for sub in endswith)]
        selected_cols.update(endswith_cols)
        ordered_cols.extend([col for col in endswith_cols if col not in ordered_cols])

    return self[ordered_cols]

# Attach to pandas DataFrame
pd.DataFrame.select = select
