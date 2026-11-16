# CLI Feature Guide: Row Filtering & Slicing

[← Back to Master Reference](../pytae.md)

Filter rows using pytae's ergonomic filter expressions (`-filter`), drop missing rows (`-dropna`), or slice rows (`-head`, `-tail`, `-arrange`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Pytae Filtering (`-filter`)](#pytae-filtering--filter)
  - [Exact Matching (`==`)](#exact-matching)
  - [Comparisons (`>`, `<`, `>=`, `<=`, `!=`)](#comparisons)
  - [Boolean Logic (`&`, `|`, `~`, and `(...)`)](#boolean-logic)
  - [Column-to-Column Comparisons (`col_a == col_b`)](#column-to-column-comparisons-col_a--col_b)
  - [Ranges & Intervals: Option 1 & Option 2 Dictionaries](#ranges--intervals)
  - [List Membership (`in` and `~in`)](#list-membership)
  - [Filtering Null Values (`is_null()`, `is_not_null()`) & Columns with Spaces](#filtering-null-values-and-columns-with-spaces)
  - [Combining Multiple Conditions](#combining-multiple-conditions)
  - [Strict Syntax Enforcement & Diagnostic Errors](#strict-syntax-enforcement)
- [Slicing Extreme Rows](#slicing-extreme-rows)
- [Inline Data Assertions (`-assert`)](#inline-data-assertions--assert)
- [Dropping Missing Values (`-dropna`)](#dropping-missing-values--dropna)
- [Quoting Best Practices](#quoting-best-practices)

---

## Overview & Differences

| Flag | Category | Key Syntax Highlights |
|---|---|---|
| `-filter CONDITIONS` | Row Filter | Strict equality `==`, boolean `&` / `|` / `~`, dict intervals `{'col': ('between', min, max)}` or `{'col': (('>=', min), ('<=', max))}`, list membership `col in ['a', 'b']`, bracketed spaces `[col name]` |
| `-dropna [COLS]` | Row Filter | Drops rows containing `NaN` (bare for all columns, or comma-separated subset) |
| `-head [LIMIT]`, `-tail [LIMIT]` | Row Slicing | Extract first/last $N$, percentage (`10%`), or with ties (`ties=true`), group-aware with `-by` |

---

## Pytae Filtering (`-filter`)

Pytae's `-filter` compiles expressions directly into Polars native engine filters, achieving high execution speeds with clean, readable syntax.

<a id="exact-matching"></a>
### Exact Matching (`==`)

String values inside `-filter` must be enclosed in single quotes `'value'`, and equality comparisons strictly require `==`:

```bash
pytae penguins.parquet -filter "species == 'Gentoo'" -head 3
```

> [!IMPORTANT]
> **Strict Equality and String Quoting Requirements**:
> - **Strict `==`**: Equality comparisons require `==`. Single `=` is reserved exclusively for column assignments in `-mutate`. Using `=` in `-filter` produces an immediate error guiding you to use `==`.
> - **Quoted String Literals**: String literals must always be quoted (e.g. `'Gentoo'`, `'9'`). If an unquoted literal or number is passed when filtering a string column (e.g. `species == Gentoo`), `pytae` raises an explicit error guiding you to quote the string.
>
> **Shell Quoting Rule (Single Quotes Inside Double Quotes)**:
> In bash, zsh, or PowerShell, wrap the `-filter` argument in outer double quotes and use **single quotes** for string literals:
> ```bash
> pytae data.parquet -filter "(currency == 'CAD') & (reporting_date in ['2026-09-30'])"
> ```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Gentoo    | Biscoe   |             46.1 |            13.2 |                 211 |          4500 | Female |
| Gentoo    | Biscoe   |             50   |            16.3 |                 230 |          5700 | Male   |
| Gentoo    | Biscoe   |             48.7 |            14.1 |                 210 |          4450 | Female |

<a id="comparisons"></a>
### Comparisons (`>`, `<`, `>=`, `<=`, `!=`)

Standard mathematical comparison operators are supported:

```bash
pytae penguins.parquet -filter "body_mass_g > 5500" -select "species, island, body_mass_g" -head 3
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5550 |

<a id="boolean-logic"></a>
### Boolean Logic (`&`, `|`, `~`, and `(...)`)

Filter expressions strictly enforce `&`, `|`, and `~` for boolean logic, matching Python's bitwise operators on Series and DataFrames:

```bash
# Conjunction with '&'
pytae penguins.parquet -filter "(species == 'Gentoo') & (body_mass_g > 5500)" -select "species, body_mass_g" -head 3

# Disjunction with '|'
pytae penguins.parquet -filter "(island == 'Dream') | (island == 'Torgersen')" -select "species, island" -head 3

# Negation with '~'
pytae penguins.parquet -filter "~(body_mass_g > 4000)" -head 3

# Bare boolean columns
pytae loans.parquet -filter "is_active & ~is_delinquent"

# Grouping and precedence with nested parentheses:
pytae penguins.parquet -filter "((species == 'Adelie') | (species == 'Chinstrap')) & (body_mass_g > 4000)" -head 3
```

> [!NOTE]
> Following Python's *"one and only one obvious way"*, `pytae` strictly uses `&`, `|`, and `~` everywhere for boolean logic. The English words `and`, `or`, and `not` are retired. Using `and`, `or`, `not`, `!`, or `,` raises an explicit error guiding you to use `&`, `|`, or `~`.

### Chained Comparisons & LHS Arithmetic Expressions

Filter expressions support chained comparisons and arithmetic operations:

```bash
# Chained mathematical intervals
pytae penguins.parquet -filter "3000 <= body_mass_g <= 4500"

# Arithmetic expressions
pytae penguins.parquet -filter "bill_length_mm * 2 > 80"
```

<a id="column-to-column-comparisons-col_a--col_b"></a>
### Column-to-Column Comparisons (`col_a == col_b`)

You can compare two columns directly against each other (e.g. reconciling IDs, detecting limit breaches) using `c.` in Python and bare column names in CLI:

```python
# In Python API (type-safe c. expressions)
from pytae import c

df.filter(c.tranche_id == c.deal_id)
df.filter(c.amount > c.limit)
```

```bash
# In CLI (bare column names on both sides)
pytae loans.parquet -filter "tranche_id == deal_id"
pytae loans.parquet -filter "amount > limit"
```

> [!NOTE]
> In `pytae`, unquoted identifiers on the right-hand side of a comparison resolve to the corresponding DataFrame column. If the name is not found in the DataFrame schema, `pytae` raises an explicit error with a fuzzy-match suggestion and a reminder to quote string literals, preventing silent zero-row matches.

<a id="ranges--intervals"></a>
### Ranges & Intervals: Option 1 & Option 2 Dictionaries

Mathematical bracket strings like `[3000, 3200]` have been dropped to eliminate list ambiguity. In modern `pytae`, range and interval queries are expressed through dictionary options or boolean string expressions:

#### Option 1: Native Polars `between`
Pass a dictionary specifying `('between', min, max)` for high-speed inclusive bounds:

```bash
pytae penguins.parquet -filter "{'body_mass_g': ('between', 3000, 3200)}" -select "species,body_mass_g" -head 3
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |          3200 |
| Adelie    |          3200 |
| Adelie    |          3000 |

#### Option 2: Multi-Condition Tuples `(('op1', val1), ('op2', val2))`
Pass a dictionary containing a tuple of `(operator, value)` pairs to apply multiple conditions on the same column:

```bash
pytae penguins.parquet -filter "{'body_mass_g': (('>=', 3000), ('<=', 3200))}" -select "species,body_mass_g" -head 3
```

#### String Expression Range
You can also write ranges directly in filter strings using `&`:

```bash
pytae penguins.parquet -filter "(body_mass_g >= 3000) & (body_mass_g <= 3200)" -select "species,body_mass_g" -head 3
```

<a id="list-membership"></a>
### List Membership (`in` and `~in`)

Match against a set of candidate values using `in` or `~` negation:

```bash
# Inclusive candidate set
pytae penguins.parquet -filter "species in ['Chinstrap', 'Gentoo']" -select "species,island" -head 3

# Exclusion
pytae penguins.parquet -filter "~(species in ['Adelie'])" -select "species,island" -head 3
```

**Output:**

| species   | island   |
|:----------|:---------|
| Chinstrap | Dream    |
| Chinstrap | Dream    |
| Chinstrap | Dream    |

<a id="filtering-null-values-and-columns-with-spaces"></a>
### Filtering Null Values (`is_null()`, `is_not_null()`) & Columns with Spaces

In Pytae, all missing data and non-finite floating-point values (`NaN`) are normalized uniformly to Arrow `null` upon ingestion and derivation. In line with **"One and only one obvious way"**, null checking follows a single canonical standard across both expressions and dictionaries:
- **`null` checks**: Use `.is_null()` or `.is_not_null()`.
  - In string expressions: `"sex.is_null()"` or `"sex.is_not_null()"`
  - In dictionaries: `"{sex: is_null()}"` or `"{sex: is_not_null()}"`
  - *(Note: Parentheses are strictly required; bare words like `{sex: is_null}` and `None` like `{sex: None}` are disallowed)*
  - *(Note: Dedicated `is_nan()` and `is_not_nan()` tokens are retired; all `NaN` values normalize to `null` so `is_null()` handles all missing and non-finite values uniformly)*
- For columns whose names contain spaces or special punctuation, enclose the column name in brackets `[col name]`.

```bash
# 1. Bracket method notation for non-null values
pytae penguins.parquet -rename "bill_length_mm:[bill length mm]" -filter "[bill length mm].is_not_null()" -select "species,[bill length mm]" -head 3

# 2. String expression for null values
pytae penguins.parquet -filter "sex.is_null()" -select "species,sex" -head 3

# 3. Dictionary filter with canonical 'is_null()' method token
pytae penguins.parquet -filter "{sex: is_null()}" -select "species,sex" -head 3
pytae penguins.parquet -filter "{sex: is_not_null()}" -select "species,sex" -head 3
```

**Output:**

| species   |   bill length mm |
|:----------|-----------------:|
| Adelie    |             39.1 |
| Adelie    |             39.5 |
| Adelie    |             40.3 |

<a id="combining-multiple-conditions"></a>
### Combining Multiple Conditions

Combine multiple conditions with `&`:

```bash
pytae penguins.parquet \
  -filter "(species == 'Gentoo') & (body_mass_g > 5500) & (island == 'Biscoe')" \
  -select "species,body_mass_g,sex" \
  -head 3
```

**Output:**

| species   |   body_mass_g | sex   |
|:----------|--------------:|:------|
| Gentoo    |          5700 | Male  |
| Gentoo    |          5700 | Male  |
| Gentoo    |          5550 | Male  |

<a id="strict-syntax-enforcement"></a>
### Strict Syntax Enforcement & Diagnostic Errors

`pytae` strictly validates filter expressions to prevent subtle bugs and provide immediate clarity:

1. **Single `=` is rejected**:
   ```bash
   pytae penguins.parquet -filter "species = 'Gentoo'"
   # Error: invalid filter condition 'species = 'Gentoo'': use '==' for equality comparisons (e.g. species == 'Gentoo'). Single '=' is for assignment (-mutate), not comparison (-filter).
   ```
2. **Comma `,` as a boolean operator is rejected**:
   ```bash
   pytae penguins.parquet -filter "species == 'Gentoo', body_mass_g > 5000"
   # Error: invalid filter condition 'species == 'Gentoo', body_mass_g > 5000': comma ',' is not supported as a boolean operator. Use '&' instead.
   ```
3. **English words `and`, `or`, and `not` are retired**:
   ```bash
   pytae penguins.parquet -filter "species == 'Gentoo' and body_mass_g > 5000"
   # Error: invalid filter condition 'species == 'Gentoo' and body_mass_g > 5000': 'and' is retired in filter. In line with 'one and only one obvious way', use '&' instead (e.g. (a == 1) & (b == 2)).
   ```
4. **Bracket interval notation `[min, max]` is rejected**:
   ```bash
   pytae penguins.parquet -filter "body_mass_g = [3000, 3200]"
   # Error: filter(): interval notation '[3000, 3200]' is not supported. Use '&' (e.g. (body_mass_g >= 3000) & (body_mass_g <= 3200)), or dict syntax 'body_mass_g: ("between", 3000, 3200)'.
   ```

---

## Slicing Extreme Rows

Extract top or bottom rows ordered by a specific column by composing `-arrange` with group-aware `-head` or `-tail`. For complete details and syntax, see the [Row Slicing Guide](head_tail.md).

### Top N Rows Overall

```bash
pytae penguins.parquet -arrange "body_mass_g.desc()" -head 3 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |

### Bottom N Rows per Group (`-by`)

When combined with `-by`, `-head` and `-tail` extract rows within each unique group:

```bash
pytae penguins.parquet -by species -arrange body_mass_g -head 1 -select "species,body_mass_g"
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |          2850 |
| Chinstrap |          2700 |
| Gentoo    |          3950 |

---

## Inline Data Assertions (`-assert`)

While `-filter` silently keeps only matching rows, `-assert` enforces data quality and schema invariants at any point in the pipeline. If all rows satisfy the assertion conditions, the pipeline continues uninterrupted; if any condition fails, execution halts immediately with an informative error displaying the number of failing rows and sample violations.

```bash
# Validate ranges and non-null constraints:
pytae penguins.parquet -assert "body_mass_g > 0 and species.is_not_null()"

# Chain assertions between transformations:
pytae raw_events.parquet \
  -filter "status == 'SUCCESS'" \
  -assert "user_id.is_not_null() and amount >= 0" \
  -mutate "tax = amount * 0.08" \
  -assert "tax >= 0" \
  -o processed_events.parquet
```

### Python API (`df.assert_()` / `pt.assert_()`)

```python
import pytae as pt
from pytae import c

df = pt.read("penguins.parquet")

# Method chaining:
validated = (
    df
    .filter(c.body_mass_g > 3000)
    .assert_(c.species.is_in(['Adelie', 'Gentoo', 'Chinstrap']))
    .mutate(mass_kg=c.body_mass_g / 1000)
    .assert_(c.mass_kg > 3.0)
)

# Functional API:
pt.assert_(df, c.bill_length_mm > 0, c.sex.is_not_null())

# Accessor API:
df.pt.assert_(c.body_mass_g > 0)
```

---

## Dropping Missing Values (`-dropna`)

Drop rows with missing values (`NaN`). Can be run bare or scoped to a comma-separated column list:

```bash
# Drop rows with NaN in any column
pytae penguins.parquet -dropna -head 3
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Torgersen | 39.5 | 17.4 | 186.0 | 3800.0 | Female |
| Adelie | Torgersen | 40.3 | 18.0 | 195.0 | 3250.0 | Female |

```bash
# Drop rows with NaN in specific column(s)
pytae penguins.parquet -dropna "body_mass_g,sex" -head 3
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Torgersen | 39.5 | 17.4 | 186.0 | 3800.0 | Female |
| Adelie | Torgersen | 40.3 | 18.0 | 195.0 | 3250.0 | Female |

> [!NOTE]
> For scoped aggregations and pivot tables, pass `dropna=true` inside the operation's spec (e.g., `-agg "a=mean,dropna=true"` or `-pivot "r=species,c=sex,dropna=true"`).

---

## Quoting Best Practices

In terminal shells (bash, zsh):
- Enclose the entire spec in outer double quotes: `-filter "..."`.
- Enclose string literals in inner single quotes: `'Gentoo'`, `'9'`. Unquoted strings or numbers against string columns will raise an explicit `TypeError`.
- Numeric literals should remain unquoted: `body_mass_g > 3500`.
- Columns with spaces should be wrapped in brackets: `[bill length mm] > 40` or `-arrange "[bill length mm].desc()" -head 3`.
