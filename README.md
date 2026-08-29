# pytae

**pytae** is a lightweight Python package that makes everyday data science tasks faster and more readable — think R-style chaining on top of pandas.

## Installation

```bash
pip install pytae
```

Requires Python ≥ 3.7, pandas ≥ 1.0.0

## Documentation

pytae ships two things: a set of pandas extensions you use in your own code, and a command-line tool for inspecting/converting tabular files directly from the shell.

- **[Library reference](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md)** — `Plotter`, `qry()`, `select()`, `long()`/`wide()`, `agg_df()`, and utility methods registered on `pd.DataFrame`.
- **[CLI reference](https://github.com/maddytae/pytae/blob/master/docs/CLI.md)** — the `pytae` command: `-select`, `-qry`/`-query`, `-agg_df`/`-group_by`+`-agg`, `-value_counts`, `-unique`, `-sort_by`, `-convert`, and more.

## Features at a glance

| # | Feature | Where |
|---|---|---|
| 1 | Plotting — `Plotter` | [Library reference](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#1-plotting--plotter) |
| 2 | Filtering — `qry()` | [Library reference](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#2-filtering--qry) |
| 3 | Selection — `select()` | [Library reference](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#3-selection--select) |
| 4 | Reshaping — `long()`, `wide()` | [Library reference](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#4-reshaping--long-wide) |
| 5 | Aggregation — `agg_df()` | [Library reference](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#5-aggregation--agg_df) |
| 6 | Utilities — `clip()`, `handle_missing()`, `cols()`, `group_x()` | [Library reference](https://github.com/maddytae/pytae/blob/master/docs/LIBRARY.md#6-utilities--clip-handle_missing-cols-group_x) |
| 7 | CLI — `pytae` | [CLI reference](https://github.com/maddytae/pytae/blob/master/docs/CLI.md) |

