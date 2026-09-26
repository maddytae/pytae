# pytae — Plotting Reference (`Plotter`)

[← Back to Library Hub](library.md)

`Plotter` is a method-chainable visualization engine built on top of `pandas.plot()` and Matplotlib. It eliminates plotting boilerplate by providing automatic aggregations, intelligent color mapping, secondary Y-axis overlays, arbitrary multi-panel mosaic layouts, and grid faceting—all with a unified, fluent API.

Requires the plotting extra:
```bash
pip install "pytae[plot]"
```

---

## Contents

- [Core Architecture & Execution Model](#architecture)
- [Key Capabilities & Syntax](#capabilities)
  - [1. Single Plots with Auto-Aggregation](#single-plots)
  - [2. Secondary Y-Axis Overlays (`on='A^'`)](#secondary-axis)
  - [3. Multi-Panel Mosaic Dashboards](#mosaic-dashboards)
  - [4. Grid Faceting / Small Multiples (`Plotter.facet`)](#faceting)
  - [5. Fine-Tuning & Matplotlib Customization](#fine-tuning)
- [Interactive Notebook Guides](#notebooks)
- [Quick Reference Cheat Sheet](#cheat-sheet)

---

<a id="architecture"></a>
## Core Architecture & Execution Model

1. **Fluent Pipeline**: Chain `.data()` → `.plot()` → `.plot()` → `.finalize()`:
   - `df.pt.plot(...)` or `Plotter(df)`: Creates a plotter pre-loaded with data.
   - `.data(df)`: Dynamically sets or switches the working DataFrame for subsequent plots.
   - `.plot(...)`: Draws a chart on the active or specified subplot axis.
   - `.finalize(...)`: Formats legends, tightens layout, and produces the completed figure.
   - **Auto-Display**: In Jupyter notebooks, `Plotter` implements `_repr_png_()` so figures render directly without requiring `p.fig`.
2. **Context Memory**: Consecutive `.plot()` calls remember previous parameters (such as `x=`, `by=`, or `aggfunc=`) unless explicitly changed, making multi-series and secondary-axis plots clean and concise.
3. **Versatile Entry Points**:
   - `df.pt.plot(...)`: Direct DataFrame accessor chaining from data-wrangling verbs.
   - `pt.plot(df, ...)` & `pt.finalize([p])`: Standalone functional interface for procedural workflows.
   - `pt.Plotter(df, mosaic=..., figsize=...)`: Flexible multi-panel mosaic dashboards.
   - `pt.Plotter.facet(df, by=..., ...)`: Convenient one-liner for small multiples with optional `sharex=True` / `sharey=True`.

---

<a id="capabilities"></a>
## Key Capabilities & Syntax

<a id="single-plots"></a>
### 1. Single Plots & Direct Accessor Chaining

Specify `by=` and `aggfunc=` to group and aggregate data automatically without manual `groupby()` or `pivot_table()` preprocessing. You can chain directly from `df.pt.plot(...)`:

```python
import pandas as pd
import pytae as pt

tips = pt.sample("tips")
penguins = pt.sample("penguins")

# Direct accessor one-liner:
tips.pt.plot(kind="bar", x="day", y="total_bill", by="sex", aggfunc="mean",
             palette="tab10", title="Average Bill by Day and Sex").pt.finalize()

# Or functional style with pt.plot and pt.finalize:
p = pt.plot(tips, kind="scatter", x="total_bill", y="tip", c="day", title="Bill vs Tip")
pt.finalize(p)
```

**Supported Plot Kinds**: `bar`, `barh`, `line`, `scatter`, `pie`, `hist`, `box`, `kde` / `density`, `area`, `heatmap`.

---


<a id="secondary-axis"></a>
### 2. Secondary Y-Axis Overlays (`on='A^'`)

Append `^` to an axis identifier (e.g. `on="A^"`) to plot on an independent secondary Y-axis that shares the same X-axis. Combine with `consolidate_legends=True` to merge legends from both axes into a single box:

```python
k = pt.Plotter(figsize=(8, 5))
(
    k
    .data(tips)
    .plot(kind="bar", x="day", y="total_bill", aggfunc="mean", legend=False,
          title="Average Bill (Bars) vs Average Tip (Line)")
    .plot(kind="line", x="day", y="tip", aggfunc="mean", on="A^", color="crimson", marker="o")
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.15), ncols=2)
)
```

---

### 3. Subplots & Multi-Panel Dashboards

#### Subplots Without Mosaic (`nrows`, `ncols`)

To create multiple subplots without specifying an ASCII mosaic string, use standard `nrows` and `ncols`. Panels are automatically assigned keys `'A'`, `'B'`, `'C'`, etc.:

```python
# Side-by-side subplots without mosaic:
p = pt.Plotter(tips, nrows=1, ncols=2, figsize=(11, 4.5))
(
    p
    .plot(on="A", kind="bar", x="day", y="total_bill", aggfunc="mean", palette="tab10", title="Mean Bill by Day")
    .plot(on="B", kind="scatter", x="total_bill", y="tip", c="day", cmap="viridis", title="Bill vs Tip")
    .finalize()
)
```

#### Mosaic Dashboards (ASCII Layouts)

Define complex dashboard layouts using ASCII string diagrams or lists of lists. Each panel letter corresponds to an axis name (`on='A'`, `on='B'`, etc.). Mix different datasets and plot kinds freely across panels:

```python
titanic = pt.sample("titanic")

mosaic = """
AB
CD
"""

p = pt.Plotter(titanic, mosaic=mosaic, figsize=(12, 8))
(
    p
    .plot(on="A", kind="bar", x="pclass", y="survived", aggfunc="mean", title="Survival by Class")
    .plot(on="B", kind="bar", x="sex", y="survived", aggfunc="mean", title="Survival by Sex")
    .plot(on="C", kind="hist", column="age", by="alive", bins=20, alpha=0.6, title="Age Distribution")
    .plot(on="D", kind="kde", column="fare", by="class", title="Fare Density")
    .finalize(consolidate_legends=True)
)
```

#### Mixing pandas & pytae in a Continuous Pipeline

You can seamlessly mix standard pandas methods (`.dropna()`, `.rename()`, `.sort_values()`, `.query()`) with `pytae` verbs (`.pt.mutate()`, `.pt.qry()`, `.pt.select()`) in a single chained pipeline that ends directly in a mosaic dashboard:

```python
# Continuous chain: pandas wrangling + pytae verbs + multi-panel mosaic
(
    penguins
    .dropna(subset=["bill_length_mm", "bill_depth_mm", "body_mass_g"])       # pandas
    .pt.mutate(bill_ratio="bill_length_mm / bill_depth_mm", mass_kg="body_mass_g / 1000") # pytae
    .pt.qry("mass_kg > 3.0")                                                 # pytae
    .sort_values("body_mass_g", ascending=False)                             # pandas
    .pt.plot(                                                                # pytae mosaic
        mosaic="""
        AB
        CD
        """,
        figsize=(13, 9)
    )
    .plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species", palette="Set1", title="Bill Dimensions")
    .plot(on="B", kind="box", x="species", y="body_mass_g", title="Body Mass Distribution")
    .plot(on="C", kind="bar", x="species", y="bill_ratio", aggfunc="mean", palette="tab10", title="Mean Bill Ratio")
    .plot(on="D", kind="kde", x="body_mass_g", by="species", title="Body Mass Density")
    .finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.05), ncols=3)
)
```


---

<a id="faceting"></a>
### 4. Grid Faceting / Small Multiples (Auto-Faceting with `by` & `ncols`)

Split a dataset across an automated grid of subplots for each distinct level of a categorical column.

`pytae` automatically recognizes when faceting is needed whenever `by=` and `ncols=` are passed to `pt.plot(...)`, `df.pt.plot(...)`, or `pt.Plotter(...)`—you do **not** need to remember a separate `pt.Plotter.facet` class method (though `pt.Plotter.facet` is still fully supported as an explicit alias):

```python
penguins = pt.sample("penguins")

# 1. Standalone auto-faceting: pt.plot with by and ncols
pt.plot(
    penguins,
    by="species",
    ncols=3,
    x="bill_length_mm",
    y="bill_depth_mm",
    kind="scatter",
    sharex=True,
    sharey=True,
    title="Bill Dimensions by Species"
).finalize()

# 2. Direct accessor auto-faceting in a pipeline
(
    penguins
    .pt.plot(
        by="species",
        ncols=3,
        x="bill_length_mm",
        y="bill_depth_mm",
        kind="scatter",
        sharex=True,
        sharey=True
    )
    .pt.finalize()
)
```

---

<a id="fine-tuning"></a>
### 5. Advanced Controls & Inspection (`_CONTROL_KWARGS`)

`Plotter` accepts 10 pytae-only control keyword arguments that configure plot behavior directly before delegating to Matplotlib:

| Control Kwarg | Type / Values | Description |
|---|---|---|
| `on` | `str` (`'A'`, `'B'`, `'A^'`) | Routes plot to a specific mosaic panel or secondary axis |
| `print_data` | `bool` | Prints the post-aggregated/pivoted DataFrame to stdout |
| `clip_data` | `bool` | Copies the post-aggregated DataFrame to system clipboard |
| `secondary_y` | `bool` | Routes to secondary Y-axis (equivalent to `on='A^'`) |
| `aggregate` | `bool` (default `True`) | Controls pre-aggregation; set `False` for wide/raw data |
| `xlabel` | `str` | Custom X-axis label override |
| `ylabel` | `str` | Custom Y-axis label override |
| `palette` | `str` (e.g. `'tab10'`, `'Set2'`) | Built-in colormap for discrete categories |
| `annot` | `bool` | Annotates heatmap cells with numeric values |
| `fmt` | `str` (e.g. `'.2f'`, `'.1f'`) | Format string specifier for heatmap annotations |

```python
# 1. Print & copy plotted data with custom axis labels and secondary Y-axis
(
    tips
    .pt.plot(
        kind="bar",
        x="day",
        y="total_bill",
        aggfunc="mean",
        palette="tab10",
        xlabel="Day of Week",
        ylabel="Mean Total Bill ($)",
        title="Average Bill by Day",
        print_data=True,  # Prints exact aggregated DataFrame to stdout
        clip_data=True,   # Copies aggregated DataFrame to clipboard
    )
    .plot(
        kind="line",
        x="day",
        y="tip",
        aggfunc="mean",
        secondary_y=True, # Automatically routes to secondary Y-axis (A^)
        color="crimson",
        ylabel="Mean Tip ($)",
    )
    .pt.finalize(consolidate_legends=True, bbox_to_anchor=(0.5, -0.15), ncols=2)
)

# 2. Distribution box plot (unaggregated true quartiles)
pt.Plotter(penguins).plot(kind="box", x="species", y="body_mass_g").finalize()

# 3. Correlation heatmap with annot=True and fmt='.2f'
corr = penguins.select_dtypes("number").corr()
pt.Plotter(corr).plot(kind="heatmap", annot=True, fmt=".2f", cmap="coolwarm").finalize()

# 4. Wide-format plotting without pre-aggregation (aggregate=False)
pre_agg = pd.DataFrame({"quarter": ["Q1", "Q2"], "rev": [100, 200]})
pre_agg.pt.plot(kind="bar", x="quarter", y="rev", aggregate=False).pt.finalize()
```

---

<a id="post-plot-manipulation"></a>
### 6. Post-Plot Manipulation Across Subplots in a `for` Loop

Every `Plotter` instance stores its underlying Matplotlib `Axes` in the `p.axd` dictionary (mapping panel identifiers like `'A'`, `'B'`—or category names when using `.facet()`—to their respective `Axes` objects).

You can loop over `p.axd.items()` to apply batch styling, custom grids, title decorations, or axis limits across all subplots, and still target individual panels for specific annotations:

```python
p = pt.Plotter(tips, nrows=1, ncols=2, figsize=(11, 4.5))
(
    p
    .plot(on="A", kind="bar", x="day", y="total_bill", aggfunc="mean", palette="tab10", title="Mean Bill by Day")
    .plot(on="B", kind="scatter", x="total_bill", y="tip", c="day", cmap="viridis", title="Bill vs Tip")
    .finalize()
)

# Loop over all subplots via p.axd for fine-grained Matplotlib controls
for key, ax in p.axd.items():
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.set_title(f"[{key}] {ax.get_title()}", fontsize=11, fontweight="bold", pad=8)
    ax.tick_params(axis="both", labelsize=9)

# Subplot-specific custom annotation on panel 'B'
p.axd["B"].axhline(3.0, color="crimson", linestyle="--", linewidth=1.2, label=r"Tip Ref ($3)")
p.axd["B"].legend(loc="upper left", frameon=True, fontsize=8)

p.fig
```

---

<a id="notebooks"></a>
## Interactive Notebook Guide

For full executable code, rich rendered visualizations, and advanced styling recipes, explore the consolidated progressive notebook:

- **[Interactive Plotting Guide (`plotting/plotter.ipynb`)](plotting/plotter.ipynb)**:
  A structured, progressive walkthrough building from basic one-liner entry points (`df.pt.plot`, `pt.plot`, `Plotter`) through plot kinds, secondary Y-axes, multi-panel mosaic dashboards, small-multiples faceting, end-to-end mixed pandas/pytae pipelines, batch post-plot manipulation in a `for` loop, and direct Matplotlib fine-tuning.

---

<a id="cheat-sheet"></a>
## Quick Reference Cheat Sheet

| Goal | Syntax / Method | Notes |
|---|---|---|
| **Direct accessor** | `df.pt.plot(...).pt.finalize()` | Unified `.pt` namespace from wrangling through plot completion |
| **Constructor with data** | `pt.Plotter(df, mosaic="AB")` | Pre-loads DataFrame into instance |
| **Grouped aggregation** | `.plot(..., by="category", aggfunc="mean")` | Defaults to `"sum"`; no prior `groupby` required |
| **Categorical scatter** | `.plot(kind="scatter", x=..., y=..., by="category")` | Groups points with discrete labels and colors |
| **Unaggregated box plot** | `.plot(kind="box", x="cat", y="val")` | Preserves individual observations per group |
| **Matrix heatmap** | `.plot(kind="heatmap", annot=True)` | Annotates numeric matrices or pivot tables |
| **Built-in palette** | `.plot(..., palette="tab10")` | Auto-assigns discrete colors to categories |
| **Custom axis labels** | `.plot(..., xlabel="X", ylabel="Y")` | Clean axis labels without manual matplotlib calls |
| **Secondary Y-axis** | `.plot(..., on="A^")` | Overlays on panel `'A'` sharing x-axis |
| **Hide secondary Y spine/ticks** | `.finalize(hide_secondary_y=True)` | Clean appearance when using secondary axis for scaling |
| **Consolidate legends** | `.finalize(consolidate_legends=True, ncols=3)` | Merges all panel legends into one unified legend |
| **Mosaic multi-panel** | `pt.Plotter(df, "AB\nCD", figsize=(10, 8))` | Layout defined via ASCII characters |
| **Subplots without mosaic** | `pt.Plotter(df, nrows=1, ncols=2)` | Auto-assigns panel keys `'A'`, `'B'`, etc. |
| **Grid faceting** | `pt.plot(df, by="grp", ncols=3, ...)` or `.facet(...)` | Auto-facets when `by` and `ncols` are present |
| **Retrieve plotted table** | `k.get_data("A")` or `k.tables["A"]` | Access post-aggregated table sent to Matplotlib |
| **Access raw figure/axes** | `k.fig`, `k.axd["A"]` | Standard Matplotlib objects |
| **Iterate subplots in loop** | `for key, ax in p.axd.items():` | Batch Matplotlib styling across all subplots |
| **Functional finalize** | `pt.finalize(p)` or `pt.finalize()` | Finalizes explicit or active Plotter (like `plt.tight_layout()`) |

