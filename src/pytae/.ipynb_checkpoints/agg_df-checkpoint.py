import pandas as pd




def agg_df(self, **kwargs):
    """
    Aggregate the DataFrame based on specified aggregation types, ensuring that aggregated
    column names, including 'n' for counts, follow the specified order in the 'type' list.

    Parameters:
    - self (DataFrame): The pandas DataFrame to be aggregated.
    - **kwargs:
        - aggfunc (list): Specifies the types of aggregation to perform on numeric columns
                       and 'n' for counting. The order in the list determines the column order
                       in the result. Includes 'sum', 'mean', 'max', 'min', and 'n'.
                       Ensures no duplicate types. Defaults to ['sum'].

    - dropna=True by default inline with general convention used in pandas

    Returns:
    - DataFrame: The aggregated DataFrame with specified aggregations applied. Column names
                 for aggregated values are updated to include the aggregation type. 'n' is always first of part of aggfunc else aggfunc                   order is followed.
    """
    agg_types = kwargs.get('aggfunc', ['sum'])
    dropna = kwargs.get('dropna', True)


    
    unique_agg_types = list(dict.fromkeys(agg_types))  # Preserve order and remove duplicates
    remaining_agg_types = [agg for agg in unique_agg_types if agg != 'n']
   

    # Group by all non-numeric columns
    group_cols = self.select_dtypes(exclude=['number']).columns.tolist()

    # Define aggregation operations for numeric columns excluding 'n'
    numeric_cols = self.select_dtypes(include=['number']).columns
    agg_operations = {col: [agg for agg in unique_agg_types if agg != 'n'] for col in numeric_cols}

    # Perform aggregation
    grouped_df = self.groupby(group_cols, as_index=False,dropna=dropna).agg(agg_operations)

    # Flatten MultiIndex in columns if necessary
    if len(remaining_agg_types)>1:
        grouped_df.columns = ['_'.join(col).strip('_') for col in grouped_df.columns.values]
    else:
        grouped_df.columns = [col[0] for col in grouped_df.columns.values]

    g_cols=group_cols
    # Handle counting ('n') if specified and integrate it based on its order in 'type'
    if 'n' in unique_agg_types:
        grouped_df['n'] = self.groupby(group_cols,dropna=dropna).size().reset_index(drop=True)
        g_cols=group_cols+['n']

    # Reorder columns to match the order of aggfunc
    grouped_df = grouped_df.reindex(columns=g_cols+ [col for col in grouped_df.columns if col not in g_cols])


    return grouped_df

pd.DataFrame.agg_df = agg_df