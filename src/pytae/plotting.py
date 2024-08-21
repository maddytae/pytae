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
    def __init__(self, mosaic=None,figsize=None):
        if mosaic is not None:
            self.fig, self.axd = plt.subplot_mosaic(mosaic=mosaic,figsize=figsize)
        else:
            self.fig, ax = plt.subplots(figsize=figsize)
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
        elif self.kind == 'line':
            self._plot_line(ax)
        else:
            self._plot_other(ax)

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

    # def _plot_scatter(self, ax):
    #     plot_dict = self._filter_plot_kwargs(['by', 'aggfunc', 'dropna', 'on','print_data','clip_data'])

    #     if self.aggfunc is None:
    #         self.ax = self.df.plot(ax=ax, **plot_dict)
    #     else:
    #         self.df = self.df[[self.x, self.y, self.by]].groupby(self.by).agg({
    #             self.x: self.aggfunc,
    #             self.y: self.aggfunc
    #         }).reset_index()
    #         self.ax = self.df.plot(ax=ax, **plot_dict)

    #     if self.print_data:
    #         print(self.df)
    #     if self.clip_data:
    #         self.df.to_clipboard(index=False)
            
    def _plot_scatter(self,ax):
        plot_dict = self._filter_plot_kwargs([ 'by', 'aggfunc', 'dropna', 'on','print_data','clip_data'])
        



        if self.by:
            
            #handle special case
            color_dict = plot_dict.pop('color', {}) 
            marker_dict = plot_dict.pop('marker', {}) 
            size_dict = plot_dict.pop('s', {})
            

            df=self.df[[self.x,self.y,self.by]]
            if self.aggfunc:
                df = self.df.groupby(self.by, observed=True).agg({self.x: self.aggfunc, self.y: self.aggfunc}).reset_index()

            for l, group_df in df.groupby(self.by, observed=True):

                group_color = color_dict.get(l, None)  # Default to None if color not provided
                group_marker = marker_dict.get(l, 'o')  # Default marker to 'o' if not provided
                group_size = size_dict.get(l, 20)  # Default size to 20 if not provided
                
                self.ax=group_df.plot(ax=ax,marker=group_marker,
                                                  color=group_color,
                                                  s=group_size,
                                      label=l,**plot_dict)
                ax.legend()
            

                    
        else:
            # Handle case when 'by' is not provided
            color = plot_dict.pop('color', 'blue')  # Default to 'blue' if not provided
            marker = plot_dict.pop('marker', 'o')  # Default marker to 'o' if not provided
            size = plot_dict.pop('s', 20)  # Default size to 20 if not provided
            label = plot_dict.pop('label', f"{self.x} vs {self.y}")
    
            df = self.df[[self.x, self.y]]
            self.ax = df.plot(ax=ax, marker=marker, color=color, s=size,label=label, **plot_dict)
            
            ax.legend()  


        
        if self.print_data:
            print(self.df)
        if self.clip_data:
            self.df.to_clipboard(index=False)        



        

            




            
    def _plot_line(self, ax):
        plot_dict = self._filter_plot_kwargs(['y', 'by', 'aggfunc', 'dropna', 'on','print_data','clip_data'])

        #handle special case for lines
        style = plot_dict.pop('style', None) 
        width = plot_dict.pop('width', None) 

        
        pivot_data = self.get_pivot_data()
        self.ax = pivot_data.plot(ax=ax, **plot_dict)
        

        if style:
            for line, (name, style_value) in zip(self.ax.get_lines(), style.items()):
                line.set_linestyle(style_value)
        if width:
            for line, (name, width_value) in zip(self.ax.get_lines(), width.items()):
                line.set_linewidth(width_value)


        
        if self.print_data:
            print(pivot_data)
        if self.clip_data:
            pivot_data.to_clipboard(index=False)
            
    def _plot_other(self, ax):
        plot_dict = self._filter_plot_kwargs(['y', 'by', 'aggfunc', 'dropna', 'on','print_data','clip_data','style','width'])
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


    def finalize(self, consolidate_legends=False, bbox_to_anchor=(0.8, -0.05), ncols=10):
        self.consolidate_legends = consolidate_legends
        self.bbox_to_anchor = bbox_to_anchor
        self.ncols = ncols
    
        handles = []
        labels = []
        seen = set()  # To track unique (label, type) combinations
    
        for ax in self.axd.values():
            # ax.customize_spines()
            # ax.spines['left'].set_position(('outward', 5))
            # ax.spines['bottom'].set_position(('outward', 5))
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
                
        
            # Collect handles and labels for the legends
            h, l = ax.get_legend_handles_labels()
            
            for handle, label in zip(h, l):
                # Create a unique identifier for the (label, type) combination
                handle_type = type(handle)
                identifier = (label, handle_type)
                
                if identifier not in seen:
                    handles.append(handle)
                    labels.append(label)
                    seen.add(identifier)  # Mark this (label, type) as seen
    
            # Manage the legend for the current axis
            legend = ax.get_legend()
            if legend and any(len(text.get_text()) > 0 for text in legend.get_texts()):
                if not self.consolidate_legends:
                    ax.legend(frameon=False)  # Keep individual legends if not consolidating
                else:
                    legend.remove()  # Remove individual legend if consolidating
    
        if self.consolidate_legends:
            # Add a single consolidated legend to the figure
            self.fig.legend(handles, labels, bbox_to_anchor=self.bbox_to_anchor, ncol=self.ncols, frameon=False)
    
        # Adjust the layout
        self.fig.tight_layout()
    
        return self


