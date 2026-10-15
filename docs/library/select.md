# `select` — Reference

[← Back to Library Reference Hub](../library.md)


`select` picks columns by name, slice, dtype, or substring. Negative names (`'-col'`, `'~col'`), negative slices (`'-start:end'`), and `exclude=` drop columns while preserving relative order. Regex is the `regex=` keyword — a positional string that is not an exact name is an error, not a silent regex. `everything()` pulls in "the rest" after pinning specific columns first.

| Argument type | Example | Selects |
|---|---|---|
| List | `['a','b']` | exact named columns |
| String (name) | `'species'` | exact column |
| Negative string | `'-species'`, `'~island'` | exclude named column |
| Negative slice | `'-bill_length_mm:body_mass_g'` | exclude contiguous range |
| `exclude=` | `exclude='species'`, `exclude=['a','b']` | exclude specific column(s) |
| String (slice) | `'bill_length_mm:body_mass_g'` | contiguous range |
| `everything()` | after explicit cols | remaining columns |
| callable | `lambda c: c.startswith('b')` | columns passing test |
| `regex=` | `regex='mm$'` | names matching regex |
| `dtype=` | `dtype='numeric'` | by dtype |
| `exclude_dtype=` | `exclude_dtype='number'` | excluding dtype |
| `contains=` | `contains='mm'` | substring in name |
| `startswith=` | `startswith='bill'` | name prefix |
| `endswith=` | `endswith='mm'` | name suffix |

---

```python
import pytae as pt

penguins = pt.sample_data["penguins"]
titanic = pt.sample_data["titanic"]
tips = pt.sample_data["tips"]

penguins.pt.cols(ascending=None)  # see column order
```

**Output:**
```text
['species', 'island', 'bill_length_mm', 'bill_depth_mm', 'flipper_length_mm', 'body_mass_g', 'sex']
```

## Names, `contains`, and `regex`
Criteria are a union (OR). Prefer `contains=` for substrings and `regex=` for patterns. Multiple values in a list are also OR.

```python
# All columns that contain 'bill' OR 'mass', plus species
(penguins.pt.select("species", contains=["bill", "mass"]).head())
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |   body_mass_g |
|:----------|-----------------:|----------------:|--------------:|
| Adelie    |             39.1 |            18.7 |          3750 |
| Adelie    |             39.5 |            17.4 |          3800 |
| Adelie    |             40.3 |            18   |          3250 |
| Adelie    |            nan   |           nan   |           nan |
| Adelie    |             36.7 |            19.3 |          3450 |

```python
# Column order rule: explicit list preserves YOUR order; contains/regex follow original DataFrame order
# island, sex, species are listed explicitly so they come first in that exact order,
# then contains='mm' adds remaining mm-cols in original df order
(penguins.pt.select("island", "sex", "species", contains="mm").head())
```

**Output:**

| island    | sex    | species   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |
|:----------|:-------|:----------|-----------------:|----------------:|--------------------:|
| Torgersen | Male   | Adelie    |             39.1 |            18.7 |                 181 |
| Torgersen | Female | Adelie    |             39.5 |            17.4 |                 186 |
| Torgersen | Female | Adelie    |             40.3 |            18   |                 195 |
| Torgersen | nan    | Adelie    |            nan   |           nan   |                 nan |
| Torgersen | Female | Adelie    |             36.7 |            19.3 |                 193 |

```python
# Columns ending in 'mm' — anchored regex
(penguins.pt.select(regex="mm$").head())
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |
|-----------------:|----------------:|--------------------:|
|             39.1 |            18.7 |                 181 |
|             39.5 |            17.4 |                 186 |
|             40.3 |            18   |                 195 |
|            nan   |           nan   |                 nan |
|             36.7 |            19.3 |                 193 |

```python
# Combining contains= with a slice in one call (union)
# contains='mm' picks the mm-cols; 'island:body_mass_g' slice picks everything between those two cols
(penguins.pt.select("island:body_mass_g", contains="mm").head())
```

**Output:**

| island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|:----------|-----------------:|----------------:|--------------------:|--------------:|
| Torgersen |             39.1 |            18.7 |                 181 |          3750 |
| Torgersen |             39.5 |            17.4 |                 186 |          3800 |
| Torgersen |             40.3 |            18   |                 195 |          3250 |
| Torgersen |            nan   |           nan   |                 nan |           nan |
| Torgersen |             36.7 |            19.3 |                 193 |          3450 |

## Slice notation — contiguous column range
`'start_col:end_col'` selects all columns from start to end (inclusive), in DataFrame order.

```python
# Select from 'bill_length_mm' through 'body_mass_g' (all measurement cols)
(penguins.pt.select("bill_length_mm:body_mass_g").head())
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |
|            nan   |           nan   |                 nan |           nan |
|             36.7 |            19.3 |                 193 |          3450 |

```python
# Advanced regex: columns containing 'mm' but NOT 'flipper'
# this is regex for selecting all columns containing 'mm' but not 'flipper'.
# just because it can be done, does not mean it should be done.
# use more readable ways like list comprehension — this will ensure your co-workers
# don't stab you in the middle of the night
(
    penguins.pt.select(regex=r"^(?=.*mm)(?!.*flipper).*").head()  # regex sorcery
)

# More readable alternative:
cols_with_mm_not_flipper = [c for c in penguins.columns if "mm" in c and "flipper" not in c]
(penguins.pt.select(cols_with_mm_not_flipper).head())
```

**Output:**

|   bill_length_mm |   bill_depth_mm |
|-----------------:|----------------:|
|             39.1 |            18.7 |
|             39.5 |            17.4 |
|             40.3 |            18   |
|            nan   |           nan   |
|             36.7 |            19.3 |

## `everything()` — pin key columns first, then the rest
Use `everything()` to move specific columns to the front without dropping any.

```python
# Move 'body_mass_g' and 'species' to front, keep all other columns after
(penguins.pt.select("body_mass_g", "species", pt.everything()).head())
```

**Output:**

|   body_mass_g | species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm | sex    |
|--------------:|:----------|:----------|-----------------:|----------------:|--------------------:|:-------|
|          3750 | Adelie    | Torgersen |             39.1 |            18.7 |                 181 | Male   |
|          3800 | Adelie    | Torgersen |             39.5 |            17.4 |                 186 | Female |
|          3250 | Adelie    | Torgersen |             40.3 |            18   |                 195 | Female |
|           nan | Adelie    | Torgersen |            nan   |           nan   |                 nan | nan    |
|          3450 | Adelie    | Torgersen |             36.7 |            19.3 |                 193 | Female |

## Callable — select columns with a function

```python
# Lambda: columns whose name has more than 6 characters
(penguins.pt.select(lambda c: len(c) > 6).head())
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|:----------|-----------------:|----------------:|--------------------:|--------------:|
| Adelie    |             39.1 |            18.7 |                 181 |          3750 |
| Adelie    |             39.5 |            17.4 |                 186 |          3800 |
| Adelie    |             40.3 |            18   |                 195 |          3250 |
| Adelie    |            nan   |           nan   |                 nan |           nan |
| Adelie    |             36.7 |            19.3 |                 193 |          3450 |

## `dtype`, `exclude_dtype`, `contains`, `startswith`, `endswith`, `regex`

```python
# All numeric columns only
(penguins.pt.select(dtype="numeric").head())
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |
|            nan   |           nan   |                 nan |           nan |
|             36.7 |            19.3 |                 193 |          3450 |

```python
# Drop numeric columns — keep only categorical/string columns
(penguins.pt.select(exclude_dtype="number").head())
```

**Output:**

| species   | island    | sex    |
|:----------|:----------|:-------|
| Adelie    | Torgersen | Male   |
| Adelie    | Torgersen | Female |
| Adelie    | Torgersen | Female |
| Adelie    | Torgersen | nan    |
| Adelie    | Torgersen | Female |

```python
# exclude_dtype also accepts a list — exclude multiple dtype families at once
(penguins.pt.select(exclude_dtype=["datetime", "object"]).head())
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |
|            nan   |           nan   |                 nan |           nan |
|             36.7 |            19.3 |                 193 |          3450 |

```python
# Titanic: columns starting with 'p' or 'a', plus all numeric; behaviour here is | and not &
(titanic.pt.select(startswith=["p", "a"], dtype="numeric").head())
```

**Output:**

|   survived |   pclass |   age |   sibsp |   parch |    fare | adult_male   | alive   | alone   |
|-----------:|---------:|------:|--------:|--------:|--------:|:-------------|:--------|:--------|
|          0 |        3 |    22 |       1 |       0 |  7.25   | True         | no      | False   |
|          1 |        1 |    38 |       1 |       0 | 71.2833 | False        | yes     | False   |
|          1 |        3 |    26 |       0 |       0 |  7.925  | False        | yes     | True    |
|          1 |        1 |    35 |       1 |       0 | 53.1    | False        | yes     | False   |
|          0 |        3 |    35 |       0 |       0 |  8.05   | True         | no      | True    |

```python
# endswith — select columns whose name ends with a given suffix
(
    penguins.pt.select(endswith="mm").head()  # same result as .select(regex='mm$') but more readable
)
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |
|-----------------:|----------------:|--------------------:|
|             39.1 |            18.7 |                 181 |
|             39.5 |            17.4 |                 186 |
|             40.3 |            18   |                 195 |
|            nan   |           nan   |                 nan |
|             36.7 |            19.3 |                 193 |

```python
# Columns containing 'bill' or 'flipper' in name, used in a full chain ;  behaviour here is | and not &
(
    penguins.pt.filter(species=["Adelie", "Gentoo"])
    .pt.select("species", "island", contains=["bill", "flipper"])
    .pt.by("species", "island")
    .pt.agg(a=["mean", "n"])
)
```

**Output:**

| species   | island    |   n |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |
|:----------|:----------|----:|-----------------:|----------------:|--------------------:|
| Adelie    | Biscoe    |  44 |          38.975  |         18.3705 |             188.795 |
| Adelie    | Dream     |  56 |          38.5018 |         18.2518 |             189.732 |
| Adelie    | Torgersen |  52 |          38.951  |         18.4294 |             191.196 |
| Gentoo    | Biscoe    | 124 |          47.5049 |         14.9821 |             217.187 |

## Negative selection & exclusion — `-col`, `~col`, negative slices, and `exclude=`
Drop or exclude columns by prefixing names with `-` or `~`, passing a negative slice (`'-start:end'`), or using the `exclude=` parameter. Remaining columns preserve their original relative DataFrame order without needing a separate drop function.

```python
# Drop single column by negating with '-' or '~'
(penguins.pt.select("-species").head(3))
```

**Output:**

| island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

```python
# Drop multiple columns
(penguins.pt.select("-species", "-island", "-sex").head(3))
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |

```python
# Exclude a contiguous slice of columns
(penguins.pt.select("-bill_length_mm:body_mass_g").head(3))
```

**Output:**

| species   | island    | sex    |
|:----------|:----------|:-------|
| Adelie    | Torgersen | Male   |
| Adelie    | Torgersen | Female |
| Adelie    | Torgersen | Female |

```python
# Exclude columns using the exclude= keyword
(penguins.pt.select(exclude=["species", "island"]).head(3))
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|-----------------:|----------------:|--------------------:|--------------:|:-------|
|             39.1 |            18.7 |                 181 |          3750 | Male   |
|             39.5 |            17.4 |                 186 |          3800 | Female |
|             40.3 |            18   |                 195 |          3250 | Female |

```python
# Combine positive selection with negative exclusion in a chain
(penguins.pt.select(dtype="numeric").pt.select("-bill_depth_mm").head(3))
```

**Output:**

|   bill_length_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|--------------------:|--------------:|
|             39.1 |                 181 |          3750 |
|             39.5 |                 186 |          3800 |
|             40.3 |                 195 |          3250 |

## Columns with spaces — bracket notation `[col]`

Square brackets `[col name]` allow selecting and manipulating columns with spaces without quoting ambiguity, supporting individual names, comma lists, ranges, and exclusions:

```python
# Select columns with spaces using bracket notation
penguins_spaced = penguins.rename(columns={"bill_length_mm": "bill length mm", "body_mass_g": "body mass g"})
(penguins_spaced.pt.select("species", "[bill length mm]", "[body mass g]").head())
```

**Output:**

| species   |   bill length mm |   body mass g |
|:----------|-----------------:|--------------:|
| Adelie    |             39.1 |          3750 |
| Adelie    |             39.5 |          3800 |
| Adelie    |             40.3 |          3250 |
| Adelie    |            nan   |           nan |
| Adelie    |             36.7 |          3450 |

```python
# Comma-separated string with bracketed space columns
(penguins_spaced.pt.select("species, [bill length mm], [body mass g]").head())
```

**Output:**

| species   |   bill length mm |   body mass g |
|:----------|-----------------:|--------------:|
| Adelie    |             39.1 |          3750 |
| Adelie    |             39.5 |          3800 |
| Adelie    |             40.3 |          3250 |
| Adelie    |            nan   |           nan |
| Adelie    |             36.7 |          3450 |

```python
# Drop a spaced column using negative bracket syntax -[col]
(penguins_spaced.pt.select("species", "[bill length mm]", "-[bill length mm]").head())
```

**Output:**

| species   |
|:----------|
| Adelie    |
| Adelie    |
| Adelie    |
| Adelie    |
| Adelie    |
