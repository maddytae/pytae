import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

def customize_spines(self):
    self.spines['left'].set_position(('outward', 5))
    self.spines['bottom'].set_position(('outward', 5))
    self.spines['right'].set_visible(False)
    self.spines['top'].set_visible(False)

Axes.customize_spines = customize_spines


#wrapper function
def plot_x(self, ax=None, x=None, y=None, by=None,clip_data=False,print_data=False, aggfunc='sum', 
           dropna=False, **plot_kwargs):
    """
    Plots data from a pivot table, allowing customization of plot type and appearance.

    Parameters:
    - ax (matplotlib.axes.Axes, optional): The axes on which to plot. If None, a new figure and axes will be created.
    - x (str): Column name to use for the x-axis.
    - y (str): Column name to use for the y-axis.
    - by (str): Column name to group by for pivoting the table.
    - clip_data (bool, optional): If True, copies the resulting pivot table to the clipboard. Default is False.
    - print_data (bool, optional): If True, prints the resulting pivot table. Default is False.
    - aggfunc (str or function, optional): Aggregation function to use for the pivot table. Default is 'sum'.
    - dropna (bool, optional): If True, excludes missing values from the pivot table. Default is False.
    - **plot_kwargs: Additional keyword arguments passed to pandas' plot method (e.g., 'legend', 'kind').

    Returns:
    - ax (matplotlib.axes.Axes): The axes with the plotted data.

    Notes:
    - Scatter plots are not supported and will raise a warning.
    - The function assumes that the x-axis label is categorical if it is numeric to avoid issues with plotting.
    - The `plot_kwargs` parameter allows for customization of the plot, such as setting the legend visibility or plot kind (e.g., 'line', 'bar').
    """
    show_legend = plot_kwargs.pop('legend', True)
    kind = plot_kwargs.pop('kind', 'line') #line is default in pandas.plot

    if kind == 'scatter':
        # raise NotImplementedError("Scatter plot is not supported yet!")
        print("Scatter plot is not supported yet!")
        return
        
        
    
    pivot_table = self.pivot_table(index=x, columns=by, values=y,
                                   aggfunc=aggfunc, dropna=dropna,observed=False).reset_index()
    pivot_table[x]=pivot_table[x].astype('object') #numeric x label creates issue
    
    if print_data:
        print(pivot_table)
    if clip_data:
        pivot_table.to_clipboard(index=False)
    
    # Plot the data
    ax = pivot_table.plot(ax=ax,x=x,kind=kind, **plot_kwargs) 
    
    #not intended to handle scatter because scatter needs numeric x and y
    #will enhance this in future to handle the scatter plot; else continue to use other tools like seaborn etc for scatter
    
    ax.customize_spines()
    if show_legend:
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=10, frameon=False)
    
    return ax


pd.DataFrame.plot_x = plot_x

