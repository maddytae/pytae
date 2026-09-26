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
   - `.data(df)`: Sets the working DataFrame for subsequent plots.
   - `.plot(...)`: Draws a chart on the active or specified subplot axis.
   - `.finalize(...)`: Formats legends, tightens layout, and produces the completed figure.
2. **Context Memory**: Consecutive `.plot()` calls remember previous parameters (such as `x=`, `by=`, or `aggfunc=`) unless explicitly changed, making multi-series and secondary-axis plots clean and concise.
3. **Dual Entry Points**:
   - `pt.Plotter(mosaic=..., figsize=...)`: Primary class for flexible single-panel or multi-panel dashboards.
   - `pt.Plotter.facet(df, by=..., ...)`: Convenient one-liner for small multiples.

---

<a id="capabilities"></a>
## Key Capabilities & Syntax

<a id="single-plots"></a>
### 1. Single Plots with Auto-Aggregation

Specify `by=` and `aggfunc=` to group and aggregate data automatically without manual `groupby()` or `pivot_table()` preprocessing:

```python
import pytae as pt

tips = pt.sample("tips")

k = pt.Plotter(figsize=(8, 5))
(
    k
    .data(tips)
    .plot(kind="bar", x="day", y="total_bill", by="sex", aggfunc="mean",
          title="Average Bill by Day and Sex")
    .finalize()
)
```

**Supported Plot Kinds**: `bar`, `barh`, `line`, `scatter`, `pie`, `hist`, `box`, `kde` / `density`, `area`.

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

<a id="mosaic-dashboards"></a>
### 3. Multi-Panel Mosaic Dashboards

Define complex dashboard layouts using ASCII string diagrams or lists of lists. Each panel letter corresponds to an axis name (`on='A'`, `on='B'`, etc.). Mix different datasets and plot kinds freely across panels:

```python
titanic = pt.sample("titanic")

mosaic = """
AB
CD
"""

p = pt.Plotter(mosaic=mosaic, figsize=(12, 8))
(
    p
    .data(titanic)
    .plot(on="A", kind="bar", x="pclass", y="survived", aggfunc="mean", title="Survival by Class")
    .plot(on="B", kind="bar", x="sex", y="survived", aggfunc="mean", title="Survival by Sex")
    .plot(on="C", kind="hist", column="age", by="alive", bins=20, alpha=0.6, title="Age Distribution")
    .plot(on="D", kind="kde", column="fare", by="class", title="Fare Density")
    .finalize(consolidate_legends=True)
)
```

---

<a id="faceting"></a>
### 4. Grid Faceting / Small Multiples (`Plotter.facet`)

Split a dataset across an automated grid of subplots for each distinct level of a categorical column with a single function call:

```python
penguins = pt.sample("penguins")

# Facet scatter plots by species across 2 columns
pt.Plotter.facet(
    penguins,
    by="species",
    ncols=2,
    x="bill_length_mm",
    y="bill_depth_mm",
    kind="scatter",
    title="Bill Dimensions by Species"
)
```

---

<a id="fine-tuning"></a>
### 5. Fine-Tuning & Matplotlib Customization

Access underlying Matplotlib `Figure` (`k.fig`) and `Axes` dictionary (`k.axd["A"]`) directly for full programmatic styling, reference lines, custom tick formatting, or looping across all subplots:

```python
k = pt.Plotter(mosaic="AB", figsize=(10, 4))
(
    k
    .data(penguins)
    .plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm")
    .plot(on="B", kind="hist", column="body_mass_g", bins=20)
)

# Direct axis customization prior to finalization
k.axd["A"].axhline(18, color="red", linestyle="--", label="Threshold")
k.axd["A"].grid(True, linestyle=":", alpha=0.6)

k.finalize(tight_layout=True)
```

---

<a id="notebooks"></a>
## Interactive Notebook Guides

For full executable code, rich rendered visualizations, and advanced styling recipes, explore the dedicated notebooks in [`docs/plotting/`](plotting/):

- **[Core Plotting Guide (`plotting/plotter.ipynb`)](plotting/plotter.ipynb)**:
  Comprehensive walkthrough of every plot kind, automatic group color schemes, secondary axes, faceting variations, legend consolidation, and post-plot fine-tuning.
- **[Advanced Dashboards & Recipes (`plotting/more_plots.ipynb`)](plotting/more_plots.ipynb)**:
  Multi-panel analytical dashboards (Titanic, Diamonds, FMRI), dual-scale time series, multi-dataset compositions, and custom matplotlib styling patterns.

---

<a id="cheat-sheet"></a>
## Quick Reference Cheat Sheet

| Goal | Syntax / Method | Notes |
|---|---|---|
| **Grouped aggregation** | `.plot(..., by="category", aggfunc="mean")` | Defaults to `"sum"`; no prior `groupby` required |
| **Secondary Y-axis** | `.plot(..., on="A^")` | Overlays on panel `'A'` sharing x-axis |
| **Hide secondary Y spine/ticks** | `.finalize(hide_secondary_y=True)` | Clean appearance when using secondary axis for scaling |
| **Consolidate legends** | `.finalize(consolidate_legends=True, ncols=3)` | Merges all panel legends into one unified legend |
| **Mosaic multi-panel** | `pt.Plotter("AB\nCD", figsize=(10, 8))` | Layout defined via ASCII characters |
| **Grid faceting** | `pt.Plotter.facet(df, by="group", ncols=3, ...)` | Auto-sizes grid and leaves leftover cells blank |
| **Access raw figure/axes** | `k.fig`, `k.axd["A"]` | Standard Matplotlib objects |
