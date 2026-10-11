# Other Utilities — Reference

[← Back to Library Reference Hub](../library.md)


| Utility | Purpose |
|---|---|
| `.pt.cols()` | List column names sorted or in original order |
| `.pt.glimpse()` | Transposed column overview with dtypes and sample values (returns self for chaining) |
| `.pt.freq()` | Frequency distribution DataFrame with counts, percentages, and ASCII bars |
| `.pt.hist()` | Numeric histogram DataFrame with bin intervals, counts, and ASCII bars |
| `.pt.handle_missing()` | Fill string NaN with a marker, numeric NaN with 0, strip whitespace |
| `.pt.clean_columns()` | Clean column header names (strip, squeeze, fill, case, dedupe) |
| `.pt.replace_values()` | Replace values, optionally scoped to columns, exact or substring match |
| `df.to_clip()` | Copy DataFrame to clipboard (tab-separated, no index) |

---

```python
import pytae as pt

penguins = pt.sample_data['penguins']
titanic = pt.sample_data['titanic']
penguins.head(3)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

## `cols()` — list column names

```python
# Alphabetical column list — useful for quick discovery
penguins.pt.cols()
```

**Output:**
```text
['bill_depth_mm', 'bill_length_mm', 'body_mass_g', 'flipper_length_mm', 'island', 'sex', 'species']
```

```python
# Descending alphabetical sort — useful when column names form a natural reverse order
penguins.pt.cols(ascending=False)
```

**Output:**
```text
['species', 'sex', 'island', 'flipper_length_mm', 'body_mass_g', 'bill_length_mm', 'bill_depth_mm']
```

## `glimpse()` — transposed column overview

`.pt.glimpse()` prints a compact, transposed overview of the DataFrame inspired by R/dplyr's `glimpse()`:
- Summarizes row count, column count, and in-memory footprint.
- Lists every column name alongside its dtype and inline sample values.
- Non-destructive: prints to stdout and returns `self` (the unchanged DataFrame) so it can be inserted anywhere inside a method chain for debugging.

```python
# Direct glimpse overview
penguins.pt.glimpse()
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |            nan   |           nan   |                 nan |           nan | nan    |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |
| Adelie    | Torgersen |             39.3 |            20.6 |                 190 |          3650 | Male   |
| Adelie    | Torgersen |             38.9 |            17.8 |                 181 |          3625 | Female |
| Adelie    | Torgersen |             39.2 |            19.6 |                 195 |          4675 | Male   |
| Adelie    | Torgersen |             34.1 |            18.1 |                 193 |          3475 | nan    |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | nan    |

```python
# Non-destructive: returns self, allowing inspection mid-pipeline
(
    penguins
    .pt.filter("body_mass_g > 4000")
    .pt.glimpse()
    .pt.select("species", "island", "body_mass_g")
    .head(3)
)
```

**Output:**

| species   | island    |   body_mass_g |
|:----------|:----------|--------------:|
| Adelie    | Torgersen |          4675 |
| Adelie    | Torgersen |          4250 |
| Adelie    | Torgersen |          4400 |

## `handle_missing()` — clean before aggregating
Fills string/category NaN with a visible marker (default `.`) and numeric NaN with `0`. Also strips leading/trailing whitespace from string columns.

```python
# Default fillna='.': NaN sex becomes '.', NaN numerics become 0
# Then aggregate to see the '.' group alongside real groups
(
    penguins
    .pt.handle_missing()
)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |              0   |             0   |                   0 |             0 | .      |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |
| Adelie    | Torgersen |             39.3 |            20.6 |                 190 |          3650 | Male   |
| Adelie    | Torgersen |             38.9 |            17.8 |                 181 |          3625 | Female |
| Adelie    | Torgersen |             39.2 |            19.6 |                 195 |          4675 | Male   |
| Adelie    | Torgersen |             34.1 |            18.1 |                 193 |          3475 | .      |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | .      |

```python
# Custom fillna marker — makes missing group explicit in reports
(
    penguins
    .pt.handle_missing(fillna='Unknown')
)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex     |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:--------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male    |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female  |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female  |
| Adelie    | Torgersen |              0   |             0   |                   0 |             0 | Unknown |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female  |
| Adelie    | Torgersen |             39.3 |            20.6 |                 190 |          3650 | Male    |
| Adelie    | Torgersen |             38.9 |            17.8 |                 181 |          3625 | Female  |
| Adelie    | Torgersen |             39.2 |            19.6 |                 195 |          4675 | Male    |
| Adelie    | Torgersen |             34.1 |            18.1 |                 193 |          3475 | Unknown |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | Unknown |

```python
# Use a single-char marker like '$' to make missing data stand out in reports
(
    penguins
    .pt.handle_missing(fillna='$')
)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |              0   |             0   |                   0 |             0 | $      |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |
| Adelie    | Torgersen |             39.3 |            20.6 |                 190 |          3650 | Male   |
| Adelie    | Torgersen |             38.9 |            17.8 |                 181 |          3625 | Female |
| Adelie    | Torgersen |             39.2 |            19.6 |                 195 |          4675 | Male   |
| Adelie    | Torgersen |             34.1 |            18.1 |                 193 |          3475 | $      |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | $      |

## `df.to_clip()` — copy to clipboard
`df.to_clip()` copies the DataFrame to the system clipboard as tab-separated text (no index). Paste directly into Excel, Google Sheets, or any text editor. Invisible in notebook output — run it and then paste.

```python
# df.to_clip() copies the current DataFrame to clipboard — paste into Excel/Sheets
# Run this cell then Cmd+V in any spreadsheet application
(penguins
 .pt.select('species', 'island', 'bill_length_mm', 'body_mass_g')
 .pt.by('species', 'island')
 .pt.agg(a=['mean', 'n'])
).to_clip()
```

**Output:**

*(Data copied to clipboard as tab-separated text ready to paste into Excel or Sheets):*

| species   | island    |   n |   bill_length_mm |   body_mass_g |
|:----------|:----------|----:|-----------------:|--------------:|
| Adelie    | Biscoe    |  44 |          38.975  |       3709.66 |
| Adelie    | Dream     |  56 |          38.5018 |       3688.39 |
| Adelie    | Torgersen |  52 |          38.951  |       3706.37 |
| Chinstrap | Dream     |  68 |          48.8338 |       3733.09 |
| Gentoo    | Biscoe    | 124 |          47.5049 |       5076.02 |

## `clean_columns()` — clean messy header names
Cleans column header names in a fixed order: `strip` -> `strip_special` -> `squeeze` -> `fill` -> `case` -> `dedupe`. Handy after loading a spreadsheet export with inconsistent spacing/casing.

```python
# messy headers: leading/trailing spaces, repeated internal spaces, mixed case
messy = penguins.rename(columns={
    'species': '  Species  ',
    'island': 'Island   Name',
    'body_mass_g': 'Body Mass (g)',
})

(messy
 .pt.clean_columns(strip=True, squeeze=True, strip_special=True, fill='_', case='lower')
 .pt.cols(ascending=None)
)
```

**Output:**
```text
['species', 'island_name', 'bill_length_mm', 'bill_depth_mm', 'flipper_length_mm', 'body_mass_g', 'sex']
```

```python
# Method chain: clean names, then display them in original column order
(
    penguins
    .pt.clean_columns(case='proper')
    .pt.cols(ascending=None)
)
```

**Output:**
```text
['Species', 'Island', 'Bill_Length_Mm', 'Bill_Depth_Mm', 'Flipper_Length_Mm', 'Body_Mass_G', 'Sex']
```

## `replace_values()` — replace values, whole-cell or substring
Wraps pandas `replace()`. `exact=True` (default) only replaces a cell whose entire value matches a key exactly; `exact=False` replaces a key anywhere it occurs as a substring, leaving the rest of the cell untouched. Optionally scope to specific columns with `c=`. Parameter names (`v=`, `c=`, `exact=`) match the `-replace_values` CLI flag.

```python
# exact=True (default): only cells that equal 'Adelie'/'Male' exactly are replaced
(penguins
 .pt.replace_values({'Adelie': 'Adelie (renamed)', 'Male': 'M'})
 .pt.select('species', 'sex')
 .drop_duplicates()
)
```

**Output:**

| species          | sex    |
|:-----------------|:-------|
| Adelie (renamed) | M      |
| Adelie (renamed) | Female |
| Adelie (renamed) | nan    |
| Chinstrap        | Female |
| Chinstrap        | M      |
| Gentoo           | Female |
| Gentoo           | M      |
| Gentoo           | nan    |

```python
# c= restricts the replace to specific columns — 'island' untouched even though
# it never contained 'Male' anyway, this shows the scoping mechanism itself
(penguins
 .pt.replace_values({'Male': 'M', 'Female': 'F'}, c='sex')
 .pt.select('island', 'sex')
 .drop_duplicates()
)
```

**Output:**

| island    | sex   |
|:----------|:------|
| Torgersen | M     |
| Torgersen | F     |
| Torgersen | nan   |
| Biscoe    | F     |
| Biscoe    | M     |
| Dream     | F     |
| Dream     | M     |
| Dream     | nan   |
| Biscoe    | nan   |

```python
# exact=False: substring match anywhere in the cell, rest of the cell untouched
import pandas as pd

notes = pd.DataFrame({'note': ['a magician performed', 'not a magician exactly', 'no match here']})
notes.pt.replace_values({'a magician': 'the magic'}, exact=False)
```

**Output:**

| note                  |
|:----------------------|
| the magic performed   |
| not the magic exactly |
| no match here         |

## `freq()` & `hist()` — ASCII frequency bars and histograms

Inspect categorical frequency distributions and numeric histograms directly in Python or notebooks using the exact same engine as CLI `-freq` and `-hist`.
- **Returns a DataFrame**: Produces a clean DataFrame with counts, percentages, and proportional ASCII bars (`[col, "Count", "Distribution"]` for `freq`, `["Range", "Count", "Distribution"]` for `hist`).
- **`freq(col=None, *, dropna=False)`**: Counts unique values (including `NaN` by default) with percentages and proportional ASCII bars.
- **`hist(col=None, bins=10)`**: Accepts `"col:bins"` shorthand (e.g. `"body_mass_g:8"`) or explicit `bins=8`.

```python
# Categorical frequency distribution (includes NaN group by default)
penguins.pt.freq("species")
```

**Output:**

| species   |   Count | Distribution                 |
|:----------|--------:|:-----------------------------|
| Adelie    |     152 | ████████████████████ (44.2%) |
| Gentoo    |     124 | ████████████████ (36.0%)     |
| Chinstrap |      68 | █████████ (19.8%)            |

```python
# Numeric distribution histogram with 8 bins using col:bins shorthand
penguins.pt.hist("body_mass_g:8")
```

**Output:**

| Range          |   Count | Distribution                 |
|:---------------|--------:|:-----------------------------|
| [2696.4, 3150] |      21 | █████ (6.1%)                 |
| [3150, 3600]   |      76 | ███████████████████ (22.2%)  |
| [3600, 4050]   |      79 | ████████████████████ (23.1%) |
| [4050, 4500]   |      51 | █████████████ (14.9%)        |
| [4500, 4950]   |      47 | ████████████ (13.7%)         |
| [4950, 5400]   |      34 | █████████ (9.9%)             |
| [5400, 5850]   |      28 | ███████ (8.2%)               |
| [5850, 6300]   |       6 | ██ (1.8%)                    |
