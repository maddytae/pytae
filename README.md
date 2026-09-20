# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Pandas helpers for everyday data-science tasks (filtering, selection, reshaping, aggregation, plotting), plus a `pytae` CLI that exposes the same operations for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.dat`, `.sas7bdat`) without writing any Python.

## Install

```bash
pip install pytae
```

## CLI

```bash
pytae data.parquet -head
pytae data.parquet -qry "species: 'Adelie'" -select "species,body_mass_g" -convert -o subset.csv
pytae data.parquet -sql "select species, avg(body_mass_g) from df group by species"
pytae -file "data1.parquet=df1; data2.parquet=df2" -merge "left=df1,right=df2,on=id"
```

See [docs/FLAGS.md](https://github.com/maddytae/pytae/blob/master/docs/FLAGS.md) for which flag to use, [docs/CLI.md](https://github.com/maddytae/pytae/blob/master/docs/CLI.md) for the full reference, and [docs/CLI_MULTI_FILE.md](https://github.com/maddytae/pytae/blob/master/docs/CLI_MULTI_FILE.md) for `-file`/`-merge`/`-concat`.

## Plotting

`Plotter`: method-chainable plots on top of `pandas.plot()` (`pip install pytae[plot]`).

```python
from pytae.plotting import Plotter

Plotter().data(penguins).plot(
    x="bill_length_mm", y="bill_depth_mm", kind="scatter", c="species", cmap="viridis"
).finalize()
```

See [docs/PLOTTING.md](https://github.com/maddytae/pytae/blob/master/docs/PLOTTING.md) for more examples with sample data.

## Library

Import `pytae as pt` and call package functions — they take the DataFrame as the first argument (`pt.select(df, ...)`). They do not attach to `pd.DataFrame`. CLI flags (`-select`, `-qry`, …) are unchanged.

```python
import pytae as pt
penguins = pt.sample("penguins")
pt.select(penguins, "species", contains="bill")
pt.qry(penguins, {"species": "Adelie"})
```

- **Filtering** — `pt.qry()`: dict-based filters (equality, lists, `in`/`not in`, comparisons, intervals)
- **Selection** — `pt.select()`: columns by name, regex, dtype, or name pattern
- **Reshaping** — `pt.long()` / `pt.wide()`: melt numeric columns to rows, pivot back to columns
- **Aggregation** — `pt.agg_df()`: auto-detects group columns and aggregates the rest
- **Utilities** — `pt.to_clip()`, `pt.handle_missing()`, `pt.cols()`, `pt.group_x()`, `pt.clean_columns()`, `pt.replace_values()`

See [docs/LIBRARY.md](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md) for examples of each.

## License

MIT — see [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE).
