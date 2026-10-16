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
| **Smart Imputation** | `df.fillna(0)` / `df.fillna(0, "a", "b")` | `-fillna 0` | Smartly fills both Arrow `null` and float `NaN` |
| **Null-Only Imputation**| `df.fill_null(0)` | `-fill_null 0` | Fills only Arrow `null` values |
| **NaN-Only Imputation** | `df.fill_nan(0)` | `-fill_nan 0` | Fills only floating-point IEEE-754 `NaN` values |
| **Non-Destructive Drop**| `df.dropna()` / `df.dropna("a", "b")` | `-dropna` / `-dropna "a, b"` | Bare call drops 100% empty rows (`how='all'`); subset drops `how='any'` |
| **Smart Handle Missing**| `df.handle_missing(fillna=".")` | `-handle_missing "."` | Fills strings with `.` and numerics with `0` for reports |
| **Clean Headers** | `df.clean_columns(case="lower")` | `-clean_columns "case=lower"`| Sanitizes column names (strip, squeeze, case, dedupe) |
| **Replace Values** | `df.replace_values({"M": "Male"})` | `-replace_values "M=Male"` | Exact or substring value replacement across columns |
| **Clipboard Copy** | `df.to_clip()` | `-o clip` | Copies table to system clipboard (no index) |

---

## Missing Value Architecture (`fillna`, `fill_null`, `fill_nan`, `dropna`)

Pytae unifies missing data management across Arrow `null` and IEEE-754 float `NaN`:

### 1. Symmetrical `fillna`
By default, `fillna` operates with `nans=True`, replacing **both** Arrow nulls and floating-point `NaN` in numeric columns:

```python
import pytae as pt

df = pt.DataFrame({
    "a": [1.0, float("nan"), None, 4.0],
    "b": ["x", None, "y", "z"]
})

# Replaces both NaN and null across entire table
clean = df.fillna(0)

# Target specific columns
clean_a = df.fillna(0, "a")

# Target with subset parameter
clean_sub = df.fillna(0, subset=["a"])
```
```bash
# In CLI
pytae messy.parquet -fillna 0 -head 5
```

### 2. Format-Explicit Imputation (`fill_null` and `fill_nan`)
When strict type separation is required:
- `fill_null(value)`: Only replaces Arrow `null` values; leaves float `NaN` intact.
- `fill_nan(value)`: Only replaces float `NaN` values; leaves Arrow `null` intact.

```python
df.fill_null("Unknown")
df.fill_nan(0.0)
```

### 3. Non-Destructive `dropna` & Option B Semantics
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

### 4. `handle_missing()` — Fast Imputation for Categorical Reports
Prepares raw datasets for grouped aggregation reports by filling string/category missing values with a visible marker (default `.`) and numeric missing values with `0`:

```python
# Missing sex becomes '.', missing mass becomes 0
penguins.handle_missing()

# Custom marker
penguins.handle_missing(fillna="Unknown")
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
    penguins
    .filter("body_mass_g > 4000")
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
penguins.cols()                 # Alphabetical ascending
penguins.cols(ascending=False)  # Alphabetical descending
penguins.cols(ascending=None)   # Original schema order
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
messy = pt.DataFrame({
    "  Species  ": [1],
    "Island   Name": [2],
    "Body Mass (g)": [3]
})

clean = messy.clean_columns(strip=True, squeeze=True, strip_special=True, fill="_", case="lower")
# Resulting columns: ['species', 'island_name', 'body_mass_g']
```
```bash
pytae messy.csv -clean_columns "case=lower, fill=_" -head 3
```

### 2. `replace_values()` — Batch Value Replacement
Replaces values across the entire DataFrame or scoped to specific columns (`exact=True` for full cell match, `exact=False` for substring match):

```python
# Exact match
penguins.replace_values({"Adelie": "Adelie Penguin", "Male": "M"})

# Substring replacement scoped to column 'notes'
df.replace_values({"temporary": "temp"}, c="notes", exact=False)
```
```bash
pytae penguins.parquet -replace_values "Male=M, Female=F" -head 5
```


