import pandas as pd

def get_data(self, **kwargs):

    '''
    very flexible method to get the subset of a dataframe. Though usual filters can be applied but
    this makes it very powerful to use inside loops when criteria could be on different cols in each loop.

    returns aggregated dataframe.

    some usage:-
    penguins.get_data(value=['body_mass_g'],
                  default_cols=['species'],
                  aggfunc='sum')

    #notice for aggfunc n, value col is not necessary
    penguins.get_data(aggfunc='n',default_cols=['species'])
                    
    penguins.get_data(value='body_mass_g',island='Biscoe',species='Gentoo',
                  default_cols=['island','sex','species'],
                  aggfunc='sum')

    conditions can be both a list or a string

    penguins.get_data(value=['body_mass_g','bill_length_mm','flipper_length_mm','bill_depth_mm'],
                  default_cols=['species','sex','island'], aggfunc='mean',dropna=False)
    '''
    
    cols = list(kwargs.keys())
    if 'dropna' in cols:
        cols.remove('dropna')
    agg_cols=['value']
    default_cols=[]
    aggfunc='sum'
    dropna = kwargs.get('dropna', True)

    #manage aggfunc
    if 'aggfunc' in cols:
        cols.remove('aggfunc')
        aggfunc=kwargs['aggfunc']

        
    #manage agg cols
    if 'value' in cols:
        cols.remove('value')
        agg_cols.remove('value')
        if isinstance(kwargs['value'], list):  # Check if value is a list
            agg_cols = kwargs['value']
        else:
            agg_cols = [kwargs['value']]  # If not a list, wrap it in a list

    #manage default cols
    if 'default_cols' in cols:
        cols.remove('default_cols')
        if isinstance(kwargs['default_cols'], list):  # Check if value is a list
            default_cols=default_cols+  kwargs['default_cols']
        else:
            default_cols=default_cols+  [kwargs['default_cols']]  # If not a list, wrap it in a list

    combined_cols=list(set(cols+default_cols))

    #basically works even if 'value' i.e col to be aggregated is not provided i.e when aggfunc to be used is 'n'
    try:
        filtered_self = self[combined_cols+agg_cols].copy()
    except:
        filtered_self = self[combined_cols].copy()
        
    for c in cols:    
        if kwargs[c]=='':
            None
        elif isinstance(kwargs[c], list):
            filtered_self = filtered_self[filtered_self[c].isin(kwargs[c])]
        else:
            filtered_self = filtered_self[filtered_self[c]==kwargs[c]]
    #aggregate self

    if aggfunc!='n':    
        grouped_self = filtered_self.groupby(combined_cols,dropna=dropna)[agg_cols].agg(aggfunc).reset_index()
    else:
        grouped_self = filtered_self.groupby(combined_cols, dropna=dropna).size().reset_index(name='n')

    return grouped_self



pd.DataFrame.get_data = get_data