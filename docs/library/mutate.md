# `mutate` — Reference

[← Back to Library Reference Hub](../library.md)

`mutate` creates or overwrites columns using clean keyword argument syntax (`col="expr"` or `col=callable`) or string specifications (`"col = expr"`). Each entry is evaluated in order via pandas `eval()` — a plain formula per column, a multi-column transform `(col1, col2) = _ * 2`, or a lambda when needed.
### Calling Styles
1. **Keyword arguments** (most Pythonic): `.pt.mutate(bmi="body_mass_g / bill_length_mm ** 2", mass_kg="body_mass_g / 1000")`
2. **String expressions & multi-column transforms**: `.pt.mutate("(bill_length_mm, bill_depth_mm)_cm = _ / 10")`
3. **Dictionary unpacking** (for new column names with spaces): `.pt.mutate(**{"body mass kg": "body_mass_g / 1000"})`
4. **External file specification**: `.pt.mutate("@features.txt")`
---

```python
import numpy as np
import pytae as pt

penguins = pt.sample_data["penguins"]
penguins.head(3)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

## A single derived column

```python
# Body mass index style ratio — clean assignment formula via kwargs
(
    penguins.pt.mutate(bmi="body_mass_g / bill_length_mm ** 2")
    .pt.select("species", "body_mass_g", "bill_length_mm", "bmi")
    .head(5)
)
```

**Output:**

| species   |   body_mass_g |   bill_length_mm |       bmi |
|:----------|--------------:|-----------------:|----------:|
| Adelie    |          3750 |             39.1 |   2.45289 |
| Adelie    |          3800 |             39.5 |   2.43551 |
| Adelie    |          3250 |             40.3 |   2.00112 |
| Adelie    |           nan |            nan   | nan       |
| Adelie    |          3450 |             36.7 |   2.56146 |

```python
# Column names inside the expression must stay unquoted — quoting one turns it into
# a string literal, which will break arithmetic
try:
    penguins.pt.mutate(bmi="'body_mass_g' / 'bill_length_mm' ** 2")
except TypeError as exc:
    print(f"TypeError (as expected): {exc}")
```

**Output:**
```text
TypeError (as expected): unsupported operand type(s) for ** or pow(): 'str' and 'int'
```

## Multiple entries in one call, and chaining a later entry off an earlier one
Entries are applied left to right, so a later expression can reference a column derived earlier in the *same* `mutate()` call.

```python
# Two independent derived columns in one call via kwargs
(
    penguins.pt.mutate(heavy="body_mass_g > 4000", mass_kg="body_mass_g / 1000")
    .pt.select("species", "body_mass_g", "mass_kg", "heavy")
    .head(5)
)
```

**Output:**

| species   |   body_mass_g |   mass_kg | heavy   |
|:----------|--------------:|----------:|:--------|
| Adelie    |          3750 |      3.75 | False   |
| Adelie    |          3800 |      3.8  | False   |
| Adelie    |          3250 |      3.25 | False   |
| Adelie    |           nan |    nan    | False   |
| Adelie    |          3450 |      3.45 | False   |

```python
# mass_lb references mass_kg, derived by the keyword just before it
(
    penguins.pt.mutate(mass_kg="body_mass_g / 1000", mass_lb="mass_kg * 2.20462")
    .pt.select("species", "body_mass_g", "mass_kg", "mass_lb")
    .head(5)
)
```

**Output:**

| species   |   body_mass_g |   mass_kg |   mass_lb |
|:----------|--------------:|----------:|----------:|
| Adelie    |          3750 |      3.75 |   8.26732 |
| Adelie    |          3800 |      3.8  |   8.37756 |
| Adelie    |          3250 |      3.25 |   7.16501 |
| Adelie    |           nan |    nan    | nan       |
| Adelie    |          3450 |      3.45 |   7.60594 |

## String comparisons and local variables
String literals *inside* the expression (e.g. `'Adelie'`) need real quotes — column names stay bare. A variable from the calling scope can be referenced with an `@` prefix, same as pandas' own `eval()`/`query()`.

```python
# String comparisons inside the expression formula
(penguins.pt.mutate(is_adelie="species == 'Adelie'").pt.select("species", "is_adelie").head(5))
```

**Output:**

| species   | is_adelie   |
|:----------|:------------|
| Adelie    | True        |
| Adelie    | True        |
| Adelie    | True        |
| Adelie    | True        |
| Adelie    | True        |

```python
# @-prefixed names resolve against the scope that called mutate(), not the module
# — works identically whether calling pt.mutate() or chaining .pt.mutate()
threshold = 4000

(penguins.pt.mutate(heavy="body_mass_g >= @threshold").pt.select("species", "body_mass_g", "heavy").head(5))
```

**Output:**

| species   |   body_mass_g | heavy   |
|:----------|--------------:|:--------|
| Adelie    |          3750 | False   |
| Adelie    |          3800 | False   |
| Adelie    |          3250 | False   |
| Adelie    |           nan | False   |
| Adelie    |          3450 | False   |

## Overwriting an existing column

```python
# mutate() can overwrite a column in place, e.g. converting units
(penguins.pt.mutate(body_mass_g="body_mass_g / 1000").pt.select("species", "body_mass_g").head(5))
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |          3.75 |
| Adelie    |          3.8  |
| Adelie    |          3.25 |
| Adelie    |        nan    |
| Adelie    |          3.45 |

## Column names with spaces — bracket syntax
Use square brackets `[col name]` to reference column names containing spaces without shell or syntax hazards (backticks are also supported):

```python
import pandas as pd

spaced = pd.DataFrame({"body mass g": [3750, 4200], "bill length mm": [39.1, 46.5]})

# Square brackets protect column names that contain spaces
spaced.pt.mutate(bmi="[body mass g] / [bill length mm] ** 2")
```

**Output:**

|   body mass g |   bill length mm |     bmi |
|--------------:|-----------------:|--------:|
|          3750 |             39.1 | 2.45289 |
|          4200 |             46.5 | 1.94242 |

## Real-world pipeline: mutate → filter → select
`mutate()` chains like any other pytae method — filter on a column you just derived with `filter()`.

```python
(
    penguins.pt.mutate(bmi="body_mass_g / bill_length_mm ** 2")
    .pt.filter(bmi="> 2")
    .pt.select("species", "island", "body_mass_g", "bill_length_mm", "bmi")
    .head(5)
)
```

**Output:**

| species   | island    |   body_mass_g |   bill_length_mm |     bmi |
|:----------|:----------|--------------:|-----------------:|--------:|
| Adelie    | Torgersen |          3750 |             39.1 | 2.45289 |
| Adelie    | Torgersen |          3800 |             39.5 | 2.43551 |
| Adelie    | Torgersen |          3250 |             40.3 | 2.00112 |
| Adelie    | Torgersen |          3450 |             36.7 | 2.56146 |
| Adelie    | Torgersen |          3650 |             39.3 | 2.36324 |

## Conditional column creation — `if_else()`, `case_when()`, `map()`
Plain `eval()` has no ternary/`where()` support, so `mutate()` provides three dplyr-style helpers as ordinary function calls, evaluated via `np.where()`/`np.select()`/`Series.map()`: `if_else(condition, true_value, false_value)`, `case_when((cond1, val1), (cond2, val2), ..., default)`, and `map(column, {key: value, ...}, default)`. A trailing bare argument to `case_when` is the catch-all default (like SQL ELSE). Because they are ordinary calls, they compose and chain with each other and with any pandas method. String outcomes need quotes; conditions are vectorized — prefer `and`/`or`/`not` (the bitwise `&`/`|`/`~` also work).

```python
# if_else(condition, true_value, false_value) — like dplyr's if_else()
# true_value and false_value can be scalars or column names; conditions are vectorized
(
    penguins.pt.mutate(weight_class="if_else(body_mass_g > 4000, 'heavy', 'light')")
    .pt.select("species", "body_mass_g", "weight_class")
    .head(5)
)
```

**Output:**

| species   |   body_mass_g | weight_class   |
|:----------|--------------:|:---------------|
| Adelie    |          3750 | light          |
| Adelie    |          3800 | light          |
| Adelie    |          3250 | light          |
| Adelie    |           nan | light          |
| Adelie    |          3450 | light          |

```python
# case_when supports tuples or flat pairs with default=
(
    penguins.pt.mutate(
        size_class="case_when(body_mass_g >= 4500, 'large', body_mass_g >= 3500, 'medium', default='small')"
    )
    .pt.select("species", "body_mass_g", "size_class")
    .head(5)
)
```

**Output:**

| species   |   body_mass_g | size_class   |
|:----------|--------------:|:-------------|
| Adelie    |          3750 | medium       |
| Adelie    |          3800 | medium       |
| Adelie    |          3250 | small        |
| Adelie    |           nan | small        |
| Adelie    |          3450 | small        |

```python
# map(column, {key: value, ...}, default) — recode a column through a dictionary lookup
# unmapped keys become default if given, else null.
# 'default' can be a literal string ('OTH'), the column itself (island), or another column!
(
    penguins.pt.mutate(
        # Fallback to column itself preserves original names for unmatched rows
        island_code="map(island, {'Torgersen': 'TOR', 'Biscoe': 'BIS'}, island)",
        # Or provide a literal fallback string
        island_other="map(island, {'Torgersen': 'TOR'}, 'OTHER')",
    )
    .pt.select("species", "island", "island_code", "island_other")
    .head(5)
)
```

**Output:**

| species   | island    | island_code   | island_other   |
|:----------|:----------|:--------------|:---------------|
| Adelie    | Torgersen | TOR           | TOR            |
| Adelie    | Torgersen | TOR           | TOR            |
| Adelie    | Torgersen | TOR           | TOR            |
| Adelie    | Torgersen | TOR           | TOR            |
| Adelie    | Torgersen | TOR           | TOR            |

## First non-null resolution — `coalesce()`

`coalesce(col1, col2, ..., default)` evaluates candidates left-to-right and returns the first non-null value per row, like SQL `COALESCE()` or `dplyr::coalesce()`:

```python
contacts = pd.DataFrame(
    {
        "mobile": [None, "555-1234", None],
        "home": ["555-5678", None, None],
        "work": [None, None, "555-9012"],
    }
)

contacts.pt.mutate(preferred_contact="coalesce(mobile, home, work, 'N/A')")
```

**Output:**

| mobile   | home     | work     | preferred_contact   |
|:---------|:---------|:---------|:--------------------|
| nan      | 555-5678 | nan      | 555-5678            |
| 555-1234 | nan      | nan      | 555-1234            |
| nan      | nan      | 555-9012 | 555-9012            |

## Missing & NaN Value Filling — `fillna()`, `fill_null()`, `fill_nan()`

In expressions, `mutate()` provides smart missing-value handlers:

- `fillna(col, val, nans=True)` / `col.fillna(val)`: Fills **both** floating-point `NaN` (e.g. from division by zero) and Arrow `null` with `val` by default. Set `nans=False` to only fill Arrow `null`s.
- `fill_null(col, val)` / `col.fill_null(val)`: Strict Arrow `null` filling (leaves `NaN` untouched).
- `fill_nan(col, val)` / `col.fill_nan(val)`: Strict float `NaN` filling (leaves `null` untouched).

```python
calc_df = pt.DataFrame(
    {
        "profit": [100.0, 0.0, None],
        "revenue": [500.0, 0.0, 100.0],
    }
)

(
    calc_df
    # 0 / 0 produces NaN; row 3 produces null. fillna cleans both!
    .mutate(
        margin="fillna(profit / revenue, 0.0)",
        # Or using method syntax:
        margin_alt="(profit / revenue).fillna(0.0)",
    )
)
```

## Combining expressions and callables in kwargs

`mutate()` cleanly mixes expression strings and python callables (e.g. lambdas) in keyword arguments:

```python
(
    penguins.pt.mutate(
        bmi="body_mass_g / bill_length_mm ** 2",
        mass_kg="body_mass_g / 1000",
        is_heavy=lambda df: df["body_mass_g"] > 4000,
    )
    .pt.select("species", "bmi", "mass_kg", "is_heavy")
    .head(5)
)
```

**Output:**

| species   |       bmi |   mass_kg | is_heavy   |
|:----------|----------:|----------:|:-----------|
| Adelie    |   2.45289 |      3.75 | False      |
| Adelie    |   2.43551 |      3.8  | False      |
| Adelie    |   2.00112 |      3.25 | False      |
| Adelie    | nan       |    nan    | False      |
| Adelie    |   2.56146 |      3.45 | False      |

### Row-wise custom logic with `lambda df: df.apply(func, axis=1)`

When custom logic requires multi-column `if/elif/else` branching or arbitrary Python functions expecting a single row (a `pandas.Series`), pass `lambda df: df.apply(custom_func, axis=1)`.

Because `mutate()` executes sequentially, the row function can even access columns created earlier in the very same `mutate()` call (such as `row["mass_kg"]`):

```python
def classify_penguin(row):
    if pd.isna(row["mass_kg"]):
        return "Incomplete Data"
    if row["species"] == "Gentoo" and row["mass_kg"] > 5.0:
        return "Giant Gentoo"
    elif row["island"] == "Torgersen" and row["mass_kg"] > 3.7:
        return "Prime Torgersen"
    else:
        return "Standard"


(
    penguins.pt.mutate(
        mass_kg="body_mass_g / 1000",
        category=lambda df: df.apply(classify_penguin, axis=1),
    )
    .pt.select("species", "island", "body_mass_g", "mass_kg", "category")
    .head(6)
)
```

**Output:**

| species   | island    |   body_mass_g |   mass_kg | category        |
|:----------|:----------|--------------:|----------:|:----------------|
| Adelie    | Torgersen |          3750 |      3.75 | Prime Torgersen |
| Adelie    | Torgersen |          3800 |      3.8  | Prime Torgersen |
| Adelie    | Torgersen |          3250 |      3.25 | Standard        |
| Adelie    | Torgersen |           nan |    nan    | Incomplete Data |
| Adelie    | Torgersen |          3450 |      3.45 | Standard        |
| Adelie    | Torgersen |          3650 |      3.65 | Standard        |

## Loading specs from an external file — `@specs.txt`
For complex feature engineering or shared pipelines across Python and the CLI, specs can be loaded from an external file. The file supports multiline expressions, `#` comments, empty lines, and column chaining (where later formulas reference columns defined earlier in the same file).
### File content of `penguin_features.txt`:
```text
# Engineering features for penguins
mass_kg = body_mass_g / 1000
# Convert kg to lbs (references mass_kg computed above)
mass_lb = mass_kg * 2.20462
```

```python
# Write a small demo spec file with comments and assignment '=' syntax
spec_content = """# Engineering features for penguins
mass_kg = body_mass_g / 1000

# Convert kg to lbs
mass_lb = mass_kg * 2.20462
"""
with open("penguin_features.txt", "w") as f:
    f.write(spec_content)

# Load directly using @filename
result = penguins.pt.mutate("@penguin_features.txt")
out = result.pt.select("species", "mass_kg", "mass_lb").sample(5)

# Clean up demo file
import os

os.remove("penguin_features.txt")

out
```

**Output:**

| species   |   mass_kg |   mass_lb |
|:----------|----------:|----------:|
| Gentoo    |     5.65  |  12.4561  |
| Adelie    |     4.775 |  10.5271  |
| Chinstrap |     3.775 |   8.32244 |
| Adelie    |     3.75  |   8.26732 |
| Adelie    |     3.75  |   8.26732 |

## Columns with spaces — SQL-style brackets `[col]`

SQL-style square brackets `[col a]` are supported alongside backticks, avoiding shell backtick substitution hazards:

```python
spaced.pt.mutate(ratio="[body mass g] / [bill length mm]")
```

**Output:**

|   body mass g |   bill length mm |   ratio |
|--------------:|-----------------:|--------:|
|          3750 |             39.1 | 95.9079 |
|          4200 |             46.5 | 90.3226 |

## Creating new columns with spaces — string expressions `[col] = ...`

You can create columns with spaces directly using string assignment expressions with brackets `[new col] = ...` with zero dictionary unpacking.

(Dictionary unpacking `**{'col name': ...}` is also supported for kwargs).

```python
# Create a new column with spaces using bracket string expression (no dict unpacking!)
(
    spaced.pt.mutate("[body mass ratio] = [body mass g] / [bill length mm]")
    .pt.select("[body mass g]", "[body mass ratio]")
    .head()
)
```

**Output:**

|   body mass g |   body mass ratio |
|--------------:|------------------:|
|          3750 |           95.9079 |
|          4200 |           90.3226 |

```python
# Define multiple new columns with spaces at once via string expressions
(
    penguins.pt.mutate(
        "[body mass kg] = body_mass_g / 1000",
        "[bill ratio] = bill_length_mm / bill_depth_mm",
    )
    .pt.select("species", "[body mass kg]", "[bill ratio]")
    .head()
)
```

**Output:**

| species   |   body mass kg |   bill ratio |
|:----------|---------------:|-------------:|
| Adelie    |           3.75 |      2.09091 |
| Adelie    |           3.8  |      2.27011 |
| Adelie    |           3.25 |      2.23889 |
| Adelie    |         nan    |    nan       |
| Adelie    |           3.45 |      1.90155 |

Note: When loading specs from an external file (`@specs.txt`) or via the CLI (`-mutate`), names with spaces can be written directly on the left-hand side of `=` without dictionary unpacking:

```text
# inside an external spec file or CLI flag:
my bmi = [body mass g] / [bill length mm] ** 2
```

## Grouped mutations — `df.pt.by(...).pt.mutate(...)`

Unlike `pt.agg()` which collapses rows ($N \to K$), `df.pt.by(...).pt.mutate(...)` evaluates window calculations and group-level summaries and broadcasts them back to every row ($N \to N$).

Supported features:
- **Injected aggregation functions**: `mean(x)`, `sum(x)`, `median(x)`, `min(x)`, `max(x)`, `std(x)`, `var(x)`
- **Group row count**: `n` or `n()` (dplyr / Polars convention)
- **Sequential expressions**: Later expressions within the same `mutate` call can immediately reference earlier group-derived columns (e.g. `diff = tip - avg_tip`)
- **Arbitrary output column names**: Name target columns cleanly without hardcoded prefixes
- **Multi-column grouping**: `.pt.by('species', 'island')`
- **Spaced column names**: `[total bill]`
- **Missing group handling**: `dropna=False` retains NA groups

```python
# Compute group average tip, deviation from group average, and group sample size
tips = pt.sample("tips")
(
    tips.pt.select("day", "time", "total_bill", "tip")
    .pt.by("day")
    .pt.mutate("avg_tip = mean(tip), diff = tip - avg_tip, group_size = n")
    .head(6)
)
```

**Output:**

| day   | time   |   total_bill |   tip |   avg_tip |       diff |   group_size |
|:------|:-------|-------------:|------:|----------:|-----------:|-------------:|
| Sun   | Dinner |        16.99 |  1.01 |   3.25513 | -2.24513   |           76 |
| Sun   | Dinner |        10.34 |  1.66 |   3.25513 | -1.59513   |           76 |
| Sun   | Dinner |        21.01 |  3.5  |   3.25513 |  0.244868  |           76 |
| Sun   | Dinner |        23.68 |  3.31 |   3.25513 |  0.0548684 |           76 |
| Sun   | Dinner |        24.59 |  3.61 |   3.25513 |  0.354868  |           76 |
| Sun   | Dinner |        25.29 |  4.71 |   3.25513 |  1.45487   |           76 |

```python
# Multi-column grouping with spaced columns
(
    tips.rename(columns={"total_bill": "total bill"})
    .pt.select("day", "time", "total bill", "tip")
    .pt.by("day", "time")
    .pt.mutate("[avg bill] = mean([total bill]), [bill diff] = [total bill] - [avg bill], count = n()")
    .head(6)
)
```

**Output:**

| day   | time   |   total bill |   tip |   avg bill |   bill diff |   count |
|:------|:-------|-------------:|------:|-----------:|------------:|--------:|
| Sun   | Dinner |        16.99 |  1.01 |      21.41 |       -4.42 |      76 |
| Sun   | Dinner |        10.34 |  1.66 |      21.41 |      -11.07 |      76 |
| Sun   | Dinner |        21.01 |  3.5  |      21.41 |       -0.4  |      76 |
| Sun   | Dinner |        23.68 |  3.31 |      21.41 |        2.27 |      76 |
| Sun   | Dinner |        24.59 |  3.61 |      21.41 |        3.18 |      76 |
| Sun   | Dinner |        25.29 |  4.71 |      21.41 |        3.88 |      76 |

```python
# De-meaning and z-score calculation per group
(
    penguins.pt.select("species", "body_mass_g")
    .pt.by("species")
    .pt.mutate(
        "mean_mass = mean(body_mass_g), std_mass = std(body_mass_g), z_score = (body_mass_g - mean_mass) / std_mass"
    )
    .head(6)
)
```

**Output:**

| species   |   body_mass_g |   mean_mass |   std_mass |    z_score |
|:----------|--------------:|------------:|-----------:|-----------:|
| Adelie    |          3750 |     3700.66 |    458.566 |   0.107591 |
| Adelie    |          3800 |     3700.66 |    458.566 |   0.216627 |
| Adelie    |          3250 |     3700.66 |    458.566 |  -0.982764 |
| Adelie    |           nan |     3700.66 |    458.566 | nan        |
| Adelie    |          3450 |     3700.66 |    458.566 |  -0.546622 |
| Adelie    |          3650 |     3700.66 |    458.566 |  -0.11048  |

### Grouped vs. Overall Window Calculations with `ungroup()`

Because `mutate()` always preserves the row count ($N \to N$) and retains the active grouping context across consecutive calls, call `.pt.ungroup()` whenever you want a subsequent mutation to calculate statistics across the **entire dataset** (grand total) rather than within groups.

```python
# Comparing species-level mean to overall dataset mean in a single pipeline
(
    penguins.pt.select("species", "body_mass_g")
    .pt.by("species")
    .pt.mutate("species_mean = mean(body_mass_g)")
    .pt.ungroup()
    .pt.mutate("overall_mean = mean(body_mass_g)")
    .pt.mutate("species_vs_overall = species_mean - overall_mean")
    .head(6)
)
```

**Output:**

| species   |   body_mass_g |   species_mean |   overall_mean |   species_vs_overall |
|:----------|--------------:|---------------:|---------------:|---------------------:|
| Adelie    |          3750 |        3700.66 |        4201.75 |             -501.092 |
| Adelie    |          3800 |        3700.66 |        4201.75 |             -501.092 |
| Adelie    |          3250 |        3700.66 |        4201.75 |             -501.092 |
| Adelie    |           nan |        3700.66 |        4201.75 |             -501.092 |
| Adelie    |          3450 |        3700.66 |        4201.75 |             -501.092 |
| Adelie    |          3650 |        3700.66 |        4201.75 |             -501.092 |

### Handling missing grouping values with `dropna`

By default, `dropna=False` computes group statistics across `NA` rows as their own distinct group (no silent data loss). Pass `dropna=True` to exclude rows with `NA` in grouping columns from calculations, filling `NaN` in mutated columns while preserving total row count and index alignment:

```python
sample_data = pd.DataFrame({"grp": ["A", "A", None, "B", None], "val": [10.0, 20.0, 100.0, 30.0, 200.0]})

# dropna=False (default): NA rows form a distinct group
print("dropna=False (default):")
print(sample_data.pt.by("grp").pt.mutate("avg = mean(val), sz = n", dropna=False))

# dropna=True: NA groups receive NaN
print("\ndropna=True:")
print(sample_data.pt.by("grp").pt.mutate("avg = mean(val), sz = n", dropna=True))
```

**Output:**
```text
dropna=False (default):
   grp    val    avg  sz
0    A   10.0   15.0   2
1    A   20.0   15.0   2
2  NaN  100.0  150.0   2
3    B   30.0   30.0   1
4  NaN  200.0  150.0   2

dropna=True:
   grp    val   avg   sz
0    A   10.0  15.0  2.0
1    A   20.0  15.0  2.0
2  NaN  100.0   NaN  NaN
3    B   30.0  30.0  1.0
4  NaN  200.0   NaN  NaN
```

## Comprehensive end-to-end recipe: combining all `mutate` capabilities

This master example combines all core features in a single fluent pipeline:
1. **Normal mutate**: Standard arithmetic derivation (`bill_ratio`, `mass_kg`).
2. **Sequential column referencing**: Using a freshly created column (`mass_kg`) inside subsequent expressions (`bmi`, `above_target`, `size_label`) within the *same* `mutate()` call.
3. **Binary conditional (`if_else`)**: Conditional branching into `'Heavy'` / `'Standard'`.
4. **Multi-condition tiers (`case_when`)**: Multi-tier categorization with ordered tuples and a fallback `default`.
5. **Null fallback (`coalesce`)**: Resolving the first non-null value across columns or supplying a fallback for missing data.
6. **Dictionary mapping (`map`)**: Category recoding through a dictionary lookup with fallback handling.
7. **Local variables (`@var`)**: Referencing caller-scope Python variables directly using the `@` prefix.
8. **Columns with spaces (`[col]`)**: Defining spaced columns via dict unpacking and referencing them with brackets `[mass lbs]`.
9. **Grouped window transforms (`pt.by()`)**: Computing group-level aggregations (`mean(mass_kg)`), relative offsets (`mass_diff`), and group sizes (`n`) without collapsing rows.
10. **Lambda callables**: Custom function inspecting the accumulated DataFrame with all prior mutations already attached.

```python
import numpy as np
import pytae as pt

penguins = pt.sample("penguins")

# 7. Local Python variable from caller scope (referenced with @ prefix)
target_threshold = 4.2

master_df = penguins.pt.by("species").pt.mutate(
    # 1. Normal mutate: standard arithmetic derivation
    bill_ratio="bill_length_mm / bill_depth_mm",
    mass_kg="body_mass_g / 1000",
    # 3. Referencing newly created col (mass_kg) in the same mutate call
    bmi="mass_kg / ((flipper_length_mm / 1000) ** 2)",
    # 7a. Local variable reference (@target_threshold) from caller scope
    above_target="mass_kg > @target_threshold",
    # 4. if_else: binary conditional logic
    size_label="if_else(mass_kg >= 4.5, 'Heavy', 'Standard')",
    # 5. case_when: multi-condition tiered categorization
    weight_tier="case_when((mass_kg >= 5.0, 'XL'), (mass_kg >= 4.0, 'Large'), (mass_kg >= 3.0, 'Medium'), default='Small')",
    # 6. coalesce: prioritize sex, fall back to 'Undetermined' when null (row 3 has sex=NaN)
    effective_sex="coalesce(sex, 'Undetermined')",
    # 7b. map(): category dictionary lookup with default fallback
    species_code="map(species, {'Adelie': 'AD', 'Gentoo': 'GE', 'Chinstrap': 'CH'}, 'OTHER')",
    # 7c. Spaced column creation via dict unpacking & bracket referencing
    **{"mass lbs": "mass_kg * 2.20462"},
    heavy_lbs="[mass lbs] > 9.5",
    # 9. Grouped window transforms via standalone pt.by() without collapsing rows
    species_avg_mass="mean(mass_kg)",
    mass_diff="mass_kg - species_avg_mass",
    group_size="n",
    # 2. lambda: custom callable inspecting the accumulated DataFrame
    is_large=lambda df: (df["mass_kg"] > 4.0) & (df["bill_ratio"] > 2.5),
    # analysis='species', #if we don't use pt.lit, it will just assign value of speciec column
    # analysis='species2', #it will throw error because there is not 'species2 column'
    analysis=pt.lit("species"),
)

cols_to_show = [
    "species",
    "species_code",
    "mass_kg",
    "species_avg_mass",
    "mass_diff",
    "group_size",
    "bmi",
    "size_label",
    "weight_tier",
    "effective_sex",
    "above_target",
    "heavy_lbs",
    "is_large",
    "analysis",
]
master_df[cols_to_show].head(8)
```

**Output:**

| species   | species_code   |   mass_kg |   species_avg_mass |   mass_diff |   group_size |      bmi | size_label   | weight_tier   | effective_sex   | above_target   | heavy_lbs   | is_large   | analysis   |
|:----------|:---------------|----------:|-------------------:|------------:|-------------:|---------:|:-------------|:--------------|:----------------|:---------------|:------------|:-----------|:-----------|
| Adelie    | AD             |     3.75  |            3.70066 |   0.0493377 |          152 | 114.465  | Standard     | Medium        | Male            | False          | False       | False      | species    |
| Adelie    | AD             |     3.8   |            3.70066 |   0.0993377 |          152 | 109.839  | Standard     | Medium        | Female          | False          | False       | False      | species    |
| Adelie    | AD             |     3.25  |            3.70066 |  -0.450662  |          152 |  85.4701 | Standard     | Medium        | Female          | False          | False       | False      | species    |
| Adelie    | AD             |   nan     |            3.70066 | nan         |          152 | nan      | Standard     | Small         | Undetermined    | False          | False       | False      | species    |
| Adelie    | AD             |     3.45  |            3.70066 |  -0.250662  |          152 |  92.6199 | Standard     | Medium        | Female          | False          | False       | False      | species    |
| Adelie    | AD             |     3.65  |            3.70066 |  -0.0506623 |          152 | 101.108  | Standard     | Medium        | Male            | False          | False       | False      | species    |
| Adelie    | AD             |     3.625 |            3.70066 |  -0.0756623 |          152 | 110.65   | Standard     | Medium        | Female          | False          | False       | False      | species    |
| Adelie    | AD             |     4.675 |            3.70066 |   0.974338  |          152 | 122.945  | Heavy        | Large         | Male            | True           | True        | False      | species    |

## Assigning Literal Constants with `pt.lit()`
In `mutate()`, all string arguments are evaluated as **formulas and column expressions**, never as raw string literals:
- If you write `status="active"`, pytae searches for a column named `active`. Because no such column exists, it raises `KeyError: name 'active' is not defined`.
- Worse, if a column named `original` happens to exist, writing `source="original"` will silently copy that column instead of assigning the word `"original"`.

To assign a standalone literal constant value directly as a keyword argument without awkward nested quotes (`status="'active'"`), wrap it in `pt.lit()`:
- `.pt.mutate(status=pt.lit("active"), source=pt.lit("original"))`

> **When is `pt.lit()` NOT needed?**
> 1. **Inside conditional helpers (`if_else`, `case_when`, `coalesce`)**: `pt.lit()` is **completely irrelevant here**. Inside formula expressions, standard inner single quotes `'...'` already distinguish string literals from column references:
>    ```python
>    df.pt.mutate(size="if_else(mass_kg >= 4.5, 'Heavy', 'Standard')")
>    ```
> 2. **In the CLI**: `pt.lit()` is **never needed in the CLI**. In terminal commands, standard inner single quotes are always used:
>    ```bash
>    pytae data.parquet -mutate "status = 'active'"
>    ```

```python
import pandas as pd
import pytae as pt

# Sample dataframe containing a column named 'original'
df = pd.DataFrame({"original": [100, 200], "val": [1, 2]})

# 1. Unquoted string matching an existing column -> copies that column!
print("Copied column 'original':\n", df.pt.mutate(source="original"))

# 2. With pt.lit(): assigns literal string constants cleanly and safely
print("\nWith pt.lit():\n", df.pt.mutate(source=pt.lit("original"), status=pt.lit("active")))
```

**Output:**
```text
Copied column 'original':
    original  val  source
0       100    1     100
1       200    2     200

With pt.lit():
    original  val    source  status
0       100    1  original  active
1       200    2  original  active
```

## Multi-Column Transforms (`(col1, col2) = _ * 2`)

Apply the same formula across multiple columns at once using parenthesized target specifications `[prefix](target_cols)[suffix] = expr` and `_` as the placeholder for each target column:
- **In-place overwrite**: `"(bill_length_mm, bill_depth_mm) = _ / 10"`
- **Create new columns via suffix or prefix**: `"(bill_length_mm, bill_depth_mm)_cm = _ / 10"` or `"norm_(bill_length_mm, bill_depth_mm) = _ / max(_)"`
- **Pattern & dtype selectors**: Any `select()` selector works inside the parentheses (`startswith=`, `endswith=`, `contains=`, `regex=`, `dtype=numeric`, slices `a:b`).
- **Group-aware**: Combines naturally with `.pt.by()`, automatically excluding active grouping columns when selecting by `dtype=`.

```python
# Create new columns with a _cm suffix across multiple columns
(
    penguins.pt.mutate("(bill_length_mm, bill_depth_mm)_cm = _ / 10")
    .pt.select("species", "bill_length_mm", "bill_length_mm_cm", "bill_depth_mm", "bill_depth_mm_cm")
    .head(5)
)
```

**Output:**

| species   |   bill_length_mm |   bill_length_mm_cm |   bill_depth_mm |   bill_depth_mm_cm |
|:----------|-----------------:|--------------------:|----------------:|-------------------:|
| Adelie    |             39.1 |                3.91 |            18.7 |               1.87 |
| Adelie    |             39.5 |                3.95 |            17.4 |               1.74 |
| Adelie    |             40.3 |                4.03 |            18   |               1.8  |
| Adelie    |            nan   |              nan    |           nan   |             nan    |
| Adelie    |             36.7 |                3.67 |            19.3 |               1.93 |

```python
# Grouped z-score standardization across all numeric columns using (dtype=numeric)
(
    penguins.pt.select("species", "bill_length_mm", "bill_depth_mm", "body_mass_g")
    .pt.by("species")
    .pt.mutate("z_(dtype=numeric) = (_ - mean(_)) / std(_)")
    .head(5)
)
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |   body_mass_g |   z_bill_length_mm |   z_bill_depth_mm |   z_body_mass_g |
|:----------|-----------------:|----------------:|--------------:|-------------------:|------------------:|----------------:|
| Adelie    |             39.1 |            18.7 |          3750 |           0.11587  |          0.290669 |        0.107591 |
| Adelie    |             39.5 |            17.4 |          3800 |           0.266054 |         -0.777839 |        0.216627 |
| Adelie    |             40.3 |            18   |          3250 |           0.566421 |         -0.284681 |       -0.982764 |
| Adelie    |            nan   |           nan   |           nan |         nan        |        nan        |      nan        |
| Adelie    |             36.7 |            19.3 |          3450 |          -0.785232 |          0.783827 |       -0.546622 |
