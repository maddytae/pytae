import pandas as pd
import numpy as np

# define a function and monkey patch pandas.DataFrame
def clip(self):
    return self.to_clipboard(index=False) #e index=False not working in wsl at the moment


def handle_missing(self):

    df_cat_cols = self.columns[self.dtypes =='category'].tolist()
    for c in df_cat_cols:
        self[c] = self[c].astype("object")    

    df_str_cols=self.columns[self.dtypes==object]
    self[df_str_cols]=self[df_str_cols].fillna('.') #fill string missing values with .
    self[df_str_cols]=self[df_str_cols].apply(lambda x: x.str.strip()) #remove any leading and trailing zeros.    
    self = self.fillna(0) #fill numeric missing values with 0

    return self


def cols(self):#this is for more general situations
    return sorted(self.columns.to_list())

def group_n(self,group=None,dropna=False):
    if group is None:
        group = self.select_dtypes(exclude=['number']).columns.tolist()

    k=self.groupby(group,dropna=dropna).size().reset_index(name='n')
    self=self.merge(k,on=group,how='left')
    if dropna:
        self.dropna(subset=['n'], inplace=True)
    return self





#direct alternate is a little more verbose

# df = (
#     penguins
#     .assign(count=lambda x: x.groupby(['species', 'island', 'sex'],dropna=False).transform('size'))
#     .reset_index(drop=True)
# )

# df = (
#     penguins
#     .pipe(pt.add_group_count,group=['species', 'island', 'sex'],dropna=False)
# )

pd.DataFrame.clip = clip
pd.DataFrame.handle_missing = handle_missing
pd.DataFrame.cols = cols
pd.DataFrame.group_n = group_n