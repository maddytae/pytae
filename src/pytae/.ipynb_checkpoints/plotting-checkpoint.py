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
        self._update_kwargs(kwargs)
        ax = self._get_target_axis()

        if self.kind == 'scatter':
            self._plot_scatter(ax)
        else:
            self._plot_others(ax)

        return self


    
    def _update_kwargs(self, kwargs):
        # Extract print_data and clip_data before updating last_kwargs
        self.print_data = kwargs.get('print_data', False)
        self.clip_data = kwargs.get('clip_data', False)
        
        # Combine kwargs but exclude print_data and clip_data from last_kwargs
        combined_kwargs = {**self.last_kwargs, **kwargs}
        self.last_kwargs = {k: v for k, v in combined_kwargs.items() if k not in ['print_data', 'clip_data']}

        self.x = combined_kwargs.get('x', None)
        self.y = combined_kwargs.get('y', None)
        self.by = combined_kwargs.get('by', None)
        self.kind = combined_kwargs.get('kind', 'line')
        self.aggfunc = combined_kwargs.get('aggfunc', None) if self.kind == 'scatter' else combined_kwargs.get('aggfunc', 'sum')
        self.dropna = combined_kwargs.get('dropna', False)
        
    def _get_target_axis(self):
        ax_key = self.last_kwargs.get('on', 'default')
        return self.axd.get(ax_key, self.axd.get('default'))

    def _plot_scatter(self, ax):
        plot_dict = self._filter_plot_kwargs(['by', 'aggfunc', 'dropna', 'on','print_data','clip_data'])

        if self.aggfunc is None:
            self.ax = self.df.plot(ax=ax, **plot_dict)
        else:
            self.df = self.df[[self.x, self.y, self.by]].groupby(self.by).agg({
                self.x: self.aggfunc,
                self.y: self.aggfunc
            }).reset_index()
            self.ax = self.df.plot(ax=ax, **plot_dict)

        if self.print_data:
            print(self.df)
        if self.clip_data:
            self.df.to_clipboard(index=False)

    def _plot_others(self, ax):
        plot_dict = self._filter_plot_kwargs(['y', 'by', 'aggfunc', 'dropna', 'on','print_data','clip_data'])
        self.ax = self.get_pivot_data().plot(ax=ax, **plot_dict)
        
        if self.print_data:
            print(self.get_pivot_data())
        if self.clip_data:
            self.get_pivot_data().to_clipboard(index=False)
    

    def _filter_plot_kwargs(self, keys_to_remove):
        return {k: v for k, v in self.last_kwargs.items() if k not in keys_to_remove}

    def get_pivot_data(self):
        pivot_table = self.df.pivot_table(index=self.x, columns=self.by, values=self.y,
                                          aggfunc=self.aggfunc, dropna=self.dropna, observed=False).reset_index()
        pivot_table[self.x] = pivot_table[self.x].astype('object')

        pivot_table.columns.name = None


        return pivot_table

    def finalize(self):
        self.fig.tight_layout()

        for ax in self.axd.values():
            ax.customize_spines()
            
            legend = ax.get_legend()
            if legend and any(len(text.get_text()) > 0 for text in legend.get_texts()):
                ax.legend(frameon=False)

    


        return self
