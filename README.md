# pytae

**pytae** is a lightweight Python package that makes everyday data science tasks faster and more readable — think R-style chaining on top of pandas.

## Installation

```bash
pip install pytae
```

Requires Python ≥ 3.7, pandas ≥ 1.0.0



## Features

Seven feature sets, each with a companion reference notebook (1–6) or usage guide (7):

### 1) Plotting — `Plotter`
Lightweight plotting built on top of `pandas.plot`, fully compatible with matplotlib and ability to method chain plots.
[plotter.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/plotter.ipynb)

### 2) Filtering — `qry()`
Dict based filtering making it more versatile.
[qry.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/qry.ipynb)

### 3) Selection — `select()`
R like select but on steroid.
[select.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/select.ipynb)

### 4) Reshaping — `long()`, `wide()`
`long()` melts all numeric columns to rows. `wide()` pivots a column's values into headers.
[shape.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/shape.ipynb)

### 5) Aggregation — `agg_df()`
Auto-detects group columns (non-numeric) and aggregates the rest. Supports `str`, `list`, and `dict` aggfunc. `n` is a special token for group count.
[agg_df.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/agg_df.ipynb)

### 6) Utilities — `clip()`, `handle_missing()`, `cols()`, `group_x()`
- `cols()` — sorted column list
- `handle_missing()` — fill NaN with a visible marker before aggregating
- `group_x()` — broadcast a group aggregate back to every row (like `transform`)
- `clip()` — copy DataFrame to clipboard for pasting into Excel / Sheets

[other_utilities.ipynb](https://github.com/maddytae/pytae/blob/master/notebooks/other_utilities.ipynb)

### 7) CLI — `pytae`

A command-line tool for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.sas7bdat`). Powered by pytae's own `qry()`, `select()`, and `agg_df()` under the hood.

```bash
pytae data.parquet -head
pytae data.parquet -shape
pytae data.parquet -cols
pytae data.parquet -dtype
pytae data.parquet -nulls
pytae data.parquet -stats
```

**Column selection — `-select`, `-select-dtype`, `-select-contains`, `-select-startswith`, `-select-endswith`, `-exclude-dtype`**

Uses pytae's `select()` under the hood — all flags are additive (except `-exclude-dtype` which is standalone):

```bash
# explicit column list
pytae data.parquet -select species,island -head 5
pytae data.parquet -select "'bill length mm','body mass g'" -describe

# by dtype
pytae data.parquet -select-dtype numeric -describe
pytae data.parquet -exclude-dtype numeric -head 5

# by name pattern
pytae data.parquet -select-contains bill -head 5
pytae data.parquet -select-startswith bill -dtype
pytae data.parquet -select-endswith _mm -nulls

# combine explicit + pattern
pytae data.parquet -select species -select-contains bill -head 5
```

**Row filtering — `-qry` and `-query`**

`-qry` uses pytae's dict-based `qry()` syntax; `-query` uses a pandas query string:

```bash
pytae data.parquet -qry "{'species': 'Adelie', 'body_mass_g': ('>', 3500)}"
pytae data.parquet -query "body_mass_g > 3500 and island == 'Dream'"
```

**Aggregation — `-agg`**

Groups by all non-numeric columns and aggregates the rest, using pytae's `agg_df()`. Accepts a string, list, or dict aggfunc:

```bash
pytae data.parquet -agg           # defaults to sum
pytae data.parquet -agg mean
pytae data.parquet -agg "['mean', 'sum']"
pytae data.parquet -agg "{'body_mass_g': 'mean', 'n': 'n'}"
# combine with filters
pytae data.parquet -qry "{'species': 'Adelie'}" -agg mean
```

**Conversion — `-convert`**

Any supported format can be converted to any other — except writing `.sas7bdat` (pandas has no SAS writer). The output format is inferred from the `-o` extension; omitting `-o` defaults to `.csv` alongside the source.

| Format | Read | Write |
|---|---|---|
| `.parquet` / `.pq` | ✓ | ✓ |
| `.csv` | ✓ | ✓ |
| `.txt` | ✓ | ✓ |
| `.sas7bdat` | ✓ | — |

```bash
# parquet → csv (default when -o is omitted)
pytae data.parquet -convert

# parquet → txt (tab-delimited by default for .txt)
pytae data.parquet -convert -o data.txt

# parquet → parquet (column-subset via -select)
pytae data.parquet -select col_a,col_b -convert -o subset.parquet

# csv → parquet
pytae data.csv -convert -o data.parquet

# sas7bdat → parquet
pytae data.sas7bdat -convert -o data.parquet

# txt with a custom delimiter → csv
pytae data.txt -dlim "|" -convert -o data.csv

# batch convert all parquets in a folder to csv
pytae 'data/*.parquet' -convert

# rename columns on the way out
pytae data.parquet -convert -rename "old_name:new_name,another:clean"
```

> **Delimiter (`-dlim`):** only applies to `.csv`, `.txt`, and `.sas7bdat` — `.parquet` is binary and has no delimiter.
> Common values: `,` (csv default), `\t` (tab, txt default), `|`, `;`, `:`, `~`
>
> ```bash
> pytae data.txt -dlim "|" -head
> pytae data.csv -dlim ";" -convert -o data.parquet
> ```

**Other flags**

| Flag | Description |
|---|---|
| `-head N` | First N rows (default 5) |
| `-tail N` | Last N rows (default 5) |
| `-sample N` | N random rows (default 5) |
| `-nrows N` | Cap rows loaded |
| `-sort asc\|desc\|none` | Column order for `-cols`/`-dtype`/`-nulls` |
| `-dlim CHAR` | Field delimiter for `.csv`/`.txt`/`.sas7bdat` (not `.parquet`) |
| `-stats` | Numeric summary (alias `-describe`) |
| `-select-dtype TYPE` | Add columns of dtype to selection |
| `-select-contains STR` | Add columns whose names contain STR |
| `-select-startswith STR` | Add columns whose names start with STR |
| `-select-endswith STR` | Add columns whose names end with STR |
| `-exclude-dtype TYPE` | Keep all columns except this dtype |
| `-encoding ENC` | Text encoding for `.csv`/`.txt`/`.sas7bdat` (e.g. `latin-1`); not used for `.parquet` |
| `-rename old:new,...` | Rename columns on conversion |
| `-pretty` | Render tables as markdown |
| `-clip` | Copy output to clipboard |
| `-progress` | Show progress for large files |

