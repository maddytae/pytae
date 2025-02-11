from .other_utilities import *
from .agg_df import *
from .shape import *
from .plot_x import *
from .plotting import *
from .qry import *
from .select import *

import os
import pandas as pd

# Define the path to the datasets directory
DATA_PATH = os.path.join(os.path.dirname(__file__), 'datasets')

# Load each parquet file into a pandas DataFrame and store them in the dictionary
sample_data = {
    'anagrams': pd.read_parquet(os.path.join(DATA_PATH, 'anagrams.parquet')),
    'anscombe': pd.read_parquet(os.path.join(DATA_PATH, 'anscombe.parquet')),
    'attention': pd.read_parquet(os.path.join(DATA_PATH, 'attention.parquet')),
    'brain_networks': pd.read_parquet(os.path.join(DATA_PATH, 'brain_networks.parquet')),
    'car_crashes': pd.read_parquet(os.path.join(DATA_PATH, 'car_crashes.parquet')),
    'diamonds': pd.read_parquet(os.path.join(DATA_PATH, 'diamonds.parquet')),
    'dots': pd.read_parquet(os.path.join(DATA_PATH, 'dots.parquet')),
    'dowjones': pd.read_parquet(os.path.join(DATA_PATH, 'dowjones.parquet')),
    'exercise': pd.read_parquet(os.path.join(DATA_PATH, 'exercise.parquet')),
    'flights': pd.read_parquet(os.path.join(DATA_PATH, 'flights.parquet')),
    'fmri': pd.read_parquet(os.path.join(DATA_PATH, 'fmri.parquet')),
    'geyser': pd.read_parquet(os.path.join(DATA_PATH, 'geyser.parquet')),
    'glue': pd.read_parquet(os.path.join(DATA_PATH, 'glue.parquet')),
    'healthexp': pd.read_parquet(os.path.join(DATA_PATH, 'healthexp.parquet')),
    'iris': pd.read_parquet(os.path.join(DATA_PATH, 'iris.parquet')),
    'mpg': pd.read_parquet(os.path.join(DATA_PATH, 'mpg.parquet')),
    'penguins': pd.read_parquet(os.path.join(DATA_PATH, 'penguins.parquet')),
    'planets': pd.read_parquet(os.path.join(DATA_PATH, 'planets.parquet')),
    'seaice': pd.read_parquet(os.path.join(DATA_PATH, 'seaice.parquet')),
    'taxis': pd.read_parquet(os.path.join(DATA_PATH, 'taxis.parquet')),
    'tips': pd.read_parquet(os.path.join(DATA_PATH, 'tips.parquet')),
    'titanic': pd.read_parquet(os.path.join(DATA_PATH, 'titanic.parquet'))
    # Add more datasets as needed
}



# Make sample_data available when importing the package
__all__ = ['sample_data']
