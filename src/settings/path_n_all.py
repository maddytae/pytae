import os
import yaml
from yaml.loader import SafeLoader
import pandas as pd


class PrepareSettings:
    def __init__(self):
        self.project_path = os.path.dirname(os.getcwd())
        self.config_path= os.path.join(self.project_path, 'configuration')


        with open(os.path.join(self.config_path, 'config.yaml')) as f:
            self.config = yaml.load(f, Loader=SafeLoader)
            
        self.user= self.config['user']





