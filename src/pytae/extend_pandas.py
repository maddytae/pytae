import pandas as pd
pd.set_option('mode.chained_assignment', None)
import numpy as np

# define a function and monkey patch pandas.DataFrame
def clip(self):
    return self.to_clipboard() #e index=False not working in wsl at the moment



def agg_df_old(self,count=False):
    
    #add functionality for count
    if count==True:
        self=self.assign(count=1.0)
        
    #address categorical columns if any   
    cat_columns = self.select_dtypes(['category']).columns
    for x in cat_columns:
        self[x] = self[x].astype("object")
        
    #identify string columns
    non_num_cols = self.columns[(self.dtypes =='object')].tolist()
    if len(non_num_cols)>0:
        df=self.groupby(non_num_cols,dropna=False).sum().reset_index()
        self=df.copy()
        
    return self

def agg_df(self, **kwargs):
    """
    Aggregate the DataFrame based on the specified aggregation type and optional counting.

    Supports various aggregation operations on numeric columns and allows for counting the number
    of rows in each group, adding a specific 'n' column for this purpose. Categorical columns are
    considered for grouping, and aggregation is applied accordingly.

    Parameters:
    - self (DataFrame): The pandas DataFrame to be aggregated.
    - **kwargs:
        - type (str): The type of aggregation to perform on numeric columns. 
                      Accepts 'sum', 'mean', 'max', 'min'. Defaults to 'sum'.
        - count (bool): If True, adds a column 'n' to the DataFrame, counting 
                        the number of occurrences in each group. Defaults to False.

    Returns:
    - DataFrame: The aggregated DataFrame with specified aggregations applied. If 'count' is True,
                 the DataFrame will include an 'n' column representing counts, which is always of 
                 integer type.

    Examples:
    ```python
    import pandas as pd

    # Example DataFrame
    df = pd.DataFrame({
        'group': ['A', 'A', 'B', 'B', 'C', 'C'],
        'balance': [100, 150, 200, 250, 300, 350],
        'n': [1, 2, 1, 3, 2, 4]
    })

    # Aggregating using max and counting
    agg_df_max_count = df.agg_df(type='max', count=True)

    # Aggregating using min without counting
    agg_df_min = df.agg_df(type='min')
    ```
    """
    # Parse the 'type' keyword argument for aggregation ('sum', 'mean', 'max', 'min')
    agg_type = kwargs.get('type', 'sum')
    
    # Validate aggregation type
    if agg_type not in ['sum', 'mean', 'max', 'min']:
        raise ValueError(f"Unsupported aggregation type '{agg_type}'. Choose from 'sum', 'mean', 'max', 'min'.")
    
    # Parse the 'count' keyword argument (True or False, with False as default)
    count = kwargs.get('count', False)
    
    # If counting is enabled, add a column 'n' with 1 for each row to later sum up
    if count:
        self = self.assign(n=1)
        
    # Convert categorical columns to 'object' type for consistent handling
    cat_columns = self.select_dtypes(['category']).columns
    self[cat_columns] = self[cat_columns].astype("object")
    
    # Identify non-numeric (string) columns for grouping
    non_num_cols = self.columns[(self.dtypes == 'object')].tolist()
    
    # Define aggregation dictionary for numeric columns and 'n' column
    agg_dict = {col: agg_type for col in self.select_dtypes(include=['number']).columns if col != 'n'}
    if count:
        agg_dict['n'] = 'sum'
    
    # Perform the specified aggregation operation
    if non_num_cols:
        self = self.groupby(non_num_cols, dropna=False).agg(agg_dict).reset_index()
    else:
        self = self.agg(agg_dict)
    
    # Ensure 'n' column is integer type if counting is enabled
    if count:
        self['n'] = self['n'].astype(int)
    
    return self



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




pd.DataFrame.clip = clip
pd.DataFrame.agg_df = agg_df
pd.DataFrame.handle_missing = handle_missing
pd.DataFrame.return_join_table = return_join_table
pd.DataFrame.cols = cols

