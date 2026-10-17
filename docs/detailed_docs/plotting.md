# Visualization & Dashboarding with Pytae

[← Back to Master Reference](../pytae.md) | [Interactive Notebook](library/plotting.ipynb) | [CLI Guide](cli/plotting.md)

`pytae` provides a modern, fluent visualization and dashboarding system designed around a simple, powerful philosophy:

> **Compute in Polars, Visualize in Pandas.**

While **Polars** provides unmatched multithreaded SIMD vector performance for data filtering, transformation, and aggregation, **Pandas** and **Matplotlib** remain the undisputed industry standard for 2D data visualization in Python.

`pytae` bridges both worlds seamlessly: you manipulate, aggregate, and reshape your data at Polars speed, and when you call `.plot()`, `pytae` automatically converts the prepared dataset into a Pandas DataFrame and delegates directly to the rich, battle-tested `pandas.DataFrame.plot` and `matplotlib.pyplot` ecosystem.

---

## Table of Contents

1. [Core Architecture & Philosophy](#1-core-architecture--philosophy)
2. [Three Entry Points](#2-three-entry-points)
3. [Clean Separation of Concerns](#3-clean-separation-of-concerns)
4. [Supported Plot Kinds](#4-supported-plot-kinds)
   - [Bar & Column Charts (`bar`, `barh`)](#bar--column-charts-bar-barh)
   - [Trends & Time Series (`line`, `area`)](#trends--time-series-line-area)
   - [Relationships & Correlation (`scatter`, `hexbin`, `heatmap`)](#relationships--correlation-scatter-hexbin-heatmap)
   - [Distributions (`hist`, `box`, `kde` / `density`)](#distributions-hist-box-kde--density)
   - [Proportions (`pie`)](#proportions-pie)
5. [Advanced Capabilities](#5-advanced-capabilities)
   - [Secondary Y-Axis (`^` Syntax)](#secondary-y-axis--syntax)
   - [Small Multiples & Auto-Faceting (`by=`, `ncols=`)](#small-multiples--auto-faceting-by-ncols)
   - [Multi-Panel Dashboards (`Plotter` Mosaic Layouts)](#multi-panel-dashboards-plotter-mosaic-layouts)
   - [Custom Styling & Finalization (`finalize()`)](#custom-styling--finalization-finalize)
6. [Command Line Interface (CLI) Visualizations](#6-command-line-interface-cli-visualizations)
   - [In-Terminal ASCII Distribution Charts (`-freq`, `-hist`)](#in-terminal-ascii-distribution-charts--freq--hist)
   - [Headless Figure Generation (`-plot`, `-finalize`, `-o`)](#headless-figure-generation--plot--finalize--o)
7. [Installation & Requirements](#7-installation--requirements)

---

## 1. Core Architecture & Philosophy

### Why Pandas for Plotting?

Many modern DataFrame libraries attempt to invent their own proprietary plotting syntax or bundle heavy web JavaScript engines. In contrast, `pytae` leverages the existing, trusted Python data science stack:

```
┌────────────────────────────────┐
│   Source Data (Disk / Memory)  │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  Polars SIMD Execution Engine  │  ◄── Vectorized speed for filter, mutate,
│   (pt.DataFrame / .by / .agg)  │      count, arrange, pivot, join
└───────────────┬────────────────┘
                │
                │ Automatic Zero-Friction Bridge (.to_pandas())
                ▼
┌────────────────────────────────┐
│  Pandas / Matplotlib Engine    │  ◄── 100% compatibility with pandas.DataFrame.plot,
│    (Plotter / df.plot())       │      custom colormaps, styles, mosaic layouts
└────────────────────────────────┘
```

1. **Zero Learning Curve**: Every parameter from `pandas.DataFrame.plot()` (`color`, `colormap`, `alpha`, `grid`, `rot`, `stacked`, `logy`, `figsize`, `title`, etc.) is fully supported because `pandas.plot()` executes the rendering.
2. **Zero Conversion Boilerplate**: You never need to write manual `.to_pandas()` conversions before plotting. Calling `df.plot()` off a `pt.DataFrame`, `GroupedDataFrame`, or `.pt` accessor handles the handoff automatically.
3. **No In-Plot Aggregation Traps**: Libraries like Seaborn or ggplot often hide implicit aggregations (like calculating means on the fly), obscuring performance bottlenecks. `pytae` enforces a clean separation of concerns: summarize your data explicitly at Polars speed, then plot the result.

---

## 2. Three Entry Points

`pytae` offers three equivalent, ergonomic ways to create visualizations:

### 1. Fluent Method Chaining (`df.plot(...)`)
Call `.plot()` directly at the end of your data pipeline:

```python
import pytae as pt

penguins = pt.sample("penguins")

(
    penguins
    .by("species")
    .agg(avg_mass="body_mass_g:mean")
    .plot(kind="bar", x="species", y="avg_mass", title="Average Mass by Species")
    .finalize(save="avg_mass.png")
)
```

### 2. Functional API (`pt.plot(df, ...)`)
Pass any DataFrame (Pytae, Pandas, or Polars) into top-level `pt.plot()`:

```python
pt.plot(penguins, kind="scatter", x="bill_length_mm", y="bill_depth_mm", color="species")
```

### 3. Dashboard Mosaic Builder (`pt.Plotter(...)`)
Construct multi-panel dashboards combining multiple subplots on an ASCII layout:

```python
plotter = pt.Plotter("""
    AAAB
    AAAC
""", figsize=(14, 8))

plotter.data(penguins).plot(on="A", kind="scatter", x="bill_length_mm", y="body_mass_g")
plotter.data(penguins).plot(on="B", kind="box", y="body_mass_g", by="species")
plotter.data(penguins.count("species")).plot(on="C", kind="bar", x="species", y="n")
plotter.finalize(title="Comprehensive Penguin Dashboard", save="dashboard.png")
```

---

## 3. Clean Separation of Concerns

`pytae` intentionally does not perform aggregation inside plotting calls. For example, passing `aggfunc="mean"` to `.plot()` will raise an explicit `ValueError`:

```python
# ❌ INCORRECT: In-plot aggregation is rejected
df.plot(kind="bar", x="species", y="body_mass_g", aggfunc="mean")
# ValueError: Plotter does not perform aggregation. Aggregate your DataFrame first using df.pt.agg(...) or df.pt.pivot(...) before plotting.

# ✅ CORRECT: Explicit, fast Polars aggregation, followed by clean plotting
(
    df
    .by("species")
    .agg(avg_mass="body_mass_g:mean")
    .plot(kind="bar", x="species", y="avg_mass")
)
```

This design guarantees that:
- You always know the exact rows and numbers being rendered.
- You take full advantage of Polars' multithreaded SIMD aggregation engine.
- Debugging is trivial: just inspect the DataFrame right before `.plot()`.

---

## 4. Supported Plot Kinds

All standard Pandas plot kinds are natively available:

### Bar & Column Charts (`bar`, `barh`)

```python
# Single bar chart
(
    penguins
    .by("species")
    .agg(avg_mass="body_mass_g:mean")
    .plot(kind="bar", x="species", y="avg_mass", rot=0, color="#2b5c8f")
)

# Stacked horizontal bar chart using pivot
(
    penguins
    .pivot(r="species", c="island", a="count")
    .plot(kind="barh", x="species", stacked=True)
)
```

### Trends & Time Series (`line`, `area`)

```python
# Multi-line trend chart
(
    sales_df
    .by("month", "category")
    .agg(revenue="sales:sum")
    .wide(r="month", c="category", v="revenue")
    .arrange("month")
    .plot(kind="line", x="month", grid=True)
)

# Cumulative stacked area chart
sales_wide.plot(kind="area", x="month", alpha=0.7)
```

### Relationships & Correlation (`scatter`, `hexbin`, `heatmap`)

```python
# Scatter plot with custom sizing and alpha
penguins.plot(
    kind="scatter",
    x="bill_length_mm",
    y="body_mass_g",
    alpha=0.6,
    color="darkorange",
    s=50,
)

# Hexagonal binning for dense observations
diamonds = pt.sample("diamonds")
diamonds.plot(
    kind="hexbin",
    x="carat",
    y="price",
    gridsize=25,
    cmap="viridis",
)

# Correlation heatmap
(
    penguins
    .select(dtype="numeric")
    .plot(kind="heatmap", annot=True, cmap="coolwarm")
)
```

### Distributions (`hist`, `box`, `kde` / `density`)

```python
# Binned numeric histogram
penguins.plot(kind="hist", column="body_mass_g", bins=20, color="teal")

# Grouped box plots
penguins.plot(kind="box", y="body_mass_g", by="species")

# Kernel density estimation (KDE)
penguins.plot(kind="kde", column="body_mass_g")
```

### Proportions (`pie`)

```python
# Categorical frequency pie chart
(
    penguins
    .count("species")
    .plot(kind="pie", y="n", by="species", autopct="%1.1f%%")
)
```

---

## 5. Advanced Capabilities

### Secondary Y-Axis (`^` Syntax)

Plot two metrics with different magnitudes on the same chart using secondary Y-axis syntax:

```python
# Use '^' suffix on column name:
sales_summary.plot(
    kind="line",
    x="date",
    y=["revenue", "profit_margin^"],
    title="Revenue vs Margin",
)

# Or pass secondary_y explicitly:
sales_summary.plot(
    kind="line",
    x="date",
    y=["revenue", "profit_margin"],
    secondary_y=["profit_margin"],
)
```

### Small Multiples & Auto-Faceting (`by=`, `ncols=`)

Generate small-multiple grid subplots split across categorical groupings:

```python
# Facet scatter plots by island across 3 columns:
pt.plot(
    penguins,
    by="island",
    ncols=3,
    kind="scatter",
    x="bill_length_mm",
    y="bill_depth_mm",
    figsize=(12, 4),
)
```

### Multi-Panel Dashboards (`Plotter` Mosaic Layouts)

`pt.Plotter` lets you compose complex, publication-grade analytical dashboards using intuitive ASCII character layouts:

```python
dashboard = pt.Plotter("""
    AABB
    AACC
    DDDD
""", figsize=(14, 10))

# Panel A: Main Scatter Relationship
dashboard.data(penguins).plot(
    on="A",
    kind="scatter",
    x="bill_length_mm",
    y="body_mass_g",
    title="Bill Length vs Body Mass",
)

# Panel B: Species Mass Distribution (Box Plot)
dashboard.data(penguins).plot(
    on="B",
    kind="box",
    y="body_mass_g",
    by="species",
    title="Body Mass by Species",
)

# Panel C: Species Headcount (Bar Chart)
dashboard.data(penguins.count("species")).plot(
    on="C",
    kind="bar",
    x="species",
    y="n",
    rot=0,
    title="Species Population",
)

# Panel D: Flipper Length Distribution (Histogram)
dashboard.data(penguins).plot(
    on="D",
    kind="hist",
    column="flipper_length_mm",
    bins=25,
    title="Flipper Length Histogram",
)

# Finalize dashboard styling and export
dashboard.finalize(
    title="Palmer Penguins Comprehensive Analysis",
    tight_layout=True,
    save="penguins_dashboard.png",
    dpi=300,
)
```

### Custom Styling & Finalization (`finalize()`)

`finalize()` provides high-level control over the figure aesthetics:

```python
plot.finalize(
    title="Quarterly Performance",
    xlabel="Fiscal Quarter",
    ylabel="Revenue ($M)",
    style="seaborn-v0_8-whitegrid",  # Any Matplotlib style sheet
    grid=True,
    save="quarterly_report.svg",      # Automatic vector/raster export
    dpi=300,
    show=True,
)
```

---

## 6. Command Line Interface (CLI) Visualizations

Visualizations are fully integrated into the `pytae` Unix command line tool:

### In-Terminal ASCII Distribution Charts (`-freq`, `-hist`)

Inspect distributions immediately inside your console scrollback without opening external windows:

```bash
# 1. Categorical distribution bar chart
pytae penguins.parquet -freq species
```
```text
species    count
Adelie       152  ████████████████████ (44.2%)
Gentoo       124  ████████████████     (36.0%)
Chinstrap     68  █████████            (19.8%)
```

```bash
# 2. Binned numeric distribution histogram
pytae penguins.parquet -hist body_mass_g:8
```
```text
body_mass_g          count
[2700.0, 3150.0)        31  ████
[3150.0, 3600.0)        80  ██████████
[3600.0, 4050.0)        87  ███████████
[4050.0, 4500.0)        44  █████
[4500.0, 4950.0)        36  ████
[4950.0, 5400.0)        41  █████
[5400.0, 5850.0)        21  ██
[5850.0, 6300.0]         4  █
```

### Headless Figure Generation (`-plot`, `-finalize`, `-o`)

Render publication-grade PNG, SVG, or PDF figures headlessly on remote servers, in CI/CD pipelines, or in automated scripts:

```bash
# Filter, aggregate with Polars, plot with Pandas/Matplotlib, and export to PNG:
pytae penguins.parquet \
  -filter "body_mass_g > 3000" \
  -by species \
  -agg "avg_mass = body_mass_g:mean" \
  -plot "kind=bar, x=species, y=avg_mass, color='#2b5c8f'" \
  -finalize "title='Average Mass by Species', rot=0" \
  -o species_mass.png
```

---

## 7. Installation & Requirements

The core `pytae` package has zero GUI dependencies. To enable plotting, install the optional `plot` extra:

```bash
pip install "pytae[plot]"
```

This installs `matplotlib`, unlocking all plotting capabilities across both the Python library and CLI.

