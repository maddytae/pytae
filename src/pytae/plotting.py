import warnings
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

def customize_spines(self):
    self.spines['left'].set_position(('outward', 5))
    self.spines['bottom'].set_position(('outward', 5))
    self.spines['right'].set_visible(False)
    self.spines['top'].set_visible(False)

Axes.customize_spines = customize_spines




class Plotter:
    def __init__(self, mosaic=None):
        if mosaic is not None:
            self.fig, self.axd = plt.subplot_mosaic(mosaic)
        else:
            self.fig, ax = plt.subplots()
            self.axd = {'default': ax}
        self.last_kwargs = {}
        self.df = None
        plt.close()

    def data(self, df):
        self.df = df
        self.last_kwargs = {}  # Reset kwargs when new data is provided
        return self

    def plot(self, **kwargs):
        self.kwargs = kwargs 

        # Merge new kwargs with the last kwargs, giving precedence to the new ones
        combined_kwargs = {**self.last_kwargs, **self.kwargs}
        
        # Store the combined kwargs for the next call
        self.last_kwargs = combined_kwargs

        self.x = self.last_kwargs.get('x', None)
        self.y = self.last_kwargs.get('y', None)
        self.by = self.last_kwargs.get('by', None)
        
        self.kind = self.last_kwargs.get('kind', 'line') 
        self.aggfunc = self.last_kwargs.get('aggfunc', None) if self.kind == 'scatter' else self.last_kwargs.get('aggfunc', 'sum')
        self.dropna = self.last_kwargs.get('dropna', False)


        # Determine which axis to plot on
        ax_key = self.last_kwargs.get('on', 'default')
        ax = self.axd.get(ax_key, self.axd.get('default'))
        
        self.last_kwargs = {**self.last_kwargs,
                            'aggfunc': self.aggfunc, 
                            'dropna': self.dropna, 
                            'kind': self.kind}

        if self.kind == 'scatter':
            keys_to_remove = {'by', 'aggfunc', 'dropna', 'on'}  # these are kwargs not supported by pandas plot
            plot_dict = {k: v for k, v in self.last_kwargs.items() if k not in keys_to_remove}


            
            if self.aggfunc is None:
                self.ax = self.df.plot(ax=ax, **plot_dict)
            else:
                # Apply aggregation if aggfunc is provided
                dx = self.df[[self.x, self.y, self.by]].groupby(self.by).agg({
                    self.x: self.aggfunc,
                    self.y: self.aggfunc
                }).reset_index()
                self.ax = dx.plot( ax=ax, **plot_dict)
                    
                    
        else:
            keys_to_remove = {'y', 'by', 'aggfunc', 'dropna', 'on'}  # these are kwargs not supported by pandas plot
            plot_dict = {k: v for k, v in self.last_kwargs.items() if k not in keys_to_remove}
            self.ax = self.get_pivot_data().plot(ax=ax, **plot_dict)

        return self

    def get_pivot_data(self):
        self.pivot_table = self.df.pivot_table(index=self.x, columns=self.by, values=self.y,
                                               aggfunc=self.aggfunc, dropna=self.dropna, observed=False).reset_index()
        
        self.pivot_table[self.x] = self.pivot_table[self.x].astype('object')  # Ensure x-axis is not numeric
        return self.pivot_table

    def finalize(self):
        

        # plt.tight_layout()  # Adjust subplots to fit into the figure area nicely
        self.fig.tight_layout()  # or self.fig.set_constrained_layout(True)

        for ax in self.axd.values():
            ax.customize_spines()
            legend = ax.legend()

            if legend:
                legend.get_frame().set_linewidth(0)  # Set legend border linewidth to 0

                
            

            
        
        return self
