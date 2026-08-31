# pytae

R-style chaining on pandas, plus a CLI for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.sas7bdat`).

## Install

```bash
pip install pytae          # CLI + DataFrame methods (pandas ≥ 2.0, pyarrow ≥ 15)
pip install pytae[plot]    # plus matplotlib — only needed for Plotter
```

Requires **Python ≥ 3.10** and **pandas ≥ 2.0**. Matplotlib is **not** installed by default. If you call `Plotter` without it, you get:

```text
ImportError: Plotter requires matplotlib. Install with: pip install 'pytae[plot]'
```

Local development:

```bash
pip install -e ".[dev]"    # pytest + matplotlib for tests
pytest
```

## CLI

```bash
pytae data.parquet -head
pytae data.parquet -shape
pytae data.parquet -cols
pytae data.parquet -select "species,regex=^bill,dtype=numeric" -head 5
pytae data.parquet -qry "{'species': 'Adelie'}" -agg_df mean
pytae data.parquet -group_by species -group_x body_mass_g:max
pytae data.parquet -convert -o data.csv
```

`-select` is one flag. Tokens are a **union** (same as `df.select(...)`): names, `start:end` slices, and `key=value` (`dtype`, `contains`, `startswith`, `endswith`, `regex`, `exclude_dtype`). Regex is always `regex=`, never a bare pattern.

`-group_x` keeps every row and adds a column. `body_mass_g:max` is **column then function** (same order as `-agg "{'body_mass_g': 'max'}"`). Bare `-group_x` is group size `n`.

Clipboard copy is `-to_clip` (not `-clip`). Pandas `DataFrame.clip(lower=0)` is left alone.

Full CLI reference: [docs/CLI.md](https://github.com/maddytae/pytae/blob/master/docs/CLI.md)

## Library

```python
import pytae as pt

penguins = pt.sample("penguins")          # or pt.sample_data["penguins"]

penguins.qry({"species": "Adelie", "body_mass_g": (">", 3500)})
penguins.select("species", regex="^bill", dtype="numeric")
penguins.select(exclude_dtype="numeric")       # keep non-numeric
penguins.select(exclude_dtype="non_numeric")   # keep numeric
penguins.agg_df(["mean", "n"])
penguins.group_x(group=["species"], aggfunc="max", value="body_mass_g")
penguins.to_clip()                             # clipboard; not pandas clip()
```

`import pytae` registers the DataFrame methods. It does **not** load matplotlib, Plotter, or the bundled parquets until you use them.

Plotting:

```python
from pytae.plotting import Plotter   # requires pytae[plot]

Plotter().data(penguins).plot(
    x="bill_length_mm", y="bill_depth_mm", kind="scatter", by="species"
).finalize()
```

Full library reference: [docs/LIBRARY.md](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md)

Notebooks: [plotter](https://github.com/maddytae/pytae/blob/master/notebooks/plotter.ipynb), [qry](https://github.com/maddytae/pytae/blob/master/notebooks/qry.ipynb), [select](https://github.com/maddytae/pytae/blob/master/notebooks/select.ipynb), [shape](https://github.com/maddytae/pytae/blob/master/notebooks/shape.ipynb), [agg_df](https://github.com/maddytae/pytae/blob/master/notebooks/agg_df.ipynb), [utilities](https://github.com/maddytae/pytae/blob/master/notebooks/other_utilities.ipynb)

## Features at a glance

| # | Feature | Where |
|---|---|---|
| 1 | Plotting — `Plotter` (`pytae[plot]`) | [Library](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#1-plotting--plotter) |
| 2 | Filtering — `qry()` | [Library](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#2-filtering--qry) |
| 3 | Selection — `select()` / `-select` | [Library](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#3-selection--select) · [CLI](https://github.com/maddytae/pytae/blob/master/docs/CLI.md) |
| 4 | Reshaping — `long()`, `wide()` | [Library](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#4-reshaping--long-wide) |
| 5 | Aggregation — `agg_df()` | [Library](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#5-aggregation--agg_df) |
| 6 | Utilities — `to_clip()`, `handle_missing()`, `cols()`, `group_x()` | [Library](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#6-utilities--to_clip-handle_missing-cols-group_x) |
| 7 | CLI — `pytae` | [CLI](https://github.com/maddytae/pytae/blob/master/docs/CLI.md) |
