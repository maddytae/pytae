import pandas as pd
import numpy as np

# define a function and monkey patch pandas.DataFrame
def clip(self):
    return self.to_clipboard(index=False) #e index=False not working in wsl at the moment


def handle_missing(self, fillna='.'):
    df = self.copy()

    df_cat_cols = df.columns[df.dtypes == 'category'].tolist()
    for c in df_cat_cols:
        df[c] = df[c].astype("object")

    df_str_cols = df.columns[df.dtypes == object]
    df[df_str_cols] = df[df_str_cols].fillna(fillna)
    df[df_str_cols] = df[df_str_cols].apply(lambda x: x.str.strip())
    df = df.fillna(0)

    return df


def cols(self, ascending=True):
    '''
    Return the column names of the DataFrame sorted or in original order.
    
    Parameters:
    self (pd.DataFrame): The DataFrame whose columns are to be returned.
    ascending (bool or None, optional): 
        - True (default): Sort alphabetically A-Z.
        - False: Sort alphabetically Z-A.
        - None: Return columns in their original DataFrame order (unsorted).
    
    Returns:
    list: A list of column names in the specified order.
    
    Raises:
    ValueError: If an invalid ascending parameter is provided.
    '''
    columns = self.columns.to_list()
    
    if ascending is True:
        return sorted(columns)
    elif ascending is False:
        return sorted(columns, reverse=True)
    elif ascending is None:
        return columns
    else:
        raise ValueError(f"Invalid ascending value '{ascending}'. Must be True, False, or None")

# Attach to pandas DataFrame
pd.DataFrame.cols = cols




def group_x(self, group=None, dropna=True, observed=True, aggfunc='n', value=None):
    '''
    penguins.group_x(group=['island','species','sex'],dropna=True,value='body_mass_g',aggfunc='max')
    penguins.group_x(group=['island','species','sex'],dropna=False) since no aggfunc provided so count will be provided by default
    '''
    df = self.copy()

    if group is None:
        group = df.select_dtypes(exclude=['number']).columns.tolist()

    if aggfunc == 'n' or value is None:
        df['n'] = df.groupby(group, dropna=dropna, observed=observed).transform('size')
    else:
        df['x'] = df.groupby(group, dropna=dropna, observed=observed)[value].transform(aggfunc)

    return df



pd.DataFrame.clip = clip
pd.DataFrame.handle_missing = handle_missing
pd.DataFrame.cols = cols
pd.DataFrame.group_x = group_x