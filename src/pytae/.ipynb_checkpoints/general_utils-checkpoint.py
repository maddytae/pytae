import os, sys, gc,importlib
import pandas as pd
import numpy as np
from pathlib import Path
import tarfile
import yaml
from yaml.loader import SafeLoader
import warnings
# warnings.filterwarnings('ignore')



class ProcessTar(object):
    
    '''
    import pytae as pt
    u=pt.ProcessTar(some_path)
    u.return_df()
    
    If tar file contains single file it will be returned as pandas dataframe; else it will return list of all file in tar and you can choose one of the all available files.
    u.return_df('sometable')
    
    '''
    
    def __init__(self,tar_path):
        self.tar_path=tar_path
        
    def return_df(self,tbl=None,cols=None):
        self.tbl=tbl
        self.cols=cols
        
        if self.tbl==None:  #table value is not provided
            
            if len(self.return_file_list())==1:  
                with tarfile.open(self.tar_path, "r:*") as tar:
                    for item in tar.getnames(): 
                        if self.cols==None:
                            
                            self.df= pd.read_csv(tar.extractfile(item),low_memory=False)
                        else:
                            self.df=pd.read_csv(tar.extractfile(item),low_memory=False,usecols=self.cols)
                        return self.df #check if there is only one table then still give the result
            
            else:
                print('select one of the following files\n')
                with tarfile.open(self.tar_path, "r:*") as tar:
                    for item in tar.getnames():
                        file=(os.path.splitext(os.path.basename(item))[0])
                        print(file) ### if more than one table is packed inside the tar file just display the filenames so that user can select       
        
        else:
            with tarfile.open(self.tar_path, "r:*") as tar:
                for item in tar.getnames():
                    file=(os.path.splitext(os.path.basename(item))[0])
                    if self.tbl==file:
                        if self.cols==None:
                            self.df= pd.read_csv(tar.extractfile(item),low_memory=False)
                        else:
                            self.df= pd.read_csv(tar.extractfile(item),low_memory=False,usecols=self.cols)

            return self.df               
            
    def return_sample_df(self,k):

        with tarfile.open(self.tar_path, "r:*") as tar:
            for item in tar.getnames():
                file=(os.path.splitext(os.path.basename(item))[0])

                if k==file:                  
                    df= pd.read_csv(tar.extractfile(item),nrows=10)
        return df
    
    def return_file_list(self):
        file_list=[]
        with tarfile.open(self.tar_path, "r:*") as tar:
            for item in tar.getnames():
                file=(os.path.splitext(os.path.basename(item))[0])
                file_list.append(file)
        return file_list
    
    


class Connectors(object):
    def __init__(self,user,remote_server):
        


        """Supported remote servers are:- 
        
   
        
        
        """
        self.user=user
        self.remote_server= remote_server
        self.local_credential_file='/home/'+user+'/.ssh/credentials.yaml'
        
        #read login credentials
        with open(self.local_credential_file) as f:
            self.cred = yaml.load(f, Loader=SafeLoader)
        
        self.userid=self.cred[self.remote_server]['userid']
        self.passwd=self.cred[self.remote_server]['passwd']
        self.host=self.cred[self.remote_server]['host']
        if self.remote_server=='idp':
            self.port=self.cred[self.remote_server]['port']
            self.database=self.cred[self.remote_server]['database']
        
        

        
    def est_conn(self):
          
        if self.remote_server=='idp':
        #"SELECT * FROM _v_sys_columns " #useful query this gives everything i.e all database, schema, columns and their types.
            conn = nzpy.connect(user=self.userid, password=self.passwd,host=self.host, 
                            port=self.port, database=self.database, securityLevel=1,logLevel=0) 
        
        if self.remote_server in ['prod','uat']:

            conn = paramiko.SSHClient()
            conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            conn.connect(hostname=self.host,username=self.userid, password=self.passwd)
        
        return conn

def create_qry(lib,tbl,nums,non_nums,whr=False):

    '''
            nums={'x':['sum','x1'],'y':['sum','y1'],'z':['sum','z1']}
            non_nums=['a','b','c']
            create_qry('data','tbl',nums,non_nums)
            'select a, b, c, sum(x) as x1, sum(y) as y1, sum(z) as z1 from data.tbl group by a, b, c;'
            
            #if num is a list 
            nums=['x','y','z']
            create_qry('data','tbl',nums,non_nums)
            'select a, b, c, sum(x) as x, sum(y) as y, sum(z) as z from data.tbl group by a, b, c;'
            
    '''

    if type(nums) is list:
        
        q=', '
        for i in nums:
            t='sum('+i+') as '+ i +', '
            q=q+t
        q=q[:-2]
        
    if type(nums) is dict:
        
        q=', '
        for i in nums:
            t=nums[i][0]+'('+i+') as '+ nums[i][1] +', '
            q=q+t
        q=q[:-2]  

    if whr:
        qry='select ' + ', '.join(non_nums) + \
            q + \
            ' from '+ lib + '.' +tbl +' '+ whr +\
            ' group by ' + ', '.join(non_nums) + \
            ';'
    else:
        qry='select ' + ', '.join(non_nums) + \
            q + \
            ' from '+ lib + '.' +tbl + \
            ' group by ' + ', '.join(non_nums) + \
            ';'
    
    
    return qry



def push_granularity(from_frame,have,push_to,by):
    import numpy as np
    result_frame=from_frame[list(set(have) | set(push_to))+[by]].groupby(list(set(have) | set(push_to)),dropna=False).sum().reset_index()
    result_frame['attr_sum'] = result_frame.groupby(have,dropna=False)[by].transform('sum')
    result_frame['attr_sum_wt'] =result_frame[by]/result_frame['attr_sum']
    #result_frame.loc[result_frame['attr_sum']<0,'attr_sum_wt']=result_frame['attr_sum_wt']*-1  #this is required for cases involving negative values to have weight consistent with amount

    ###start-handle edge cases of weights

    result_frame['wt']=result_frame['attr_sum_wt']

    result_frame.loc[result_frame['attr_sum_wt'].isin([np.inf]),'wt']=1
    result_frame.loc[result_frame['attr_sum_wt'].isin([-np.inf]),'wt']=-1

    #Sometime a granualr key (for ex:-'bmo_instrument_id') might have zero  sum(for ex ead) not beause of +x -x but +0 +0 and so on...; Assign zero weight because we can not assign wt if summing value is not available. We don't artificially want to assign wt as 1 in these cases because sum might be zero across multiple rows.
    result_frame.loc[result_frame['wt'].isnull(),'wt']=0

    result_frame.drop(columns=['attr_sum','attr_sum_wt'],inplace=True)
    result_frame=result_frame.sort_values(by=have)
    ###end-handle edge cases of weights
   

    #result_frame.to_csv(os.path.join(mock_up_temp,'result_frame.csv'),index=False)
    return result_frame

class HeadDF():
    
    '''
    Explore any file parquet/csv/tar
    
    '''
    
    
    
    def __init__(self,file_path):
        self.file_path=file_path
        
    def return_head(self):  #this can be used before reading df
        if self.file_path.endswith('.parquet'):
            pf = ParquetFile(self.file_path) 
            first_ten_rows = next(pf.iter_batches(batch_size = 10)) 
            self.df = pa.Table.from_batches([first_ten_rows]).to_pandas() 
        if self.file_path.endswith('.csv'):
            self.df=pd.read_csv(self.file_path,nrows=10)
        if self.file_path.endswith('.tar.gz'):
            u = ProcessTar(self.file_path)
            file_list=u.return_file_list()
            if len(file_list)==1:
                self.df = u.return_sample_df(file_list[0])        
            else:
                print(str(file_list))
                table = input('choose table without quote!\n')
                self.df = u.return_sample_df(table)
        return self.df