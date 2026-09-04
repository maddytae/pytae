# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Pandas extensions for everyday data-science tasks (filtering, selection, reshaping, aggregation, plotting), plus a `pytae` CLI that exposes the same operations for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.sas7bdat`) without writing any Python.

## Install

```bash
pip install pytae
```

## Library

Pandas extensions registered on `pd.DataFrame` — import `pytae` and the methods attach automatically.

- **Plotting** — `Plotter`: method-chainable plots on `pandas.plot` (`pip install pytae[plot]`)
- **Filtering** — `qry()`: dict-based filters (equality, lists, `in`/`not in`, comparisons, intervals)
- **Selection** — `select()`: columns by name, regex, dtype, or name pattern
- **Reshaping** — `long()` / `wide()`: melt numeric columns to rows, pivot back to columns
- **Aggregation** — `agg_df()`: auto-detects group columns and aggregates the rest
- **Utilities** — `to_clip()`, `handle_missing()`, `cols()`, `group_x()`

See [docs/LIBRARY.md](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md) for examples of each.

## CLI

```bash
pytae data.parquet -head
pytae data.parquet -qry "{'species': 'Adelie'}" -select species,body_mass_g -convert -o subset.csv
```

See [docs/CLI.md](https://github.com/maddytae/pytae/blob/master/docs/CLI.md) for the full flag reference.

## License

MIT — see [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE).
