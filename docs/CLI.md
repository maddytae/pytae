# pytae — CLI Reference

Inspect and convert tabular files (`.parquet`, `.csv`, `.txt`, `.dat`, `.sas7bdat`). The CLI mirrors pytae's library verbs — `pt.qry()`, `pt.select()`, `pt.agg_df()`, `pt.group_x()`, `pt.handle_missing()`, `pt.long()`, `pt.wide()` — plus CLI-native operations like value replacement (`-replace_values`), header cleanup (`-clean_columns`), column renaming (`-rename`), and multi-file merges/concats (`-file`/`-merge`/`-concat`).

## Contents

- [Detailed feature guides](#feature-guides)
- [Getting started](#getting-started)
  - [Basics](#basics)
  - [Sample datasets](#sample-datasets)
- [Pytae-specific operations](#pytae-specific-operations)
  - [Column selection — `-select`](#select)
  - [Drop columns — `-drop`](#drop)
  - [Row filtering — `-qry`](#qry)
  - [Mutated columns — `-mutate`](#mutate)
  - [SQL — `-sql`](#sql)
  - [Value replacement — `-replace_values`](#replace-values)
  - [Aggregation (auto group columns) — `-agg_df`](#agg-df)
  - [Broadcast — `-group_x`](#group-x)
  - [Missing values — `-handle_missing`](#handle-missing)
  - [Header cleanup — `-clean_columns`](#clean-columns)
  - [Unique rows — `-unique`](#unique)
  - [Reshape — `-long` / `-wide`](#reshape)
  - [Column renaming — `-rename`](#rename)
  - [Output routing & file I/O — `-o`](#output)
  - [Multi-file operations — `-file` / `-merge` / `-concat`](#merge)
- [Pandas-mirrored operations](#pandas-mirrored-operations)
  - [Row filtering — `-query`](#query)
  - [Aggregation (explicit group columns) — `-group_by` + `-agg`](#group-by-agg)
  - [Value counts — `-value_counts`](#value-counts)
  - [Inspect & display — `-head`/`-tail`/`-sample`/`-shape`/`-cols`/`-dtype`/`-nulls`/`-describe`/`-info`](#listing)
  - [Dataset & schema comparison — `-diff`](#diff)
  - [Sorting rows — `-sort_by`](#sort-by)
  - [Cross-tabulation — `-crosstab`](#crosstab)
- [Conventions & reference](#conventions-reference)
  - [Spec families and quoting](#quoting)
  - [Pandas defaults vs pytae-specific](#pandas-vs-pytae)
    - [`-wide` vs `-crosstab`](#wide-vs-crosstab)
    - [`-agg_df` vs `-group_by` + `-agg`](#agg-df-vs-group-by-agg)
  - [Display extras](#display-extras)
  - [Recipes](#recipes)
  - [Flag reference](#flag-reference)
- [Which flag should I use?](#which-flag)
  - [Decision table](#decision-table)
  - [Polarity chaining: `-select` vs `-drop`](#polarity-chaining)
  - [Standard parameter keys: `c=`, `v=`, `a=`](#pytae-kwargs)

---

<a id="feature-guides"></a>
## Detailed Feature Guides

For in-depth guides with complete command syntax, parameters, edge cases, and real terminal outputs, see each dedicated feature guide:

| Feature Area | Documentation Guide | Key Flags & Capabilities |
|---|---|---|
| **Inspection & Metadata** | [Inspection & Metadata Guide](cli/inspect.md) | `-head`, `-tail`, `-sample`, `-shape`, `-cols`, `-dtype`, `-nulls`, `-describe`, `-info`, `-meta`, `-pager` |
| **Column Selection** | [Column Selection & Dropping Guide](cli/select_drop.md) | `-select`, `-drop`, slices `a:b`, `contains=`, `startswith=`, `regex=`, `dtype=numeric` |
| **Row Filtering** | [Row Filtering Guide](cli/filter.md) | `-qry`, `-query`, `-dropna`, intervals `[min, max]`, set membership, comparisons |
| **Feature Engineering** | [Mutating & Computing Guide](cli/mutate.md) | `-mutate`, formulas, arithmetic, boolean indicators, `@specs.txt` |
| **SQL Engine** | [DuckDB SQL Engine Guide](cli/sql.md) | `-sql`, querying table `data`, window functions, CTEs, `@query.sql` |
| **Data Cleaning** | [Data Cleaning & Value Replacement Guide](cli/clean_replace.md) | `-clean_columns` (strip, squeeze, fill, case, dedupe), `-replace_values`, `-handle_missing`, `-rename` |
| **Aggregations & Grouping** | [Aggregations & Grouping Guide](cli/aggregate.md) | `-agg_df` (auto-detect group cols), `-group_by` + `-agg`, `-group_x` (broadcast transforms) |
| **Reshaping & Matrices** | [Reshaping & Cross-Tabulation Guide](cli/reshape.md) | `-long` (melt), `-wide` (pivot), `-crosstab` (contingency matrix), `-value_counts`, `-unique`, `-sort_by` |
| **Dataset Comparison** | [Dataset & Schema Diffing Guide](cli/diff.md) | `-diff`, shape deltas, column changes, schema drift, null count variations, cell mismatches |
| **File I/O & Compression** | [File I/O, Export, & Compression Guide](cli/export_io.md) | `-o`, `-out_dir`, `.parquet`, `.csv`, `.txt`, `.dat`, `.jsonl`, `.csv.gz`, `.jsonl.gz`, `-progress` |
| **Multi-File Pipelines** | [Multi-File Pipelines Guide](cli/multi_file.md) | `-file`, `-merge` (joins), `-concat` (stacking), cross-file `-sql` |

---

<a id="getting-started"></a>
## Getting started

The `pytae` CLI brings the expressive power of Python and SQL directly to the command line. By chaining intuitive flags that mirror library operations and SQL queries, you can inspect, filter, transform, and convert datasets with very little friction from raw data to results—without needing to write boilerplate code or Python scripts.

---

<a id="basics"></a>
### Basics

Flag **order is the pipeline**, the same as composing `pt.select` / `pt.agg_df` in order. `-select … -agg_df … -select … -shape` is `pt.select(…)` then `pt.agg_df(…)` then `pt.select(…)` then `.shape`. Put `-qry` / `-query` first yourself if you need a column you later `-drop` / `-select` away. **Only the last operation prints.** Earlier flags still run.

```bash
# first 3 rows, then shape of that 3-row frame → prints (3, n)
pytae penguins.parquet -head 3 -shape

# names only (head runs but is not printed)
pytae penguins.parquet -head 5 -cols

# filter rows, then pick columns (see Spec families and quoting)
pytae penguins.parquet -qry "species='Adelie'" -select "species,island,body_mass_g" -head 5

# average body mass per species
pytae penguins.parquet -select "species,body_mass_g" -agg_df mean

# heaviest 5 penguins, name + weight only
pytae penguins.parquet -select "species,body_mass_g" -sort_by "body_mass_g desc" -head 5

# drop columns; the rest keep file order
pytae penguins.parquet -drop "sex,island" -head 5

# ad-hoc SQL over the same file
pytae penguins.parquet -sql "select species, avg(body_mass_g) from data group by species"
```

See [Inspect & display](#listing) for the full list of inspection flags (`-head`/`-tail`/`-sample`/`-shape`/`-cols`/`-dtype`/`-nulls`/`-describe`/`-info`) and their chaining rules.

The examples below run directly against the bundled `penguins` dataset (see [Sample datasets](#sample-datasets)) — `species`, `island`, `body_mass_g`, `bill_length_mm`, …

---

<a id="sample-datasets"></a>
### Sample datasets

pytae bundles real datasets (`penguins`, `tips`, `titanic`, `diamonds`, `mpg`, `flights`, …) — the library's `pytae.sample_data` dict, keyed by name. Save any of them as a parquet file in the current folder once, then run `pytae` on it like any other file:

```bash
# one-time setup: write a bundled dataset out as a real file
python -c "import pytae; pytae.sample_data['tips'].to_parquet('tips.parquet')"
```

Do the same for any others you want to try (`penguins`, `titanic`, `diamonds`, `mpg`, `flights`, …), then use plain filenames everywhere below:

```bash
pytae tips.parquet -select "day,total_bill,tip" -group_x "group=day,v=tip,a=mean"
pytae titanic.parquet -crosstab "index=pclass,columns=survived,margins=true"
pytae diamonds.parquet -select "cut,price" -agg_df mean
pytae mpg.parquet -select "origin,mpg" -sort_by "mpg desc" -head 5
```

---

<a id="pytae-specific-operations"></a>
## Pytae-specific operations

These flags/verbs are pytae's own vocabulary — either a dedicated method the library adds (`qry()`, `sql()`, `clean_columns()`, `replace_values()`, `group_x()`) or a CLI-native capability with no direct pandas equivalent (`-file`/`-merge`/`-concat`). See [Pandas defaults vs pytae-specific](#pandas-vs-pytae) for the full flag/key-level breakdown.

---

<a id="select"></a>
### Column selection — `-select`

Tokens in one `-select` are a **union** (each token *adds* columns). Repeat `-select` to filter that result: each call is `pt.select()` on the current working columns (including after `-agg_df` / `-long` / `-wide`).

Bare tokens are column names or `start:end` slices. `key=value` tokens map to the same kwargs as `pt.select(df, ...)`.

| Token | Meaning |
|---|---|
| `species` | exact column name |
| `species,island` | several exact names |
| `bill length mm` or `'bill length mm'` | name with spaces — quoting is optional (a space is never a token separator, only `,` is); quoting only becomes *necessary* if the name itself contains a literal comma |
| `species:bill_length_mm` | slice from `species` through `bill_length_mm` |
| `dtype=numeric` | add this dtype (`numeric`, `non_numeric`, `object`, `datetime`, `bool`, `category`) |
| `contains=bill` | add names containing `bill` |
| `startswith=bill` | add names starting with `bill` |
| `endswith=_mm` | add names ending with `_mm` |
| `regex=^bill` | add names matching this regex |
| `exclude_dtype=numeric` | keep every column except this dtype (**standalone**; cannot mix with other tokens) |
| `exclude_dtype=non_numeric` | keep numeric columns only |

```python
pt.select(df, "species", "island")
pt.select(df, regex="^bill")
pt.select(df, "species", contains="bill", dtype="numeric")
pt.select(df, exclude_dtype="numeric")
```

```bash
# exact names
pytae penguins.parquet -select "species,island" -head 5
# names with spaces: inner quotes are optional (a space is never a token separator).
# Quote an individual name only if it contains a comma — see Spec families and quoting.
pytae data.parquet -select "bill length mm,body mass g" -describe

# regex (always regex= — a bare ^bill is an unknown column)
pytae penguins.parquet -select "regex=^bill" -head 5
pytae penguins.parquet -select "regex=bill|body" -describe

# dtype
pytae penguins.parquet -select "dtype=numeric" -describe
pytae penguins.parquet -select "exclude_dtype=numeric" -head 5

# name patterns (contains=bill is a token, not a Python string — no quotes)
pytae penguins.parquet -select "contains=bill" -head 5
pytae penguins.parquet -select "startswith=bill" -dtype
pytae penguins.parquet -select "endswith=_mm" -nulls

# slice
pytae penguins.parquet -select "species:bill_length_mm" -cols

# union in one -select (species, then names containing bill, then remaining numerics)
pytae penguins.parquet -select "species,contains=bill,dtype=numeric" -head 5

# repeated keys become a list (names containing bill OR body)
pytae penguins.parquet -select "contains=bill,contains=body" -cols

# a later -select filters remaining columns (numeric AND name contains bill)
pytae penguins.parquet -select "dtype=numeric" -select "contains=bill" -cols

# after another op, -select sees that op's columns (here: pick from the agg table)
pytae penguins.parquet -select "species,body_mass_g" -agg_df mean -select "species,body_mass_g" -shape
```

Exact names must exist on the **current** columns; missing names error with a typo suggestion — `-select "d,a,b"` does **not** silently return `a,b`. A positional token that is not a real column is **not** a regex — use `regex=`. Tokens in **one** spec are a union; each extra `-select` filters whatever is left (it is not last-wins).

#### `pt.select()` but not `-select`

- `everything()` — remaining columns after an explicit list
- a callable, e.g. `pt.select(df, lambda c: c.endswith("_mm"))`
- a Python `list` as one positional arg (CLI sends each name as its own string)
- `contains` / `regex` as a Python list — CLI repeats the key: `contains=bill,contains=body`

---

<a id="drop"></a>
### Drop columns — `-drop`

Subtract **exact column names**. Complements `-select`: `-select` picks (and may reorder); `-drop` removes and leaves the rest in their current order. No `dtype=` / `contains=` / `regex=` / slices — those stay on `-select`.

```python
df.drop(columns=["sex", "island"])
```

```bash
# yank known columns
pytae penguins.parquet -drop "sex,island" -head 5

# keep a shape, then pull one column out of it
pytae penguins.parquet -select "dtype=numeric,species" -drop "body_mass_g" -cols

# filter on a column, then remove it
pytae penguins.parquet -qry "species='Adelie'" -drop "species" -head
```

Same quoting as `-select` names (a space is not a separator; quote a name only to protect a comma). Missing names error with a typo suggestion. Repeat `-drop` to subtract more. Dropping every remaining column is an error.

---

<a id="qry"></a>
### Row filtering — `-qry`

pytae's keyword-based filter, `pt.qry()` — safer than `-query` for odd strings (values with spaces or special characters). **Narrows rows** at this point in the pipeline. Put it **before** `-select` / `-drop` if you need a column you then drop. Can be combined with [`-query`](#query) (stacks sequentially — AND on the remaining rows).

```python
# Keyword filtering:
pt.qry(df, species="Adelie", body_mass_g="> 3500")

# Positional string expressions or dicts (convenient for columns with spaces):
df.pt.qry("bill length mm > 40", species="Adelie")
df.pt.qry({"bill length mm": "> 40"})

# Compose with other operations:
pt.select(pt.qry(df, species="Adelie"), "species", "body_mass_g")
```

```bash
# surrounding {} are optional; string values need quotes (typed literals: 'Adelie'
# vs 3500). Direct comparisons (col > 3500), equality (col = 'val'), and operator prefixes all work!
pytae penguins.parquet -qry "species = 'Adelie', body_mass_g > 3500"
pytae penguins.parquet -qry "body_mass_g > 3500"
pytae penguins.parquet -qry "body_mass_g = > 3500"

# filter first, then drop the filter column — same as pt.qry(df, ...).drop(columns=...)
pytae penguins.parquet -qry "species = 'Adelie'" -drop "species" -head

# string-matching operators: startswith / endswith / contains / regex (search-anywhere,
# like re.search — 'regex' is 'contains' with regex=True); missing values never match (na=False)
pytae penguins.parquet -qry "species = ('startswith', 'Ad')" -head

# null checks: isna / notna are one-element tuples (no value)
pytae penguins.parquet -qry "sex = ('isna',)" -head
```

`-select "body_mass_g" -qry "species='Adelie'"` errors (`species` is already gone), matching `pt.qry(pt.select(df, "body_mass_g"), species="Adelie")`.

---

<a id="mutate"></a>
### Mutated columns — `-mutate`

pytae's expression-based column creator, `pt.mutate()`. Creates or overwrites columns at this point in the pipeline. Uses `"new_col = expression"` entries, comma- or newline-separated, quoting the key optional. Can also read specs directly from a file: `-mutate @specs.txt`.

Unlike `-qry`, the value is a pandas `eval()` **expression**, not a literal: column names in it must stay unquoted (quoting one turns it into a string literal instead of a column reference — same rule as SQL identifiers, see [Spec families and quoting](#quoting)). Columns with spaces can be enclosed in SQL-style brackets `[col a]` or backticks `` `col a` ``.

```python
# kwargs in Python:
pt.mutate(df, bmi="body_mass_g / bill_length_mm ** 2", mass_kg="body_mass_g / 1000")

# a local variable from the calling scope can be referenced with an `@` prefix,
# same as pandas' own eval()/query() — library-only, there's no local scope on the CLI
threshold = 4000
pt.mutate(df, heavy="body_mass_g >= @threshold")
```

```bash
# single mutated column
pytae penguins.parquet -mutate "bmi = body_mass_g / bill_length_mm ** 2" -head

# multiple entries in one -mutate
pytae penguins.parquet -mutate "heavy = body_mass_g > 4000, mass_kg = body_mass_g / 1000" -select "species,mass_kg,heavy" -head

# columns with spaces use [brackets] to avoid shell backtick substitution
pytae data.parquet -mutate "total = [col a] + [col b]" -head

# later entries can reference columns derived earlier in the same call
pytae penguins.parquet -mutate "mass_kg = body_mass_g / 1000, mass_lb = mass_kg * 2.20462" -select "mass_kg,mass_lb" -head

# key quoting optional (matches -qry); string literals in the expression still need quotes
pytae penguins.parquet -mutate "is_adelie = species == 'Adelie'" -select "species,is_adelie" -head

# string concat: pandas eval does not support + for strings; use .str.cat
pytae penguins.parquet -mutate "dummy = species.str.cat(island, sep='_')" -select "species,island,dummy" -head

# chains into -qry, filtering on a column just mutated
pytae penguins.parquet -mutate "bmi = body_mass_g / bill_length_mm ** 2" -qry "bmi > 2" -select "species,bmi" -head

# dplyr-style if_else(condition, true_value, false_value)
pytae penguins.parquet -mutate "weight_class = if_else(body_mass_g > 4000, 'heavy', 'light')" -select "species,weight_class" -head

# case_when supports tuples or flat pairs with default=
pytae penguins.parquet -mutate "size_class = case_when((body_mass_g >= 4500, 'large'), (body_mass_g >= 3500, 'medium'), default='small')" -select "species,size_class" -head

# coalesce(col1, col2, ..., default) — first non-null value per row
pytae data.parquet -mutate "phone = coalesce(mobile, home, 'N/A')" -head

# map(column, {key: value, ...}[, default]) — recode through a lookup dict
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'A', 'Gentoo': 'G'}, 'Other')" -select "species,code" -head

# load complex multiline specs with comments from a file
pytae penguins.parquet -mutate @features.txt -head
```

Four functional helpers are available as ordinary function calls: `if_else(condition, true_value, false_value)`, `case_when((cond1, val1), ..., default=...)` (or flat pairs `case_when(c1, v1, c2, v2, default=d)`), `coalesce(*cols, default)`, and `map(column, {key: value, ...}[, default])`. Because they are ordinary calls, they compose and chain freely with each other and with pandas methods (e.g. `.str.upper()`). String outcomes need quotes; conditions are vectorized — prefer `and`/`or`/`not` (bitwise `&`/`|`/`~` also work).

---

<a id="sql"></a>
### SQL — `-sql`

`-sql` runs a real SQL query against the current view at this point in the pipeline, using [duckdb](https://duckdb.org/) (an optional dependency — install with `pip install pytae[sql]`). Same verb in Python: `pt.sql(df, "select … from data")` / `df.pt.sql(…)` — see [docs/LIBRARY.md](LIBRARY.md). The view is queryable as table **`data`, and only `data`** — the file itself is already named on the command line (`pytae penguins.parquet ...`), so there's no separate file-derived alias to remember.

Column names with spaces can use SQL-style brackets `[bill length mm]` (recommended to avoid bash backtick substitution), double quotes (`"bill length mm"`), or backticks. Single quotes are string literals in SQL, e.g. `'Adelie'`.

Queries can also be loaded from a file using `@path.txt`:
```bash
pytae data.parquet -sql @query.txt
pytae \path\to\abc.parquet -sql '@path\to\sql_query.txt'
```

**Performance:** when `-sql` is the first thing to touch the view (nothing has filtered/selected/aggregated yet), duckdb scans the source `.parquet`/`.csv`/`.txt`/`.dat` file **directly** instead of first loading it into pandas — often several times faster, especially on CSV.

```bash
pytae penguins.parquet -sql "select species, body_mass_g from data where body_mass_g > 3500"
pytae penguins.parquet -sql "select species, avg(body_mass_g) as avg_mass from data group by species"

# bracketed identifiers avoid bash backtick execution and ugly quote escaping
pytae data.parquet -sql "select [bill length mm] from data where island = 'Dream'"

# load full query from a file (relative or absolute, with forward slashes or Windows backslashes)
pytae data.parquet -sql @query.txt
pytae \path\to\abc.parquet -sql '@path\to\sql_query.txt'

# chains like any other op — runs on the current view, replaces it
pytae penguins.parquet -select "species,island,body_mass_g" -sql "select * from data where island = 'Dream'" -shape
```

---

<a id="replace-values"></a>
### Value replacement — `-replace_values`

`-replace_values` swaps cell values at this point in the pipeline, same as `df.replace()` (or the library's `.replace_values()`). Its value is `key=value` tokens (comma-separated, quote a value if it needs an internal comma — same convention as `-crosstab`'s `index=`):

- `v=` (**required**) — the `old:new` mapping, comma-separated pairs, e.g. `v='old:new,alpha:bravo'`.
- `c=` (optional) — restrict the replace to specific columns, e.g. `c='col a,col b'`. Omit it to replace across every column, like plain `df.replace()`.
- `exact=` (optional, `true`/`false`, default `true`) — `true` only replaces a cell whose **entire value** matches a key exactly; `false` replaces a key **anywhere it occurs as a substring**, leaving the rest of the cell untouched (keys are escaped so they're matched literally, not as regex patterns).

```bash
# whole df, exact match only
pytae data.parquet -replace_values "v='a magician:the magic,alpha:bravo'"

# only touch col a and colb
pytae data.parquet -replace_values "c='col a,colb',v='a magician:the magic,alpha:bravo'"

# substring match: replaces the key wherever it appears inside a cell
pytae data.parquet -replace_values "v='a magician:the magic,alpha:bravo',exact=false"
```

With `exact=true` (default), a cell like `"not a magician exactly"` is left unchanged because it isn't *exactly* `"a magician"`. With `exact=false`, that same cell becomes `"not the magic exactly"` — but watch out for partial-word matches: a short key like `alpha` will also match inside `"analphabet"`, turning it into `"anbravobet"`.

Chains like any other op — runs on the current view and replaces it, so put `-replace_values` before/after `-select`/`-qry` depending on whether you want it scoped to a narrower view.

---

<a id="agg-df"></a>
### Aggregation (auto group columns) — `-agg_df`


Groups by all **non-numeric** columns and aggregates the rest. `n` is group count.

```python
pt.agg_df(df, "mean")
pt.agg_df(df, ["sum", "mean", "n"])
pt.agg_df(df, body_mass_g="mean", n="n")
pt.agg_df(df, a=["mean", "n"], dropna=False)  # a= required when other keywords are used
```

```bash
pytae penguins.parquet -agg_df           # defaults to sum
pytae penguins.parquet -agg_df mean
pytae penguins.parquet -agg_df "mean,sum"
pytae penguins.parquet -agg_df "body_mass_g = mean, n = n"
pytae penguins.parquet -agg_df sum -dropna false   # keep NA group keys
pytae penguins.parquet -agg_df mean -sort_by "body_mass_g desc"
```

---

<a id="group-x"></a>
### Broadcast — `-group_x`

Keeps **every row** and adds a column (`n` = group size, `x` = another aggregate). Like pandas `transform`. `-agg` collapses; `-group_x` does not.

```python
pt.group_x(df)
pt.group_x(df, group=["species"])
pt.group_x(df, group=["species"], v="body_mass_g", a="max")
```

```bash
pytae penguins.parquet -group_x
pytae penguins.parquet -group_x "group=species"
pytae penguins.parquet -group_x "group=species,v=body_mass_g,a=max"
pytae penguins.parquet -group_x "group='species,island',v=body_mass_g,a=max"
# illustrative: names with spaces (the bundled penguins columns use underscores, not spaces)
pytae data.parquet -group_x "group=bill length mm,v=body mass g,a=max"
```

You do **not** need `-group_by` for `-group_x` (`-group_by` is for `-agg`).

```text
# before
  species    sex  body_mass_g
   Adelie   Male       3750.0
   Adelie Female       3800.0
   Gentoo Female       4500.0
   Gentoo   Male       5700.0

# after  -group_x "group=species,v=body_mass_g,a=max"
  species    sex  body_mass_g      x
   Adelie   Male       3750.0 3800.0
   Adelie Female       3800.0 3800.0
   Gentoo Female       4500.0 5700.0
   Gentoo   Male       5700.0 5700.0
```

---

<a id="handle-missing"></a>
### Missing values — `-handle_missing`

Object/category NA → `.` (or the fill you pass); numeric NA → `0`. Also strips object columns.

```python
pt.handle_missing(df)
pt.handle_missing(df, fillna="NA")
```

```bash
pytae penguins.parquet -handle_missing -head
pytae penguins.parquet -handle_missing NA -select "species,sex" -value_counts
```

---

<a id="clean-columns"></a>
### Header cleanup — `-clean_columns`

`-clean_columns` cleans up messy column **header names** (not cell values — see [`-replace_values`](#replace-values) for that). Its value is `key[=value]` tokens, comma-separated, applied in a fixed order regardless of how you write them: **strip → strip_special → squeeze → fill → case → dedupe**.

| Key | Type | Bare (no `=value`) | Default when omitted |
|---|---|---|---|
| `strip` | bool | means `true` | `false` — trims leading/trailing whitespace |
| `strip_special` | bool | means `true` | `false` — removes anything that isn't a letter, digit, underscore, whitespace, or the `fill` character (e.g. `%`, `$`, `#`, `!`, parentheses, quotes); if `fill` is set, that character is kept in place instead of stripped |
| `squeeze` | bool | means `true` | `false` — collapses runs of internal whitespace to a single space |
| `fill` | string | defaults to `'_'` | omit the key entirely for **no fill** (whitespace left as-is) |
| `case` | `lower`\|`upper`\|`proper` | **not allowed** — always needs a value | omitted — case left unchanged |
| `dedupe` | bool | means `true` | `false` — numbers collisions after cleaning: `revenue`, `revenue_1`, `revenue_2`, … |

`fill` replaces **each individual whitespace character** with the fill string — not each *run* of whitespace. That means `"col   b"` (3 spaces) with `fill` alone becomes `"col___b"` (3 underscores); add `squeeze` first to collapse it to one separator instead.

```bash
# strip ends, fill remaining whitespace with '_' (default), lowercase
pytae data.parquet -clean_columns "strip,fill,case=lower"

# custom fill character instead of the default '_'
pytae data.parquet -clean_columns "fill=$"   # "col a" -> "col$a"

# Proper/Title Case, no fill (spaces are left alone)
pytae data.parquet -clean_columns "case=proper"   # "col a" -> "Col A"

# collapse repeated internal whitespace and strip punctuation before filling,
# then number any resulting duplicate names
pytae data.parquet -clean_columns "strip,squeeze,strip_special,fill,case=lower,dedupe=true"
```

With the last example, headers `"  Col A  "`, `"col   b"`, `"Col A"`, `"100% Match!"` become `col_a`, `col_b`, `col_a_1` (deduped against the first `col_a`), and `100_match` (the `%`/`!` punctuation is stripped by `strip_special` before the remaining space is filled).

`strip_special` keeps the `fill` character in place rather than stripping it — e.g. `-clean_columns "strip_special,fill='-'"` on `"co-op's data"` keeps the `-` but removes the quote, then `fill` replaces the space too, giving `"co-ops-data"`. Without `fill` set, `strip_special` removes all punctuation including quotes, same as before.

Chains like any other op — runs on the current view and replaces its column names, so put it before/after `-select` depending on whether you want to select by the original or cleaned names.

---

<a id="unique"></a>
### Unique rows — `-unique`

```bash
pytae penguins.parquet -unique
pytae penguins.parquet -select "species,island" -unique
```

---

<a id="reshape"></a>
### Reshape — `-long` / `-wide`

Same as `pt.long()` / `pt.wide()`. `-long` melts numeric columns; id columns stay. `-wide` pivots a long column into headers. Defaults: `c=variable`, `v=value`. Quote the spec when values have spaces.

```bash
pytae penguins.parquet -long
pytae penguins.parquet -long "c=metric,v=reading"

# create a long-form file first, then pivot it back with -wide
# (c=/v= must match the long-form column names — defaults are variable/value)
pytae penguins.parquet -long -o tall.csv
pytae tall.csv -wide
```

---

<a id="rename"></a>
### Column renaming — `-rename`

`-rename` renames columns anywhere in the pipeline using `old:new` translation mappings (colon-separated, matching dictionary syntax `{"old": "new"}`). Multiple mappings are comma-separated. Spaces in column names are supported directly without internal quoting:

```bash
# Rename in-place and inspect the output
pytae penguins.parquet -rename "island:location" -head

# Multiple renames, including names with spaces
pytae data.parquet -rename "bill length mm:bill_len,body mass g:body_mass" -cols

# Chain with other operations
pytae penguins.parquet -rename "species:penguin_species" -select "penguin_species,island" -head 5

# Rename during file conversion
pytae penguins.parquet -rename "island:location" -o renamed.parquet
```

- In Python: use pandas' `df.rename(columns={"old": "new"})` within an accessor chain, e.g. `df.rename(columns={"island": "location"}).pt.select(...)`.
- Colon (`:`) is strictly required for translation mappings; `=` is rejected with a helpful message.

---

<a id="output"></a>
<a id="convert"></a>
### Output routing & file I/O — `-o`, `-out_dir`

`-o` specifies the destination for the pipeline result: an explicit output file path, a format for in-place or batch conversion, or `clip` to copy to the clipboard. Omitting `-o` prints to stdout. Cannot write `.sas7bdat`.

`-out_dir` (or `-od` / `--out-dir`) directs all exported files into a target directory (auto-created if it does not exist). Requires `-o/--output`.

| Target | Description | Example |
|---|---|---|
| `<filename>.<ext>` | Write directly to specified path | `pytae penguins.parquet -o clean.csv`<br>`pytae penguins.csv -o data.parquet` |
| `csv` / `parquet` / `txt` / `dat` / `jsonl` / `csv.gz` / `jsonl.gz` | In-place or batch conversion alongside source file or into `-out_dir` | `pytae penguins.parquet -o csv`<br>`pytae data/*.parquet -o csv -out_dir exports/`<br>`pytae 'data/*.parquet' -o jsonl.gz` |
| `clip` / `clipboard` | Copy result to system clipboard (suppresses stdout) | `pytae penguins.parquet -head 5 -o clip` |

| Format | Read | Write | Notes |
|---|---|---|---|
| `.parquet` / `.pq` | ✓ | ✓ | Fast columnar storage with embedded schema |
| `.csv` | ✓ | ✓ | Standard comma-delimited text |
| `.txt` | ✓ | ✓ | Tab-delimited (default) or custom delimiter |
| `.dat` | ✓ | ✓ | Pipe-delimited `\|` and latin-1 encoded by default |
| `.jsonl` / `.ndjson` | ✓ | ✓ | Line-delimited JSON records (chunked streaming) |
| `.csv.gz` / `.txt.gz` / `.dat.gz` / `.jsonl.gz` | ✓ | ✓ | Transparent gzip compression & decompression |
| `.sas7bdat` | ✓ | — | SAS binary dataset (read-only) |

```bash
# Save to an explicit destination file
pytae penguins.parquet -o penguins.txt
pytae penguins.parquet -select "species,body_mass_g" -o subset.parquet
pytae penguins.csv -o penguins.parquet
pytae data.sas7bdat -o data.parquet          # character columns decoded as utf-8
pytae data.sas7bdat -encoding latin-1 -o data.parquet
pytae data.dat -o data.csv                   # .dat defaults to '|' delimiter, latin-1 encoding

# Export to JSON Lines or compressed gzip
pytae penguins.parquet -o penguins.jsonl
pytae penguins.csv -o penguins.csv.gz
pytae penguins.parquet -o penguins.jsonl.gz

# In-place conversion (saves data.csv next to data.parquet)
pytae penguins.parquet -o csv

# Output directory: write converted files to a specific target folder (created automatically)
pytae penguins.parquet -o csv -out_dir exports/
pytae data/*.parquet -o csv.gz -od compressed_data/

# Batch conversion (converts all matched files; works with unquoted shell glob or quoted pattern)
pytae data/*.parquet -o csv
pytae data/*.* -o csv
pytae 'data/*.parquet' -o csv

# Rename during export
pytae penguins.parquet -rename "old name:new_name,another:clean" -o clean.parquet
```

> **`-dlim`:** `.csv` / `.txt` / `.dat` only (not `.sas7bdat`, which has no delimiter concept). Defaults: `,` for csv, tab for txt, `|` for dat. Common: `|`, `;`, `:`, `~`.
>
> ```bash
> pytae data.txt -dlim "|" -head
> pytae data.csv -dlim ";" -o data.parquet
> ```

> **`-encoding`:** default is `utf-8` for `.sas7bdat`, `latin-1` for `.dat`, and pandas' own inference for `.csv`/`.txt` (usually `utf-8`). If the file can't be decoded with the current encoding, pytae reports the
> failing encoding and suggests common alternatives to try (`utf-8`, `utf-8-sig`, `latin-1`, `cp1252`).

---

<a id="merge"></a>
### Multi-file operations — `-file` / `-merge` / `-concat`

Everything above operates on **one** file (the positional `path`). `-file` + `-merge`/`-concat`/`-sql` are a separate mode for combining **two or more named files** into a single pipeline, replacing the positional `path` entirely. See **[docs/CLI_MULTI_FILE.md](CLI_MULTI_FILE.md)** for the full reference and examples.

```bash
pytae -file "data1.parquet=df1; data2.parquet=df2" \
      -merge "left=df1,right=df2,on='col a:cola,colb:colb',how=inner"
```

---

<a id="pandas-mirrored-operations"></a>
## Pandas-mirrored operations

These flags map directly onto existing pandas methods/parameters — if you already know pandas, the behavior transfers directly (some still use pytae's own `key=value` CLI syntax to express the same pandas call). See [Pandas defaults vs pytae-specific](#pandas-vs-pytae) for the exact key-name mappings.

---

<a id="query"></a>
### Row filtering — `-query`

pytae's direct passthrough to pandas `df.query()` (numexpr). **Narrows rows** at this point in the pipeline, same as `.query()`. Can be combined with [`-qry`](#qry) (stacks sequentially — AND on the remaining rows).

```python
df.query("body_mass_g > 3500 and island == 'Dream'")
```

```bash
pytae penguins.parquet -query "body_mass_g > 3500 and island == 'Dream'"
pytae penguins.parquet -qry "species='Adelie'" -query "body_mass_g > 3500" -head
```

---

<a id="group-by-agg"></a>
### Aggregation (explicit group columns) — `-group_by` + `-agg`

`groupby().agg()` with named aggregation. Collapses to one row per group.

```python
df.groupby("species", as_index=False).agg(
    avg_mass=("body_mass_g", "mean"),
    n=("body_mass_g", "size"),
)
```

```bash
pytae penguins.parquet -group_by species -agg "column=body_mass_g,aggfunc=mean"
pytae penguins.parquet -group_by species -agg "column=body_mass_g,aggfunc=mean; column=flipper_length_mm,aggfunc=sum"
pytae penguins.parquet -group_by species -agg "column=body_mass_g,aggfunc=mean,as=avg_mass; column=flipper_length_mm,aggfunc=sum,as=total_flipper"
pytae penguins.parquet -group_by "species,island" -agg "column=body_mass_g,aggfunc=mean"
# names with spaces (quote them) — illustrative column names, not from a bundled dataset
pytae data.parquet -group_by "Scenario Name" -agg "column='value,val_growth',aggfunc=sum"
```

> `-agg` requires `-group_by`. `-group_x` takes `group=` itself (or still accepts `-group_by` if `group=` is omitted). One output per source column per `-agg` call — for several aggs on the same column, use `-agg_df`. `-agg_df` and `-agg` cannot be combined.

---

<a id="value-counts"></a>
### Value counts — `-value_counts`

Counts across the current working columns (`-select` first to choose keys). Several columns → unique combinations.

```bash
pytae penguins.parquet -select "species" -value_counts
pytae penguins.parquet -select "species,island" -value_counts
pytae penguins.parquet -select "species" -value_counts -dropna false
pytae penguins.parquet -select "species" -value_counts -sort_by "count desc"
```

---

<a id="listing"></a>
### Inspect & display — `-head` / `-tail` / `-sample` / `-shape` / `-cols` / `-dtype` / `-nulls` / `-describe` / `-info` / `-meta`

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
pytae penguins.parquet -meta
```

`-shape` / `-cols` / `-dtype` / `-nulls` / `-info` / `-meta` / `-diff` mirror inspection operations that
don't return a DataFrame (`df.shape`, `df.columns`, `df.dtypes`, `df.info()`, zero-scan Parquet metadata, or text diffs). Like real method chaining, nothing may follow them except `-o clip`;
put them last. `-describe` is the exception — `df.describe()` returns a DataFrame, so it
can still be chained into further flags (e.g. `-describe -shape`, `-describe -round 2`).

```bash
pytae penguins.parquet -shape -o clip     # ok: -o clip is the only thing allowed after -shape
pytae penguins.parquet -meta -o clip      # ok: copy Parquet metadata report to clipboard
pytae penguins.parquet -shape -head 3      # error: -shape isn't a DataFrame, can't chain -head off it
pytae penguins.parquet -describe -shape    # ok: describe() returns a DataFrame
```

**Zero-scan Parquet metadata (`-meta`):**
Reads file header and footer metadata without scanning table rows. Instantly displays file size, Parquet format version, row groups count, column compression codecs, compression ratios, and full Arrow/Pandas schema.

```bash
pytae huge_dataset.parquet -meta
```

**Terminal Pager (`-pager`):**
Pipe long table views, `-describe`, or inspection reports through the system pager (`$PAGER` or `less`):

```bash
pytae wide_dataset.parquet -describe -pager
pytae data.parquet -head 100 -pager
```

`-cols` / `-dtype` / `-nulls` list in file (or `-select`) order by default. Optional `asc` / `desc` sorts **names**, not rows. That is not `-sort_by`.

```bash
pytae penguins.parquet -cols asc
pytae penguins.parquet -cols desc
pytae penguins.parquet -dtype desc
pytae penguins.parquet -nulls asc
```

CSV/TXT `-dtype` infers types from the first 10,000 rows, not the whole file.

---

<a id="diff"></a>
### Dataset & schema diffing — `-diff`

Compare the current pipeline result against another dataset file:

```bash
# Compare two files directly
pytae file_v1.parquet -diff file_v2.parquet

# Filter or transform before comparing against baseline
pytae updated.csv -query "status == 'active'" -diff baseline.parquet

# Copy diff report to clipboard
pytae file_v1.csv -diff file_v2.csv -o clip
```

The diff report provides a comprehensive summary:
1. **Shapes:** Row and column counts with exact delta (`+` / `-`).
2. **Column changes:** Added columns, removed columns, and common columns.
3. **Schema drift:** Data type differences across common columns.
4. **Null counts:** Changes in null / NaN values per column.
5. **Values:** Detects whether common cell values match identically or reports the number of cell mismatches.

---

<a id="sort-by"></a>
### Sorting rows — `-sort_by`

```bash
pytae penguins.parquet -sort_by body_mass_g
pytae penguins.parquet -sort_by "body_mass_g desc"
pytae penguins.parquet -sort_by "species,body_mass_g desc"
```

---

<a id="crosstab"></a>
### Cross-tabulation — `-crosstab`

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
pytae penguins.parquet -crosstab "index=species,columns=island"

# row/column/overall percentages instead of counts
pytae penguins.parquet -crosstab "index=species,columns=sex,normalize=index"
pytae penguins.parquet -crosstab "index=species,columns=sex,normalize=columns"
pytae penguins.parquet -crosstab "index=species,columns=sex,normalize=all"

# grand-total row/column
pytae penguins.parquet -crosstab "index=species,columns=island,margins=true"

# rename the totals row/column (requires margins=true)
pytae penguins.parquet -crosstab "index=species,columns=island,margins=true,margins_name=Total"

# aggregate a numeric column instead of counting (values= and aggfunc= go together)
pytae penguins.parquet -crosstab "index=species,columns=sex,values=body_mass_g,aggfunc=mean" -round 1

# filter first, then cross-tab what's left
pytae penguins.parquet -qry "island='Biscoe'" -crosstab "index=species,columns=sex"

# multi-level row index (comma-separated), single-column headers
pytae penguins.parquet -crosstab "index='species,island',columns=sex"

# keep NA index/column values as their own row/column — dropna is the shared top-level flag, not a spec key
pytae penguins.parquet -crosstab "index=species,columns=sex" -dropna false
```

> `values=` and `aggfunc=` must be given together — pandas needs both to aggregate, or neither to just count.

---

<a id="conventions-reference"></a>
## Conventions & reference

Cross-cutting rules and lookup tables that apply across the flags above, rather than belonging to any single one.

---

<a id="quoting"></a>
### Spec families and quoting

Every structured flag is one of two families. Wrap the **whole spec** in `""` whenever it contains a space (that is the shell's quoting, not pytae's — forget it and you get `unrecognized arguments`, with a hint).

**kwargs** — `key=value,key=value`. Used by `-select` kwargs, `-agg`, `-group_x`, `-crosstab`, `-long`/`-wide`, `-merge`, `-concat`, `-replace_values`, `-clean_columns`, `-file` extras. Quote a value only when it contains a comma. `contains=bill`, `index=species`, and `dtype=numeric` stay unquoted — they are tokens, not Python literals (`contains='bill'` is accepted, not the style).

**names and mappings** — `a,b` lists, assignments (`name=payload` for `-mutate`/`-qry`), or translation mappings (`name:payload` for `-rename` and `-replace_values`'s `v=`). `-qry` requires quotes on string values: they are typed literals (`'Adelie'` vs `3500` vs `('>', 3500)`). `-mutate` column names inside an expression must stay unquoted.

Simple flags (`-head 5`, `-sql "..."`, `-query "..."`, `-pretty`, `-dropna false`) are neither family.

```bash
# shell quoting — wrap the whole spec when it has a space
pytae penguins.parquet -select species,bill length mm -head
# pytae: error: unrecognized arguments: length mm
# wrap the whole spec in quotes, e.g. -select "col a,col b"

# kwargs: unquoted tokens; quote a value only to protect a comma
pytae penguins.parquet -select "species,contains=bill"
pytae penguins.parquet -crosstab "index=species,columns=island"
pytae penguins.parquet -crosstab "index='species,island',columns=sex"
pytae penguins.parquet -group_x "group=species,v=body_mass_g,a=max"
pytae -file "a.csv=df1;b.csv=df2" -concat "frames='df1,df2'"

# names: comma list; quote a name only to protect a comma
pytae data.parquet -select "bill length mm,body mass g"
pytae data.parquet -select "'city, state',other_col"
pytae penguins.parquet -drop "sex,island"
pytae penguins.parquet -sort_by "species,body_mass_g desc"

# assignments use '=':
pytae penguins.parquet -qry "species='Adelie', body_mass_g=('>', 3500)"
pytae penguins.parquet -mutate "bmi=body_mass_g / bill_length_mm ** 2"

# translation mappings use ':':
pytae data.parquet -rename "old col:new col" -o clean.parquet
pytae data.parquet -replace_values "v='a magician:the magic'"
```

`-clean_columns` `strip_special` removes quotes as punctuation — pair with `fill=` to keep one character (`fill='-'`).

---

<a id="pandas-vs-pytae"></a>
### Pandas defaults vs pytae-specific

Some flags/keys are thin passthroughs to standard pandas methods and parameter names — pandas knowledge transfers directly. Others are pytae's own vocabulary layered on top. Knowing which is which tells you what to expect.

**Pandas defaults** — same names, same behavior as plain pandas:

| Flag / key | Pandas equivalent |
|---|---|
| `-query` | `df.query()` |
| `-drop` | `df.drop(columns=...)` — exact names only; patterns/dtypes/slices stay on `-select` |
| `-describe` / `-info` / `-shape` / `-cols` / `-dtype` / `-nulls` | `df.describe()` / `df.info()` / `df.shape` / `df.columns` / `df.dtypes` / `df.isna().sum()` |
| `-sort_by` | `df.sort_values()` |
| `-crosstab`'s `values=` / `aggfunc=` / `normalize=` / `margins=` | same keyword names as `pd.crosstab()` |
| `-group_by` + `-agg`'s `aggfunc=` values (`'mean'`, `'sum'`, `'size'`, …) | real pandas aggfunc names, passed straight to `groupby().agg()` |
| `-wide`'s `a=` (aside from `'n'`) | passed straight to `pivot_table(aggfunc=...)` |
| `-dropna` | pandas' own `dropna=` parameter (`groupby()` / `value_counts()` / `crosstab()` / `pivot_table()`) — one top-level flag for `-agg_df`/`-agg`/`-group_x`/`-wide`/`-value_counts`/`-crosstab` |

**pytae-specific** — pytae's own conventions, not pandas itself:

| Flag / key | pytae convention |
|---|---|
| `-qry` | keyword filter syntax (`col=('>', 5)`, column-name quotes optional) — pytae's own `qry()`, not a pandas method |
| `-sql` | real SQL via duckdb (not pandas) — the current view is registered as table `data` only (no file-derived alias) |
| `-select`'s `contains=` / `startswith=` / `endswith=` / `regex=` / `dtype=` / `exclude_dtype=` | pytae's own column-picking vocabulary; no equivalent shorthand in plain pandas |
| `-agg_df` | auto-detects group columns (every non-numeric column becomes a group key) — pandas' `groupby()` always requires you to name them |
| `-group_x` | broadcasts a group aggregate to every row via `group=`/`v=`/`a=` keys — wraps pandas `transform()` as a ready-made verb |
| `-long` / `-wide`'s `c=`/`v=`/`a=` | pytae's short names for what pandas calls `var_name`/`value_name` (`melt()`) and `columns`/`values`/`aggfunc` (`pivot_table()`) — see below |
| `'n'` | pytae-only token meaning "row count" (aliases pandas' `'size'` internally) |
| `-handle_missing` | pytae's own opinionated fill convention (`.` for object/category, `0` for numeric) |
| `-unique` | pytae's own flag name for `df.drop_duplicates()` — not a mirrored pandas name |

**`c=` / `v=` / `a=`** are pytae's short, consistent names for the same underlying pandas reshape/pivot parameters, reused across `-long`, `-wide`, and `-group_x`:

```python
# pandas
df.melt(id_vars=[...], value_vars=[...], var_name="metric", value_name="reading")
df.pivot_table(index=[...], columns="metric", values="reading", aggfunc="mean")

# pytae — same operations, shorter/consistent keys
pt.long(df, c="metric", v="reading")
pt.wide(df, c="metric", v="reading", a="mean")
```

```bash
pytae penguins.parquet -long "c=metric,v=reading" -o metrics.csv
pytae metrics.csv -wide "c=metric,v=reading,a=mean"
```

`'n'` is recognized by `-agg_df`, `-group_x` (its default), and `-wide`'s `a=` — but **not** by `-agg`'s `aggfunc=`, which passes straight to pandas and only understands real aggfunc names (use `aggfunc='size'` there instead):

```bash
pytae penguins.parquet -group_by species -agg "column=body_mass_g,aggfunc=n"     # errors — 'n' isn't a pandas aggfunc
pytae penguins.parquet -group_by species -agg "column=body_mass_g,aggfunc=size"  # works — real pandas name
```

<a id="wide-vs-crosstab"></a>
#### `-wide` vs `-crosstab`

**Use `-wide` almost always.** It handles both "pivot an existing value column" and, with `a='n'`, "pivot a count" directly — no `-value_counts` step needed. Reach for `-crosstab` only when you need `normalize=` (row/column/overall percentages) or `margins=` (grand-total row/column) — `-wide` has no equivalent for either.

```bash
# counting combinations as a matrix — the same result, two ways
pytae penguins.parquet -select "species,island,sex" -wide "c=island,v=sex,a=n"         # -wide (one step)
pytae penguins.parquet -crosstab "index=species,columns=island"                        # -crosstab (one step)

# aggregating a numeric column as a matrix — the same result, two ways
# (-wide's index is implicit — every column except c=/v= — so -select first to trim to just the id column)
pytae penguins.parquet -select "species,sex,body_mass_g" -wide "c=sex,v=body_mass_g,a=mean"        # -wide
pytae penguins.parquet -crosstab "index=species,columns=sex,values=body_mass_g,aggfunc=mean"   # -crosstab
```

> Unlike `-crosstab`, `-wide` shows missing combinations as `NaN` rather than `0`.

| Need | Use |
|---|---|
| Pivot an existing value column | `-wide` |
| Pivot a count | `-wide` (`a='n'`) |
| Row/column/overall percentages | `-crosstab` (`normalize=`) |
| Grand-total row/column | `-crosstab` (`margins=`) |

<a id="agg-df-vs-group-by-agg"></a>
#### `-agg_df` vs `-group_by` + `-agg`

**Use `-agg_df` for a quick summary** — it auto-detects group columns (every non-numeric column) and aggregates the rest with minimal typing. Reach for `-group_by` + `-agg` when you need to group by a **numeric** column, want **custom output names**, or don't want every non-numeric column swept into the group key.

```bash
# same result, two ways
pytae penguins.parquet -select "species,body_mass_g" -agg_df mean                       # -agg_df (auto group: species)
pytae penguins.parquet -group_by species -agg "column=body_mass_g,aggfunc=mean"   # -group_by + -agg (explicit)

# custom output column name — only -group_by + -agg can do this
pytae penguins.parquet -group_by species -agg "column=body_mass_g,aggfunc=mean,as=avg_mass"

# group by a numeric column — -agg_df can't, it always groups by every non-numeric column
pytae flights.parquet -group_by year -agg "column=passengers,aggfunc=sum"
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

<a id="display-extras"></a>
### Display extras

```bash
pytae penguins.parquet -head -pretty
pytae penguins.parquet -describe -round 2
pytae penguins.parquet -head 20 -nrows 1000
pytae penguins.parquet -sample 10 -seed 42       # reproducible: same rows every run
pytae penguins.parquet -sample -frac 0.1         # 10% of rows instead of a fixed count
pytae penguins.parquet -head -o clip             # copy; no stdout
pytae huge.csv -o huge.parquet -progress          # default 200,000 row steps
pytae huge.csv -o huge.parquet -progress 50000    # custom chunk progress in 50k row steps
```

`-o clip` copies **only the last** clipboard-able op (`-head 5 -tail 5 -o clip` copies the tail). Non-DataFrame terminal inspection flags (`-shape`, `-cols`, `-dtype`, `-nulls`, `-info`) copy their text output to clipboard via `-o clip`, but cannot be exported to table files (`-o out.csv`).

---

<a id="recipes"></a>
### Recipes

```bash
# filter, then aggregate the remaining groups
pytae penguins.parquet -qry "species='Adelie'" -agg_df mean

# subset + export
pytae penguins.parquet -qry "island='Dream'" -select "species,island,body_mass_g" -o dream.parquet
```

---

<a id="flag-reference"></a>
### Flag reference

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
| `-meta` | Parquet file metadata (row groups, compression, schema) without loading data |
| `-diff PATH` | Compare schema and contents against another dataset file |
| `-value_counts` | Counts across current working columns |
| `-unique` | Drop duplicate rows |

**Select & filter**

| Flag | Description |
|---|---|
| `-select SPEC` | Restrict columns at this point in the pipeline (union in one spec; repeat to filter remaining) |
| `-drop COLUMNS` | Drop columns by exact name at this point (comma-separated names only; remaining keep their order) |
| `-qry CONDITIONS` | Filter rows at this point (`pt.qry()`); surrounding `{}` and column-name quotes optional |
| `-mutate SPEC` | Create/overwrite columns at this point (`pt.mutate()`); `"new_col=expression"` entries, same tokenizer/key-quoting rules as `-qry` (no surrounding `{}`), but the value is a pandas `eval()` expression, not a literal |
| `-query EXPR` | Filter rows at this point (`df.query()`) |
| `-sql QUERY` | Run a SQL query at this point via duckdb; view is table `data` (in `-file` mode, each alias is also queryable, and may be used instead of `-merge`/`-concat`) |
| `-replace_values KEY=VALUE,...` | Replace values at this point (`pt.replace_values()`); `v=` required, `c=`/`exact=` optional |
| `-clean_columns KEY=VALUE,...` | Clean header names, in order strip -> strip_special -> squeeze -> fill -> case -> dedupe |
| `-sort_by SPEC` | Sort rows by a comma-separated column list, optionally ending with `asc`/`desc` |

**Aggregate & reshape**

| Flag | Description |
|---|---|
| `-agg_df [SPEC]` | Auto-group aggregate; a name (`mean`), a comma list (`mean,sum`), or a mapping (`col=mean, n=n`); default `sum` |
| `-group_by COLUMNS` | Explicit groups for `-agg` (optional fallback for `-group_x`) |
| `-agg KEY=VALUE,...` | Named aggregation with `-group_by` (`column`, `aggfunc`, optional `as`) |
| `-group_x [KEY=VALUE,...]` | Broadcast group agg (`group`, `v`, `a`) |
| `-handle_missing [FILL]` | Fill NA (default `.` / `0`) |
| `-long [KEY=VALUE,...]` | Melt numeric columns (`c`, `v`) |
| `-wide [KEY=VALUE,...]` | Pivot long to wide (`c`, `v`, `a` — `n` aliases `'size'`); honors `-dropna` |
| `-crosstab KEY=VALUE,...` | Cross-tabulate into a matrix (`index` comma-separated list, `columns` single column, optional `values`+`aggfunc`, `normalize`, `margins`, `margins_name`) |
| `-dropna true\|false` | Drop NA keys for `-agg_df`/`-agg`/`-group_x`/`-wide`/`-value_counts`/`-crosstab` (default true) |

**Multi-file operations**

| Flag | Description |
|---|---|
| `-file PATH=ALIAS;...` | Load named files instead of the positional `path`; `;`-separated, each optionally followed by `,dlim=`/`,encoding=`; requires `-merge`, `-concat`, or `-sql` as the first op |
| `-merge KEY=VALUE,...` | Join `-file` aliases (`left`, `right`, `on`, optional `how` default `inner`, optional `validate`); repeatable, `left=`/`right=` accept `data` for the running result; or use `-sql` instead |
| `-concat KEY=VALUE,...` | Stack `-file` aliases row-wise (`frames=`, an ordered list, accepts `data` for the running result); repeatable; always resets the index |

**Output & I/O**

| Flag | Description |
|---|---|
| `-o, --output TARGET` | Output destination: `<path>.<ext>`, format (`csv`, `parquet`, `jsonl`, `csv.gz`, `jsonl.gz`), or `clip`/`clipboard` |
| `-out_dir, -od DIR` | Target directory for exported files (created if missing; requires `-o`) |
| `-nrows N` | Cap rows loaded |
| `-dlim CHAR` | Delimiter for csv/txt/dat (not sas7bdat) |
| `-encoding ENC` | Text encoding (SAS default: utf-8; dat default: latin-1; csv/txt: pandas infer) |
| `-rename OLD:NEW,...` | Rename columns anywhere in pipeline or during export |
| `-pretty` | Markdown table |
| `-pager` | Pipe table or inspect outputs through system pager (`$PAGER` or `less`) |
| `-round N` | Round numeric print/copy |
| `-progress [N]` | Row progress for large file exports (default: 200000 rows; optional N sets chunk size) |

---

<a id="which-flag"></a>
## Which flag should I use?

Use this quick-decision guide to find the right flag for your task. Each flag links directly to its detailed section in this document.

<a id="decision-table"></a>
### Decision table

| Task | Flag | Notes |
|---|---|---|
| **Pick columns** | [`-select`](#select) | Union of names, slices (`a:b`), patterns (`contains=`, `regex=`), or `dtype=`; [`-drop`](#drop) only subtracts names |
| **Drop columns** | [`-drop`](#drop) | Subtracts exact column names and preserves order; patterns and dtypes stay on [`-select`](#select) |
| **Rename columns** | [`-rename`](#rename) | Uses `old:new` mapping; works anywhere in pipeline or during export ([`-o`](#output)) |
| **Clean messy headers** | [`-clean_columns`](#clean-columns) | Standardizes header names (strip, squeeze, case, fill, dedupe); for cell values use [`-replace_values`](#replace-values) |
| **Filter rows (pytae)** | [`-qry`](#qry) | Uses `col=condition` or expressions (`body_mass_g > 3500`); handles spaces and special characters safely |
| **Filter rows (pandas)** | [`-query`](#query) | Direct passthrough to pandas `df.query()` (numexpr syntax) |
| **Compute / mutate columns** | [`-mutate`](#mutate) | Uses `col=expr`; supports `@specs.txt`, `[col a]`, `if_else`, `case_when`, `coalesce`, `map` |
| **Run SQL queries** | [`-sql`](#sql) | Queries current view as table `data` via DuckDB; supports `@query.txt`, `[col a]`, zero-copy scans |
| **Replace cell values** | [`-replace_values`](#replace-values) | Swaps cell contents via `v='old:new'`; distinct from header [`-rename`](#rename) |
| **Fill missing values (NA)** | [`-handle_missing`](#handle-missing) | Replaces NA with `.` / `0`; [`-dropna`](#flag-reference) controls NA keys in aggregations |
| **Sort rows** | [`-sort_by`](#sort-by) | Comma-separated column list with optional `asc`/`desc` (e.g. `body_mass_g desc`) |
| **Deduplicate rows** | [`-unique`](#unique) | Drops duplicate rows; [`-drop`](#drop) is for columns |
| **Aggregate (auto groups)** | [`-agg_df`](#agg-df) | Auto-groups by all non-numeric columns and aggregates numerics (e.g. `-agg_df mean`) |
| **Aggregate (explicit groups)** | [`-group_by`](#group-by-agg) + [`-agg`](#group-by-agg) | Explicit group columns; supports custom output names via `as=` and standard pandas aggfuncs |
| **Broadcast group stat** | [`-group_x`](#group-x) | Appends group aggregate column to every row without collapsing (like pandas `transform()`) |
| **Melt (wide → long)** | [`-long`](#reshape) | Unpivots numeric columns into rows (`c=metric,v=reading`); id columns stay |
| **Pivot (long → wide)** | [`-wide`](#reshape) | Reshapes long column into headers (`c=`, `v=`, `a=`); [`-crosstab`](#crosstab) is for count/mean matrices |
| **Cross-tabulate** | [`-crosstab`](#crosstab) | Two-way contingency matrix; supports `normalize=` percentages and `margins=` totals |
| **Frequency counts** | [`-value_counts`](#value-counts) | Counts unique combinations across current working columns (pair with [`-select`](#select)) |
| **Peek at rows** | [`-head`](#listing) / [`-tail`](#listing) / [`-sample`](#listing) | View first, last, or random sampled rows (default 5 rows; supports `-seed` and `-frac`) |
| **Schema & summary** | [`-shape`](#listing) / [`-cols`](#listing) / [`-dtype`](#listing) / [`-nulls`](#listing) / [`-info`](#listing) / [`-describe`](#listing) | Terminal inspection flags (cannot be followed except by [`-o clip`](#output)) |
| **Parquet metadata** | [`-meta`](#listing) | Zero-scan Parquet file metadata (row groups, compression, schema) |
| **Compare datasets** | [`-diff`](#diff) | Compares shape, columns, schema drift, null count diffs, and values against another file |
| **Output / convert format** | [`-o`](#output) | Export to file (`-o out.parquet`), in-place/batch convert (`-o csv`), or clipboard (`-o clip`) |
| **Direct output folder** | [`-out_dir`](#output) | Target directory for file exports (auto-created; supports `-od`) |
| **Page long outputs** | [`-pager`](#listing) | Pipes table or report through system `$PAGER` / `less` |
| **Combine multiple files** | [`-file`](#merge) + [`-merge`](#merge) / [`-concat`](#merge) / [`-sql`](#sql) | Multi-file mode replacing positional path; see [CLI_MULTI_FILE.md](CLI_MULTI_FILE.md) |

<a id="polarity-chaining"></a>
### Polarity chaining: `-select` vs `-drop`

Compose polarities by **chaining**, not by mixing tokens:

```bash
# Pick numeric columns plus species, then drop body_mass_g
pytae penguins.parquet -select "dtype=numeric,species" -drop "body_mass_g" -cols

# Filter rows first, then drop the filtering column
pytae penguins.parquet -qry "species = 'Adelie'" -drop "species" -head
```

- [`-select`](#select) picks (and may reorder) columns.
- [`-drop`](#drop) subtracts specific columns and preserves existing column order.

<a id="pytae-kwargs"></a>
### Standard parameter keys: `c=`, `v=`, `a=`

Pytae standardizes common reshape and transformation roles across operations into three simple letters:

| Key | Meaning | Flags |
|---|---|---|
| `c=` | **Column role** (melt/pivot dimension, or replace column scope) | [`-long`](#reshape), [`-wide`](#reshape), [`-replace_values`](#replace-values) |
| `v=` | **Value column** (or the value replacement mapping) | [`-long`](#reshape), [`-wide`](#reshape), [`-group_x`](#group-x), [`-replace_values`](#replace-values) |
| `a=` | **Aggregation** function (`mean`, `sum`, `n`, etc.) | [`-wide`](#reshape), [`-group_x`](#group-x), [`-agg_df`](#agg-df) |

- When the argument **is** the column list itself, column names stay bare without `c=` ([`-select`](#select), [`-drop`](#drop), [`-group_by`](#group-by-agg), [`-sort_by`](#sort-by)).
- Flags mirroring pandas keep pandas parameter names: [`-agg`](#group-by-agg) uses `column=`, `aggfunc=`, and `as=`; [`-crosstab`](#crosstab) uses `index=`, `columns=`, `values=`, and `aggfunc=`.
- In Python code, the same operations are available via `import pytae as pt` (e.g. `pt.select(df, ...)` or `df.pt.select(...)`). CLI flags remain identical.
