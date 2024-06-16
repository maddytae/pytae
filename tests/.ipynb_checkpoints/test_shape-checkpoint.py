import pytest
import numpy as np
import pandas as pd
import seaborn as sns

import sys
import os

# Assuming the current working directory is where the project root is
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pytae import long, wide

def test_long():

    penguins = sns.load_dataset('penguins')

    
    result = penguins.long(col='features')
    

    numeric_cols = penguins.select_dtypes(include=['number']).columns.tolist()
    expected_df = pd.melt(penguins, id_vars=[col for col in penguins.columns if col not in numeric_cols],
                        value_vars=numeric_cols, var_name='features', 
                                                 value_name='value')
    
    pd.testing.assert_frame_equal(result, expected_df)


def test_wide_pivot_table():

    df=pd.DataFrame({'id':['a','b','c','d','e','','f','f'],
                      'balance':[10,20,0,21,15,10,20,25],
                      'country':['sg','cn','ca','np','in','in','in','in']})
    
    result=df.wide(col='country',value='balance')
    
    expected_df=df.pivot_table(index='id', 
                               columns='country', 
                               values='balance', 
                               aggfunc='sum').reset_index()
    expected_df.columns.name = None
    pd.testing.assert_frame_equal(result, expected_df)

def test_wide_pivot():
    #notice pivot is used if possible. pivot_table is used only if pivot is not possible.

    df=pd.DataFrame({'id':['a','b','c','d','e','','f'],
                      'balance':[10,20,0,21,15,10,20],
                      'country':['sg','cn','ca','np','in','in','in']})
    
    result=df.wide(col='country',value='balance')
    
    expected_df=df.pivot(index='id', 
                               columns='country', 
                               values='balance', 
                            ).reset_index()
    expected_df.columns.name = None
    pd.testing.assert_frame_equal(result, expected_df)
    
if __name__ == '__main__':
    pytest.main()
