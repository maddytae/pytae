import pandas as pd

def get_data(self, **kwargs):
    
    cols = list(kwargs.keys())
    agg_cols=['value']
    default_cols=[]
    aggfunc='sum'

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
    filtered_self = self[combined_cols+agg_cols].copy()
    
    for c in cols:    
        if kwargs[c]=='':
            None
        elif isinstance(kwargs[c], list):
            filtered_self = filtered_self[filtered_self[c].isin(kwargs[c])]
        else:
            filtered_self = filtered_self[filtered_self[c]==kwargs[c]]
    #aggregate self

    if aggfunc!='n':    
        grouped_self = filtered_self.groupby(combined_cols,dropna=False)[agg_cols].agg(aggfunc).reset_index()
    else:
        grouped_self = filtered_self.groupby(combined_cols, dropna=False).size().reset_index(name='n')

    return grouped_self



pd.DataFrame.get_data = get_data