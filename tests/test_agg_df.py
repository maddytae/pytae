
import os
import sys

import numpy as np
import pandas as pd
import pytest

# Assuming the current working directory is where the project root is
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytae as pt


def test_agg_df_sum():
    # Arrange: Create a sample DataFrame
    data = {
        'category': ['A', 'A', 'B', 'B', 'C'],
        'value': [10, 20, 30, 40, 50]
    }
    df = pd.DataFrame(data)
    
    # Act: Call the agg_df method with sum aggregation
    result = pt.agg_df(df, a=['sum'])
    
    # Assert: Check if the result is as expected
    expected_df =  pd.DataFrame(data).groupby('category').sum().reset_index()
    pd.testing.assert_frame_equal(result, expected_df)


def test_all_agg():
    df=pd.DataFrame({'id':['a','b','c','d','e','','f','f'],
                  'balance':[10,20,0,21,15,10,20,25],
                  'country':['sg','cn','ca','np','in','in','in','in']})
    
    df['id'] = df['id'].replace('', np.nan)
    result=pt.agg_df(df, a=['sum','min','mean','min','max','n'])

    # Group by 'id' and 'country', then aggregate
    expected_df = df.groupby(['id', 'country']).agg(
                                                        n=('id', 'size'),
                                                        balance_sum=('balance', 'sum'),
                                                        balance_min=('balance', 'min'),
                                                        balance_mean=('balance', 'mean'),
                                                        balance_max=('balance', 'max')
                                                    ).reset_index()
    
    # Adjust the column order to match the desired output
    expected_df = expected_df[['id', 'country', 'n', 'balance_sum', 'balance_min', 'balance_mean', 'balance_max']]


    
    pd.testing.assert_frame_equal(result, expected_df)
    


def test_all_agg_drop_na():
    df=pd.DataFrame({'id':['a','b','c','d','e','','f','f'],
                  'balance':[10,20,0,21,15,10,20,25],
                  'country':['sg','cn','ca','np','in','in','in','in']})
    
    df['id'] = df['id'].replace('', np.nan)
    
    result=pt.agg_df(df, a=['sum','min','mean','min','max','n'],dropna=False)

    # Group by 'id' and 'country', then aggregate
    expected_df = df.groupby(['id', 'country'],dropna=False).agg(
                                                        n=('id', 'size'),
                                                        balance_sum=('balance', 'sum'),
                                                        balance_min=('balance', 'min'),
                                                        balance_mean=('balance', 'mean'),
                                                        balance_max=('balance', 'max')
                                                    ).reset_index()
    
    # Adjust the column order to match the desired output
    expected_df = expected_df[['id', 'country', 'n', 'balance_sum', 'balance_min', 'balance_mean', 'balance_max']]
    


    pd.testing.assert_frame_equal(result, expected_df)


def test_agg_df_raises_when_n_collides_with_real_column():
    df = pd.DataFrame({"g": ["x", "x", "y"], "n": [1, 2, 3], "v": [10, 20, 30]})
    with pytest.raises(ValueError, match="already has a numeric column named 'n'"):
        pt.agg_df(df, ["sum", "n"])


if __name__ == '__main__':
    pytest.main()
