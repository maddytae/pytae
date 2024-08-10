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


def cols(self):#this is for more general situations
    return sorted(self.columns.to_list())

#select is more intuitive than filter. It can handle a list or a regex or a tuple containing list and regex
def select(self, cols_or_regex=None):
    '''
    Select columns based on a list of column names, a regex pattern, or a tuple of both.
    
    Parameters:
    self (pd.DataFrame): The DataFrame from which to select columns.
    cols_or_regex (list, str, or tuple): 
        - List of column names
        - Regex pattern
        - Tuple containing a list of column names and a regex pattern
    
    Returns:
    pd.DataFrame: A DataFrame with the selected columns.
    '''
    
    if isinstance(cols_or_regex, tuple):
        if len(cols_or_regex) != 2:
            raise ValueError("Tuple must contain exactly two elements: a list of columns and a regex pattern")
        cols, regex = cols_or_regex
        if not isinstance(cols, list) or not isinstance(regex, str):
            raise TypeError("First element of tuple must be a list, and the second element must be a string (regex pattern)")
        # Select columns based on the list and regex independently
        selected_cols = list(set(cols + self.filter(regex=regex).columns.tolist()))
        return self[selected_cols]
    
    elif isinstance(cols_or_regex, list):
        missing_cols = [col for col in cols_or_regex if col not in self.columns]
        if missing_cols:
            raise KeyError(f"Columns not found in the DataFrame: {missing_cols}")
        return self[cols_or_regex]
    
    elif isinstance(cols_or_regex, str):
        return self.filter(regex=cols_or_regex)
    
    else:
        raise TypeError("cols_or_regex must be a list, a regex string, or a tuple of (list, regex)")

# Add the method to the DataFrame class
pd.DataFrame.select = select





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
pd.DataFrame.select = select
pd.DataFrame.group_x = group_x