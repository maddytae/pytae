# pytae — Library Reference

Two call styles, same functions: `pt.select(df, ...)` or the DataFrame accessor `df.pt` (mix with pandas methods: `df.rename(...).pt.agg_df(...)`). Notebooks use the accessor chain. CLI flags (`-select`, `-qry`, …) are unchanged. `Plotter` is loaded only when you access it and needs `pip install pytae[plot]`.

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")          # or pt.sample_data["penguins"]

# function style
pt.select(penguins, "species", contains="bill")

# accessor chain (notebooks) — pandas methods sit in the same chain
(penguins
 .pt.select("species", "island", "bill_length_mm", "body_mass_g")
 .pt.agg_df(a=["mean", "n"])
)
penguins.rename(columns={"body_mass_g": "mass"}).pt.agg_df(a="mean")
```

## SQL — `sql()`

Same as CLI `-sql`: duckdb, current frame is table **`data`**. Optional extra: `pip install pytae[sql]`. Extra keyword frames are extra tables (like `-file` aliases).

```python
pt.sql(penguins, "select species, avg(body_mass_g) as avg_mass from data group by species")
penguins.pt.sql("select * from data where species = 'Adelie'")
pt.sql(left, "select * from data inner join extra using (id)", extra=right)
```

Spaced column names need double quotes: `pt.sql(df, 'select "bill length mm" from data')`.

## 1) Plotting — `Plotter`

Method-chainable plots on top of `pandas.plot`. Requires matplotlib (`pip install pytae[plot]`). See **[docs/PLOTTING.md](PLOTTING.md)** for more examples (bar, pie, multi-panel dashboards, faceting, …) with sample data, or [plotter.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/plotter.ipynb) for the full notebook.

```python
from pytae.plotting import Plotter

Plotter().data(penguins).plot(
    x="bill_length_mm", y="bill_depth_mm", kind="scatter", c="species", cmap="viridis"
).finalize()

# small multiples: one panel per group, grid auto-sized (leftover cells left blank)
Plotter.facet(penguins, by="species", ncols=2, x="bill_length_mm", y="bill_depth_mm", kind="scatter")
```

## 2) Filtering — `qry()`

Clean keyword argument filters (equality, lists, comparisons, intervals, string matching, null checks). [qry.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/qry.ipynb)

```python
# Keyword arguments:
pt.qry(penguins, species="Adelie", body_mass_g="> 3500")
pt.qry(penguins, species=["Adelie", "Gentoo"])
pt.qry(penguins, species=("not in", ["Adelie"]))
pt.qry(penguins, body_mass_g="[3000,4000]")
pt.qry(penguins, species=("startswith", "Ad"))   # also endswith, contains, regex (search-anywhere)
pt.qry(penguins, sex=("notna",))                 # also isna — one-element tuple, no value
```

## 3) Selection — `select()`

Pick columns by name, regex, dtype, or name pattern. [select.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/select.ipynb)

```python
pt.select(penguins, "species", "island")
pt.select(penguins, regex="^bill")                 # regex= only; a bare "^bill" is an error
pt.select(penguins, dtype="numeric")
pt.select(penguins, exclude_dtype="numeric")       # keep non-numeric
pt.select(penguins, exclude_dtype="non_numeric")   # keep numeric
pt.select(penguins, contains="bill", startswith="flip")
pt.select(penguins, "species", regex="bill|body")
pt.select(penguins, "d", "a", "b")                 # KeyError if d is not a column
```

## 4) Reshaping — `long()`, `wide()`

`long()` melts numeric columns to rows. `wide()` pivots a column's values into headers. [shape.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/shape.ipynb)

```python
tall = pt.long(penguins, c="feature")
pt.wide(tall, c="feature", v="value")
pt.wide(tall, c="feature", v="value", a="mean")
pt.wide(tall, c="feature", v="value", a="n")  # 'n' aliases pandas' 'size' (group row count), matching agg_df
```

## 5) Aggregation — `agg_df()`

Groups by all non-numeric columns and aggregates the rest. `n` is group count. [agg_df.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/agg_df.ipynb)

```python
# Aggregate all numeric columns:
pt.agg_df(penguins, "mean")
pt.agg_df(penguins, ["sum", "mean", "n"])

# Keyword arguments for specific columns (most Pythonic):
pt.agg_df(penguins, body_mass_g="mean", flipper_length_mm="max", count="n")
pt.agg_df(penguins, a=["mean", "n"], dropna=False)
```

## 6) Mutated columns — `mutate()`

Create/overwrite columns using clean keyword arguments (`col="expr"` or `col=callable`), evaluated in order via pandas `eval()` — a plain formula per column, no lambda required (though lambdas are supported if desired).

```python
# Kwargs syntax (most Pythonic)
pt.mutate(penguins, bmi="body_mass_g / bill_length_mm ** 2", mass_kg="body_mass_g / 1000")

# Later entries can reference earlier ones in the same call
pt.mutate(penguins, mass_kg="body_mass_g / 1000", mass_lb="mass_kg * 2.20462")

# Callables / lambdas and constants
pt.mutate(penguins, bmi=lambda d: d.body_mass_g / d.bill_length_mm ** 2, status="active")

# Spec files (for external configurations)
pt.mutate(penguins, "@features.txt")
```

A local variable from the calling scope can be referenced with an `@` prefix, same as pandas' own `eval()`/`query()`, or passed explicitly via `params=`:

```python
threshold = 4000
pt.mutate(penguins, heavy="body_mass_g >= @threshold")
# or with explicit params:
pt.mutate(penguins, heavy="body_mass_g >= @thresh", params={"thresh": 4000})
```

Four functional helpers are built in and compose freely with each other and with pandas methods:

```python
# if_else(condition, true_value, false_value) — like dplyr's if_else()
pt.mutate(penguins, weight_class="if_else(body_mass_g > 4000, 'heavy', 'light')")

# case_when((cond1, val1), (cond2, val2), ..., default=...) — like dplyr's case_when()
# checked in order, first match wins; supports tuples or flat alternating pairs
pt.mutate(
    penguins,
    size_class="case_when((body_mass_g >= 4500, 'large'), (body_mass_g >= 3500, 'medium'), default='small')",
)
# flat pairs also work:
pt.mutate(penguins, size_class="case_when(body_mass_g >= 4500, 'large', body_mass_g >= 3500, 'medium', default='small')")

# coalesce(col1, col2, ..., default) — first non-null value per row
pt.mutate(df, contact="coalesce(mobile, home_phone, work_phone, 'N/A')")

# map(column, {key: value, ...}[, default]) — recode through a lookup dict
pt.mutate(penguins, code="map(species, {'Adelie': 'A', 'Gentoo': 'G'}, 'Other')")
```

## 7) Utilities — `to_clip()`, `handle_missing()`, `cols()`, `group_x()`, `clean_columns()`, `replace_values()`

[other_utilities.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/other_utilities.ipynb)

```python
pt.cols(penguins)                    # sorted names; cols(..., ascending=None) keeps file order
pt.handle_missing(penguins)          # object NA -> '.', numeric NA -> 0
pt.group_x(penguins)                 # group size column `n`
pt.group_x(penguins, group=["species"], v="body_mass_g", a="max")
pt.to_clip(penguins)                 # copy to clipboard (does not shadow pandas clip)
pt.clean_columns(penguins, strip=True, fill="_", case="lower")  # clean header names
pt.replace_values(penguins, {"Adelie": "Adelie (renamed)"})     # exact=True by default
pt.replace_values(penguins, {"a": "z"}, c="species", exact=False)  # substring, scoped
```
