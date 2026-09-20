# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Pandas extensions for everyday data-science tasks (filtering, selection, reshaping, aggregation, plotting), plus a `pytae` CLI that exposes the same operations for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.dat`, `.sas7bdat`) without writing any Python.

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

See [docs/CLI.md](https://github.com/maddytae/pytae/blob/master/docs/CLI.md) for the full flag reference, and [docs/CLI_MULTI_FILE.md](https://github.com/maddytae/pytae/blob/master/docs/CLI_MULTI_FILE.md) for `-file`/`-merge`/`-concat`.

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

Pandas extensions registered on `pd.DataFrame` — import `pytae` and the methods attach automatically.

- **Filtering** — `qry()`: dict-based filters (equality, lists, `in`/`not in`, comparisons, intervals)
- **Selection** — `select()`: columns by name, regex, dtype, or name pattern
- **Reshaping** — `long()` / `wide()`: melt numeric columns to rows, pivot back to columns
- **Aggregation** — `agg_df()`: auto-detects group columns and aggregates the rest
- **Utilities** — `to_clip()`, `handle_missing()`, `cols()`, `group_x()`, `clean_columns()`, `replace_values()`

See [docs/LIBRARY.md](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md) for examples of each.

## License

MIT — see [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE).
