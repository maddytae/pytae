# pytae — CLI Reference

Inspect and convert tabular files (`.parquet`, `.csv`, `.txt`, `.dat`, `.sas7bdat`). The CLI is the same verbs as the library: `qry()`, `select()`, `agg_df()`, `group_x()`, `handle_missing()`, `long()`, `wide()`.

## Contents

- [Basics](#basics)
- [Sample datasets](#sample-datasets)
- [Column selection — `-select`](#select)
- [Row filtering — `-qry` / `-query`](#filtering)
- [Aggregation (auto group columns) — `-agg_df`](#agg-df)
- [Aggregation (explicit group columns) — `-group_by` + `-agg`](#group-by-agg)
- [Broadcast — `-group_x`](#group-x)
- [Value counts — `-value_counts`](#value-counts)
- [Unique rows — `-unique`](#unique)
- [Listing — `-cols` / `-dtype` / `-nulls`](#listing)
- [Sorting rows — `-sort_by`](#sort-by)
- [Missing values — `-handle_missing`](#handle-missing)
- [Reshape — `-long` / `-wide`](#reshape)
- [Cross-tabulation — `-crosstab`](#crosstab)
- [Conversion — `-convert`](#convert)
- [Display extras](#display-extras)
- [Recipes](#recipes)
- [Flag reference](#flag-reference)

<a id="basics"></a>
## Basics

```bash
pytae penguins.parquet -head
pytae penguins.parquet -tail
pytae penguins.parquet -sample
pytae penguins.parquet -shape
pytae penguins.parquet -cols
pytae penguins.parquet -dtype
pytae penguins.parquet -nulls
pytae penguins.parquet -describe
pytae penguins.parquet -info
```

Flag **order is the pipeline**, the same as a pandas/pytae method chain. `-select … -agg_df … -select … -shape` is `df.select(…).agg_df(…).select(…).shape`. Put `-qry` / `-query` first yourself if you need a column you later drop. **Only the last operation prints.** Earlier flags still run.

```bash
# first 3 rows, then shape of that 3-row frame → prints (3, n)
pytae penguins.parquet -head 3 -shape

# names only (head runs but is not printed)
pytae penguins.parquet -head 5 -cols
```

`-shape` / `-cols` / `-dtype` / `-nulls` / `-info` mirror pandas attributes/methods that
don't return a DataFrame (`df.shape`, `df.columns`, `df.dtypes`, `df.info()` — `-nulls` is
`df.isna().sum()`). Like real method chaining, nothing may follow them except `-to_clip`;
put them last. `-describe` is the exception — `df.describe()` returns a DataFrame, so it
can still be chained into further flags (e.g. `-describe -shape`, `-describe -round 2`).

```bash
pytae penguins.parquet -shape -to_clip     # ok: -to_clip is the only thing allowed after -shape
pytae penguins.parquet -shape -head 3      # error: -shape isn't a DataFrame, can't chain -head off it
pytae penguins.parquet -describe -shape    # ok: describe() returns a DataFrame
```

The examples below run directly against the bundled `penguins` dataset (see [Sample datasets](#sample-datasets)) — `species`, `island`, `body_mass_g`, `bill_length_mm`, …

---

<a id="sample-datasets"></a>
## Sample datasets

pytae bundles real datasets (`penguins`, `tips`, `titanic`, `diamonds`, `mpg`, `flights`, …) — the library's `pytae.sample_data` dict, keyed by name. Save any of them as a parquet file in the current folder once, then run `pytae` on it like any other file:

```bash
# one-time setup: write a bundled dataset out as a real file
python -c "import pytae; pytae.sample_data['tips'].to_parquet('tips.parquet')"
```

Do the same for any others you want to try (`penguins`, `titanic`, `diamonds`, `mpg`, `flights`, …), then use plain filenames everywhere below:

```bash
pytae penguins.parquet -qry "'species': 'Adelie'" -agg_df mean
pytae penguins.parquet -crosstab "index='species',columns='island'"
pytae tips.parquet -select day,total_bill,tip -group_x "group='day',v='tip',a='mean'"
pytae titanic.parquet -crosstab "index='pclass',columns='survived',margins=true"
pytae diamonds.parquet -select cut,price -agg_df mean
pytae mpg.parquet -select origin,mpg -sort_by mpg desc -head 5
pytae flights.parquet -group_by year -agg "column='passengers',aggfunc='sum'"
```

---

<a id="select"></a>
## Column selection — `-select`

Tokens in one `-select` are a **union** (each token *adds* columns). Repeat `-select` to filter that result: each call is `df.select()` on the current working columns (including after `-agg_df` / `-long` / `-wide`).

Bare tokens are column names or `start:end` slices. `key=value` tokens map to the same kwargs as `df.select(...)`.

| Token | Meaning |
|---|---|
| `species` | exact column name |
| `species,island` | several exact names |
| `'bill length mm'` | name with spaces (quote it) |
| `species:bill_length_mm` | slice from `species` through `bill_length_mm` |
| `dtype=numeric` | add this dtype (`numeric`, `non_numeric`, `object`, `datetime`, `bool`, `category`) |
| `contains=bill` | add names containing `bill` |
| `startswith=bill` | add names starting with `bill` |
| `endswith=_mm` | add names ending with `_mm` |
| `regex=^bill` | add names matching this regex |
| `exclude_dtype=numeric` | keep every column except this dtype (**standalone**; cannot mix with other tokens) |
| `exclude_dtype=non_numeric` | keep numeric columns only |

```python
df.select("species", "island")
df.select(regex="^bill")
df.select("species", contains="bill", dtype="numeric")
df.select(exclude_dtype="numeric")
df.select(exclude_dtype="non_numeric")
```

```bash
# exact names
pytae penguins.parquet -select species,island -head 5
# illustrative: quoting a name with spaces (the bundled penguins columns use underscores, not spaces)
pytae data.parquet -select "'bill length mm','body mass g'" -describe

# regex (always regex= — a bare ^bill is an unknown column)
pytae penguins.parquet -select "regex=^bill" -head 5
pytae penguins.parquet -select "regex=_mm$" -nulls
pytae penguins.parquet -select "regex=bill|body" -describe

# dtype
pytae penguins.parquet -select dtype=numeric -describe
pytae penguins.parquet -select exclude_dtype=numeric -head 5
pytae penguins.parquet -select exclude_dtype=non_numeric -cols

# name patterns
pytae penguins.parquet -select contains=bill -head 5
pytae penguins.parquet -select startswith=bill -dtype
pytae penguins.parquet -select endswith=_mm -nulls

# slice
pytae penguins.parquet -select species:bill_length_mm -cols

# union in one -select (species, then names containing bill, then remaining numerics)
pytae penguins.parquet -select "species,contains=bill,dtype=numeric" -head 5
pytae penguins.parquet -select "species,regex=bill|body" -head 5

# repeated keys become a list (names containing bill OR body)
pytae penguins.parquet -select "contains=bill,contains=body" -cols

# a later -select filters remaining columns (numeric AND name contains bill)
pytae penguins.parquet -select dtype=numeric -select contains=bill -cols
pytae penguins.parquet -select species,island,body_mass_g -select species,body_mass_g -cols

# after another op, -select sees that op's columns (here: pick from the agg table)
pytae penguins.parquet -select species,body_mass_g -agg_df mean -select species,body_mass_g -shape
```

Exact names must exist on the **current** columns; missing names error with a typo suggestion — `-select d,a,b` does **not** silently return `a,b`. A positional token that is not a real column is **not** a regex — use `regex=`. Tokens in **one** spec are a union; each extra `-select` filters whatever is left (it is not last-wins).

### `df.select()` but not `-select`

- `everything()` — remaining columns after an explicit list
- a callable, e.g. `df.select(lambda c: c.endswith("_mm"))`
- a Python `list` as one positional arg (CLI sends each name as its own string)
- `contains` / `regex` as a Python list — CLI repeats the key: `contains=bill,contains=body`

---

<a id="filtering"></a>
## Row filtering — `-qry` and `-query`

`-qry` is pytae's dict `qry()` (safer for odd strings). `-query` is pandas `DataFrame.query()` (numexpr). Both **narrow rows** at this point in the pipeline, same as `.qry()` / `.query()`. Stacking them is sequential (AND on the remaining rows). Put the filter **before** `-select` if you need a column you then drop.

```python
df.qry({"species": "Adelie", "body_mass_g": (">", 3500)})
df.query("body_mass_g > 3500 and island == 'Dream'")
df.qry({"species": "Adelie"}).select("species", "body_mass_g")
```

```bash
# surrounding {} are optional for -qry — the CLI adds them for you
pytae penguins.parquet -qry "'species': 'Adelie', 'body_mass_g': ('>', 3500)"
pytae penguins.parquet -query "body_mass_g > 3500 and island == 'Dream'"
pytae penguins.parquet -qry "'species': 'Adelie'" -query "body_mass_g > 3500" -head

# filter first, then drop the filter column — same as df.qry(...).select(...)
pytae penguins.parquet -qry "'species': 'Adelie'" -select species,body_mass_g -head
```

`-select body_mass_g -qry "'species': 'Adelie'"` errors (`species` is already gone), matching `df.select("body_mass_g").qry({"species": "Adelie"})`.

---

<a id="agg-df"></a>
## Aggregation (auto group columns) — `-agg_df`

Groups by all **non-numeric** columns and aggregates the rest. `n` is group count.

```python
df.agg_df("mean")
df.agg_df(["sum", "mean", "n"])
df.agg_df({"body_mass_g": "mean", "n": "n"})
df.agg_df(a=["mean", "n"], dropna=False)  # a= required when other keywords are used
```

```bash
pytae penguins.parquet -agg_df           # defaults to sum
pytae penguins.parquet -agg_df mean
pytae penguins.parquet -agg_df "['mean', 'sum']"
# surrounding {} are optional for the dict form too
pytae penguins.parquet -agg_df "'body_mass_g': 'mean', 'n': 'n'"
pytae penguins.parquet -qry "'species': 'Adelie'" -agg_df mean
pytae penguins.parquet -agg_df sum -dropna false   # keep NA group keys
pytae penguins.parquet -agg_df mean -sort_by body_mass_g desc
pytae penguins.parquet -select species,body_mass_g -agg_df mean -select species,body_mass_g -shape
```

---

<a id="group-by-agg"></a>
## Aggregation (explicit group columns) — `-group_by` + `-agg`

`groupby().agg()` with named aggregation. Collapses to one row per group.

```python
df.groupby("species", as_index=False).agg(
    avg_mass=("body_mass_g", "mean"),
    n=("body_mass_g", "size"),
)
```

```bash
pytae penguins.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean'"
pytae penguins.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean'; column='flipper_length_mm',aggfunc='sum'"
pytae penguins.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean',as='avg_mass'; column='flipper_length_mm',aggfunc='sum',as='total_flipper'"
pytae penguins.parquet -group_by "species,island" -agg "column='body_mass_g',aggfunc='mean'"
# names with spaces (quote them) — illustrative column names, not from a bundled dataset
pytae data.parquet -group_by "Scenario Name" -agg "column='value',aggfunc='sum',as='v'"
pytae data.parquet -group_by "Scenario Name" -agg "column='value,val_growth',aggfunc='sum'"
```

> `-agg` requires `-group_by`. `-group_x` takes `group=` itself (or still accepts `-group_by` if `group=` is omitted). One output per source column per `-agg` call — for several aggs on the same column, use `-agg_df`. `-agg_df` and `-agg` cannot be combined.

---

<a id="group-x"></a>
## Broadcast — `-group_x` / `.group_x()`

Keeps **every row** and adds a column (`n` = group size, `x` = another aggregate). Like pandas `transform`. `-agg` collapses; `-group_x` does not.

```python
df.group_x()
df.group_x(group=["species"])
df.group_x(group=["species"], v="body_mass_g", a="max")
```

```bash
pytae penguins.parquet -group_x
pytae penguins.parquet -group_x "group='species'"
pytae penguins.parquet -group_x "group='species',v='body_mass_g',a='max'"
pytae penguins.parquet -group_x "group='species,island',v='body_mass_g',a='max'"
# illustrative: quoting names with spaces (the bundled penguins columns use underscores, not spaces)
pytae data.parquet -group_x "group='bill length mm',v='body mass g',a='max'"
pytae data.parquet -group_x "group='bill length mm,island'"
```

You do **not** need `-group_by` for `-group_x` (`-group_by` is for `-agg`).

```text
# before
  species    sex  body_mass_g
   Adelie   Male       3750.0
   Adelie Female       3800.0
   Gentoo Female       4500.0
   Gentoo   Male       5700.0

# after  -group_x "group='species',v='body_mass_g',a='max'"
  species    sex  body_mass_g      x
   Adelie   Male       3750.0 3800.0
   Adelie Female       3800.0 3800.0
   Gentoo Female       4500.0 5700.0
   Gentoo   Male       5700.0 5700.0
```

---

<a id="value-counts"></a>
## Value counts — `-value_counts`

Counts across the current working columns (`-select` first to choose keys). Several columns → unique combinations.

```bash
pytae penguins.parquet -select species -value_counts
pytae penguins.parquet -select species,island -value_counts
pytae penguins.parquet -select species -value_counts -dropna false
pytae penguins.parquet -select species -value_counts -sort_by count desc
```

---

<a id="unique"></a>
## Unique rows — `-unique`

```bash
pytae penguins.parquet -unique
pytae penguins.parquet -select species,island -unique
pytae penguins.parquet -unique -shape
```

---

<a id="listing"></a>
## Listing — `-cols` / `-dtype` / `-nulls`

File (or `-select`) order by default. Optional `asc` / `desc` sorts **names**, not rows. That is not `-sort_by`.

```bash
pytae penguins.parquet -cols
pytae penguins.parquet -cols asc
pytae penguins.parquet -cols desc
pytae penguins.parquet -dtype desc
pytae penguins.parquet -nulls asc
pytae penguins.parquet -select dtype=numeric -cols
```

CSV/TXT `-dtype` infers types from the first 10,000 rows, not the whole file.

---

<a id="sort-by"></a>
## Sorting rows — `-sort_by`

```bash
pytae penguins.parquet -sort_by body_mass_g
pytae penguins.parquet -sort_by body_mass_g desc
pytae penguins.parquet -sort_by species,body_mass_g desc
pytae penguins.parquet -select species,body_mass_g -sort_by body_mass_g desc -head 5
```

---

<a id="handle-missing"></a>
## Missing values — `-handle_missing` / `.handle_missing()`

Object/category NA → `.` (or the fill you pass); numeric NA → `0`. Also strips object columns.

```python
df.handle_missing()
df.handle_missing(fillna="NA")
```

```bash
pytae penguins.parquet -handle_missing -head
pytae penguins.parquet -handle_missing NA -select species,sex -value_counts
```

---

<a id="reshape"></a>
## Reshape — `-long` / `-wide`

Same as `df.long()` / `df.wide()`. `-long` melts numeric columns; id columns stay. `-wide` pivots a long column into headers. Defaults: `c=variable`, `v=value`. Quote the spec when values have spaces.

```bash
pytae penguins.parquet -long
pytae penguins.parquet -long "c='metric',v='reading'"

# create a long-form file first, then pivot it back with -wide
pytae penguins.parquet -long -convert -o tall.csv
pytae tall.csv -wide

# -wide's c=/v= just need to match your own long-form file's column names (illustrative):
pytae tall.csv -wide "c='metric',v='reading'"
pytae tall.csv -wide "c='country',v='balance',a='mean'"
pytae tall.csv -wide "c='country name',v='body mass'"
```

---

<a id="crosstab"></a>
## Cross-tabulation — `-crosstab`

A matrix version of `-value_counts` for two columns (pandas `pd.crosstab()`): one column's values become rows, the other's become headers. Only single columns for `index=`/`columns=` — no multi-column headers. Honors the shared `-dropna` flag.

```python
pd.crosstab(df["species"], df["island"])
pd.crosstab(df["species"], df["island"], margins=True)
pd.crosstab(df["species"], df["sex"], normalize="index")
pd.crosstab(df["species"], df["sex"], values=df["body_mass_g"], aggfunc="mean")
```

```bash
# counts
pytae penguins.parquet -crosstab "index='species',columns='island'"

# row/column/overall percentages instead of counts
pytae penguins.parquet -crosstab "index='species',columns='sex',normalize='index'"
pytae penguins.parquet -crosstab "index='species',columns='sex',normalize='columns'"
pytae penguins.parquet -crosstab "index='species',columns='sex',normalize='all'"

# grand-total row/column
pytae penguins.parquet -crosstab "index='species',columns='island',margins=true"

# aggregate a numeric column instead of counting (values= and aggfunc= go together)
pytae penguins.parquet -crosstab "index='species',columns='sex',values='body_mass_g',aggfunc='mean'" -round 1

# filter first, then cross-tab what's left
pytae penguins.parquet -qry "'island': 'Biscoe'" -crosstab "index='species',columns='sex'"

# keep NA index/column values as their own row/column
pytae penguins.parquet -crosstab "index='species',columns='sex',dropna=false"
```

> `values=` and `aggfunc=` must be given together — pandas needs both to aggregate, or neither to just count.

---

<a id="convert"></a>
## Conversion — `-convert`

Output format is the `-o` extension. Omitting `-o` writes `.csv` next to the source. Cannot write `.sas7bdat`.

| Format | Read | Write |
|---|---|---|
| `.parquet` / `.pq` | ✓ | ✓ |
| `.csv` | ✓ | ✓ |
| `.txt` | ✓ | ✓ |
| `.dat` | ✓ | ✓ |
| `.sas7bdat` | ✓ | — |

```bash
pytae penguins.parquet -convert
pytae penguins.parquet -convert -o penguins.txt
pytae penguins.parquet -select species,body_mass_g -convert -o subset.parquet
pytae penguins.csv -convert -o penguins.parquet
pytae data.sas7bdat -convert -o data.parquet          # character columns decoded as utf-8
pytae data.sas7bdat -encoding latin-1 -convert -o data.parquet
pytae data.txt -dlim "|" -convert -o data.csv
pytae data.dat -convert -o data.csv                   # .dat defaults to '|' delimiter
pytae 'data/*.parquet' -convert
pytae penguins.parquet -convert -rename "old_name:new_name,another:clean"
pytae data.csv -encoding latin-1 -convert -o data.parquet
```

> **`-dlim`:** `.csv` / `.txt` / `.dat` / `.sas7bdat` only. Defaults: `,` for csv, tab for txt, `|` for dat. Common: `|`, `;`, `:`, `~`.
>
> ```bash
> pytae data.txt -dlim "|" -head
> pytae data.csv -dlim ";" -convert -o data.parquet
> ```

> **`-encoding`:** if the file can't be decoded with the current encoding, pytae reports the
> failing encoding and suggests common alternatives to try (`utf-8`, `utf-8-sig`, `latin-1`, `cp1252`).

---

<a id="display-extras"></a>
## Display extras

```bash
pytae penguins.parquet -head -pretty
pytae penguins.parquet -describe -round 2
pytae penguins.parquet -head 20 -nrows 1000
pytae penguins.parquet -sample 10
pytae penguins.parquet -sample 10 -seed 42       # reproducible: same rows every run
pytae penguins.parquet -sample -frac 0.1         # 10% of rows instead of a fixed count
pytae penguins.parquet -sample -frac 0.1 -seed 42
pytae penguins.parquet -tail 3
pytae penguins.parquet -head -to_clip          # copy; no stdout
pytae penguins.parquet -shape -to_clip
pytae huge.csv -convert -o huge.parquet -progress
```

`-to_clip` copies **only the last** clipboard-able op (`-head 5 -tail 5 -to_clip` copies the tail). Do not combine `-to_clip -shape` with a table-producing flag.

---

<a id="recipes"></a>
## Recipes

```bash
# inspect a new file
pytae penguins.parquet -shape
pytae penguins.parquet -cols
pytae penguins.parquet -dtype
pytae penguins.parquet -nulls
pytae penguins.parquet -info
pytae penguins.parquet -describe
pytae penguins.parquet -head
pytae penguins.parquet -tail
pytae penguins.parquet -sample

# Adelie penguins, mean of numeric columns by the remaining (island, sex) groups
pytae penguins.parquet -qry "'species': 'Adelie'" -agg_df mean

# heaviest 5 after ranking
pytae penguins.parquet -select species,body_mass_g -sort_by body_mass_g desc -head 5

# species counts, then sort the count table
pytae penguins.parquet -select species -value_counts -sort_by count desc

# subset + convert
pytae penguins.parquet -qry "'island': 'Dream'" -select species,island,body_mass_g -convert -o dream.parquet

# batch csv next to each parquet
pytae 'folder/*.parquet' -convert
```

---

<a id="flag-reference"></a>
## Flag reference

**Inspect & display**

| Flag | Description |
|---|---|
| `-head N` | First N rows (default 5) |
| `-tail N` | Last N rows (default 5) |
| `-sample N` | N random rows (default 5) |
| `-seed N` | Random seed for `-sample` (reproducible rows) |
| `-frac P` | Sample a fraction of rows (0 < P <= 1) instead of `-sample`'s N |
| `-shape` | `(rows, cols)` |
| `-cols [asc\|desc]` | Column names (default: file order) |
| `-dtype [asc\|desc]` | Dtypes (CSV/TXT: first 10k rows) |
| `-nulls [asc\|desc]` | Null counts |
| `-describe` | pandas `describe()` summary (becomes the working frame) |
| `-info` | pandas `info()` (columns, non-nulls, dtypes, memory) |
| `-value_counts` | Counts across current working columns |
| `-unique` | Drop duplicate rows |

**Select & filter**

| Flag | Description |
|---|---|
| `-select SPEC` | Restrict columns at this point in the pipeline (union in one spec; repeat to filter remaining) |
| `-qry CONDITIONS` | Filter rows at this point (`df.qry()`); surrounding `{}` optional |
| `-query EXPR` | Filter rows at this point (`df.query()`) |
| `-sort_by COLUMNS [asc\|desc]` | Sort rows (default: ascending) |

**Aggregate & reshape**

| Flag | Description |
|---|---|
| `-agg_df [AGGFUNC]` | Auto-group aggregate; groups by non-numeric columns (default: `sum`) |
| `-group_by COLUMNS` | Explicit groups for `-agg` (optional fallback for `-group_x`) |
| `-agg KEY=VALUE,...` | Named aggregation with `-group_by` (`column`, `aggfunc`, optional `as`) |
| `-group_x [KEY=VALUE,...]` | Broadcast group agg (`group`, `v`, `a`) |
| `-handle_missing [FILL]` | Fill NA (default `.` / `0`) |
| `-long [KEY=VALUE,...]` | Melt numeric columns (`c`, `v`) |
| `-wide [KEY=VALUE,...]` | Pivot long to wide (`c`, `v`, `a`, `dropna`) |
| `-crosstab KEY=VALUE,...` | Cross-tabulate two columns (`index`, `columns`, optional `values`+`aggfunc`, `normalize`, `margins`) |
| `-dropna true\|false` | Drop NA keys for `-agg_df`/`-agg`/`-value_counts`/`-crosstab` (default true) |

**Convert & I/O**

| Flag | Description |
|---|---|
| `-convert` | Convert to another format (extension inferred from `-o`, defaults to `.csv`) |
| `-o, --output PATH` | Output path for `-convert` |
| `-nrows N` | Cap rows loaded |
| `-dlim CHAR` | Delimiter for csv/txt/dat/sas7bdat |
| `-encoding ENC` | Text encoding (SAS default: utf-8; csv/txt/dat: pandas infer) |
| `-rename old:new,...` | Rename columns on convert |

**Output formatting**

| Flag | Description |
|---|---|
| `-pretty` | Markdown table |
| `-round N` | Round numeric print/copy |
| `-to_clip` | Copy last result; suppress stdout |
| `-progress` | Progress for large converts |

