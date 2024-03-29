import pandas as pd
pd.set_option('mode.chained_assignment', None)
import numpy as np

# define a function and monkey patch pandas.DataFrame
def clip(self):
    return self.to_clipboard() #e index=False not working in wsl at the moment

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


def handle_missing(self):

    df_cat_cols = self.columns[self.dtypes =='category'].tolist()
    for c in df_cat_cols:
        self[c] = self[c].astype("object")    

    df_str_cols=self.columns[self.dtypes==object]
    self[df_str_cols]=self[df_str_cols].fillna('.') #fill string missing values with .
    self[df_str_cols]=self[df_str_cols].apply(lambda x: x.str.strip()) #remove any leading and trailing zeros.    
    self = self.fillna(0) #fill numeric missing values with 0

    return self
def return_join_table(self, col_list):
    '''
                first item of the col_list is supposed to be joining key; rest are attributes that you want to bring by removing any duplicates

            for ex:-
            df={'A':['x','y','x','z','y'],
               'B':[1,2,2,2,2],
               'C':['a','b','a','d','d']}
            df=pd.DataFrame(df)
            df
            A	B	C
            0	x	1	a
            1	y	2	b
            2	x	2	a
            3	z	2	d
            4	y	2	d
            return_join_keys(df,['A','B','C'])

               A	B	C
            0	x	multiple_values	a
            1	y	2.00	multiple_values
            2	z	2.00	d
    '''

    key=col_list[0]
    k=self[[key]].drop_duplicates().dropna()
    for c in col_list[1:]:
        tf=self[[key,c]].drop_duplicates()
        tf['check_dup']=tf[key].duplicated(keep=False)
        tf=tf[tf['check_dup']!=True].drop(columns=['check_dup'])
        k=k.merge(tf,on=key,how='left')
    k.fillna('multiple_values', inplace = True)
    self=k.copy()
    return self

def cols(self):#this is for more general situations
    return sorted(self.columns.to_list())


def long(self, var_name='variable', val_name='value'):
    """
    This function converts a wide dataframe to a long format by melting all numeric columns.
    The two new columns are named 'variable' and 'value' by default, but can be changed using
    keyword arguments.

    Parameters:
    - var_name (str, optional): The name to be used for the 'variable' column. Default is 'variable'.
    - value_name (str, optional): The name to be used for the 'value' column. Default is 'value'.

    Returns:
    - pd.DataFrame: The melted dataframe with all numeric columns converted to long format.
    """

    
    # Identify numeric columns in the dataframe
    numeric_cols = self.select_dtypes(include=['number']).columns.tolist()
    
    # Melt the dataframe to long format, keeping only numeric columns
    melted_df = pd.melt(self, id_vars=[col for col in self.columns if col not in numeric_cols],
                        value_vars=numeric_cols, var_name=var_name, value_name=val_name)
    
    return melted_df



#note that long and wide are not fungible

def wide(self, col='variable', value='value', aggfunc='sum', dropna=False):
    """
    This function converts a long dataframe back to a wide format. It pivots the dataframe
    so that unique values from the specified column become the new columns headers, with values
    filled according to the corresponding values in another column. The 'value' column is assumed
    to be the only numeric column present in the dataframe by default, but this can be changed.

    Please note that wide performs aggregation and thus long followd by wide will not reproduce original long dataframe.
    Also wide by default introduces NANs for missing values so this is yet another reason why wide followed by long will 
    not return original long.

    penguins.long(var_name='variable',val_name='value').wide(col='variable') is not same as penguins even though this fuction were 
    to use pivot instead of pivot_table.

    Parameters:
    - col (str, optional): The column whose unique values will become the new column headers in the wide dataframe.
                           Default is 'variable'.
    - value (str, optional): The name of the column containing the values to fill the wide dataframe. This is assumed
                             to be the only numeric column present by default. Default is 'value'.
    - aggfunc (function, str, list or dict, optional): Function to use for aggregating the data. If a function, must either
                                                       work when passed a DataFrame or when passed to DataFrame.apply.
                                                       Accepted combinations are:
                                                       - function
                                                       - string function name
                                                       - list of functions and/or function names, e.g. [np.sum, 'mean']
                                                       - dict of axis labels -> functions, function names or list of such.
                                                       Default is 'sum'.
    - dropna (bool, optional): Do not include columns whose entries are all NaN. Default is False.

    Returns:
    - pd.DataFrame: The pivoted dataframe in a wide format.
    """


    # Pivot the dataframe
    wide_df = self.pivot_table(index=[c for c in self.columns if c not in [col, value]], 
                             columns=col, 
                             values=value, 
                             aggfunc=aggfunc,
                             dropna=dropna).reset_index()

    # Flatten the columns (if necessary) and return
    wide_df.columns.name = None
    return wide_df.reset_index(drop=True)





pd.DataFrame.clip = clip
pd.DataFrame.agg_df = agg_df
pd.DataFrame.long = long
pd.DataFrame.wide = wide
pd.DataFrame.handle_missing = handle_missing
pd.DataFrame.return_join_table = return_join_table
pd.DataFrame.cols = cols

