import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

def customize_spines(self):
    self.spines['left'].set_position(('outward', 5))
    self.spines['bottom'].set_position(('outward', 5))
    self.spines['right'].set_visible(False)
    self.spines['top'].set_visible(False)

Axes.customize_spines = customize_spines

# Wrapper function
def plot_x(self, ax=None, x=None, y=None, by=None, clip_data=False, print_data=False, aggfunc='sum', 
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
        - **plot_kwargs: Additional keyword arguments passed to pandas' plot method.
    
        Special `plot_kwargs` for 'line' plots:
        - style (dict, optional): A dictionary mapping each `by` value to a line style (e.g., '-', '--').
        - width (dict, optional): A dictionary mapping each `by` value to a line width.
    
        Returns:
        - ax (matplotlib.axes.Axes): The axes with the plotted data.
    
        Notes:
        - Scatter plots are not supported and will raise a warning.
        - The function assumes that the x-axis is not numeric.
        - For `kind='line'`, `style` and `width` are removed before plotting and then reapplied afterward to bypass crrent pandas           limitations.
        - xlabel and ylabel by default are x and y unless it is not passed specifically.
    """
    show_legend = plot_kwargs.pop('legend', True)
    kind = plot_kwargs.pop('kind', 'line')  # 'line' is the default in pandas.plot

    if kind == 'scatter':
        print("Scatter plot is not supported yet!")
        return
        

    # Store and remove style and width if kind == 'line' 
    #https://github.com/pandas-dev/pandas/issues/59461

    style = plot_kwargs.pop('style', None) if kind == 'line' else None
    width = plot_kwargs.pop('width', None) if kind == 'line' else None

    # Remove xlabel and ylabel from plot_kwargs to avoid conflict
    xlabel = plot_kwargs.pop('xlabel', x)
    ylabel = plot_kwargs.pop('ylabel', y)

    pivot_table = self.pivot_table(index=x, columns=by, values=y,
                                   aggfunc=aggfunc, dropna=dropna, observed=False).reset_index()
    pivot_table[x] = pivot_table[x].astype('object')  # Ensure x-axis is not numeric
    
    if print_data:
        print(pivot_table)
    if clip_data:
        pivot_table.to_clipboard(index=False)
    

    ax = pivot_table.plot(ax=ax, x=x, kind=kind,xlabel=xlabel,ylabel=ylabel, **plot_kwargs)

    # Reapply color and style if kind == 'line'
    if kind == 'line':

        if style:
            for line, (name, style_value) in zip(ax.get_lines(), style.items()):
                line.set_linestyle(style_value)
        if width:
            for line, (name, width_value) in zip(ax.get_lines(), width.items()):
                line.set_linewidth(width_value)

    ax.customize_spines()

    if show_legend:
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=10, frameon=False)
    
    return ax

# Attach the function to pandas DataFrame
pd.DataFrame.plot_x = plot_x


