# pytae — CLI Reference

A command-line tool for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.sas7bdat`). Powered by pytae's own `qry()`, `select()`, and `agg_df()` under the hood.

```bash
pytae data.parquet -head
pytae data.parquet -shape
pytae data.parquet -cols
pytae data.parquet -dtype
pytae data.parquet -nulls
pytae data.parquet -stats
```

**Column selection — `-select`**

One flag, one `df.select()` call. Tokens are a **union** (each token adds columns; nothing intersects).

Bare tokens are column names or `start:end` slices. `key=value` tokens map to the same kwargs as `df.select(...)`.

| Token | Meaning |
|---|---|
| `species` | exact column name |
| `species,island` | several exact names |
| `'bill length mm'` | name with spaces (quote it) |
| `species:bill_length_mm` | slice of columns from `species` through `bill_length_mm` |
| `dtype=numeric` | add columns of this dtype (`numeric`, `non_numeric`, `object`, `datetime`, `bool`, `category`) |
| `contains=bill` | add names containing `bill` |
| `startswith=bill` | add names starting with `bill` |
| `endswith=_mm` | add names ending with `_mm` |
| `regex=^bill` | add names matching this regex |
| `exclude_dtype=numeric` | keep every column except this dtype (**standalone**; cannot mix with other tokens) |

```bash
# exact names
pytae data.parquet -select species,island -head 5
pytae data.parquet -select "'bill length mm','body mass g'" -stats

# regex
pytae data.parquet -select "regex=^bill" -head 5
pytae data.parquet -select "regex=_mm$" -nulls
pytae data.parquet -select "regex=bill|body" -stats

# dtype
pytae data.parquet -select dtype=numeric -stats
pytae data.parquet -select exclude_dtype=numeric -head 5

# name patterns
pytae data.parquet -select contains=bill -head 5
pytae data.parquet -select startswith=bill -dtype
pytae data.parquet -select endswith=_mm -nulls

# slice
pytae data.parquet -select species:bill_length_mm -cols

# union of exact names + kwargs (species, then any name containing bill, then remaining numerics)
pytae data.parquet -select "species,contains=bill,dtype=numeric" -head 5
pytae data.parquet -select "species,regex=bill|body" -head 5

# repeated keys become a list (names containing bill OR body)
pytae data.parquet -select "contains=bill,contains=body" -cols
```

Unknown exact names error with a typo suggestion. A positional token that is not a real column is **not** a regex in either the CLI or `df.select()` — use `regex=`.

**`df.select()` but not `-select`**

These library forms have no CLI spelling:

- `everything()` — remaining columns after an explicit list
- a callable, e.g. `df.select(lambda c: c.endswith("_mm"))`
- passing a Python `list` as a single positional arg (CLI always sends each name as its own string; the result is the same for exact names)
- `contains` / `startswith` / `endswith` / `regex` as a Python list object in one kwarg — CLI repeats the key instead: `contains=bill,contains=body`

**Row filtering — `-qry` and `-query`**

`-qry` uses pytae's dict-based `qry()` syntax; `-query` uses a pandas query string:

```bash
pytae data.parquet -qry "{'species': 'Adelie', 'body_mass_g': ('>', 3500)}"
pytae data.parquet -query "body_mass_g > 3500 and island == 'Dream'"
```

Both apply to `-head`/`-tail`/`-nulls`/`-describe`/`-sample`/`-convert`/`-agg_df`/`-agg`/`-value_counts`.

**Aggregation (auto group columns) — `-agg_df`**

Groups by all non-numeric columns and aggregates the rest, using pytae's `agg_df()`. Accepts a string, list, or dict aggfunc:

```bash
pytae data.parquet -agg_df           # defaults to sum
pytae data.parquet -agg_df mean
pytae data.parquet -agg_df "['mean', 'sum']"
pytae data.parquet -agg_df "{'body_mass_g': 'mean', 'n': 'n'}"
# combine with filters
pytae data.parquet -qry "{'species': 'Adelie'}" -agg_df mean
# keep the NA grouping key instead of dropping it (default drops NA keys)
pytae data.parquet -agg_df sum -dropna false
```

**Aggregation (explicit group columns) — `-group_by` + `-agg`**

For full control over which columns to group by (instead of `-agg_df`'s auto-detected non-numeric columns), use `-group_by` together with `-agg`. `-agg` takes a dict literal mapping each source column to either a bare aggfunc, or an `(output_name, aggfunc)` tuple for a custom output column name — built on plain pandas `groupby().agg()` with named aggregation, not `agg_df()`:

```bash
# bare aggfunc: output column keeps the source column's name
pytae data.parquet -group_by species -agg "{'body_mass_g': 'mean', 'flipper_length_mm': 'sum'}"

# (output_name, aggfunc): custom output column names
pytae data.parquet -group_by species -agg "{'body_mass_g': ('avg_mass', 'mean'), 'flipper_length_mm': ('total_flipper', 'sum')}"

# multiple group columns
pytae data.parquet -group_by "species,island" -agg "{'body_mass_g': 'mean'}"
```

> `-agg` requires `-group_by`. `-group_by` is also used by `-group_x` (and can be omitted there to auto-detect non-numeric columns). Each source column can appear once per `-agg` call (one output per input column) — for multiple aggregations on the same source column, use `-agg_df`'s list/dict aggfunc instead. `-dropna` applies here too (drops NA group keys by default). `-agg_df` and `-agg` can't be combined.

**Broadcast — `-group_x`**

Broadcast a group aggregate back onto every row (like pandas `transform`). Defaults to group size `n`. Optional `-group_by` picks the groups; otherwise non-numeric columns are used.

```bash
pytae data.parquet -group_x
pytae data.parquet -group_by species -group_x
pytae data.parquet -group_by species -group_x max:body_mass_g
```

**Value counts — `-value_counts`**

Counts occurrences across the current working columns (use `-select` to narrow columns first). With multiple columns, counts unique combinations:

```bash
pytae data.parquet -select species -value_counts
pytae data.parquet -select species,island -value_counts
# keep NA as its own key instead of dropping it (default drops NA)
pytae data.parquet -select species -value_counts -dropna false
```

**Unique rows — `-unique`**

Drops duplicate rows and prints the remaining unique rows:

```bash
pytae data.parquet -unique
pytae data.parquet -select species,island -unique
```

**Listing — `-cols` / `-dtype` / `-nulls`**

Print schema in file (or `-select`) order. Optional `asc` / `desc` sorts by column name:

```bash
pytae data.parquet -cols
pytae data.parquet -cols asc
pytae data.parquet -cols desc
pytae data.parquet -dtype desc
pytae data.parquet -nulls asc
```

**Sorting — `-sort_by`**

Sorts **rows** by one or more columns (comma-separated). Optional `asc` / `desc` sets direction (default: ascending).

```bash
pytae data.parquet -sort_by body_mass_g
pytae data.parquet -sort_by body_mass_g desc
pytae data.parquet -sort_by species,body_mass_g desc
pytae data.parquet -select species,body_mass_g -sort_by body_mass_g desc -head 5
```

> When chained with another DataFrame-producing op (`-agg_df`, `-agg`, `-value_counts`, `-unique`, `-head`, etc.), only the final operation's result is printed — e.g. `-agg_df -sort_by grp` prints just the sorted aggregated table.

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
| `-unique` | Drop duplicate rows and print unique rows |
| `-value_counts` | Count occurrences across current working columns (use `-select` to choose columns) |
| `-cols [asc\|desc]` | Print column names; optional A–Z / Z–A (default: file order) |
| `-dtype [asc\|desc]` | Print dtypes; optional sort by name (default: file order) |
| `-nulls [asc\|desc]` | Print null counts; optional sort by name (default: file order) |
| `-sort_by COLUMNS [asc\|desc]` | Sort rows by column(s), comma-separated (default: ascending) |
| `-group_by COLUMNS` | Explicit group-by columns for `-agg` or `-group_x` (comma-separated) |
| `-group_x [AGGFUNC[:VALUE_COL]]` | Broadcast a group aggregate to every row (default: group size `n`) |
| `-dropna true\|false` | For `-agg_df`/`-agg`/`-value_counts`: drop NA keys when `true` (default: `true`) |
| `-nrows N` | Cap rows loaded |
| `-dlim CHAR` | Field delimiter for `.csv`/`.txt`/`.sas7bdat` (not `.parquet`) |
| `-stats` | Numeric summary (alias `-describe`) |
| `-select SPEC` | Restrict columns (union of names, slices, and `key=value` tokens) |
| `-encoding ENC` | Text encoding for `.csv`/`.txt`/`.sas7bdat` (e.g. `latin-1`); not used for `.parquet` |
| `-rename old:new,...` | Rename columns on conversion |
| `-pretty` | Render tables as markdown |
| `-round N` | Round numeric columns to N decimal places before printing/copying; non-numeric columns unchanged |
| `-to_clip` | Copy output to clipboard; suppresses terminal output |
| `-progress` | Show progress for large files |
