# pytae — CLI Reference

Inspect and convert tabular files (`.parquet`, `.csv`, `.txt`, `.dat`, `.sas7bdat`). The CLI is the same verbs as the library: `qry()`, `select()`, `agg_df()`, `group_x()`, `handle_missing()`, `long()`, `wide()`.

## Contents

- [Basics](#basics)
- [Sample datasets](#sample-datasets)
- [Column selection — `-select`](#select)
- [Row filtering — `-qry` / `-query`](#filtering)
- [SQL — `-sql`](#sql)
- [Value replacement — `-replace`](#replace)
- [Aggregation (auto group columns) — `-agg_df`](#agg-df)
- [Aggregation (explicit group columns) — `-group_by` + `-agg`](#group-by-agg)
- [Broadcast — `-group_x`](#group-x)
- [Value counts — `-value_counts`](#value-counts)
- [Unique rows — `-unique`](#unique)
- [Listing — `-cols` / `-dtype` / `-nulls`](#listing)
- [Sorting rows — `-sort_by`](#sort-by)
- [Missing values — `-handle_missing`](#handle-missing)
- [Header cleanup — `-clean_columns`](#clean-columns)
- [Reshape — `-long` / `-wide`](#reshape)
- [Cross-tabulation — `-crosstab`](#crosstab)
- [Multi-file merge — `-file` / `-merge`](#merge)
- [Conversion — `-convert` / `-rename`](#convert)
- [Display extras](#display-extras)
- [Pandas defaults vs pytae-specific](#pandas-vs-pytae)
  - [`-wide` vs `-crosstab`](#wide-vs-crosstab)
  - [`-agg_df` vs `-group_by` + `-agg`](#agg-df-vs-group-by-agg)
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

<a id="sql"></a>
## SQL — `-sql`

`-sql` runs a real SQL query against the current view at this point in the pipeline, using [duckdb](https://duckdb.org/) (an optional dependency — install with `pip install pytae[sql]`). The view is queryable as table **`df`, and only `df`** — the file itself is already named on the command line (`pytae penguins.parquet ...`), so there's no separate file-derived alias to remember (and no ambiguity if you later pipe a differently-named file through the same command). `table` is also deliberately not registered: it's a reserved SQL keyword, so `select * from table` fails to parse unless quoted, which defeats the point of a short default name.

Unlike `-qry`, this is **standard SQL**, not pytae's dict syntax — column names with spaces need **double** quotes (`"bill length mm"`), not single quotes. Single quotes are string literals in SQL, e.g. `'Adelie'`; using them around a column name either errors or silently compares against a constant string instead of the column.

```bash
pytae penguins.parquet -sql "select species, body_mass_g from df where body_mass_g > 3500"
pytae penguins.parquet -sql "select species, avg(body_mass_g) as avg_mass from df group by species"

# a column name with a space: double quotes, not single quotes
pytae data.parquet -sql 'select species from df where "bill length mm" > 40'

# chains like any other op — runs on the current view, replaces it
pytae penguins.parquet -select species,island,body_mass_g -sql "select * from df where island = 'Dream'" -shape

# a query that needs BOTH a double-quoted identifier (space in the column name)
# and a single-quoted string literal — escape the identifier's inner double quotes
pytae penguins.parquet -select species,island,body_mass_g -sql "select \"col a\" from df where island = 'Dream'" -shape
```

Mixing a spaced identifier and a string literal in one `-sql` value means the shell has to see both `"` and `'` — one of them needs escaping. Two ways to handle it:

- **Escape in place** (above): wrap the whole `-sql` value in double quotes and escape the identifier's quotes (`\"col a\"`); the string literal's single quotes pass through untouched.
- **Rename the column first, then no quoting needed.** `-rename` only applies at `-convert`/write time (see [Convert / rename](#convert)), not mid-pipeline, so this is a two-step workflow — convert once to a space-free schema, then run `-sql` against that file with plain identifiers:

  ```bash
  pytae penguins.parquet -convert -rename "col a:col_a" -o clean.parquet
  pytae clean.parquet -sql "select col_a from df where island = 'Dream'"
  ```

---

<a id="replace"></a>
## Value replacement — `-replace`

`-replace` swaps cell values at this point in the pipeline, same as `df.replace()`. Its value is `key=value` tokens (comma-separated, quote a value if it needs an internal comma — same convention as `-crosstab`'s `index=`):

- `v=` (**required**) — the `old:new` mapping, comma-separated pairs, e.g. `v='old:new,alpha:bravo'`.
- `c=` (optional) — restrict the replace to specific columns, e.g. `c='col a,col b'`. Omit it to replace across every column, like plain `df.replace()`.
- `exact=` (optional, `true`/`false`, default `true`) — `true` only replaces a cell whose **entire value** matches a key exactly; `false` replaces a key **anywhere it occurs as a substring**, leaving the rest of the cell untouched (keys are escaped so they're matched literally, not as regex patterns).

```bash
# whole df, exact match only
pytae data.parquet -replace "v='a magician:the magic,alpha:bravo'"

# only touch col a and colb
pytae data.parquet -replace "c='col a,colb',v='a magician:the magic,alpha:bravo'"

# substring match: replaces the key wherever it appears inside a cell
pytae data.parquet -replace "v='a magician:the magic,alpha:bravo',exact=false"
```

With `exact=true` (default), a cell like `"not a magician exactly"` is left unchanged because it isn't *exactly* `"a magician"`. With `exact=false`, that same cell becomes `"not the magic exactly"` — but watch out for partial-word matches: a short key like `alpha` will also match inside `"analphabet"`, turning it into `"anbravobet"`.

Chains like any other op — runs on the current view and replaces it, so put `-replace` before/after `-select`/`-qry` depending on whether you want it scoped to a narrower view.

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

<a id="clean-columns"></a>
## Header cleanup — `-clean_columns`

`-clean_columns` cleans up messy column **header names** (not cell values — see [`-replace`](#replace) for that). Its value is `key[=value]` tokens, comma-separated, applied in a fixed order regardless of how you write them: **strip → strip_special → squeeze → fill → case → dedupe**.

| Key | Type | Bare (no `=value`) | Default when omitted |
|---|---|---|---|
| `strip` | bool | means `true` | `false` — trims leading/trailing whitespace |
| `strip_special` | bool | means `true` | `false` — removes anything that isn't a letter, digit, underscore, or whitespace (e.g. `%`, `$`, `#`, `!`, parentheses) |
| `squeeze` | bool | means `true` | `false` — collapses runs of internal whitespace to a single space |
| `fill` | string | defaults to `'_'` | omit the key entirely for **no fill** (whitespace left as-is) |
| `case` | `lower`\|`upper`\|`proper` | **not allowed** — always needs a value | omitted — case left unchanged |
| `dedupe` | bool | means `true` | `false` — numbers collisions after cleaning: `revenue`, `revenue_1`, `revenue_2`, … |

`fill` replaces **each individual whitespace character** with the fill string — not each *run* of whitespace. That means `"col   b"` (3 spaces) with `fill` alone becomes `"col___b"` (3 underscores); add `squeeze` first to collapse it to one separator instead.

```bash
# strip ends, fill remaining whitespace with '_' (default), lowercase
pytae data.parquet -clean_columns "strip,fill,case=lower"

# custom fill character instead of the default '_'
pytae data.parquet -clean_columns "fill='$'"   # "col a" -> "col$a"

# Proper/Title Case, no fill (spaces are left alone)
pytae data.parquet -clean_columns "case=proper"   # "col a" -> "Col A"

# collapse repeated internal whitespace and strip punctuation before filling,
# then number any resulting duplicate names
pytae data.parquet -clean_columns "strip,squeeze,strip_special,fill,case=lower,dedupe=true"
```

With the last example, headers `"  Col A  "`, `"col   b"`, `"Col A"`, `"100% Match!"` become `col_a`, `col_b`, `col_a_1` (deduped against the first `col_a`), and `100_match` (the `%`/`!` punctuation is stripped by `strip_special` before the remaining space is filled).

Chains like any other op — runs on the current view and replaces its column names, so put it before/after `-select` depending on whether you want to select by the original or cleaned names.

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

A matrix version of `-value_counts` for two columns (pandas `pd.crosstab()`): one or more columns become rows, a single column becomes headers. `index=` accepts a comma-separated list for a multi-level row index (like `-group_by`); `columns=` stays a single column — no multi-column headers. Honors the shared `-dropna` flag.

```python
pd.crosstab(df["species"], df["island"])
pd.crosstab(df["species"], df["island"], margins=True)
pd.crosstab(df["species"], df["island"], margins=True, margins_name="Total")
pd.crosstab(df["species"], df["sex"], normalize="index")
pd.crosstab(df["species"], df["sex"], values=df["body_mass_g"], aggfunc="mean")
pd.crosstab([df["species"], df["island"]], df["sex"])
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

# rename the totals row/column (requires margins=true)
pytae penguins.parquet -crosstab "index='species',columns='island',margins=true,margins_name='Total'"

# aggregate a numeric column instead of counting (values= and aggfunc= go together)
pytae penguins.parquet -crosstab "index='species',columns='sex',values='body_mass_g',aggfunc='mean'" -round 1

# filter first, then cross-tab what's left
pytae penguins.parquet -qry "'island': 'Biscoe'" -crosstab "index='species',columns='sex'"

# multi-level row index (comma-separated), single-column headers
pytae penguins.parquet -crosstab "index='species,island',columns='sex'"

# keep NA index/column values as their own row/column — dropna is the shared top-level flag, not a spec key
pytae penguins.parquet -crosstab "index='species',columns='sex'" -dropna false
```

> `values=` and `aggfunc=` must be given together — pandas needs both to aggregate, or neither to just count.

---

<a id="merge"></a>
## Multi-file merge — `-file` / `-merge`

Everything above operates on **one** file (the positional `path`). `-file` + `-merge` are a separate mode for joining **two named files** into a single pipeline (pandas `merge()`). They must be used **together**, and **replace** the positional `path` entirely — you can't mix a positional path with `-file`.

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -merge "left=df1,right=df2,on='col a:cola,colb:colb',how=inner"
```

### `-file` — load named inputs

Value is `;`-separated entries (at least two), each `PATH=ALIAS` optionally followed by `,dlim=`/`,encoding=` overrides for reading *that* file (handy when joining mismatched formats, e.g. a pipe-delimited `.txt` with a `.csv`):

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" ...
pytae -file "sales.txt=sales,dlim='|'; customers.csv=customers,encoding='latin-1'" ...
```

### `-merge` — join two `-file` aliases

Must be the **first** operation when `-file` is used (it's what creates the pipeline's starting DataFrame — everything after it, `-select`/`-shape`/`-o`/etc., runs on the merged result exactly like the single-file mode). Value is `key=value` tokens:

| Key | Required? | Meaning |
|---|---|---|
| `left=` / `right=` | required | the two `-file` aliases to join |
| `on=` | required | shared join column(s) (comma list) when names match on both sides, or `left:right` pairs when they differ — **quote the whole value** if it has more than one column/pair, e.g. `on='col a:cola,colb:colb'` |
| `how=` | optional (default `inner`) | `inner`/`left`/`right`/`outer`/`cross`, passed straight to pandas `merge()` |
| `validate=` | optional | e.g. `one_to_one`/`one_to_many`/`many_to_one`/`many_to_many`, passed straight to pandas `merge()` |

```bash
# join column names differ between the two files
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -merge "left=df1,right=df2,on='col a:cola',how=inner"

# join column name is shared, outer join, then keep going like any other pipeline
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on='id',how=outer" -select id,x,y -shape

# validate the join is truly one-to-one, erroring otherwise
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on='id',validate=one_to_one"
```

`-convert` after a merge requires `-o`/`--output` explicitly (there's no single source file to derive a default `.csv` name from). Glob-pattern batch mode (`pytae 'data/*.parquet' -convert`) is a different, unrelated feature — it can't be combined with `-file`/`-merge`.

---

<a id="convert"></a>
## Conversion — `-convert` / `-rename`

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
pytae penguins.parquet -convert -rename "old name:new_name,another:clean"      # spaces in a name are fine — only "," and ":" are delimiters
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

<a id="pandas-vs-pytae"></a>
## Pandas defaults vs pytae-specific

Some flags/keys are thin passthroughs to standard pandas methods and parameter names — pandas knowledge transfers directly. Others are pytae's own vocabulary layered on top. Knowing which is which tells you what to expect.

**Pandas defaults** — same names, same behavior as plain pandas:

| Flag / key | Pandas equivalent |
|---|---|
| `-query` | `df.query()` |
| `-describe` / `-info` / `-shape` / `-cols` / `-dtype` / `-nulls` | `df.describe()` / `df.info()` / `df.shape` / `df.columns` / `df.dtypes` / `df.isna().sum()` |
| `-sort_by` | `df.sort_values()` |
| `-unique` | `df.drop_duplicates()` |
| `-crosstab`'s `values=` / `aggfunc=` / `normalize=` / `margins=` | same keyword names as `pd.crosstab()` |
| `-group_by` + `-agg`'s `aggfunc=` values (`'mean'`, `'sum'`, `'size'`, …) | real pandas aggfunc names, passed straight to `groupby().agg()` |
| `-wide`'s `a=` (aside from `'n'`) | passed straight to `pivot_table(aggfunc=...)` |
| `-dropna` | pandas' own `dropna=` parameter, already shared by `groupby()`/`value_counts()`/`crosstab()` — pytae just exposes it once instead of repeating it per flag |

**pytae-specific** — pytae's own conventions, not pandas itself:

| Flag / key | pytae convention |
|---|---|
| `-qry` | dict-based filter syntax (`'col': ('>', 5)`) — pytae's own `qry()`, not a pandas method |
| `-sql` | real SQL via duckdb (not pandas) — the current view is registered as table `df` only (no file-derived alias) |
| `-select`'s `contains=` / `startswith=` / `endswith=` / `regex=` / `dtype=` / `exclude_dtype=` | pytae's own column-picking vocabulary; no equivalent shorthand in plain pandas |
| `-agg_df` | auto-detects group columns (every non-numeric column becomes a group key) — pandas' `groupby()` always requires you to name them |
| `-group_x` | broadcasts a group aggregate to every row via `group=`/`v=`/`a=` keys — wraps pandas `transform()` as a ready-made verb |
| `-long` / `-wide`'s `c=`/`v=`/`a=` | pytae's short names for what pandas calls `var_name`/`value_name` (`melt()`) and `columns`/`values`/`aggfunc` (`pivot_table()`) — see below |
| `'n'` | pytae-only token meaning "row count" (aliases pandas' `'size'` internally) |
| `-handle_missing` | pytae's own opinionated fill convention (`.` for object/category, `0` for numeric) |

**`c=` / `v=` / `a=`** are pytae's short, consistent names for the same underlying pandas reshape/pivot parameters, reused across `-long`, `-wide`, and `-group_x`:

```python
# pandas
df.melt(id_vars=[...], value_vars=[...], var_name="metric", value_name="reading")
df.pivot_table(index=[...], columns="metric", values="reading", aggfunc="mean")

# pytae — same operations, shorter/consistent keys
df.long(c="metric", v="reading")
df.wide(c="metric", v="reading", a="mean")
```

```bash
pytae penguins.parquet -long "c='metric',v='reading'" -convert -o metrics.csv
pytae metrics.csv -wide "c='metric',v='reading',a='mean'"
```

`'n'` is recognized by `-agg_df`, `-group_x` (its default), and `-wide`'s `a=` — but **not** by `-agg`'s `aggfunc=`, which passes straight to pandas and only understands real aggfunc names (use `aggfunc='size'` there instead):

```bash
pytae penguins.parquet -group_by species -agg "column='body_mass_g',aggfunc='n'"     # errors — 'n' isn't a pandas aggfunc
pytae penguins.parquet -group_by species -agg "column='body_mass_g',aggfunc='size'"  # works — real pandas name
```

<a id="wide-vs-crosstab"></a>
### `-wide` vs `-crosstab`

**Use `-wide` almost always.** It handles both "pivot an existing value column" and, with `a='n'`, "pivot a count" directly — no `-value_counts` step needed. Reach for `-crosstab` only when you need `normalize=` (row/column/overall percentages) or `margins=` (grand-total row/column) — `-wide` has no equivalent for either.

```bash
# counting combinations as a matrix — the same result, two ways
pytae penguins.parquet -select species,island,sex -wide "c='island',v='sex',a='n'"         # -wide (one step)
pytae penguins.parquet -crosstab "index='species',columns='island'"                        # -crosstab (one step)

# aggregating a numeric column as a matrix — the same result, two ways
# (-wide's index is implicit — every column except c=/v= — so -select first to trim to just the id column)
pytae penguins.parquet -select species,sex,body_mass_g -wide "c='sex',v='body_mass_g',a='mean'"        # -wide
pytae penguins.parquet -crosstab "index='species',columns='sex',values='body_mass_g',aggfunc='mean'"   # -crosstab

# percentages and totals — only -crosstab does this
pytae penguins.parquet -crosstab "index='species',columns='island',normalize='index'"   # row percentages
pytae penguins.parquet -crosstab "index='species',columns='island',margins=true"        # grand totals
```

> Unlike `-crosstab`, `-wide` shows missing combinations as `NaN` rather than `0`.

| Need | Use |
|---|---|
| Pivot an existing value column | `-wide` |
| Pivot a count | `-wide` (`a='n'`) |
| Row/column/overall percentages | `-crosstab` (`normalize=`) |
| Grand-total row/column | `-crosstab` (`margins=`) |

<a id="agg-df-vs-group-by-agg"></a>
### `-agg_df` vs `-group_by` + `-agg`

**Use `-agg_df` for a quick summary** — it auto-detects group columns (every non-numeric column) and aggregates the rest with minimal typing. Reach for `-group_by` + `-agg` when you need to group by a **numeric** column, want **custom output names**, or don't want every non-numeric column swept into the group key.

```bash
# same result, two ways
pytae penguins.parquet -select species,body_mass_g -agg_df mean                       # -agg_df (auto group: species)
pytae penguins.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean'"   # -group_by + -agg (explicit)

# custom output column name — only -group_by + -agg can do this
pytae penguins.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean',as='avg_mass'"

# group by a numeric column — -agg_df can't, it always groups by every non-numeric column
pytae flights.parquet -group_by year -agg "column='passengers',aggfunc='sum'"
```

`flights.parquet` only has one non-numeric column (`month`), so `-agg_df` groups by that and — since `year` is numeric — treats it as a value to *sum* instead of a group key, producing meaningless totals:

```bash
pytae flights.parquet -agg_df sum   # groups by month, sums year (23454, ...) — not what you want
```

| Need | Use |
|---|---|
| Quick summary, auto group by all non-numeric columns | `-agg_df` |
| Same aggfunc across several numeric columns at once | `-agg_df`, or `-agg`'s comma-separated `column=` |
| Group by a numeric column | `-group_by` + `-agg` (`-agg_df` always groups by non-numeric columns only) |
| Custom output column names | `-group_by` + `-agg` (`as=`) — `-agg_df` can only rename the `'n'` count column |
| Row count | Either — `-agg_df`'s `a='n'`, or `-agg`'s `aggfunc='size'` (`'n'` isn't recognized by `-agg`) |

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
| `-sql QUERY` | Run a SQL query at this point via duckdb; view is table `df` |
| `-replace KEY=VALUE,...` | Replace values at this point (`df.replace()`); `v=` required, `c=`/`exact=` optional |
| `-clean_columns KEY=VALUE,...` | Clean header names, in order strip -> strip_special -> squeeze -> fill -> case -> dedupe |
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
| `-wide [KEY=VALUE,...]` | Pivot long to wide (`c`, `v`, `a` — `'n'` aliases `'size'`, `dropna`) |
| `-crosstab KEY=VALUE,...` | Cross-tabulate into a matrix (`index` comma-separated list, `columns` single column, optional `values`+`aggfunc`, `normalize`, `margins`, `margins_name`) |
| `-dropna true\|false` | Drop NA keys for `-agg_df`/`-agg`/`-value_counts`/`-crosstab` (default true) |

**Multi-file merge**

| Flag | Description |
|---|---|
| `-file PATH=ALIAS;...` | Load named files instead of the positional `path`; `;`-separated, each optionally followed by `,dlim=`/`,encoding=`; requires `-merge` |
| `-merge KEY=VALUE,...` | Join two `-file` aliases (`left`, `right`, `on`, optional `how` default `inner`, optional `validate`); must be the first op when using `-file` |

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

