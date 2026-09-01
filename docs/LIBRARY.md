# pytae — Library Reference

Pandas extensions registered on `pd.DataFrame`. Importing `pytae` attaches the methods. `Plotter` is loaded only when you access it and needs `pip install pytae[plot]`.

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")          # or pt.sample_data["penguins"]
```

## 1) Plotting — `Plotter`

Method-chainable plots on top of `pandas.plot`. Requires matplotlib (`pip install pytae[plot]`). [plotter.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/plotter.ipynb)

```python
from pytae.plotting import Plotter

Plotter().data(penguins).plot(
    x="bill_length_mm", y="bill_depth_mm", kind="scatter", by="species"
).finalize()
```

## 2) Filtering — `qry()`

Dict-based filters (equality, lists, `in` / `not in`, comparisons, intervals). [qry.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/qry.ipynb)

```python
penguins.qry({"species": "Adelie", "body_mass_g": (">", 3500)})
penguins.qry({"species": ["Adelie", "Gentoo"]})
penguins.qry({"species": ("not in", ["Adelie"])})
penguins.qry({"body_mass_g": "[3000,4000]"})
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
```

## 4) Reshaping — `long()`, `wide()`

`long()` melts numeric columns to rows. `wide()` pivots a column's values into headers. [shape.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/shape.ipynb)

```python
tall = penguins.long(column="feature")
tall.wide(column="feature", value="value")
tall.wide(column="feature", value="value", aggfunc="mean")
```

## 5) Aggregation — `agg_df()`

Groups by all non-numeric columns and aggregates the rest. `n` is group count. [agg_df.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/agg_df.ipynb)

```python
penguins.agg_df("mean")
penguins.agg_df(["sum", "mean", "n"])
penguins.agg_df({"body_mass_g": "mean", "n": "n"})
```

## 6) Utilities — `to_clip()`, `handle_missing()`, `cols()`, `group_x()`

[other_utilities.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/other_utilities.ipynb)

```python
penguins.cols()                    # sorted names; cols(ascending=None) keeps file order
penguins.handle_missing()          # object NA -> '.', numeric NA -> 0
penguins.group_x()                 # group size column `n`
penguins.group_x(group=["species"], aggfunc="max", value="body_mass_g")
penguins.to_clip()                 # copy to clipboard (does not shadow pandas clip)
```
