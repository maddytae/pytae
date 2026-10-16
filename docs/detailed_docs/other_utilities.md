# Data Inspection, Missing Values, & Utilities (`other_utilities`)

Pytae provides a powerful suite of inspection, data cleaning, header sanitization, missing value imputation, and clipboard utilities that operate seamlessly across both Python and CLI environments.

---

## Rosetta Stone: Python vs. CLI

| Utility | Python Library (`pytae`) | Command Line (`pytae CLI`) | Description |
|:---|:---|:---|:---|
| **Column Names** | `df.cols()` / `df.cols(ascending=False)` | `-cols` / `-cols desc` | Lists column names sorted or in original order |
| **Glimpse Overview** | `df.glimpse()` | `-glimpse` | Transposed column overview with dtypes and sample values |
| **Frequency Bars** | `df.freq("species")` | `-freq species` | Value counts with percentages and proportional ASCII bars |
| **Histogram Bins** | `df.hist("body_mass_g:8")` | `-hist "body_mass_g:8"` | Numeric distribution with bins and ASCII bars |
| **Smart Imputation** | `df.fillna(0)` / `df.fillna({"a": 0})` | `-fillna 0` / `-fillna "a:0"`| Smartly fills null/NaN with scalar, mapping, or subset |
| **Non-Destructive Drop**| `df.dropna()` / `df.dropna("a", "b")` | `-dropna` / `-dropna "a, b"` | Bare call drops 100% empty rows (`how='all'`); subset drops `how='any'` |
| **Rename Columns** | `df.rename("old:new")` | `-rename "old:new"` | Renames columns via string spec, dict, or kwargs |
| **SQL Queries** | `df.sql("select ... from data")` | `-sql "select ... from data"` | Full ANSI SQL querying via embedded Polars SQLContext |
| **Clean Headers** | `df.clean_columns(case="lower")` | `-clean_columns "case=lower"`| Sanitizes column names (strip, squeeze, case, dedupe) |
| **Clipboard Copy** | `df.to_clip()` | `-o clip` | Copies table to system clipboard (no index) |

---

## Missing Value Architecture (`fillna`, `dropna`)

Pytae provides "One and Only One Obvious Way" to handle missing data across Arrow `null` and IEEE-754 float `NaN`:

### 1. `fillna` — Unified Symmetrical Imputation
`fillna` replaces **both** Arrow nulls and floating-point `NaN` with clean scalar values or column mappings:

```python
import pytae as pt

df = pt.DataFrame({"a": [1.0, float("nan"), None, 4.0], "b": ["x", None, "y", "z"]})

# 1. Whole-table scalar fill (targets type-appropriate columns)
clean_num = df.fillna(0)
clean_str = df.fillna("missing")

# 2. Column mapping dictionary
clean_mapped = df.fillna({"a": 0.0, "b": "Unknown"})

# 3. Targeted subset columns
clean_a = df.fillna(0, "a")
clean_sub = df.fillna(0, subset=["a"])
```
```bash
# In CLI: scalar fill, column mapping, or subset
pytae messy.parquet -fillna 0 -head 5
pytae messy.parquet -fillna "a:0, b:Unknown" -head 5
pytae messy.parquet -fillna "0, a" -head 5
```

### 2. Non-Destructive `dropna` & Option B Semantics
- **Pandas Trap**: Standard Pandas `df.dropna()` defaults to `how='any'`, silently wiping out rows if even a single optional column is missing.
- **Pytae Design**:
  - **Bare `dropna()`**: Defaults to `how='all'`. Only rows that are completely blank across all columns are dropped.
  - **Targeted `dropna("col1", "col2")`**: Defaults to `how='any'` over the specified subset, guaranteeing that only rows missing required keys are dropped.
  - **Dual Missing Cleaning (`drop_nans=True`)**: Cleans both Arrow `null` and IEEE-754 `NaN` by default.

```python
# Drops only 100% empty rows
df.dropna()

# Drops rows missing required keys 'user_id' or 'email'
df.dropna("user_id", "email")
```
```bash
# In CLI
pytae dirty.csv -dropna -o clean.parquet
pytae dirty.csv -dropna "user_id, email" -o clean.parquet
```

---

## Data Inspection Utilities

### 1. `glimpse()` — Transposed Schema & Sample Values
Prints a compact, transposed view of the DataFrame inspired by R/dplyr's `glimpse()`:
- Shows row count, column count, and types.
- Non-destructive: returns `self` so you can insert it anywhere mid-pipeline for debugging.

```python
# Inserted directly into a method chain
(
    penguins.filter("body_mass_g > 4000")
    .glimpse()  # Prints schema and sample values, passes DataFrame through!
    .select("species", "island", "body_mass_g")
    .head(3)
)
```
```bash
# In CLI
pytae penguins.parquet -glimpse
```

### 2. `freq()` & `hist()` — Terminal ASCII Distributions

#### Categorical Frequencies (`freq`)
Generates frequency tables with counts, percentages, and proportional ASCII bars:

```python
penguins.freq("species")
```
```bash
pytae penguins.parquet -freq species
```
**Output:**
```text
┌───────────┬───────┬──────────────────────────────┐
│ species   ┆ Count ┆ Distribution                 │
│ ---       ┆ ---   ┆ ---                          │
│ str       ┆ i64   ┆ str                          │
╞═══════════╪═══════╪══════════════════════════════╡
│ Adelie    ┆ 152   ┆ ████████████████████ (44.2%) │
│ Gentoo    ┆ 124   ┆ ████████████████ (36.0%)     │
│ Chinstrap ┆ 68    ┆ █████████ (19.8%)            │
└───────────┴───────┴──────────────────────────────┘
```

#### Numeric Histograms (`hist`)
Generates binned frequency tables with intervals and ASCII bars:

```python
penguins.hist("body_mass_g:8")
```
```bash
pytae penguins.parquet -hist "body_mass_g:8"
```

### 3. `cols()` — List Column Names
Returns a Python list of column names, sorted alphabetically or in original order:

```python
penguins.cols()  # Alphabetical ascending
penguins.cols(ascending=False)  # Alphabetical descending
penguins.cols(ascending=None)  # Original schema order
```
```bash
pytae penguins.parquet -cols
pytae penguins.parquet -cols desc
```

---

## Data Sanitization Utilities

### 1. `clean_columns()` — Header Name Sanitizer
Cleans inconsistent column headers in a deterministic order: `strip` -> `strip_special` -> `squeeze` -> `fill` -> `case` -> `dedupe`.

```python
messy = pt.DataFrame({"  Species  ": [1], "Island   Name": [2], "Body Mass (g)": [3]})

clean = messy.clean_columns(strip=True, squeeze=True, strip_special=True, fill="_", case="lower")
# Resulting columns: ['species', 'island_name', 'body_mass_g']
```
```bash
pytae messy.csv -clean_columns "case=lower, fill=_" -head 3
```

### 2. `rename()` — Dedicated Column Renaming
Renames one or more columns using string mappings, dictionaries, or keyword arguments:

```python
# String spec
df.rename("bill_length_mm:culmen_length, bill_depth_mm:culmen_depth")

# Dict mapping
df.rename({"species": "bird_species"})

# Keyword arguments
df.rename(species="bird_species")
```
```bash
# In CLI
pytae penguins.parquet -rename "species:bird_species" -head 5
```

> [!NOTE]
> To replace cell values within columns, use `mutate()` with `map(col, mapping)` (e.g. `df.mutate(sex="map(sex, {'M': 'Male'})")`) or `.str.replace()` (e.g. `df.mutate(name="name.str.replace('old', 'new')")`).

### 3. `sql()` — Direct Analytical SQL Execution
Executes ANSI SQL queries via Polars' embedded SQL engine directly against in-memory datasets (referenced as table `data`):

```python
# Python library
pt.sql(penguins, "SELECT species, AVG(body_mass_g) AS avg_mass FROM data GROUP BY 1")

# On DataFrame / Accessor
penguins.sql("SELECT * FROM data WHERE body_mass_g > 5000 ORDER BY body_mass_g DESC")
```
```bash
# In CLI
pytae penguins.parquet -sql "SELECT species, AVG(body_mass_g) FROM data GROUP BY 1"
```


