# pytae — Library Reference

Pandas extensions: `Plotter`, `qry()`, `select()`, `long()`/`wide()`, `agg_df()`, and utility methods, all registered directly on `pd.DataFrame`/`pd.Series`.

## 1) Plotting — `Plotter`
Lightweight plotting built on top of `pandas.plot`, fully compatible with matplotlib and ability to method chain plots.
[plotter.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/plotter.ipynb)

## 2) Filtering — `qry()`
Dict based filtering making it more versatile.
[qry.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/qry.ipynb)

## 3) Selection — `select()`
R like select but on steroid.
[select.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/select.ipynb)

## 4) Reshaping — `long()`, `wide()`
`long()` melts all numeric columns to rows. `wide()` pivots a column's values into headers.
[shape.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/shape.ipynb)

## 5) Aggregation — `agg_df()`
Auto-detects group columns (non-numeric) and aggregates the rest. Supports `str`, `list`, and `dict` aggfunc. `n` is a special token for group count.
[agg_df.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/agg_df.ipynb)

## 6) Utilities — `clip()`, `handle_missing()`, `cols()`, `group_x()`
- `cols()` — sorted column list
- `handle_missing()` — fill NaN with a visible marker before aggregating
- `group_x()` — broadcast a group aggregate back to every row (like `transform`)
- `clip()` — copy DataFrame to clipboard for pasting into Excel / Sheets

[other_utilities.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/other_utilities.ipynb)
