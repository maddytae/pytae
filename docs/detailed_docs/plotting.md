# Visualizations & Plotting (`plotting`)

`pytae` provides visualization capabilities across both Python notebooks and the terminal:
- **Terminal In-Line Visualizations**: Instant ASCII frequency bars (`freq` / `-freq`) and numeric distribution histograms (`hist` / `-hist`) rendered directly in console scrollback.
- **Publication-Grade Figure Plotting**: Full Matplotlib-backed plotting via `.plot()` in Python and `-plot` on the CLI, with custom styling and export support (`-o chart.png`).

---

## Rosetta Stone: Python vs. CLI

| Plot Type | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Terminal Frequency Bar** | `df.freq("species")` | `-freq species` |
| **Terminal Histogram** | `df.hist("body_mass_g:8")` | `-hist "body_mass_g:8"` |
| **Bar Chart** | `df.plot(kind="bar", x="species", y="mass")` | `-plot "kind=bar, x=species, y=mass"` |
| **Scatter Plot** | `df.plot(kind="scatter", x="bill_len", y="bill_depth")` | `-plot "kind=scatter, x=bill_len, y=bill_depth"` |
| **Line Chart** | `df.plot(kind="line", x="date", y="revenue")` | `-plot "kind=line, x=date, y=revenue"` |
| **Box Plot** | `df.plot(kind="box", y="body_mass_g", by="species")`| `-plot "kind=box, y=body_mass_g, by=species"` |
| **Figure Styling** | `.finalize(title="Sales", xlabel="Month")` | `-finalize "title='Sales', xlabel='Month'"` |
| **Save to File** | `fig.savefig("chart.png")` | `-o chart.png` |

---

## Terminal ASCII Visualizations

### 1. Categorical Distribution Bars (`freq`)
Generates horizontal bar charts with exact counts and percentages:

```python
penguins.freq("species")
```
```bash
pytae penguins.parquet -freq species
```

### 2. Numeric Binned Histograms (`hist`)
Visualizes spreads, skewness, and peaks:

```python
penguins.hist("body_mass_g:6")
```
```bash
pytae penguins.parquet -hist "body_mass_g:6"
```

---

## Matplotlib Figure Plotting (`.plot()` & `-plot`)

### In Python:
```python
import pytae as pt

penguins = pt.sample("penguins")

# Aggregation and plot
fig = (
    penguins
    .by("species")
    .agg(avg_mass="mean(body_mass_g)")
    .plot(kind="bar", x="species", y="avg_mass")
)
fig.savefig("penguin_mass.png", bbox_inches="tight")
```

### In CLI:
Any CLI pipeline can terminate with `-plot`, `-finalize`, and `-o target.png`:

```bash
# Filter, aggregate, and plot bar chart directly to PNG
pytae penguins.parquet \
  -by species \
  -agg "avg_mass = mean(body_mass_g)" \
  -plot "kind=bar, x=species, y=avg_mass" \
  -finalize "title='Average Body Mass by Species', ylabel='Mass (g)'" \
  -o species_mass.png

# Scatter plot
pytae penguins.parquet \
  -plot "kind=scatter, x=bill_length_mm, y=bill_depth_mm, c=species" \
  -finalize "title='Bill Dimensions by Species'" \
  -o bill_scatter.png

# Distribution box plot
pytae penguins.parquet \
  -plot "kind=box, y=body_mass_g, by=species" \
  -o mass_box.png
```

