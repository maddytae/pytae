# CLI Feature Guide: CLI Plotting & Visualizations (`cli_plots`)

[← Back to Master Reference](../../pytae.md)

`pytae` includes first-class visualization and plotting capabilities directly from the command line:
- **Terminal In-Line Visualizations**: Instant ASCII and Braille charts rendered directly in console scrollback (`-freq`, `-hist`, `-bar`, `-scatter`, `-corr`).
- **Command-Line Figure Plotting**: Full Matplotlib publication-grade plotting directly from CLI pipelines via `-plot` and `-finalize`, with automatic figure export (`-o plot.png`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Terminal Frequency Distribution (`-freq`)](#terminal-frequency-distribution--freq)
- [Terminal Numeric Histograms (`-hist`)](#terminal-numeric-histograms--hist)
- [Terminal Metric Value Bars (`-bar`)](#terminal-metric-value-bars--bar)
- [Terminal 2D Braille Scatter Plot (`-scatter`)](#terminal-2d-braille-scatter-plot--scatter)
- [Terminal Correlation Matrix & Pairs (`-corr`)](#terminal-correlation-matrix--pairs--corr)
- [Headless Figure Plotting](#headless-figure-plotting)
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
| `-bar [SPEC]` | Terminal ASCII | Metric value magnitude bars across categories | `pytae penguins.parquet -by island -agg avg=mass:mean -bar` |
| `-scatter [SPEC]` | Terminal Braille | 2D in-terminal high-res bivariate scatter plot | `pytae penguins.parquet -scatter "bill_len:bill_depth"` |
| `-corr [SPEC]` | Terminal ASCII | Pairwise correlation matrix or ranked pairs | `pytae penguins.parquet -corr pairs` |
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

Respects `-dropna` (excludes missing categories from the count and distribution):
```bash
pytae penguins.parquet -dropna sex -freq sex
```

**Output:**
```text
   sex  Count                 Distribution
  Male    168 ████████████████████ (50.5%)
Female    165 ████████████████████ (49.5%)
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

## Terminal Metric Value Bars (`-bar`)

While `-freq` visualizes row counts, `-bar` visualizes **pre-aggregated metric values** (such as averages, sums, or calculated ratios) directly in your terminal table.

### 1. Bare `-bar` with 2 Columns (Auto-detect)
When grouping and aggregating down to 2 columns (1 numeric, 1 non-numeric), bare `-bar` automatically targets the value:
```bash
pytae penguins.parquet -by island -agg avg_mass=body_mass_g:mean -bar
```

**Output:**
```text
┌───────────┬─────────────┬──────────────────────┐
│ island    ┆ avg_mass    ┆ Bar                  │
╞═══════════╪═════════════╪══════════════════════╡
│ Biscoe    ┆ 4716.017964 ┆ ████████████████████ │
│ Dream     ┆ 3712.903226 ┆ ████████████████     │
│ Torgersen ┆ 3706.372549 ┆ ████████████████     │
└───────────┴─────────────┴──────────────────────┘
```

### 2. Multi-Column Tables (Preserves Metadata)
Target a specific value column while preserving other grouping dimensions:
```bash
pytae penguins.parquet -by species,island -agg avg_mass=body_mass_g:mean -bar avg_mass
```

### 3. Percentages & Custom Bounds
Append percentage of total (`pct=true`) or set custom bounds (`limit=(min,max)`):
```bash
pytae penguins.parquet -by island -agg avg_mass=body_mass_g:mean -bar "pct=true"
pytae data.csv -bar "island:avg_mass,limit=(3000,5000),width=30"
```

---

## Terminal 2D Braille Scatter Plot (`-scatter`)

Inspect bivariate correlation, non-linear trends, and outliers directly inside your terminal using high-resolution Unicode Braille characters (2×4 subpixels per character cell):

```bash
pytae penguins.parquet -scatter "bill_length_mm:bill_depth_mm"
```

**Output:**
```text
 bill_depth_mm
    21.5 ┤     ⠠      ⠠⠠   ⠠ ⠄      ⠁                        
         │          ⡀  ⠠⠂    ⠐                ⠐   ⠈          
         │           ⡤ ⠄ ⠐ ⠌⠐      ⠁     ⢀ ⠠ ⢀⠁ ⡄⢀   ⢀       
         │      ⠄ ⠠⡀⢄  ⠐    ⠤⠄  ⠈  ⠄     ⠆ ⠄⠇ ⠠              
         │   ⠐  ⠠⠈ ⠄⠨⡀⠑⣄⠬⠄⠦⠃ ⠁⠘   ⢀⠠⠄     ⠂⢠⠘⢜⠐⠄             
         │    ⢀⡂  ⠂⠊⡐⣍ ⠈⡐⠐⠑⡹ ⠂⠖⢀    ⡈ ⠠  ⢀⢈ ⠒⢀⢀              
         │      ⠂⠁⠊⠂⠂⢀⠐⡂⠶⠈⠂⡀⠁ ⡀ ⠈ ⠐ ⠐⠂     ⠂⠐            ⠐   
    17.3 ┤    ⠄⠠ ⡁⢦ ⢀⢆⢠⠅⠅⢠⡄⠁ ⠐   ⠂ ⡢⠁⠐  ⠈ ⠐ ⠐  ⡄     ⢀      ⢀
         │       ⠡⠠⢈⠂⢀  ⠂ ⠰  ⠐⠠   ⢠  ⡠⠐⢀  ⠐  ⡀               
         │  ⠐   ⢀⠂⠂  ⠄               ⠂  ⠡⠂⢢⡃⡀⠉      ⠄        
         │ ⠄                     ⠁⠌ ⠘⡄⡄⠐⠈⠈⠁⣈⠈  ⠐ ⠁⠈          
         │                  ⡀  ⠈ ⡀⢀⠂⢕ ⠐⠊⠘⢘⠐⠃⠃                
         │                    ⡐⢂ ⠄⠊⢊⡒⡌⢘⠠⢃⠐ ⠠ ⢀               
         │                ⠠  ⠠⠄⠑⡂ ⠤⠆  ⠌                      
    13.1 ┤                  ⠈ ⡀⠁  ⠂ ⠌                        
         ┼──────────────────────────────────────────────────
          32.1                   45.9                   59.6  bill_length_mm

  Points: 342 (2 nulls excluded) | Corr (r): -0.235
```

- **Bare `-scatter`**: If the table contains exactly 2 numeric columns (e.g. after `-select "x,y"`), bare `-scatter` auto-selects them!
- Custom dimensions: `-scatter "x:y,width=60,height=20"`.

---

## Terminal Correlation Matrix & Pairs (`-corr`)

Compute Pearson or Spearman correlation coefficients across numeric columns with pairwise null handling:

### 1. Symmetric Correlation Matrix (Default)
```bash
pytae penguins.parquet -select "bill_length_mm,bill_depth_mm,body_mass_g" -corr
```
```text
┌────────────────┬────────────────┬───────────────┬─────────────┐
│ column         ┆ bill_length_mm ┆ bill_depth_mm ┆ body_mass_g │
╞════════════════╪════════════════╪═══════════════╪═════════════╡
│ bill_length_mm ┆ 1.0            ┆ -0.24         ┆ 0.6         │
│ bill_depth_mm  ┆ -0.24          ┆ 1.0           ┆ -0.47       │
│ body_mass_g    ┆ 0.6            ┆ -0.47         ┆ 1.0         │
└────────────────┴───────────────┴───────────────┴─────────────┘
```

### 2. Ranked Correlation Pairs (`-corr pairs`)
Unnest the matrix into unique pairs sorted by correlation strength with visual bars:
```bash
pytae penguins.parquet -corr pairs
```
```text
┌───────────────────┬───────────────────┬───────┬───────────────────────┐
│ Column A          ┆ Column B          ┆ Corr  ┆ Strength              │
╞═══════════════════╪═══════════════════╪═══════╪═══════════════════════╡
│ flipper_length_mm ┆ body_mass_g       ┆ 0.87  ┆ █████████ Very Strong │
│ bill_length_mm    ┆ flipper_length_mm ┆ 0.66  ┆ ███████ Strong        │
│ bill_length_mm    ┆ body_mass_g       ┆ 0.6   ┆ ██████ Moderate       │
│ bill_depth_mm     ┆ flipper_length_mm ┆ -0.58 ┆ ▒▒▒▒▒▒ Moderate (-)   │
│ bill_depth_mm     ┆ body_mass_g       ┆ -0.47 ┆ ▒▒▒▒▒ Moderate (-)    │
│ bill_length_mm    ┆ bill_depth_mm     ┆ -0.24 ┆ ▒▒ Weak (-)           │
└───────────────────┴───────────────────┴───────┴───────────────────────┘
```

### 3. Single-Target Screening
Screen all numeric features against a specific target column:
```bash
pytae penguins.parquet -corr "target=body_mass_g"
```

---

## Headless Figure Plotting

`-plot` renders publication-grade charts directly from the command-line pipeline. Any pipeline can end with a plot and route directly to disk or interactive screen.

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
  -filter "sex.notna()" \
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
pytae data.parquet -plot "kind=bar,x=cat,y=val" -o chart.png -out_dir ./reports/figures
```

---

## Interactive Viewing

If `-o` is omitted and the output is not redirected, `pytae` invokes `plt.show()` so you can inspect charts interactively in a desktop window:

```bash
pytae penguins.parquet -plot "kind=scatter, x=bill_length_mm, y=body_mass_g, by=species"
```
