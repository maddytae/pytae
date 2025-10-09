import pandas as pd

def _agg_df_list(self, agg_types, dropna):
    """
    Helper function to handle string/list aggfunc for agg_df.
    Applies aggregations to all numeric columns.
    """
    # Convert aggfunc to list if string
    agg_types = [agg_types] if isinstance(agg_types, str) else agg_types
    unique_agg_types = list(dict.fromkeys(agg_types))  # Remove duplicates, preserve order
    remaining_agg_types = [agg for agg in unique_agg_types if agg != 'n']

    # Group by all non-numeric columns
    group_cols = self.select_dtypes(exclude=['number']).columns.tolist()
    if not group_cols:
        raise ValueError("No non-numeric columns to group by")

    # Get numeric columns
    numeric_cols = self.select_dtypes(include=['number']).columns.tolist()

    # Check for no numeric columns and only 'n' requested
    if unique_agg_types == ['n'] and not numeric_cols:
        grouped_df = self.groupby(group_cols, dropna=dropna).size().reset_index(name='n')
        return grouped_df

    # Check for no numeric columns and no 'n'
    if not numeric_cols and 'n' not in unique_agg_types:
        raise ValueError("No numeric columns to aggregate and 'n' not specified")

    # Define aggregation operations for numeric columns excluding 'n'
    agg_operations = {col: [agg for agg in unique_agg_types if agg != 'n'] for col in numeric_cols}

    # Perform aggregation
    grouped_df = self.groupby(group_cols, as_index=False, dropna=dropna).agg(agg_operations)

    # Flatten MultiIndex in columns
    if len(remaining_agg_types) > 1:
        grouped_df.columns = ['_'.join(col).strip('_') for col in grouped_df.columns.values]
    else:
        grouped_df.columns = [col[0] for col in grouped_df.columns.values]

    # Handle counting ('n') if specified
    if 'n' in unique_agg_types:
        grouped_df['n'] = self.groupby(group_cols, dropna=dropna).size().reset_index(name='n')['n']

    # Reorder columns: group_cols + 'n' (if specified) + other aggregated columns
    g_cols = group_cols + (['n'] if 'n' in unique_agg_types else [])
    grouped_df = grouped_df.reindex(columns=g_cols + [col for col in grouped_df.columns if col not in g_cols])

    return grouped_df

def _agg_df_dict(self, agg_types, dropna):
    """
    Helper function to handle dictionary aggfunc for agg_df.
    Applies aggregations to specified columns, with 'n' keys used for count column names.
    Output columns follow the order of dictionary keys after group columns.
    """
    # Group by all non-numeric columns
    group_cols = self.select_dtypes(exclude=['number']).columns.tolist()
    if not group_cols:
        raise ValueError("No non-numeric columns to group by")

    # Get numeric columns
    numeric_cols = self.select_dtypes(include=['number']).columns.tolist()

    # Track output columns in dictionary order
    output_cols = []
    agg_operations = {}
    count_cols = []
    
    # Process dictionary keys in order
    for col, aggs in agg_types.items():
        aggs_list = [aggs] if isinstance(aggs, str) else aggs
        aggs_list = list(dict.fromkeys(aggs_list))  # Remove duplicates, preserve order
        if 'n' in aggs_list and (isinstance(aggs, str) or len(aggs_list) == 1):
            count_cols.append(col)
            output_cols.append(col)  # Count column appears as specified in dict
            continue
        if 'n' in aggs_list:
            raise ValueError(f"'n' cannot be used as an aggregation function for column '{col}' in a dictionary aggfunc")
        if col not in numeric_cols:
            raise ValueError(f"Column '{col}' is not numeric or does not exist")
        agg_tests = [agg for agg in aggs_list if agg != 'n']
        if not agg_tests:
            raise ValueError(f"No valid aggregation functions specified for column '{col}'")
        agg_operations[col] = agg_tests
        # Add output column names based on aggregations
        if len(agg_operations[col]) > 1:
            output_cols.extend([f"{col}_{agg}" for agg in agg_operations[col]])
        else:
            output_cols.extend([col] * len(agg_operations[col]))

    # Check if only 'n' is requested and no numeric columns are specified
    if not agg_operations and count_cols:
        grouped_df = self.groupby(group_cols, dropna=dropna).size().reset_index(name='n')
        result = grouped_df[group_cols]
        for count_col in count_cols:
            result[count_col] = grouped_df['n']
        return result.reindex(columns=group_cols + count_cols)

    # Perform numeric aggregation
    if not agg_operations:
        raise ValueError("No valid numeric aggregations specified")
    grouped_df = self.groupby(group_cols, as_index=False, dropna=dropna).agg(agg_operations)

    # Flatten MultiIndex in columns
    grouped_df.columns = [
        f"{col[0]}_{col[1]}" if len(agg_operations.get(col[0], [])) > 1 else col[0]
        for col in grouped_df.columns.values
    ]

    # Handle count columns
    for count_col in count_cols:
        grouped_df[count_col] = self.groupby(group_cols, dropna=dropna).size().reset_index(name='n')['n']

    # Reorder columns: group_cols + output_cols (in dictionary key order)
    final_cols = group_cols + output_cols
    grouped_df = grouped_df.reindex(columns=final_cols)

    return grouped_df

def agg_df(self, *args, **kwargs):
    """
    Aggregate the DataFrame based on specified aggregation types, ensuring that aggregated
    column names, including 'n' for counts, follow the specified order in the 'aggfunc' parameter.

    Parameters:
    - self (DataFrame): The pandas DataFrame to be aggregated.
    - *args: If a dictionary is provided as the first positional argument, it is treated as aggfunc.
    - **kwargs:
        - aggfunc (str, list, or dict, optional): Specifies the types of aggregation to perform.
            - If str (e.g., 'sum'): Apply the aggregation to all numeric columns.
            - If list (e.g., ['sum', 'mean']): Apply the listed aggregations to all numeric columns.
            - If dict (e.g., {'balance': 'mean', 'amount': ['sum', 'mean'], 'count': 'n'}):
                Apply specified aggregations to the corresponding columns; keys for 'n' specify
                the output column name for group counts, not an input column. 'n' cannot be used
                as an aggregation function in a list (e.g., {'amount': ['sum', 'n']} is invalid).
            The order in the list or dict determines the column order in the result.
            Defaults to ['sum'] if no positional dictionary is provided.
        - dropna (bool): Whether to drop NA values in groupby. Defaults to True.

    Returns:
    - DataFrame: The aggregated DataFrame with specified aggregations applied. Column names
                 for aggregated values include the aggregation type only if multiple aggregations
                 are specified for a column. For dict aggfunc, columns follow dictionary key order
                 after group columns. If only 'n' is specified and no numeric columns exist, returns
                 group counts.
    """
    # Get parameters
    if args and isinstance(args[0], dict):
        agg_types = args[0]
    else:
        agg_types = kwargs.get('aggfunc', ['sum'])
    dropna = kwargs.get('dropna', True)

    # Dispatch to appropriate helper function
    if isinstance(agg_types, dict):
        return _agg_df_dict(self, agg_types, dropna)
    else:
        return _agg_df_list(self, agg_types, dropna)

pd.DataFrame.agg_df = agg_df