
import pandas as pd
import numpy as np



class Recon(object):
    def __init__(self,df1,dict1,df2,dict2):
        self.df1=df1.copy()
        self.df2=df2.copy()
        self.dict1=dict1
        self.dict2=dict2



        
    def clean_fill(self):
        df1=self.df1.copy()
        df2=self.df2.copy()        
        replace_map={   None:np.NaN,
                        # np.NaN:'Null',
                        '':np.NaN}


        df1[[*self.dict1]]=df1[[*self.dict1]].replace(replace_map)
        df2[[*self.dict2]]=df2[[*self.dict2]].replace(replace_map)

   
        return df1,df2
        
    def select_n_aggregate(self,count=False):
        df1,df2=self.clean_fill()


        if count==True:
            
            df1=df1[[*self.dict1.keys(),*self.dict1.values()]].agg_df(count=True)
            df2=df2[[*self.dict2.keys(),*self.dict2.values()]].agg_df(count=True)
            df1.columns=['key','val','n']
            df2.columns=['key','val','n']
        else:
            df1=df1[[*self.dict1.keys(),*self.dict1.values()]].agg_df()
            df2=df2[[*self.dict2.keys(),*self.dict2.values()]].agg_df()
            df1.columns=['key','val']
            df2.columns=['key','val']

            
        df1['key']=df1['key'].fillna('df1.null')
        df2['key']=df2['key'].fillna('df2.null')


        return df1,df2


    
    def combined(self,count=False):
        df1,df2=self.select_n_aggregate(count)
        df1['source']='df1'
        df2['source']='df2'
        df=pd.concat([df1,df2])
        
        if count==True:
            df=df.pivot(index='key', columns='source', values=['val','n']).reset_index()
            df.columns=['key','df1_val','df2_val','df1_n','df2_n']
            
        else:
            
            df=df.pivot(index='key', columns='source', values=['val']).reset_index()
            df.columns=['key','df1_val','df2_val']
            
        return df
    
    def summary(self,count=False):
        df=self.combined(count)            
        df['source']=''
        df.loc[(~df['df1_val'].isna()) & (df['df2_val'].isna()),'source']='left_only'
        df.loc[(df['df1_val'].isna()) & (~df['df2_val'].isna()),'source']='right_only'
        df.loc[(~df['df1_val'].isna()) & (~df['df2_val'].isna()),'source']='both'
        df.loc[~df['key'].isin(['df1.null','df2.null']),'key']='non_null'
        df=df.agg_df() 
        return df
    
    
    def values_recon(self,agg=False,ignore_NA=True,th=0):
        
        df=self.combined(count=False)
        #by default value recon does not need count; To get sense of count use combined or summary methods
        df['tag']='not_matching'
        
        if ignore_NA==True:
            df['diff']=df['df1_val'].fillna(0)-df['df2_val'].fillna(0)
        else:
            df['diff']=df['df1_val']-df['df2_val']
            
        df.loc[abs(df['diff'])<=th,'tag']='matching'

        
        if agg==True:
            df=df.drop(columns=['key','diff'])
            df=df.agg_df()
            
            
        return df