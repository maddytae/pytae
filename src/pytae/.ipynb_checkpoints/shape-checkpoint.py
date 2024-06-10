import pandas as pd


def long(self, **kwargs):
    """
    This function converts a wide dataframe to a long format by melting all numeric columns.
    The two new columns are named 'variable' and 'value' by default, but can be changed using
    keyword arguments.

    Parameters:
    - col (str, optional): The name to be used for the 'variable' column. Default is 'variable'.
    - value (str, optional): The name to be used for the 'value' column. Default is 'value'.

    Returns:
    - pd.DataFrame: The melted dataframe with all numeric columns converted to long format.
    """

    
    # Identify numeric columns in the dataframe
    numeric_cols = self.select_dtypes(include=['number']).columns.tolist()
    
    # Melt the dataframe to long format, keeping only numeric columns
    melted_df = pd.melt(self, id_vars=[col for col in self.columns if col not in numeric_cols],
                        value_vars=numeric_cols, var_name=kwargs.get('col', 'variable'), 
                                                 value_name=kwargs.get('value', 'value'))
    
    return melted_df



#note that long and wide are not fungible


def wide(self, **kwargs):
    """
    Converts a long dataframe back to a wide format. It tries to use pivot for straightforward reshaping without aggregation.
    Falls back to pivot_table if there's a uniqueness constraint violation or if an aggregation function is explicitly provided.

    Parameters:
    - col (str, optional): The column whose unique values will become the new column headers in the wide dataframe.
                           Default is 'variable'.
    - value (str, optional): The name of the column containing the values to fill the wide dataframe.
                             This is assumed to be the only numeric column present by default. Default is 'value'.
    - aggfunc (function, str, list, or dict, optional): Function to use for aggregating the data. If specified,
                                                       pivot_table is used for aggregation.
    - dropna (bool, optional): Applies only to pivot_table. Specifies whether to drop columns with all NaN values.
                               Default is True.

    Returns:
    - pd.DataFrame: The pivoted dataframe in a wide format.
    """
    # Initially try to use pivot if aggfunc is not provided
    if kwargs.get('aggfunc',None) is None:
        try:
      
            wide_df = self.pivot(index=[c for c in self.columns if c not in [kwargs.get('col', 'variable'), 
                                                                             kwargs.get('value', 'value')]], 
                                                                             columns=kwargs.get('col', 'variable'),
                                                                             values=kwargs.get('value', 'value')).reset_index()
        except ValueError as e:
            # Check if the error is due to uniqueness constraint
            if 'Index contains duplicate entries' in str(e):
                print("pivot_table is used with sum as agg because Index contains duplicate entries.")
                # Use pivot_table with 'sum' as the default aggregation function
                wide_df = self.pivot_table(index=[c for c in self.columns if c not in [kwargs.get('col', 'variable'), 
                                                                             kwargs.get('value', 'value')]], 
                                                                             columns=kwargs.get('col', 'variable'),
                                                                             values=kwargs.get('value', 'value'),
                                                                             aggfunc='sum', 
                                                                             dropna=kwargs.get('dropna', False)).reset_index()
            else:
                raise
    else:
        # Use pivot_table directly if aggfunc is provided
        wide_df = self.pivot_table(index=[c for c in self.columns if c not in [kwargs.get('col', 'variable'), 
                                                                             kwargs.get('value', 'value')]], 
                                                                             columns=kwargs.get('col', 'variable'),
                                                                             values=kwargs.get('value', 'value'), 
                                                                             aggfunc=kwargs.get('aggfunc',None), 
                                                                             dropna=kwargs.get('dropna', False)).reset_index()
  
    
    # Reset index and clean column names
    wide_df.reset_index(drop=True, inplace=True)
    wide_df.columns.name = None
    
    return wide_df







pd.DataFrame.long = long
pd.DataFrame.wide = wide