# pytae — CLI Reference

Inspect and convert tabular files (`.parquet`, `.csv`, `.txt`, `.sas7bdat`). The CLI is the same verbs as the library: `qry()`, `select()`, `agg_df()`, `group_x()`, `handle_missing()`, `long()`, `wide()`.

```bash
pytae data.parquet -head
pytae data.parquet -tail
pytae data.parquet -sample
pytae data.parquet -shape
pytae data.parquet -cols
pytae data.parquet -dtype
pytae data.parquet -nulls
pytae data.parquet -describe
pytae data.parquet -info
```

Flag **order is the pipeline**. `-select` / `-qry` / `-query` define the starting view. Later ops see that view. **Only the last operation prints.** Earlier flags still run.

```bash
# first 3 rows, then shape of that 3-row frame → prints (3, n)
pytae data.parquet -head 3 -shape

# names only (head runs but is not printed)
pytae data.parquet -head 5 -cols
```

Use the bundled penguins-style names in the examples below (`species`, `island`, `body_mass_g`, `bill_length_mm`, …).

---

**Column selection — `-select`**

One flag, one `df.select()` call. Tokens are a **union** (each token *adds* columns).

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
pytae data.parquet -select species,island -head 5
pytae data.parquet -select "'bill length mm','body mass g'" -describe

# regex (always regex= — a bare ^bill is an unknown column)
pytae data.parquet -select "regex=^bill" -head 5
pytae data.parquet -select "regex=_mm$" -nulls
pytae data.parquet -select "regex=bill|body" -describe

# dtype
pytae data.parquet -select dtype=numeric -describe
pytae data.parquet -select exclude_dtype=numeric -head 5
pytae data.parquet -select exclude_dtype=non_numeric -cols

# name patterns
pytae data.parquet -select contains=bill -head 5
pytae data.parquet -select startswith=bill -dtype
pytae data.parquet -select endswith=_mm -nulls

# slice
pytae data.parquet -select species:bill_length_mm -cols

# union in one -select (species, then names containing bill, then remaining numerics)
pytae data.parquet -select "species,contains=bill,dtype=numeric" -head 5
pytae data.parquet -select "species,regex=bill|body" -head 5

# repeated keys become a list (names containing bill OR body)
pytae data.parquet -select "contains=bill,contains=body" -cols
```

Unknown exact names error with a typo suggestion. A positional token that is not a real column is **not** a regex — use `regex=`. A second `-select` flag **overwrites** the first (argparse last-wins); put everything in one spec.

**`df.select()` but not `-select`**

- `everything()` — remaining columns after an explicit list
- a callable, e.g. `df.select(lambda c: c.endswith("_mm"))`
- a Python `list` as one positional arg (CLI sends each name as its own string)
- `contains` / `regex` as a Python list — CLI repeats the key: `contains=bill,contains=body`

---

**Row filtering — `-qry` and `-query`**

`-qry` is pytae's dict `qry()` (safer for odd strings). `-query` is pandas `DataFrame.query()` (numexpr). Both **narrow rows**. Stacking `-qry` with `-query` is AND.

```python
df.qry({"species": "Adelie", "body_mass_g": (">", 3500)})
df.query("body_mass_g > 3500 and island == 'Dream'")
```

```bash
pytae data.parquet -qry "{'species': 'Adelie', 'body_mass_g': ('>', 3500)}"
pytae data.parquet -query "body_mass_g > 3500 and island == 'Dream'"
pytae data.parquet -qry "{'species': 'Adelie'}" -query "body_mass_g > 3500" -head

# filter on a column you are not printing
pytae data.parquet -qry "{'species': 'Adelie'}" -select species,body_mass_g -head
```

Applies to `-head`/`-tail`/`-nulls`/`-describe`/`-sample`/`-convert`/`-agg_df`/`-agg`/`-value_counts`/`-group_x`/`-long`/`-wide`.

---

**Aggregation (auto group columns) — `-agg_df`**

Groups by all **non-numeric** columns and aggregates the rest. `n` is group count.

```python
df.agg_df("mean")
df.agg_df(["sum", "mean", "n"])
df.agg_df({"body_mass_g": "mean", "n": "n"})
```

```bash
pytae data.parquet -agg_df           # defaults to sum
pytae data.parquet -agg_df mean
pytae data.parquet -agg_df "['mean', 'sum']"
pytae data.parquet -agg_df "{'body_mass_g': 'mean', 'n': 'n'}"
pytae data.parquet -qry "{'species': 'Adelie'}" -agg_df mean
pytae data.parquet -agg_df sum -dropna false   # keep NA group keys
pytae data.parquet -agg_df mean -sort_by body_mass_g desc
```

---

**Aggregation (explicit group columns) — `-group_by` + `-agg`**

`groupby().agg()` with named aggregation. Collapses to one row per group.

```python
df.groupby("species", as_index=False).agg(
    avg_mass=("body_mass_g", "mean"),
    n=("body_mass_g", "size"),
)
```

```bash
pytae data.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean'"
pytae data.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean'; column='flipper_length_mm',aggfunc='sum'"
pytae data.parquet -group_by species -agg "column='body_mass_g',aggfunc='mean',as='avg_mass'; column='flipper_length_mm',aggfunc='sum',as='total_flipper'"
pytae data.parquet -group_by "species,island" -agg "column='body_mass_g',aggfunc='mean'"
pytae data.parquet -group_by "Scenario Name" -agg "column='value',aggfunc='sum',as='v'"
pytae data.parquet -group_by "Scenario Name" -agg "column='value,val_growth',aggfunc='sum'"
```

> `-agg` requires `-group_by`. `-group_x` takes `group=` itself (or still accepts `-group_by` if `group=` is omitted). One output per source column per `-agg` call — for several aggs on the same column, use `-agg_df`. `-agg_df` and `-agg` cannot be combined.

---

**Broadcast — `-group_x` / `.group_x()`**

Keeps **every row** and adds a column (`n` = group size, `x` = another aggregate). Like pandas `transform`. `-agg` collapses; `-group_x` does not.

```python
df.group_x()
df.group_x(group=["species"])
df.group_x(group=["species"], value="body_mass_g", aggfunc="max")
```

```bash
pytae data.parquet -group_x
pytae data.parquet -group_x "group='species'"
pytae data.parquet -group_x "group='species',value='body_mass_g',aggfunc='max'"
pytae data.parquet -group_x "group='species,island',value='body_mass_g',aggfunc='max'"
pytae data.parquet -group_x "group='bill length mm',value='body mass g',aggfunc='max'"
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

# after  -group_x "group='species',value='body_mass_g',aggfunc='max'"
  species    sex  body_mass_g      x
   Adelie   Male       3750.0 3800.0
   Adelie Female       3800.0 3800.0
   Gentoo Female       4500.0 5700.0
   Gentoo   Male       5700.0 5700.0
```

---

**Value counts — `-value_counts`**

Counts across the current working columns (`-select` first to choose keys). Several columns → unique combinations.

```bash
pytae data.parquet -select species -value_counts
pytae data.parquet -select species,island -value_counts
pytae data.parquet -select species -value_counts -dropna false
pytae data.parquet -select species -value_counts -sort_by count desc
```

---

**Unique rows — `-unique`**

```bash
pytae data.parquet -unique
pytae data.parquet -select species,island -unique
pytae data.parquet -unique -shape
```

---

**Listing — `-cols` / `-dtype` / `-nulls`**

File (or `-select`) order by default. Optional `asc` / `desc` sorts **names**, not rows. That is not `-sort_by`.

```bash
pytae data.parquet -cols
pytae data.parquet -cols asc
pytae data.parquet -cols desc
pytae data.parquet -dtype desc
pytae data.parquet -nulls asc
pytae data.parquet -select dtype=numeric -cols
```

CSV/TXT `-dtype` infers types from the first 10,000 rows, not the whole file.

---

**Sorting rows — `-sort_by`**

```bash
pytae data.parquet -sort_by body_mass_g
pytae data.parquet -sort_by body_mass_g desc
pytae data.parquet -sort_by species,body_mass_g desc
pytae data.parquet -select species,body_mass_g -sort_by body_mass_g desc -head 5
```

---

**Missing values — `-handle_missing` / `.handle_missing()`**

Object/category NA → `.` (or the fill you pass); numeric NA → `0`. Also strips object columns.

```python
df.handle_missing()
df.handle_missing(fillna="NA")
```

```bash
pytae data.parquet -handle_missing -head
pytae data.parquet -handle_missing NA -select species,sex -value_counts
```

---

**Reshape — `-long` / `-wide`**

Same as `df.long()` / `df.wide()`. `-long` melts numeric columns; id columns stay. `-wide` pivots a long column into headers. Defaults: `column=variable`, `value=value`. Quote the spec when values have spaces.

```bash
pytae data.parquet -long
pytae data.parquet -long "column='metric',value='reading'"
pytae tall.csv -wide
pytae tall.csv -wide "column='metric',value='reading'"
pytae tall.csv -wide "column='country',value='balance',aggfunc='mean'"
pytae tall.csv -wide "column='country name',value='body mass'"
pytae data.parquet -long -convert -o tall.csv
```

---

**Conversion — `-convert`**

Output format is the `-o` extension. Omitting `-o` writes `.csv` next to the source. Cannot write `.sas7bdat`.

| Format | Read | Write |
|---|---|---|
| `.parquet` / `.pq` | ✓ | ✓ |
| `.csv` | ✓ | ✓ |
| `.txt` | ✓ | ✓ |
| `.sas7bdat` | ✓ | — |

```bash
pytae data.parquet -convert
pytae data.parquet -convert -o data.txt
pytae data.parquet -select species,body_mass_g -convert -o subset.parquet
pytae data.csv -convert -o data.parquet
pytae data.sas7bdat -convert -o data.parquet          # character columns decoded as utf-8
pytae data.sas7bdat -encoding latin-1 -convert -o data.parquet
pytae data.txt -dlim "|" -convert -o data.csv
pytae 'data/*.parquet' -convert
pytae data.parquet -convert -rename "old_name:new_name,another:clean"
pytae data.csv -encoding latin-1 -convert -o data.parquet
```

> **`-dlim`:** `.csv` / `.txt` / `.sas7bdat` only. Defaults: `,` for csv, tab for txt. Common: `|`, `;`, `:`, `~`.
>
> ```bash
> pytae data.txt -dlim "|" -head
> pytae data.csv -dlim ";" -convert -o data.parquet
> ```

---

**Display extras**

```bash
pytae data.parquet -head -pretty
pytae data.parquet -describe -round 2
pytae data.parquet -head 20 -nrows 1000
pytae data.parquet -sample 10
pytae data.parquet -tail 3
pytae data.parquet -head -to_clip          # copy; no stdout
pytae data.parquet -shape -to_clip
pytae huge.csv -convert -o huge.parquet -progress
```

`-to_clip` copies **only the last** clipboard-able op (`-head 5 -tail 5 -to_clip` copies the tail). Do not combine `-to_clip -shape` with a table-producing flag.

---

**Recipes**

```bash
# inspect a new file
pytae data.parquet -shape
pytae data.parquet -cols
pytae data.parquet -dtype
pytae data.parquet -nulls
pytae data.parquet -info
pytae data.parquet -describe
pytae data.parquet -head
pytae data.parquet -tail
pytae data.parquet -sample

# Adelie penguins, numeric columns, mean by the remaining groups
pytae data.parquet -qry "{'species': 'Adelie'}" -select dtype=numeric -agg_df mean

# heaviest 5 after ranking
pytae data.parquet -select species,body_mass_g -sort_by body_mass_g desc -head 5

# species counts, then sort the count table
pytae data.parquet -select species -value_counts -sort_by count desc

# subset + convert
pytae data.parquet -qry "{'island': 'Dream'}" -select species,island,body_mass_g -convert -o dream.parquet

# batch csv next to each parquet
pytae 'folder/*.parquet' -convert
```

---

**Other flags**

| Flag | Description |
|---|---|
| `-head N` | First N rows (default 5) |
| `-tail N` | Last N rows (default 5) |
| `-sample N` | N random rows (default 5) |
| `-unique` | Drop duplicate rows |
| `-value_counts` | Counts across current working columns |
| `-cols [asc\|desc]` | Column names (default: file order) |
| `-dtype [asc\|desc]` | Dtypes (CSV/TXT: first 10k rows) |
| `-nulls [asc\|desc]` | Null counts |
| `-sort_by COLUMNS [asc\|desc]` | Sort rows (default: ascending) |
| `-group_by COLUMNS` | Groups for `-agg` (optional fallback for `-group_x`) |
| `-group_x [KEY=VALUE,...]` | Broadcast group agg (`group`, `value`, `aggfunc`) |
| `-handle_missing [FILL]` | Fill NA (default `.` / `0`) |
| `-long [KEY=VALUE,...]` | Melt numeric columns (`column`, `value`) |
| `-wide [KEY=VALUE,...]` | Pivot long to wide (`column`, `value`, `aggfunc`, `dropna`) |
| `-dropna true\|false` | Drop NA keys for `-agg_df`/`-agg`/`-value_counts` (default true) |
| `-nrows N` | Cap rows loaded |
| `-dlim CHAR` | Delimiter for csv/txt/sas7bdat |
| `-describe` | pandas `describe()` summary |
| `-info` | pandas `info()` (columns, non-nulls, dtypes, memory) |
| `-select SPEC` | Restrict columns (union of tokens) |
| `-encoding ENC` | Text encoding (SAS default: utf-8; csv/txt: pandas infer) |
| `-rename old:new,...` | Rename on convert |
| `-pretty` | Markdown table |
| `-round N` | Round numeric print/copy |
| `-to_clip` | Copy last result; suppress stdout |
| `-progress` | Progress for large converts |
