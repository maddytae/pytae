from __future__ import annotations

import io
import math
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# pytae's own control kwargs -- these drive Plotter's behavior directly and are
# never forwarded to pandas.plot() (see _prepare_plot_kwargs/_filter_plot_kwargs).
_CONTROL_KWARGS = [
    'on', 'print_data', 'clip_data', 'secondary_y', 'aggregate',
    'xlabel', 'ylabel', 'palette', 'annot', 'fmt',
]

# Per-kind config: `strip` = last_kwargs keys to remove before calling pandas'
# own .plot(kind=...) (pytae-only knobs that aren't real pandas.plot() kwargs for
# that kind); `unsupported` = {kwarg: warning message} for kwargs that don't
# apply to this kind at all (warned about, then dropped via `strip`).
_KIND_SPECS = {
    'scatter': {
        'strip': ['aggfunc', 'dropna', *_CONTROL_KWARGS],
        'unsupported': {
            'aggfunc': "Aggregation is not supported for scatter plots. The 'aggfunc' argument will be ignored.",
            'dropna': "The 'dropna' argument is not applicable to scatter plots and will be ignored.",
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
    'box': {
        'strip': ['x', 'y', 'by', 'aggfunc', 'dropna', 'column', *_CONTROL_KWARGS],
        'unsupported': {
            'aggfunc': "Aggregation is not supported for box plots. The 'aggfunc' argument will be ignored.",
            'dropna': "The 'dropna' argument is not applicable to box plots and will be ignored.",
        },
    },
    'heatmap': {
        'strip': ['x', 'y', 'by', 'aggfunc', 'dropna', 'column', *_CONTROL_KWARGS],
        'unsupported': {},
    },
    'other': {
        'strip': ['y', 'by', 'aggfunc', 'dropna', *_CONTROL_KWARGS],
        'unsupported': {},
    },
    'kde': {
        'strip': ['x', 'y', 'by', 'aggfunc', 'dropna', 'column', *_CONTROL_KWARGS],
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
    'box': ['y'],
    'pie': ['by', 'y'],
    'kde': ['column'],
    'density': ['column'],
    'hist': ['column'],
    'heatmap': [],
}

class Plotter:
    """
    Method chainable .data() .. .plot() .. .plot() .. .data() .. .plot() .. .finalize().. 
    All args from previous plot call are carried forward unless data is changed or plot kind is changed.

    All pandas.plot **kwargs are supported except secondary_y. This is because we are handling secondary axis ourselves (e.g. A^).
    All artists like color, style etc are supported explicitly via dict or built-in palette.
    """

    _last_active = None

    def __new__(cls, *args, **kwargs):
        df = args[0] if args else kwargs.get("df")
        by_col = kwargs.get("by") or kwargs.get("col")
        has_facet_trigger = (
            kwargs.get("ncols") is not None
            or kwargs.get("facet") is True
            or "col" in kwargs
        )
        is_plot_call = bool(
            {"kind", "x", "y", "column"}.intersection(kwargs.keys())
        )

        if (
            not kwargs.get("_is_facet_grid")
            and isinstance(df, pd.DataFrame)
            and by_col
            and by_col in df
            and has_facet_trigger
            and is_plot_call
        ):
            if "mosaic" in kwargs or (len(args) > 1 and args[1] is not None):
                raise ValueError("Cannot combine 'mosaic' with faceting ('by' with 'ncols'/'facet'/'col').")
            if "nrows" in kwargs:
                raise ValueError("Cannot combine 'nrows' with faceting ('by' with 'ncols'/'facet'/'col'). Use 'ncols' to control grid columns.")

            facet_kwargs = dict(kwargs)
            facet_kwargs.pop("df", None)
            facet_kwargs.pop("by", None)
            facet_kwargs.pop("col", None)
            facet_kwargs.pop("facet", None)
            ncols = facet_kwargs.pop("ncols", None)
            return cls.facet(df, by=by_col, ncols=ncols, **facet_kwargs)

        return super().__new__(cls)

    def __init__(self, df=None, mosaic=None, figsize=None, aggregate=True, sharex=False, sharey=False, nrows=None, ncols=None, **kwargs):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True
        Plotter._last_active = self
        if df is not None and not isinstance(df, pd.DataFrame):
            # df was passed as mosaic string or grid list e.g. Plotter("AB")
            if mosaic is None:
                mosaic = df
                df = None

        if mosaic is None and (nrows is not None or ncols is not None):
            nrows = nrows or 1
            ncols = ncols or 1
            import string
            labels = string.ascii_uppercase
            grid = []
            idx = 0
            for r in range(nrows):
                row = []
                for c in range(ncols):
                    label = labels[idx] if idx < len(labels) else f"ax_{idx}"
                    row.append(label)
                    idx += 1
                grid.append(row)
            mosaic = grid

        if mosaic is None:  # If not provided, a single axis labeled 'A' is created. 'on' is optional in this case
            mosaic = """
            A
            """
        self.fig, self.axd = plt.subplot_mosaic(mosaic=mosaic, figsize=figsize, sharex=sharex, sharey=sharey)

        self.last_kwargs = {}
        self.df = None
        self.plot_kwargs_store = {}
        self.tables = {}
        self.aggregate = aggregate  # Class-level default for aggregation; can be overridden at plot level for flexibility
        if df is not None:
            self.data(df)
        plt.close()

        plot_keys = {"kind", "x", "y", "column"}
        plot_kwargs = {k: v for k, v in kwargs.items() if k != "_is_facet_grid"}
        if plot_keys.intersection(plot_kwargs.keys()):
            if self.df is not None:
                self.plot(**plot_kwargs)
        elif plot_kwargs:
            unexpected = ", ".join(repr(k) for k in plot_kwargs.keys())
            raise TypeError(f"Plotter.__init__() got unexpected keyword argument(s): {unexpected}")

    def _repr_png_(self):
        """Render figure as PNG bytes for automatic display in Jupyter notebooks."""
        buf = io.BytesIO()
        self.fig.savefig(buf, format="png", bbox_inches="tight")
        return buf.getvalue()

    @property
    def pt(self):
        """Allow consistent fluent chaining using the .pt namespace (e.g. df.pt.plot().pt.finalize())."""
        return self

    def data(self, df):
        Plotter._last_active = self
        self.df = df
        self.last_kwargs = {}  # Reset kwargs when new data is chained!
        return self

    def get_data(self, on="A"):
        """Retrieve the DataFrame plotted on the specified axis key."""
        if on in self.tables:
            return self.tables[on]
        for k, v in self.tables.items():
            if k == on or k.rstrip("^") == on:
                return v
        raise KeyError(f"No plotted data found for axis {on!r}; available: {list(self.tables)}")

    @classmethod
    def facet(cls, df, by, *, ncols=None, sort=True, titles=True, figsize=None, aggregate=True, sharex=False, sharey=False, **plot_kwargs):
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
        sharex, sharey : bool, optional
            Share x or y axis scales across facets (default False).
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

        plot_kwargs = dict(plot_kwargs)
        if "mosaic" in plot_kwargs:
            raise ValueError("Cannot combine 'mosaic' with faceting. Faceting generates its own layout grid.")
        if "nrows" in plot_kwargs:
            raise ValueError("Cannot combine 'nrows' with faceting. Use 'ncols' to control grid columns.")
        plot_kwargs.pop('mosaic', None)
        plot_kwargs.pop('nrows', None)
        plot_kwargs.pop('on', None)
        suptitle = plot_kwargs.pop('suptitle', None) or plot_kwargs.pop('title', None)
        plotter = cls(mosaic=grid, figsize=figsize, aggregate=aggregate, sharex=sharex, sharey=sharey, _is_facet_grid=True)
        for group, key in zip(groups, keys):
            plotter.data(df[df[by] == group]).plot(on=key, **plot_kwargs)
            if titles:
                plotter.axd[key].set_title(str(group))
        if suptitle:
            plotter.fig.suptitle(str(suptitle))
        plotter.df = df  # restore the full input frame -- each facet call above narrowed it to one group
        plotter._initialized = True
        Plotter._last_active = plotter
        return plotter

    def plot(self, **kwargs):
        Plotter._last_active = self
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
        elif self.kind == 'box':
            self._plot_box(ax)
        elif self.kind == 'heatmap':
            self._plot_heatmap(ax)
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
            self.last_kwargs = {}  # Reset kwargs if kind changes
        self.current_kind = new_kind

        # Combine kwargs but exclude print_data and clip_data from last_kwargs
        combined_kwargs = {**self.last_kwargs, **kwargs}
        self.last_kwargs = {k: v for k, v in combined_kwargs.items() if k not in ['print_data', 'clip_data']}
        self.last_kwargs['kind'] = new_kind
        
        self.x = combined_kwargs.get('x', None)
        self.y = combined_kwargs.get('y', None)
        self.by = combined_kwargs.get('by', None)
        if self.by is None and isinstance(self.df, pd.DataFrame):
            for alias in ('color', 'hue'):
                val = combined_kwargs.get(alias)
                if isinstance(val, str) and val in self.df.columns:
                    self.by = val
                    if alias in self.last_kwargs:
                        del self.last_kwargs[alias]
                    break
        self.column = combined_kwargs.get('column', None) or combined_kwargs.get('x', None)
        self.kind = new_kind

        if self.kind == 'box':
            self.y = self.y or self.column
            self.x = self.x or self.by

        self.aggfunc = combined_kwargs.get('aggfunc', None) if self.kind in ['scatter', 'density', 'kde', 'hist', 'box'] else combined_kwargs.get('aggfunc', 'sum')
        self.dropna = combined_kwargs.get('dropna', False)
        self.aggregate = combined_kwargs.get('aggregate', self.aggregate)  # Plot-level overrides class-level

    def _get_target_axis(self):
        ax_key = self.last_kwargs.get('on', 'A')
        if self.last_kwargs.get('secondary_y') and not ax_key.endswith('^'):
            ax_key = f"{ax_key}^"
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

    def _apply_axis_labels(self, ax):
        """Apply optional custom xlabel and ylabel."""
        xlabel = self.last_kwargs.get('xlabel')
        ylabel = self.last_kwargs.get('ylabel')
        if xlabel is not None:
            ax.set_xlabel(xlabel)
        if ylabel is not None:
            ax.set_ylabel(ylabel)

    def _get_palette_colors(self, categories, palette=None, explicit_colors=None):
        """Map category names to colors from an explicit dict, list, or named matplotlib colormap/palette."""
        if isinstance(explicit_colors, dict):
            return explicit_colors
        if isinstance(explicit_colors, str):
            return {cat: explicit_colors for cat in categories}
        if isinstance(explicit_colors, (list, tuple)):
            return {cat: explicit_colors[i % len(explicit_colors)] for i, cat in enumerate(categories)}

        palette = palette or "tab10"
        try:
            cmap = plt.get_cmap(palette)
        except (ValueError, AttributeError):
            warnings.warn(f"Unknown palette '{palette}', falling back to 'tab10'.")
            cmap = plt.get_cmap("tab10")

        n = len(categories)
        if hasattr(cmap, "colors") and len(cmap.colors) >= n:
            return {cat: cmap.colors[i] for i, cat in enumerate(categories)}
        elif n <= 1:
            return {categories[0]: cmap(0.5)}
        else:
            return {cat: cmap(i / max(n - 1, 1)) for i, cat in enumerate(categories)}

    def _plot_scatter(self, ax):
        """Plot a scatter chart with support for continuous 'c' or discrete 'by' categories."""
        plot_dict = self._prepare_plot_kwargs('scatter')
        self._store_plot_kwargs(ax, plot_dict)
        k = self.df.copy()

        if self.by and self.by in k:
            if isinstance(k[self.by].dtype, pd.CategoricalDtype):
                present = set(k[self.by].dropna().unique())
                groups = [g for g in k[self.by].cat.categories if g in present]
            else:
                groups = list(pd.unique(k[self.by].dropna()))

            palette_name = self.last_kwargs.get('palette')
            color_arg = self.last_kwargs.get('color')
            color_map = self._get_palette_colors(groups, palette=palette_name, explicit_colors=color_arg)

            scatter_kwargs = dict(plot_dict)
            for non_scatter in ['x', 'y', 'by', 'kind', 'title', 'color', 'c', 'legend', 'grid', 'logx', 'logy', 'rot', 'fontsize', 'colormap', 'colorbar', 'xlim', 'ylim']:
                scatter_kwargs.pop(non_scatter, None)

            s_arg = scatter_kwargs.pop('s', 20)
            marker = scatter_kwargs.pop('marker', 'o')
            alpha = scatter_kwargs.pop('alpha', 0.8)

            for group in groups:
                grp_mask = (k[self.by] == group)
                grp_df = k[grp_mask]
                grp_color = color_map.get(group) if isinstance(color_map, dict) else None
                if isinstance(s_arg, str) and s_arg in k.columns:
                    grp_s = k.loc[grp_mask, s_arg].to_numpy()
                elif hasattr(s_arg, '__len__') and not isinstance(s_arg, (str, bytes)):
                    grp_s = np.asarray(s_arg)[grp_mask.to_numpy()]
                else:
                    grp_s = s_arg

                ax.scatter(
                    grp_df[self.x],
                    grp_df[self.y],
                    label=str(group),
                    color=grp_color,
                    s=grp_s,
                    marker=marker,
                    alpha=alpha,
                    **scatter_kwargs,
                )
            if plot_dict.get('grid'):
                ax.grid(True)
            if plot_dict.get('logx'):
                ax.set_xscale('log')
            if plot_dict.get('logy'):
                ax.set_yscale('log')
            if 'xlim' in plot_dict:
                ax.set_xlim(plot_dict['xlim'])
            if 'ylim' in plot_dict:
                ax.set_ylim(plot_dict['ylim'])
            rot = plot_dict.get('rot')
            fontsize = plot_dict.get('fontsize')
            if rot is not None or fontsize is not None:
                tick_kw = {}
                if rot is not None:
                    tick_kw['labelrotation'] = rot
                if fontsize is not None:
                    tick_kw['labelsize'] = fontsize
                ax.tick_params(axis='x', **tick_kw)
            self.ax = ax
            if self.last_kwargs.get('title'):
                ax.set_title(self.last_kwargs['title'])
            if self.last_kwargs.get('xlabel') is None and self.x:
                ax.set_xlabel(str(self.x))
            if self.last_kwargs.get('ylabel') is None and self.y:
                ax.set_ylabel(str(self.y))
            self._apply_axis_labels(ax)
            self._handle_data_output(k, ax)
            return

        c = plot_dict.get('c', None)
        if c is not None:
            try:
                is_in_cols = (c in k.columns)
            except TypeError:
                is_in_cols = False
            if is_in_cols and not pd.api.types.is_numeric_dtype(k[c]):
                k[c] = k[c].astype('category')
        self.ax = k.plot(ax=ax, **plot_dict)
        self._apply_axis_labels(ax)
        self._handle_data_output(k, ax)

    def _plot_pie(self, ax):
        """Plot a pie chart."""
        plot_dict = self._prepare_plot_kwargs('pie')
        self._store_plot_kwargs(ax, plot_dict)
        pie_df = self.df[[self.by, self.y]].groupby(self.by, observed=True, dropna=self.dropna).agg({self.y: self.aggfunc})
        if 'colors' in self.last_kwargs:
            color_arg = self.last_kwargs['colors']
            if isinstance(color_arg, (list, tuple)):
                plot_dict['colors'] = color_arg
            elif isinstance(color_arg, dict):
                plot_dict['colors'] = [color_arg.get(category, 'grey') for category in pie_df.index]
        elif 'palette' in self.last_kwargs:
            colors = self._get_palette_colors(list(pie_df.index), palette=self.last_kwargs['palette'])
            plot_dict['colors'] = [colors.get(category, 'grey') for category in pie_df.index]
        self.ax = pie_df.plot(ax=ax, **plot_dict)
        self._apply_axis_labels(ax)
        self._handle_data_output(pie_df, ax)

    def _plot_hexbin(self, ax):
        """Plot a hexbin chart."""
        plot_dict = self._prepare_plot_kwargs('hexbin')
        self._store_plot_kwargs(ax, plot_dict)
        self.ax = self.df.plot(ax=ax, **plot_dict)
        self._apply_axis_labels(ax)
        self._handle_data_output(self.df, ax)

    def _plot_line(self, ax):
        """Plot a line chart."""
        plot_dict = self._prepare_plot_kwargs('line')
        self._store_plot_kwargs(ax, plot_dict)
        style = plot_dict.pop('style', None)
        width = plot_dict.pop('width', None)
        color_map = plot_dict.pop('color', None)
        palette = self.last_kwargs.get('palette')
        pivot_data = self.get_pivot_data()
        data_cols = [c for c in pivot_data.columns if c != self.x]

        if color_map and isinstance(color_map, dict):
            color_list = [color_map.get(col, None) for col in data_cols]
            plot_dict['color'] = color_list
        elif palette:
            colors = self._get_palette_colors(data_cols, palette=palette)
            plot_dict['color'] = [colors.get(c) for c in data_cols]
        elif color_map is not None:
            plot_dict['color'] = color_map

        if style is not None and not isinstance(style, dict):
            plot_dict['style'] = style
        if width is not None and not isinstance(width, dict):
            plot_dict['linewidth'] = width

        self.ax = pivot_data.plot(ax=ax, **plot_dict)
        if style is not None and isinstance(style, dict):
            style_lookup = {str(k): v for k, v in style.items()}
            style_lookup.update(style)
            for line in self.ax.get_lines():
                lbl = line.get_label()
                if lbl in style_lookup:
                    line.set_linestyle(style_lookup[lbl])
        if width is not None:
            if isinstance(width, dict):
                width_lookup = {str(k): v for k, v in width.items()}
                width_lookup.update(width)
                for line in self.ax.get_lines():
                    lbl = line.get_label()
                    if lbl in width_lookup:
                        line.set_linewidth(width_lookup[lbl])
            else:
                for line in self.ax.get_lines():
                    line.set_linewidth(width)
        self._apply_axis_labels(ax)
        self._handle_data_output(pivot_data, ax)

    def _plot_box(self, ax):
        """Plot a box chart showing unaggregated distributions per group or single column."""
        plot_dict = self._prepare_plot_kwargs('box')
        self._store_plot_kwargs(ax, plot_dict)
        val_col = self.y
        cat_col = self.x

        if cat_col and cat_col in self.df:
            if isinstance(self.df[cat_col].dtype, pd.CategoricalDtype):
                present = set(self.df[cat_col].dropna().unique())
                categories = [c for c in self.df[cat_col].cat.categories if c in present]
            else:
                categories = list(pd.unique(self.df[cat_col].dropna()))
            cols = {str(cat): self.df.loc[self.df[cat_col] == cat, val_col].reset_index(drop=True) for cat in categories}
            box_df = pd.DataFrame(cols)
        else:
            box_df = self.df[[val_col]]

        palette = self.last_kwargs.get('palette')
        color_arg = self.last_kwargs.get('color')
        if palette or color_arg:
            plot_dict['patch_artist'] = True
            plot_dict.pop('color', None)

        self.ax = box_df.plot(ax=ax, **plot_dict)

        if palette or color_arg:
            colors = self._get_palette_colors(list(box_df.columns), palette=palette, explicit_colors=color_arg)
            new_patches = ax.patches[-len(box_df.columns):]
            for patch, col in zip(new_patches, box_df.columns):
                if col in colors:
                    patch.set_facecolor(colors[col])

        self._apply_axis_labels(ax)
        self._handle_data_output(box_df, ax)

    def _plot_heatmap(self, ax):
        """Plot a 2D heatmap matrix (correlation matrix or pivoted data)."""
        plot_dict = self._prepare_plot_kwargs('heatmap')
        self._store_plot_kwargs(ax, plot_dict)
        cmap = self.last_kwargs.get('cmap', self.last_kwargs.get('palette', 'viridis'))
        annot = self.last_kwargs.get('annot', False)
        fmt = self.last_kwargs.get('fmt', '.2f')

        imshow_kwargs = {}
        for key in ['vmin', 'vmax', 'interpolation', 'origin', 'norm', 'alpha']:
            if key in self.last_kwargs:
                imshow_kwargs[key] = self.last_kwargs[key]

        if self.x and self.by and self.y:
            matrix = self.get_pivot_data().set_index(self.x)
        elif self.x and self.y:
            matrix = self.df.pivot_table(index=self.x, columns=self.y, aggfunc='size', fill_value=0)
        else:
            matrix = self.df.select_dtypes(include='number')

        im = ax.imshow(matrix.values, cmap=cmap, aspect='auto', **imshow_kwargs)
        ax.set_xticks(range(len(matrix.columns)))
        ax.set_xticklabels([str(c) for c in matrix.columns], rotation=45, ha='right')
        ax.set_yticks(range(len(matrix.index)))
        ax.set_yticklabels([str(idx) for idx in matrix.index])

        if annot:
            for i in range(len(matrix.index)):
                for j in range(len(matrix.columns)):
                    val = matrix.iloc[i, j]
                    is_num = isinstance(val, (int, float, np.integer, np.floating)) and not isinstance(val, (bool, np.bool_))
                    text_str = format(val, fmt) if is_num else str(val)
                    is_nan = is_num and (np.isnan(val) if isinstance(val, (float, np.floating)) else False)
                    if is_num and not is_nan:
                        rgba = im.cmap(im.norm(val))
                        luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                        text_color = "white" if luminance < 0.5 else "black"
                    else:
                        text_color = "white"
                    ax.text(j, i, text_str, ha='center', va='center', color=text_color)

        self.fig.colorbar(im, ax=ax)
        if self.last_kwargs.get('title'):
            ax.set_title(self.last_kwargs['title'])
        self._apply_axis_labels(ax)
        self.ax = ax
        self._handle_data_output(matrix, ax)

    # bar, barh, area
    def _plot_other(self, ax):
        plot_dict = self._prepare_plot_kwargs('other')
        self._store_plot_kwargs(ax, plot_dict)
        pivot_data = self.get_pivot_data()
        palette = self.last_kwargs.get('palette')
        if palette and 'color' not in plot_dict:
            data_cols = [c for c in pivot_data.columns if c != self.x]
            colors = self._get_palette_colors(data_cols, palette=palette)
            plot_dict['color'] = [colors.get(c) for c in data_cols]
        self.ax = pivot_data.plot(ax=ax, **plot_dict)
        self._apply_axis_labels(ax)
        self._handle_data_output(pivot_data, ax)

    # kde, density
    def _plot_density(self, ax):
        """Plot a density or KDE chart."""
        plot_dict = self._prepare_plot_kwargs('density')
        self._store_plot_kwargs(ax, plot_dict)
        if self.by:
            sub = self.df[[self.by, self.column]].copy()
            sub["__row__"] = sub.groupby(self.by).cumcount()
            k = sub.pivot(index="__row__", columns=self.by, values=self.column)
            k.index.name = None
            k.columns.name = None
        else:
            k = self.df[[self.column]]
        palette = self.last_kwargs.get('palette')
        if palette and 'color' not in plot_dict:
            colors = self._get_palette_colors(list(k.columns), palette=palette)
            plot_dict['color'] = [colors.get(c) for c in k.columns]
        self.ax = k.plot(ax=ax, **plot_dict)
        self._apply_axis_labels(ax)
        self._handle_data_output(k, ax)

    # hist
    def _plot_hist(self, ax):
        """Plot a histogram."""
        plot_dict = self._prepare_plot_kwargs('hist')
        self._store_plot_kwargs(ax, plot_dict)
        if self.by:
            sub = self.df[[self.by, self.column]].copy()
            sub["__row__"] = sub.groupby(self.by).cumcount()
            k = sub.pivot(index="__row__", columns=self.by, values=self.column)
            k.index.name = None
            k.columns.name = None
        else:
            k = self.df[[self.column]]
        palette = self.last_kwargs.get('palette')
        if palette and 'color' not in plot_dict:
            colors = self._get_palette_colors(list(k.columns), palette=palette)
            plot_dict['color'] = [colors.get(c) for c in k.columns]
        self.ax = k.plot(ax=ax, **plot_dict)
        self._apply_axis_labels(ax)
        self._handle_data_output(k, ax)

    def _filter_plot_kwargs(self, keys_to_remove):
        return {k: v for k, v in self.last_kwargs.items() if k not in keys_to_remove}

    def get_pivot_data(self):
        """
        Generate a pivoted DataFrame for plotting.
        Returns:
            pandas.DataFrame: Pivoted DataFrame ready for plotting.
        """
        if not self.aggregate:  # when aggregation is not required
            if self.by:  # to convert to wide format without aggregate because pandas plot would expect wide data
                # Check for potential duplicates and raise error if found
                unique_combos = self.df[[self.x, self.by]].drop_duplicates().shape[0]
                if unique_combos < len(self.df):  # to ensure data is ready for wide formatting without agg
                    raise ValueError("Duplicates found in data for pivot. Use aggregate=True or remove duplicates.")
                pivot_table = self.df.pivot(index=self.x, columns=self.by, values=self.y).reset_index()
            else:
                y_cols = list(self.y) if isinstance(self.y, (list, tuple)) else ([self.y] if self.y is not None else [])
                cols = ([self.x] if self.x is not None else []) + [c for c in y_cols if c != self.x]
                pivot_table = self.df[cols].copy()
        else:
            pivot_table = self.df.pivot_table(index=self.x, columns=self.by, values=self.y,
                                            aggfunc=self.aggfunc, dropna=self.dropna, observed=False).reset_index()
            if self.by is None and isinstance(self.y, (list, tuple)):
                desired_order = ([self.x] if self.x is not None and self.x in pivot_table.columns else []) + [c for c in self.y if c in pivot_table.columns]
                other_cols = [c for c in pivot_table.columns if c not in desired_order]
                pivot_table = pivot_table[desired_order + other_cols]

        if self.x and self.x in pivot_table.columns and self.kind in ['bar', 'barh']:
            if not pd.api.types.is_datetime64_any_dtype(pivot_table[self.x]):
                pivot_table[self.x] = pivot_table[self.x].astype('object')
        pivot_table.columns.name = None  # ensure col names are not corrupt with multi index names post pivot
        return pivot_table

    def _handle_data_output(self, data, ax=None):
        """Handle data output options (print, copy to clipboard, record table)."""
        if ax is not None:
            self.tables[ax.get_label()] = data
        if self.print_data:
            print(data)
        if self.clip_data:
            try:
                data.to_clipboard(index=False)
            except Exception:
                pass

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
        d = dict(plot_dict)
        d['kind'] = self.kind
        self.plot_kwargs_store[ax.get_label()] = d

    def finalize(self, consolidate_legends=False, bbox_to_anchor=(0.8, -0.05), ncols=10, hide_secondary_y=False, 
                 legend=True, legend_primary=True, legend_secondary=True, legend_loc='best', legend_frameon=False,
                 style=True):
        """
        Finalize the plot with layout adjustments and legend settings.
        """
        Plotter._last_active = self
        self.consolidate_legends = consolidate_legends
        self.bbox_to_anchor = bbox_to_anchor
        self.ncols = ncols
        
        if style:
            self._hide_spines()
            self._adjust_ticks_and_spines()
            for ax in self.fig.axes:
                ax_label = ax.get_label()
                if '<colorbar>' in ax_label or ax_label == '':
                    continue
                stored = self.plot_kwargs_store.get(ax_label, {})
                kind = stored.get('kind', '')
                rot = stored.get('rot')
                fontsize = stored.get('fontsize')
                if rot is None and kind == 'bar':
                    rot = 90
                elif rot is None and kind == 'barh':
                    rot = 0
                target_axis = 'y' if kind == 'barh' else 'x'
                if fontsize is not None:
                    ax.tick_params(axis='both', labelsize=fontsize)
                if rot is not None:
                    ax.tick_params(axis=target_axis, labelrotation=rot)
        self._manage_legend(legend=legend, legend_primary=legend_primary, legend_secondary=legend_secondary, 
                            legend_loc=legend_loc, legend_frameon=legend_frameon)
        
        handles, labels = self._collect_handles_and_legends()
        
        if hide_secondary_y:
            for ax_key, ax in self.axd.items():
                if '^' in ax_key:
                    ax.tick_params(axis='y', labelright=False, right=False)
                    ax.spines['right'].set_visible(False)
        
        # Apply layout adjustments before drawing figure-level legend to avoid clipping
        if self.consolidate_legends and self.bbox_to_anchor[1] < 0:
            self.fig.tight_layout(rect=[0, 0.08, 1, 1])
        else:
            self.fig.tight_layout()

        if legend and self.consolidate_legends and handles:
            self.fig.legend(handles, labels, bbox_to_anchor=self.bbox_to_anchor, ncol=self.ncols, frameon=legend_frameon)

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
        straight through to the matching pandas.plot(kind=...) call.

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
        actually plotted on each axis."""
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
        """Manage legend display for each axis."""
        for ax in self.fig.axes:
            ax_label = ax.get_label()
            is_secondary = '^' in ax_label
            
            handles, labels = ax.get_legend_handles_labels()
            labels = [label.replace(" (right)", "") for label in labels]
            
            stored_legend = self.plot_kwargs_store.get(ax_label, {}).get('legend', True)
            should_display_legend = False
            if legend and stored_legend:
                if is_secondary and legend_secondary:
                    should_display_legend = True
                elif not is_secondary and legend_primary:
                    should_display_legend = True
            
            if should_display_legend and not self.consolidate_legends:
                ax.legend(handles, labels, frameon=legend_frameon, loc=legend_loc)
            
            if ax.get_legend() and (self.consolidate_legends or not should_display_legend):
                ax.get_legend().remove()
            
            if not self.consolidate_legends and ax.get_label() in self.plot_kwargs_store:
                if self.plot_kwargs_store[ax.get_label()].get('kind') == 'pie':
                    if ax.get_legend():
                        ax.get_legend().remove()


def plot(df: pd.DataFrame, *args, **kwargs) -> Plotter:
    """Create a pytae Plotter pre-loaded with `df`, optionally executing a plot.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to plot.
    *args :
        Positional arguments passed to Plotter constructor (e.g. mosaic).
    **kwargs :
        Plotter constructor arguments (mosaic, figsize, aggregate, sharex, sharey)
        or .plot() parameters (kind, x, y, by, aggfunc, palette, etc.).

    Examples:
    ---------
    >>> import pytae as pt
    >>> tips = pt.sample("tips")
    >>> pt.plot(tips, kind="bar", x="day", y="total_bill", aggfunc="mean").finalize()
    """
    return df.pt.plot(*args, **kwargs)


def finalize(plotter: Plotter | None = None, **kwargs) -> Plotter:
    """Finalize layout, spines, and legends for a Plotter.

    If `plotter` is omitted, finalizes the most recently active Plotter
    instance (similar to matplotlib's ``plt.tight_layout()``).

    Parameters:
    -----------
    plotter : Plotter, optional
        The Plotter instance to finalize. If None, finalizes the last active Plotter.
    **kwargs :
        Optional keyword arguments passed directly to ``Plotter.finalize()``:
        - `consolidate_legends` (bool): Consolidate all legends into one unified figure legend.
        - `bbox_to_anchor` (tuple): Position for consolidated legend (e.g. `(0.5, -0.05)`).
        - `ncols` (int): Number of columns in consolidated legend.
        - `hide_secondary_y` (bool): Hide secondary y-axis spines/ticks.
        - `legend` (bool): Master toggle to display or hide legends.
        - `style` (bool): Apply pytae's spine and tick cleanup.

    Returns:
    --------
    Plotter
        The finalized Plotter instance.

    Examples:
    ---------
    >>> import pytae as pt
    >>> tips = pt.sample("tips")
    >>> p = pt.plot(tips, kind="bar", x="day", y="total_bill")
    >>> pt.finalize(p)
    """
    if plotter is None:
        plotter = Plotter._last_active
        if plotter is None:
            raise ValueError("No active pytae Plotter to finalize.")
    elif not isinstance(plotter, Plotter):
        raise TypeError(f"Expected a Plotter instance, got {type(plotter).__name__}")
    return plotter.finalize(**kwargs)


