from __future__ import annotations

import math
import warnings

import matplotlib.pyplot as plt
import pandas as pd

# pytae's own control kwargs -- these drive Plotter's behavior directly and are
# never forwarded to pandas.plot() (see _prepare_plot_kwargs/_filter_plot_kwargs).
_CONTROL_KWARGS = ['on', 'print_data', 'clip_data', 'secondary_y', 'aggregate']

# Per-kind config: `strip` = last_kwargs keys to remove before calling pandas'
# own .plot(kind=...) (pytae-only knobs that aren't real pandas.plot() kwargs for
# that kind); `unsupported` = {kwarg: warning message} for kwargs that don't
# apply to this kind at all (warned about, then dropped via `strip`).
_KIND_SPECS = {
    'scatter': {
        'strip': ['by', 'aggfunc', 'dropna', *_CONTROL_KWARGS],
        'unsupported': {
            'aggfunc': "Aggregation is not supported for scatter plots. The 'aggfunc' argument will be ignored.",
            'dropna': "The 'dropna' argument is not applicable to scatter plots and will be ignored.",
            'by': "Use 'c' and 'cmap' to split the scatter plot by a particular column. The 'by' argument will be ignored.",
        },
    },
    'hexbin': {
        'strip': ['by', 'aggfunc', 'dropna', *_CONTROL_KWARGS],
        'unsupported': {
            'aggfunc': "Aggregation is not supported for hex plots. Use reduce_C_function instead.",
            'dropna': "The 'dropna' argument is not applicable to hex plots and will be ignored.",
            'by': "Use 'c' and 'cmap' to split the hex plot by a particular column. The 'by' argument will be ignored.",
        },
    },
    'pie': {
        'strip': ['x', 'by', 'aggfunc', *_CONTROL_KWARGS],
        'unsupported': {},
    },
    'line': {
        'strip': ['y', 'by', 'aggfunc', 'dropna', *_CONTROL_KWARGS],
        'unsupported': {},
    },
    'other': {
        'strip': ['y', 'by', 'aggfunc', 'dropna', *_CONTROL_KWARGS],
        'unsupported': {},
    },
    'kde': {
        'strip': ['x', 'y', 'by', 'aggfunc', 'dropna', *_CONTROL_KWARGS],
        'unsupported': {
            'aggfunc': "Aggregation is not supported for kde/density plot. The 'aggfunc' argument will be ignored.",
            'dropna': "The 'dropna' argument is not applicable to kde/density plots and will be ignored.",
        },
    },
    'hist': {
        'strip': ['x', 'y', 'by', 'aggfunc', 'dropna', 'column', *_CONTROL_KWARGS],
        'unsupported': {
            'aggfunc': "Aggregation is not supported for hist plot. The 'aggfunc' argument will be ignored.",
            'dropna': "The 'dropna' argument is not applicable to hist plots and will be ignored.",
        },
    },
}
_KIND_SPECS['density'] = _KIND_SPECS['kde']  # 'kde' and 'density' are aliases

# Kwargs each kind needs set (via .data()/.plot(x=, y=, by=, column=, ...)) before
# it can render at all -- checked up front so a missing one raises a clear pytae
# error instead of a cryptic pandas KeyError deep inside get_pivot_data()/etc.
_REQUIRED_KWARGS = {
    'scatter': ['x', 'y'],
    'hexbin': ['x', 'y'],
    'line': ['x', 'y'],
    'other': ['x', 'y'],
    'pie': ['by', 'y'],
    'kde': ['column'],
    'density': ['column'],
    'hist': ['column'],
}

class Plotter:
    """
    Method chainable .data() .. .plot() .. .plot() .. .data() .. .plot() .. .finalize().. 
    All args from previous plot call is carried   forward unless data is changed or plot kind is changed.

    All pandas.plot **kwargs are supported except secondary_y. This is because we are handling secondary axis ourseves as for ex A^
    All artists like color, style etc are supposed to be explicitly set via dict. 
    Changing artist attribute post plotting is discouraged respects pandas categorical col for ordering. 
    This is more consistent with general plotting
    """


    def __init__(self, mosaic=None, figsize=None, aggregate=True):
        
        if mosaic is None: #If not provided, a single axis labeled 'A' is created. 'on' is optional in this case
            mosaic = """
            A
            """
        self.fig, self.axd = plt.subplot_mosaic(mosaic=mosaic, figsize=figsize)
        self.last_kwargs = {}
        self.df = None
        self.plot_kwargs_store = {}
        self.aggregate = aggregate  # Class-level default for aggregation; can be overridden at plot level for flexibility
        plt.close()


    def data(self, df):
        self.df = df
        self.last_kwargs = {} #Reset kwargs when new data is chained!
        return self

    @classmethod
    def facet(cls, df, by, *, ncols=None, sort=True, titles=True, figsize=None, aggregate=True, **plot_kwargs):
        """Build a small-multiples grid, one axis per distinct value of `by`, and plot
        the same chart (**plot_kwargs, e.g. x=/y=/kind=) on each facet's own subset of
        rows. A grid isn't always exactly fillable (e.g. 5 groups doesn't tile a 2x3
        rectangle) -- the leftover cell(s) are left blank rather than turned into
        empty/unused axes.

        Parameters:
        -----------
        df : pd.DataFrame
            The data to facet.
        by : str
            Column whose distinct values become one facet (axis) each.
        ncols : int, optional
            Columns in the grid. Defaults to a roughly square layout (ceil(sqrt(n))).
        sort : bool, optional
            Sort group values (default True). Ignored for a `category` dtype column,
            which always uses its own defined category order.
        titles : bool, optional
            Set each facet's axis title to its group value (default True).
        figsize, aggregate :
            Passed straight through to the underlying Plotter().
        **plot_kwargs :
            Passed straight through to .plot() for every facet, e.g. x=, y=, kind=.

        Returns:
        --------
        Plotter
            A regular Plotter instance (chain `.finalize()` etc. as usual); `.axd` is
            keyed by the stringified group values, e.g. `plotter.axd['Adelie']`.
        """
        if isinstance(df[by].dtype, pd.CategoricalDtype):
            present = set(df[by].dropna().unique())
            groups = [g for g in df[by].cat.categories if g in present]
        else:
            groups = list(pd.unique(df[by].dropna()))
            if sort:
                groups = sorted(groups)
        if not groups:
            raise ValueError(f"facet: no groups found in column '{by}'")

        keys = [str(g) for g in groups]
        if len(set(keys)) != len(keys):
            raise ValueError(f"facet: group values in '{by}' produce duplicate axis keys once stringified: {keys}")

        if ncols is not None and ncols < 1:
            raise ValueError(f"facet: ncols must be at least 1, got {ncols}")
        ncols = ncols or math.ceil(math.sqrt(len(groups)))
        nrows = math.ceil(len(groups) / ncols)
        cells = keys + ["."] * (nrows * ncols - len(keys))  # pad leftover cells blank -- grid may not tile exactly
        grid = [cells[i:i + ncols] for i in range(0, len(cells), ncols)]

        plotter = cls(mosaic=grid, figsize=figsize, aggregate=aggregate)
        for group, key in zip(groups, keys):
            plotter.data(df[df[by] == group]).plot(on=key, **plot_kwargs)
            if titles:
                plotter.axd[key].set_title(str(group))
        plotter.df = df  # restore the full input frame -- each facet call above narrowed it to one group
        return plotter

    def plot(self, **kwargs):

        self._update_kwargs(kwargs)
        self._validate_required_kwargs()
        ax = self._get_target_axis()

        if self.kind == 'scatter':
            self._plot_scatter(ax)
        elif self.kind == 'hexbin':
            self._plot_hexbin(ax)
        elif self.kind in ['line']:
            self._plot_line(ax)
        elif self.kind in ['kde', 'density']:
            self._plot_density(ax)
        elif self.kind == 'pie':
            self._plot_pie(ax)
        elif self.kind == 'hist':
            self._plot_hist(ax)
        else:
            self._plot_other(ax)

        return self

    def _update_kwargs(self, kwargs):
        # Extract print_data and clip_data before updating last_kwargs
        self.print_data = kwargs.get('print_data', False)
        self.clip_data = kwargs.get('clip_data', False)

        
        # Store the current kind and check if it has changed
        new_kind = kwargs.get('kind', self.current_kind if hasattr(self, 'current_kind') else 'line')
        
        if hasattr(self, 'current_kind') and self.current_kind != new_kind:
            self.last_kwargs = {} # Reset kwargs if kind changes
        self.current_kind = new_kind

        #Combine kwargs but exclude print_data and clip_data from last_kwargs
        combined_kwargs = {**self.last_kwargs, **kwargs}
        self.last_kwargs = {k: v for k, v in combined_kwargs.items() if k not in ['print_data', 'clip_data']}
        
        self.x = combined_kwargs.get('x', None)
        self.y = combined_kwargs.get('y', None)
        self.by = combined_kwargs.get('by', None)
        self.column = combined_kwargs.get('column', None)
        self.kind = new_kind
        self.aggfunc = combined_kwargs.get('aggfunc', None) if self.kind in ['scatter', 'density', 'kde', 'hist'] else combined_kwargs.get('aggfunc', 'sum')
        self.dropna = combined_kwargs.get('dropna', False)
        self.aggregate = combined_kwargs.get('aggregate', self.aggregate)  # Plot-level overrides class-level

    def _get_target_axis(self):
        ax_key = self.last_kwargs.get('on', 'A')
        if '^' in ax_key:
            base_key = ax_key.rstrip('^')
            if base_key not in self.axd:
                raise ValueError(f"Unknown mosaic key '{base_key}'; available: {list(self.axd)}")
            ax = self.axd[base_key]
            if not hasattr(ax, 'right_ax'):
                right_ax = ax.twinx()
                right_ax.set_label(ax_key)
                ax.right_ax = right_ax
                if ax_key not in self.axd:
                    self.axd[ax_key] = right_ax
                else:
                    warnings.warn(f"Axis '{ax_key}' already exists in axd; using existing axis instead of creating new one.")
                    right_ax = self.axd[ax_key]
            else:
                right_ax = ax.right_ax
            return right_ax
        else:
            if ax_key not in self.axd:
                raise ValueError(f"Unknown mosaic key '{ax_key}'; available: {list(self.axd)}")
            return self.axd[ax_key]

    def _validate_required_kwargs(self):
        """Raise a clear error if a kwarg this kind needs (x=/y=/by=/column=) was
        never set, instead of letting a cryptic pandas KeyError surface later
        from deep inside get_pivot_data()/etc."""
        spec_key = self.kind if self.kind in _REQUIRED_KWARGS else 'other'
        missing = [name for name in _REQUIRED_KWARGS[spec_key] if getattr(self, name, None) is None]
        if missing:
            needed = ', '.join(f"{name}=" for name in missing)
            raise ValueError(f"Plotter: kind='{self.kind}' needs {needed}")

    def _prepare_plot_kwargs(self, spec_key):
        """Warn about any kwarg unsupported by this kind (see _KIND_SPECS), then
        return last_kwargs with pytae's own control/unsupported keys stripped
        so only real pandas.plot() kwargs remain."""
        spec = _KIND_SPECS[spec_key]
        for key, message in spec['unsupported'].items():
            if key in self.last_kwargs:
                warnings.warn(message)
        return self._filter_plot_kwargs(spec['strip'])

    def _plot_scatter(self, ax):
        """Plot a scatter chart."""
        plot_dict = self._prepare_plot_kwargs('scatter')
        self._store_plot_kwargs(ax, plot_dict)
        k = self.df.copy()

        c = plot_dict.get('c', None)
        if c:
            k[c] = k[c].astype('category')
        self.ax = k.plot(ax=ax, **plot_dict)
        self._handle_data_output(k)

    def _plot_pie(self, ax):
        """Plot a pie chart."""
        plot_dict = self._prepare_plot_kwargs('pie')
        self._store_plot_kwargs(ax, plot_dict)
        pie_df = self.df[[self.by, self.y]].groupby(self.by, observed=True, dropna=self.dropna).agg({self.y: self.aggfunc})
        if 'colors' in self.last_kwargs:
            color_dict = self.last_kwargs['colors']
            plot_dict['colors'] = [color_dict.get(category, 'grey') for category in pie_df.index]
        self.ax = pie_df.plot(ax=ax, **plot_dict)
        self._handle_data_output(pie_df)

    def _plot_hexbin(self, ax):
        """Plot a hexbin chart."""
        plot_dict = self._prepare_plot_kwargs('hexbin')
        self._store_plot_kwargs(ax, plot_dict)
        self.ax = self.df.plot(ax=ax, **plot_dict)
        self._handle_data_output(self.df)

    def _plot_line(self, ax):
        """Plot a line chart."""
        plot_dict = self._prepare_plot_kwargs('line')
        self._store_plot_kwargs(ax, plot_dict)
        style = plot_dict.pop('style', None)
        width = plot_dict.pop('width', None)
        color_map = plot_dict.pop('color', None)
        pivot_data = self.get_pivot_data()
        # Build color list from color_map if provided as dict
        if color_map and isinstance(color_map, dict):
            # Get column names (excluding x column which is first)
            data_cols = [c for c in pivot_data.columns if c != self.x]
            color_list = [color_map.get(col, None) for col in data_cols]
            plot_dict['color'] = color_list
        self.ax = pivot_data.plot(ax=ax, **plot_dict)
        if style:
            for line, (name, style_value) in zip(self.ax.get_lines(), style.items()):
                line.set_linestyle(style_value)
        if width:
            for line, (name, width_value) in zip(self.ax.get_lines(), width.items()):
                line.set_linewidth(width_value)
        self._handle_data_output(pivot_data)

    #bar, barh, area
    def _plot_other(self, ax):
        plot_dict = self._prepare_plot_kwargs('other')
        self._store_plot_kwargs(ax, plot_dict)
        pivot_data = self.get_pivot_data()
        self.ax = pivot_data.plot(ax=ax, **plot_dict)
        self._handle_data_output(pivot_data)

    #kde, density
    def _plot_density(self, ax):
        """Plot a density or KDE chart."""
        plot_dict = self._prepare_plot_kwargs('density')
        self._store_plot_kwargs(ax, plot_dict)
        if self.by:
            k = self.df.pivot(columns=self.by, values=self.column)
        else:
            k = self.df[[self.column]]
        self.ax = k.plot(ax=ax, **plot_dict)
        self._handle_data_output(k)

    #hist
    def _plot_hist(self, ax):
        """Plot a histogram."""
        plot_dict = self._prepare_plot_kwargs('hist')
        self._store_plot_kwargs(ax, plot_dict)
        k = self.df.copy()
        if self.by:
            k = k[[self.by, self.column]]
            k = k.pivot(columns=self.by, values=self.column)
        else:
            k = k[[self.column]]
        self.ax = k.plot(ax=ax, **plot_dict)
        self._handle_data_output(k)

    def _filter_plot_kwargs(self, keys_to_remove):
        return {k: v for k, v in self.last_kwargs.items() if k not in keys_to_remove}

    def get_pivot_data(self):
        """
        Generate a pivoted DataFrame for plotting.
        Returns:
            pandas.DataFrame: Pivoted DataFrame ready for plotting.
        """
        if not self.aggregate:  #when aggregation is not required
            if self.by:  #to convert to wide format without aggregate because pandas plot would expect wide data
                # Check for potential duplicates and raise error if found
                unique_combos = self.df[[self.x, self.by]].drop_duplicates().shape[0]
                if unique_combos < len(self.df): #to ensure data is ready for wide formatting without agg
                    raise ValueError("Duplicates found in data for pivot. Use aggregate=True or remove duplicates.")
                pivot_table = self.df.pivot(index=self.x, columns=self.by, values=self.y).reset_index()
            else:
                pivot_table = self.df[[self.x, self.y]].copy()
                # No renaming: Preserve original self.y column name for legend
        else:
            pivot_table = self.df.pivot_table(index=self.x, columns=self.by, values=self.y,
                                            aggfunc=self.aggfunc, dropna=self.dropna, observed=False).reset_index()
        pivot_table[self.x] = pivot_table[self.x].astype('object') if not pd.api.types.is_datetime64_any_dtype(pivot_table[self.x]) else pivot_table[self.x]
        pivot_table.columns.name = None #ensure col names are not corrup with multi index names post pivot
        return pivot_table

    def _handle_data_output(self, data):
        """Handle data output options (print or copy to clipboard)."""
        if self.print_data:
            print(data)
        if self.clip_data:
            data.to_clipboard(index=False)

    def _collect_handles_and_legends(self):
        """
        Collect unique handles and labels from all axes for legend creation.

        Returns:
            tuple: (handles, labels) for legend construction.
        """
        handles = []
        labels = []
        seen = set()
        
        for ax in self.fig.axes:

            ax_label = ax.get_label()
            
            
            # Skip this axis if legend=False is set in plot_kwargs_store
            if ax_label in self.plot_kwargs_store and not self.plot_kwargs_store[ax_label].get('legend', True):
                continue
   

            h, l = ax.get_legend_handles_labels()

            for handle, label in zip(h, l):
                
                label = label.replace(" (right)", "")
                identifier = (label, type(handle))
                if identifier not in seen:
                    handles.append(handle)
                    labels.append(label)
                    seen.add(identifier)

        return handles, labels

    def _store_plot_kwargs(self, ax, plot_dict):
        """Store plot kwargs for the given axis."""
        self.plot_kwargs_store[ax.get_label()] = plot_dict

    def finalize(self, consolidate_legends=False, bbox_to_anchor=(0.8, -0.05), ncols=10, hide_secondary_y=False, 
                 legend=True, legend_primary=True, legend_secondary=True, legend_loc='best', legend_frameon=False,
                 style=True):
        """
        Finalize the plot with layout adjustments and legend settings.
    
        Args:
            consolidate_legends (bool, optional): If True, create a single legend for all axes at the 
                specified `bbox_to_anchor`. If False, allow per-axis legends controlled by `legend_primary` 
                and `legend_secondary`. When True, per-axis legends are suppressed, and only the consolidated 
                legend is displayed if `legend` is True. Default is False.
            bbox_to_anchor (tuple, optional): Anchor point for the consolidated legend as (x, y) in 
                figure coordinates (0 to 1). Ignored if `consolidate_legends` is False. Default is (0.8, -0.05).
            ncols (int, optional): Number of columns in the consolidated legend. Ignored if 
                `consolidate_legends` is False. Default is 10.
            hide_secondary_y (bool, optional): If True, hide secondary y-axis elements (ticks, labels, 
                and right spine) for axes with '^' in their key (e.g., 'A^'). Default is False.
            legend (bool, optional): Global switch to enable or disable all legends (consolidated or 
                per-axis). If False, no legends are displayed regardless of other settings. Default is True.
            legend_primary (bool, optional): Enable/disable legends on primary axes (e.g., 'A') when 
                `consolidate_legends` is False. Ignored when `consolidate_legends` is True. Default is True.
            legend_secondary (bool, optional): Enable/disable legends on secondary axes (e.g., 'A^') when 
                `consolidate_legends` is False. Ignored when `consolidate_legends` is True. Default is True.
            legend_loc (str, optional): Location of per-axis legends (e.g., 'best', 'upper left', 'upper right') 
                when `consolidate_legends` is False. Ignored for consolidated legends, which use `bbox_to_anchor`. 
                Default is 'best'.
            legend_frameon (bool, optional): If True, display a frame around legends (both consolidated and 
                per-axis). Default is False.
            style (bool, optional): If True (default), apply pytae's opinionated spine-hiding and blank-axis
                tick cleanup (see _hide_spines()/_adjust_ticks_and_spines()). Set False to leave matplotlib's
                own default spines/ticks untouched.
    
        Returns:
            Plotter: Self, for method chaining.
    
        Notes:
            - When `consolidate_legends=True`, a single legend is created using all unique handles and labels 
              from all axes, positioned at `bbox_to_anchor`. The `legend_primary` and `legend_secondary` settings 
              are ignored, and per-axis legends are removed. The `legend` parameter must be True for the 
              consolidated legend to appear.
            - When `consolidate_legends=False`, per-axis legends are displayed based on `legend_primary` and 
              `legend_secondary`, with their locations determined by `legend_loc`. The `bbox_to_anchor` and 
              `ncols` parameters are ignored.
            - The `legend` parameter acts as a master switch. If False, no legends (consolidated or per-axis) 
              are shown, overriding all other legend-related settings.
            - Tight layout is applied to prevent overlap of plot elements.
    
        Examples:
            >>> # Consolidated legend
            >>> k.finalize(consolidate_legends=True, legend=True, bbox_to_anchor=(0.75, -0.005), ncols=2)
            >>> # Per-axis legends on primary axes only
            >>> k.finalize(consolidate_legends=False, legend=True, legend_primary=True, legend_secondary=False)
            >>> # No legends
            >>> k.finalize(legend=False)
        """
        self.consolidate_legends = consolidate_legends
        self.bbox_to_anchor = bbox_to_anchor
        self.ncols = ncols
        
        if style:
            self._hide_spines()
            self._adjust_ticks_and_spines()
        self._manage_legend(legend=legend, legend_primary=legend_primary, legend_secondary=legend_secondary, 
                            legend_loc=legend_loc, legend_frameon=legend_frameon)
        
        handles, labels = self._collect_handles_and_legends()
        
        if legend and self.consolidate_legends:
            self.fig.legend(handles, labels, bbox_to_anchor=self.bbox_to_anchor, ncol=self.ncols, frameon=legend_frameon)
        
        if hide_secondary_y:
            for ax_key, ax in self.axd.items():
                if '^' in ax_key:
                    ax.tick_params(axis='y', labelright=False, right=False)
                    ax.spines['right'].set_visible(False)
        
        self.fig.tight_layout()
        return self

    def save(self, path, **kwargs):
        """Save the figure (thin wrapper around fig.savefig()). Chainable, e.g.
        `Plotter().data(df).plot(...).finalize().save('out.png')`."""
        self.fig.savefig(path, **kwargs)
        return self

    @classmethod
    def supported_kwargs(cls, kind):
        """Describe which kwargs are ignored (with a warning) for a given plot
        `kind`, and which pytae-only control kwargs are never forwarded to
        pandas.plot() at all. Everything else in a .plot() call is passed
        straight through to the matching pandas.plot(kind=...) call, so see
        pandas' own docs for the full list of what that kind itself accepts.

        Returns:
        --------
        dict
            {'unsupported': [...], 'pytae_controls': [...]}
        """
        spec_key = 'density' if kind == 'kde' else kind
        spec = _KIND_SPECS.get(spec_key, _KIND_SPECS['other'])
        return {
            'unsupported': sorted(spec['unsupported']),
            'pytae_controls': sorted(set(spec['strip']) - set(spec['unsupported'])),
        }

    def _hide_spines(self):
        """Hide all spines by default, with adjustments for visibility."""
        for ax in self.fig.axes:
            ax_label = ax.get_label()
            if '<colorbar>' in ax_label or ax_label == '':
                continue
            
            ax.spines['top'].set_position(('outward', 5))
            ax.spines['bottom'].set_position(('outward', 5))
            ax.spines['left'].set_position(('outward', 5))
            ax.spines['right'].set_position(('outward', 5))
            
            for spine in ax.spines.values():
                spine.set_visible(False)
    
    def _adjust_ticks_and_spines(self):
        """Adjust tick visibility and spine settings based on whether anything was
        actually plotted on each axis -- using matplotlib's own Axes.has_data()
        rather than pattern-matching its default blank-axis tick label text
        (fragile: real data spanning exactly 0-1 in 0.2 steps would coincidentally
        match the old hardcoded default_labels list and be wrongly treated as blank)."""
        for ax in self.fig.axes:
            ax_label = ax.get_label()
            if '<colorbar>' in ax_label or ax_label == '':
                continue

            blank = not ax.has_data()
            for spine, axis, label_position in [
                ('top', ax.xaxis, 'top'),
                ('bottom', ax.xaxis, 'bottom'),
                ('left', ax.yaxis, 'left'),
                ('right', ax.yaxis, 'right')
            ]:
                labels = ax.get_xticklabels() if axis == ax.xaxis else ax.get_yticklabels()
                labels = [label.get_text() for label in labels if label.get_text()]
                
                if (label_position == axis.get_label_position() and 
                    labels and 
                    not blank):
                    ax.spines[spine].set_visible(True)
                    
                if blank:
                    tick_params_position = 'labeltop' if label_position == 'top' else (
                        'labelbottom' if label_position == 'bottom' else (
                        'labelleft' if label_position == 'left' else 'labelright'
                    ))
                    ax.tick_params(
                        axis='x' if axis == ax.xaxis else 'y', 
                        which='both',
                        length=0,
                        **{tick_params_position: False}
                    )
    
    def _manage_legend(self, legend=True, legend_primary=True, legend_secondary=True, legend_loc='best', legend_frameon=False):
        """
        Manage legend display for each axis.

        Args:
            legend (bool): Enable/disable all legends.
            legend_primary (bool): Enable/disable legends on primary axes.
            legend_secondary (bool): Enable/disable legends on secondary axes.
            legend_loc (str): Location of per-axis legends.
            legend_frameon (bool): Display a frame around legends.
        """
        for ax in self.fig.axes:
            ax_label = ax.get_label()
            is_secondary = '^' in ax_label
            count = sum(1 for k in self.plot_kwargs_store if k.replace('^', '') == ax_label.replace('^', ''))
            
            handles, labels = ax.get_legend_handles_labels()
            labels = [label.replace(" (right)", "") for label in labels]
            
            should_display_legend = False
            if legend:
                if is_secondary and legend_secondary:
                    should_display_legend = True
                elif not is_secondary and legend_primary:
                    should_display_legend = True
            
            if should_display_legend and not self.consolidate_legends:
                ax.legend(handles, labels, frameon=legend_frameon, loc=legend_loc)
            
            if ax.get_legend() and (self.consolidate_legends or not should_display_legend):
                ax.get_legend().remove()
            
            if not self.consolidate_legends and ax.get_label() in self.plot_kwargs_store:
                if self.plot_kwargs_store[ax.get_label()]['kind'] == 'pie':
                    if ax.get_legend():
                        ax.get_legend().remove()
