# CLI Feature Guide: Visualizations & In-Line Charts

[← Back to CLI Reference Hub](../cli.md)

`pytae` includes first-class visualization capabilities directly from the command line:
- **Terminal In-Line Visualizations**: Instant ASCII frequency bars (`-freq`) and numeric distribution histograms (`-hist`) rendered directly in console scrollback.
- **Headless Figure Plotting**: Full Matplotlib publication-grade plotting via `-plot` and `-finalize`, with automatic figure export (`-o plot.png`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Terminal Frequency Distribution (`-freq`)](#terminal-frequency-distribution--freq)
- [Terminal Numeric Histograms (`-hist`)](#terminal-numeric-histograms--hist)
- [Headless Figure Plotting (`-plot` & `-finalize`)](#headless-figure-plotting--plot--finalize)
  - [1. Single Plots with Explicit Pipeline Aggregation](#1-single-plots-with-explicit-pipeline-aggregation)
  - [2. Multi-Dimensional Categorical Grouping (`by=`)](#2-multi-dimensional-categorical-grouping-by)
  - [3. Distribution Plots (`box`, `kde`, `hist`)](#3-distribution-plots-box-kde-hist)
  - [4. Custom Styling & Finalization (`-finalize`)](#4-custom-styling--finalization--finalize)
  - [5. Exporting Figures (`-o`)](#5-exporting-figures--o)
- [Interactive Viewing](#interactive-viewing)

---

## Overview & Quick Reference

| Flag | Category | Purpose | Example |
|---|---|---|---|
| `-freq COL` | Terminal ASCII | Categorical distribution bar chart | `pytae penguins.parquet -freq species` |
| `-hist COL[:BINS]` | Terminal ASCII | Numeric binned distribution histogram | `pytae penguins.parquet -hist body_mass_g:8` |
| `-plot SPEC` | Figure Plot | Draw bar, line, scatter, box, area, kde | `pytae data.csv -plot "kind=bar,x=cat,y=val"` |
| `-finalize SPEC` | Figure Style | Title, axis labels, styles, tight layout | `pytae data.csv -finalize "title='Sales',style=dark_background"` |
| `-o TARGET.ext` | Export | Save figure to PNG, SVG, PDF, etc. | `-o chart.png -out_dir ./figures` |

---

## Terminal Frequency Distribution (`-freq`)

Render instant ASCII horizontal bars with exact counts and percentages for any categorical column:

```bash
pytae penguins.parquet -freq species
```

**Output:**
```text
species    count
Adelie       152  ████████████████████ (44.2%)
Gentoo       124  ████████████████     (36.0%)
Chinstrap     68  █████████            (19.8%)
```

Respects `-dropna` (defaults to `false` to retain NA; set `true` to exclude):
```bash
pytae penguins.parquet -freq sex -dropna true
```

---

## Terminal Numeric Histograms (`-hist`)

Inspect numeric distributions, spreads, and peaks directly in your console:

```bash
pytae penguins.parquet -hist body_mass_g:6
```

**Output:**
```text
body_mass_g            count
[2700.0, 3300.0)          63  ████████████
[3300.0, 3900.0)         105  ████████████████████
[3900.0, 4500.0)          69  █████████████
[4500.0, 5100.0)          57  ███████████
[5100.0, 5700.0)          40  ████████
[5700.0, 6300.0]           8  ██
```

- If bins count is omitted (`-hist body_mass_g`), defaults to 10 bins.
- Automatically handles missing values and filters out non-numeric rows.

---

## Headless Figure Plotting (`-plot` & `-finalize`)

`-plot` connects `pytae`'s visualization engine (`Plotter`) directly to the command line. Any pipeline can end with a plot and route directly to disk or interactive screen.

### 1. Single Plots with Explicit Pipeline Aggregation

Filter, aggregate, and plot in one pipeline:

```bash
pytae penguins.parquet \
  -by species \
  -agg "avg_mass=body_mass_g:mean" \
  -plot "kind=bar, x=species, y=avg_mass" \
  -finalize "title='Average Body Mass by Species', ylabel='Mass (g)'" \
  -o avg_mass.png
```

### 2. Multi-Dimensional Categorical Grouping (`by=`)

Produce multi-series bar or scatter plots with automated color mapping:

```bash
pytae penguins.parquet \
  -filter "sex = ('notna',)" \
  -plot "kind=scatter, x=bill_length_mm, y=body_mass_g, by=species" \
  -finalize "title='Bill Length vs Body Mass', tight_layout=true" \
  -o scatter.png
```

### 3. Distribution Plots (`box`, `kde`, `hist`)

Visualise unaggregated distributions grouped by category:

```bash
pytae penguins.parquet \
  -plot "kind=box, x=species, y=flipper_length_mm" \
  -finalize "title='Flipper Length Distribution by Species'" \
  -o flipper_box.png
```

### 4. Custom Styling & Finalization (`-finalize`)

Pass any figure-level customization keys to `-finalize`:

```bash
pytae tips.parquet \
  -by day -agg "avg_bill=total_bill:mean" \
  -plot "kind=bar, x=day, y=avg_bill" \
  -finalize "title='Average Bill by Day', style=seaborn-v0_8-whitegrid, xlabel='Day of Week', ylabel='Average Bill ($)'" \
  -o daily_bill.svg
```

Supported `-finalize` keys:
- `title='...'`: Figure or chart title
- `xlabel='...'`, `ylabel='...'`: Axis labels
- `style='...'`: Matplotlib style sheet (e.g. `seaborn-v0_8-whitegrid`, `dark_background`)
- `tight_layout=true`: Apply tight bounding box
- `sharex=true`, `sharey=true`: Link axis scales across subplots

### 5. Exporting Figures (`-o`)

When `-o` specifies an image extension (`.png`, `.svg`, `.pdf`, `.jpg`, `.jpeg`), `pytae` automatically switches to the non-interactive Matplotlib backend (`Agg`) and saves the figure directly to the destination:

```bash
# Save to current working directory
pytae data.parquet -plot "kind=bar,x=cat,y=val" -o chart.png

# Save to dedicated output directory (created automatically if missing)
pytae data.parquet -plot "kind=bar,x=cat,y=val" -o chart.png -od ./reports/figures
```

---

## Interactive Viewing

If `-o` is omitted and the output is not redirected, `pytae` invokes `plt.show()` so you can inspect charts interactively in a desktop window:

```bash
pytae penguins.parquet -plot "kind=scatter, x=bill_length_mm, y=body_mass_g, by=species"
```
