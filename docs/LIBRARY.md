# pytae — Library Reference

Pandas extensions registered on `pd.DataFrame`. Importing `pytae` attaches the methods. `Plotter` is loaded only when you access it and needs `pip install pytae[plot]`.

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")          # or pt.sample_data["penguins"]
```

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

Dict-based filters (equality, lists, `in` / `not in`, comparisons, intervals, string matching, null checks). [qry.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/qry.ipynb)

```python
penguins.qry({"species": "Adelie", "body_mass_g": (">", 3500)})
penguins.qry({"species": ["Adelie", "Gentoo"]})
penguins.qry({"species": ("not in", ["Adelie"])})
penguins.qry({"body_mass_g": "[3000,4000]"})
penguins.qry({"species": ("startswith", "Ad")})   # also endswith, contains, regex (search-anywhere)
penguins.qry({"sex": ("notna",)})                  # also isna \u2014 one-element tuple, no value
```

## 3) Selection — `select()`

Pick columns by name, regex, dtype, or name pattern. [select.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/select.ipynb)

```python
penguins.select("species", "island")
penguins.select(regex="^bill")                 # regex= only; df.select("^bill") is an error
penguins.select(dtype="numeric")
penguins.select(exclude_dtype="numeric")       # keep non-numeric
penguins.select(exclude_dtype="non_numeric")   # keep numeric
penguins.select(contains="bill", startswith="flip")
penguins.select("species", regex="bill|body")
penguins.select("d", "a", "b")                 # KeyError if d is not a column
```

## 4) Reshaping — `long()`, `wide()`

`long()` melts numeric columns to rows. `wide()` pivots a column's values into headers. [shape.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/shape.ipynb)

```python
tall = penguins.long(c="feature")
tall.wide(c="feature", v="value")
tall.wide(c="feature", v="value", a="mean")
tall.wide(c="feature", v="value", a="n")  # 'n' aliases pandas' 'size' (group row count), matching agg_df
```

## 5) Aggregation — `agg_df()`

Groups by all non-numeric columns and aggregates the rest. `n` is group count. [agg_df.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/agg_df.ipynb)

```python
penguins.agg_df("mean")
penguins.agg_df(["sum", "mean", "n"])
penguins.agg_df({"body_mass_g": "mean", "n": "n"})
penguins.agg_df(a=["mean", "n"], dropna=False)  # a= required when other keywords are used
```

## 6) Mutated columns — `mutate()`

Create/overwrite columns from `qry()`-style `"new_col: expression"` entries, evaluated in order via pandas `eval()` — a plain formula per column, no lambda required. Column names in the expression must stay unquoted — quoting one turns it into a string literal instead of a column reference.

```python
penguins.mutate("bmi: body_mass_g / bill_length_mm ** 2")
penguins.mutate("heavy: body_mass_g > 4000, mass_kg: body_mass_g / 1000")  # multiple entries in one call
penguins.mutate("mass_kg: body_mass_g / 1000, mass_lb: mass_kg * 2.20462")  # later entries can reference earlier ones
penguins.mutate("is_adelie: species == 'Adelie'")  # string literals still need quotes
```

A local variable from the calling scope can be referenced with an `@` prefix, same as pandas' own `eval()`/`query()`:

```python
threshold = 4000
penguins.mutate("heavy: body_mass_g >= @threshold")
```

For conditional/string outcomes — where plain `eval()` can't help — two dplyr-style forms are built in:

```python
# if_else(condition, true_value, false_value) — like dplyr's if_else()
penguins.mutate("weight_class: if_else(body_mass_g > 4000, 'heavy', 'light')")

# case_when(cond1: val1, cond2: val2, ..., default) — like dplyr's case_when()
# checked in order, first match wins; a last argument with no colon is the optional
# catch-all (like SQL ELSE) and must be listed last; unmatched rows are NaN without it
penguins.mutate(
    "size_class: case_when(body_mass_g >= 4500: 'large', body_mass_g >= 3500: 'medium', 'small')"
)
```

## 7) Utilities — `to_clip()`, `handle_missing()`, `cols()`, `group_x()`, `clean_columns()`, `replace_values()`

[other_utilities.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/other_utilities.ipynb)

```python
penguins.cols()                    # sorted names; cols(ascending=None) keeps file order
penguins.handle_missing()          # object NA -> '.', numeric NA -> 0
penguins.group_x()                 # group size column `n`
penguins.group_x(group=["species"], v="body_mass_g", a="max")
penguins.to_clip()                 # copy to clipboard (does not shadow pandas clip)
penguins.clean_columns(strip=True, fill="_", case="lower")  # clean header names
penguins.replace_values({"Adelie": "Adelie (renamed)"})     # exact=True by default
penguins.replace_values({"a": "z"}, c="species", exact=False)  # substring, scoped
```
