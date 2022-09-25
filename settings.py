import os
import yaml
from yaml.loader import SafeLoader
import pandas as pd


class PrepareSettings:
    def __init__(self):
        self.project_path = os.path.dirname(os.getcwd())

        self.sd = os.path.join(self.project_path, 'sas_datasets')
        self.config_path= os.path.join(self.project_path, 'configuration')
        self.input_path = os.path.join(self.project_path, 'input_files')
        self.output_path = os.path.join(self.project_path, 'output_files')
        self.temp_path = os.path.join(self.project_path, 'temp_files')
        self.control_path=os.path.join(self.project_path, 'control_files')
        self.mock_up_assumption_path = os.path.join(self.project_path, 'mock_up_assumptions')



        with open(os.path.join(self.config_path, 'config.yaml')) as f:
            self.config = yaml.load(f, Loader=SafeLoader)
        self.jump_off = [self.config['jump_off']]
        self.forecast_horizon = pd.period_range(start=pd.Period(self.config['stress_horizon_start'], freq='Q'),
                                            end=pd.Period(self.config['stress_horizon_end'], freq='Q')+4,freq='Q') #added 4 qtrs because for coverage ratio calculation for non-modelled we need                                                                                                           #additional 4 qtrs
        self.forecast_horizon = [str(x) for x in self.forecast_horizon]

        self.forecast_horizon_reporting = pd.period_range(start=pd.Period(self.config['stress_horizon_start'], freq='Q'),
                                            end=pd.Period(self.config['stress_horizon_end'], freq='Q'),freq='Q')
        self.forecast_horizon_reporting = [str(x) for x in self.forecast_horizon_reporting]

        self.airb_sk = str(self.config['airb_sk']) #for instrument id
        self.project_sk = str(self.config['project_sk'])
        self.path_to_local_data_source = self.config['path_to_local_data_source']
        self.reqd_level=self.config['airb_not_in_cecl_level']    
        self.cube_path = os.path.join(self.path_to_local_data_source, 'cubes', 'CA_' + self.project_sk + '_MASTER_DETAIL' + '.parquet')
        self.dimensions=self.config['dimensions']
        self.measures=self.config['measures']
        self.non_modelled_sk_ng = str(self.config['project_sk'])
        self.non_modelled_sk_ng = str(self.config['non_modelled_sk_ng'])
        self.non_modelled_sk = str(self.config['non_modelled_sk'])
        self.nm_ng = os.path.join(self.path_to_local_data_source, 'cubes', 'CA_' + self.non_modelled_sk_ng + '_MASTER_DETAIL' + '.parquet')
        self.nm = os.path.join(self.path_to_local_data_source, 'cubes', 'CA_' + self.non_modelled_sk + '_MASTER_DETAIL' + '.parquet')
        self.user=self.config['user']
        self.nm_level = self.config['non_modelled_level']
        self.nm_unique_level = self.config['non_modelled_unique_level']
        self.quali= self.config['quali']
        self.bau_mths=pd.date_range(self.config['bau_idp_mth'], periods=2, freq="M")
        self.bau_idp_mth= str(self.bau_mths[0].date())
        self.bau_idp_mth_plus_one= str(self.bau_mths[1].date())

#         self.bau_cecl_agg_cols=self.config['bau_cecl_agg_cols']
#         self.bau_cecl_num_cols=self.config['bau_cecl_num_cols']

#this is way to call it
#import settings
#st=settings.PrepareSettings()
