import pandas as pd




def agg_df(self, **kwargs):
    """
    Aggregate the DataFrame based on specified aggregation types, ensuring that aggregated
    column names, including 'n' for counts, follow the specified order in the 'type' list.

    Parameters:
    - self (DataFrame): The pandas DataFrame to be aggregated.
    - **kwargs:
        - type (list): Specifies the types of aggregation to perform on numeric columns
                       and 'n' for counting. The order in the list determines the column order
                       in the result. Includes 'sum', 'mean', 'max', 'min', and 'n'.
                       Ensures no duplicate types. Defaults to ['sum'].

    Returns:
    - DataFrame: The aggregated DataFrame with specified aggregations applied. Column names
                 for aggregated values are updated to include the aggregation type.
    """
    agg_types = kwargs.get('type', ['sum'])
    unique_agg_types = list(dict.fromkeys(agg_types))  # Preserve order and remove duplicates

    # Group by all non-numeric columns
    group_cols = self.select_dtypes(exclude=['number']).columns.tolist()

    # Define aggregation operations for numeric columns excluding 'n'
    numeric_cols = self.select_dtypes(include=['number']).columns
    agg_operations = {col: [agg for agg in unique_agg_types if agg != 'n'] for col in numeric_cols}

    # Perform aggregation
    grouped_df = self.groupby(group_cols, as_index=False).agg(agg_operations)

    # Flatten MultiIndex in columns if necessary
    grouped_df.columns = ['_'.join(col).strip('_') for col in grouped_df.columns.values]

    # Handle counting ('n') if specified and integrate it based on its order in 'type'
    if 'n' in unique_agg_types:
        grouped_df['n'] = self.groupby(group_cols).size().reset_index(drop=True)

    # Construct the final column order based on 'type', ensuring 'n' is correctly positioned
    final_columns = group_cols[:]
    for agg_type in unique_agg_types:
        if agg_type == 'n':
            final_columns.append('n')
        else:
            final_columns.extend([f"{col}_{agg_type}" for col in numeric_cols])

    return grouped_df.loc[:, final_columns]

pd.DataFrame.agg_df = agg_df