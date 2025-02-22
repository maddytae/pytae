import pandas as pd
import numpy as np

# define a function and monkey patch pandas.DataFrame
def clip(self):
    return self.to_clipboard(index=False) #e index=False not working in wsl at the moment


def handle_missing(self,fillna='.'):

    df_cat_cols = self.columns[self.dtypes =='category'].tolist()
    for c in df_cat_cols:
        self[c] = self[c].astype("object")    

    df_str_cols=self.columns[self.dtypes==object]
    self[df_str_cols]=self[df_str_cols].fillna(fillna) #fill string missing values with .
    self[df_str_cols]=self[df_str_cols].apply(lambda x: x.str.strip()) #remove any leading and trailing zeros.    
    self = self.fillna(0) #fill numeric missing values with 0

    return self


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




def group_x(self, group=None, dropna=True, aggfunc='n', value=None):
    '''
    penguins.group_x(group=['island','species','sex'],dropna=True,value='body_mass_g',aggfunc='max')
    penguins.group_x(group=['island','species','sex'],dropna=False) since no aggfunc provided so count will be provided by default
    '''
    if group is None:
        group = self.select_dtypes(exclude=['number']).columns.tolist()

    if aggfunc=='n' or value==None:
        self['n'] = self.groupby(group, dropna=dropna).transform('size')
        col='n'
    else:
        self['x'] = self.groupby(group, dropna=dropna)[value].transform(aggfunc)
        col='x'
        

    return self



pd.DataFrame.clip = clip
pd.DataFrame.handle_missing = handle_missing
pd.DataFrame.cols = cols
pd.DataFrame.group_x = group_x