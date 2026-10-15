# `filter` — Reference

[← Back to Library Reference Hub](../library.md)


`filter` filters a DataFrame using intuitive keyword arguments, CLI-style string expressions, plain dictionaries, or any combination of the three.

### Calling Styles

`filter` supports multiple flexible calling styles to fit interactive analysis, programmatic pipelines, and column names with spaces:

- **Keyword arguments**: `df.pt.filter(species='Adelie', body_mass_g='> 5000')`
- **String expressions** (matches CLI `-filter` syntax; handles spaces directly): `df.pt.filter("bill length mm > 40, species = 'Adelie'")`
- **Plain dictionaries** (ideal for dynamic keys or columns with spaces): `df.pt.filter({"bill length mm": "> 40", "species": "Adelie"})`
- **Mixed calling**: `df.pt.filter("bill length mm > 40", {"island": "Biscoe"}, species="Gentoo")`
- **Library function**: `pt.filter(df, species='Adelie', body_mass_g='> 5000')`

### Supported Condition Types

| Condition | Example Syntax | Meaning |
|---|---|---|
| Equality | `species='Adelie'` or `"species = Adelie"` | exact match |
| Membership | `species=['Adelie', 'Gentoo']` | in list |
| Tuple membership | `species=('in', ['Adelie', 'Gentoo'])` | in list |
| Exclusion | `sex=('not in', ['Male'])` | not in list |
| Comparison (operator) | `body_mass_g='> 5000'` or `body_mass_g=('>', 5000)` | `>`, `>=`, `<`, `<=`, `==`, `!=` |
| Open interval | `body_mass_g='(3500,4500)'` | `3500 < x < 4500` |
| Half-open interval | `bill_length_mm='[40,50)'` | `40 <= x < 50` |
| Closed interval | `body_mass_g='[3500,4000]'` | `3500 <= x <= 4000` |
| String matching | `species=('startswith', 'Ad')` | `startswith`, `endswith`, `contains`, `regex` |
| Multiple prefixes/suffixes | `species=('startswith', ['Ad', 'Ge'])` | matches any prefix/suffix in list/tuple |
| Null check | `sex=('isna',)` / `sex=('notna',)` | missing / non-missing (unary tuple) |
| Columns with spaces | `"bill length mm > 40"` or `{"bill length mm": "> 40"}` | spaces handled without dict unpacking |
| Same-column bounds | `"mass > 3000, mass < 5000"` or `"mass > 3000", "mass < 5000"` | multiple conditions on same column |

---

```python
import pytae as pt

penguins = pt.sample_data["penguins"]
tips = pt.sample_data["tips"]
titanic = pt.sample_data["titanic"]
penguins.head(3)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

## Flexible calling styles: kwargs, string expressions, and dictionaries

`filter()` accepts conditions as keyword arguments, string expressions matching the CLI `-filter` syntax, plain dictionaries, or any mix of the three. Both the DataFrame accessor (`df.pt.filter(...)`) and the top-level library verb (`pt.filter(df, ...)`) are supported.

```python
# 1. Keyword arguments — clean and pythonic
(penguins.pt.filter(species="Adelie", island="Dream").head(5))
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Dream    |             39.5 |            16.7 |                 178 |          3250 | Female |
| Adelie    | Dream    |             37.2 |            18.1 |                 178 |          3900 | Male   |
| Adelie    | Dream    |             39.5 |            17.8 |                 188 |          3300 | Female |
| Adelie    | Dream    |             40.9 |            18.9 |                 184 |          3900 | Male   |
| Adelie    | Dream    |             36.4 |            17   |                 195 |          3325 | Female |

```python
# 2. String expressions — matches pytae CLI -qry syntax; supports comma-separated conditions
(penguins.pt.filter("species = 'Adelie', body_mass_g > 4000").head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex   |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:------|
| Adelie    | Torgersen |             39.2 |            19.6 |                 195 |          4675 | Male  |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | nan   |
| Adelie    | Torgersen |             34.6 |            21.1 |                 198 |          4400 | Male  |
| Adelie    | Torgersen |             42.5 |            20.7 |                 197 |          4500 | Male  |
| Adelie    | Torgersen |             46   |            21.5 |                 194 |          4200 | Male  |

```python
# 3. Plain dictionaries — useful for programmatic pipelines or dynamic key mapping
(penguins.pt.filter({"species": "Adelie", "island": "Dream"}).head(5))
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Dream    |             39.5 |            16.7 |                 178 |          3250 | Female |
| Adelie    | Dream    |             37.2 |            18.1 |                 178 |          3900 | Male   |
| Adelie    | Dream    |             39.5 |            17.8 |                 188 |          3300 | Female |
| Adelie    | Dream    |             40.9 |            18.9 |                 184 |          3900 | Male   |
| Adelie    | Dream    |             36.4 |            17   |                 195 |          3325 | Female |

```python
# 4. Mixed calling — combine string expressions, dicts, and kwargs in a single call
(penguins.pt.filter("body_mass_g > 4000", {"island": "Biscoe"}, sex="Female").head(5))
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Gentoo    | Biscoe   |             46.1 |            13.2 |                 211 |          4500 | Female |
| Gentoo    | Biscoe   |             48.7 |            14.1 |                 210 |          4450 | Female |
| Gentoo    | Biscoe   |             46.5 |            13.5 |                 210 |          4550 | Female |
| Gentoo    | Biscoe   |             45.4 |            14.6 |                 211 |          4800 | Female |
| Gentoo    | Biscoe   |             43.3 |            13.4 |                 209 |          4400 | Female |

```python
# 5. Top-level function pt.filter(df, ...) — works identically to the .pt accessor
pt.filter(penguins, species="Gentoo", body_mass_g="> 5000").head(5)
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex   |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:------|
| Gentoo    | Biscoe   |             50   |            16.3 |                 230 |          5700 | Male  |
| Gentoo    | Biscoe   |             50   |            15.2 |                 218 |          5700 | Male  |
| Gentoo    | Biscoe   |             47.6 |            14.5 |                 215 |          5400 | Male  |
| Gentoo    | Biscoe   |             46.7 |            15.3 |                 219 |          5200 | Male  |
| Gentoo    | Biscoe   |             46.8 |            15.4 |                 215 |          5150 | Male  |

## Column names with spaces — bracket notation `[col]`

When columns have spaces (like `'bill length mm'`), enclose them in square brackets `[col]` inside string expressions. This avoids keyword argument restrictions and dictionary unpacking entirely.

```python
# DataFrame with spaces in column names
penguins_spaces = penguins.rename(columns={"bill_length_mm": "bill length mm", "body_mass_g": "body mass g"})

# String expressions with brackets handle spaced column names cleanly:
(penguins_spaces.pt.filter("[bill length mm] > 45", "[body mass g] > 4000").head(5))
```

**Output:**

| species   | island    |   bill length mm |   bill_depth_mm |   flipper_length_mm |   body mass g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             46   |            21.5 |                 194 |          4200 | Male   |
| Adelie    | Torgersen |             45.8 |            18.9 |                 197 |          4150 | Male   |
| Adelie    | Biscoe    |             45.6 |            20.3 |                 191 |          4600 | Male   |
| Chinstrap | Dream     |             46   |            18.9 |                 195 |          4150 | Female |
| Chinstrap | Dream     |             52   |            18.1 |                 201 |          4050 | Male   |

## Equality and multi-value filters

```python
# Single equality — keep only Dream island
(penguins.pt.filter(island="Dream").head(5))
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Dream    |             39.5 |            16.7 |                 178 |          3250 | Female |
| Adelie    | Dream    |             37.2 |            18.1 |                 178 |          3900 | Male   |
| Adelie    | Dream    |             39.5 |            17.8 |                 188 |          3300 | Female |
| Adelie    | Dream    |             40.9 |            18.9 |                 184 |          3900 | Male   |
| Adelie    | Dream    |             36.4 |            17   |                 195 |          3325 | Female |

```python
# List — keep Adelie and Chinstrap, aggregate per species + island
# Kwargs accept a list directly:
(
    penguins.pt.filter(species=["Adelie", "Chinstrap"])
    .pt.select("species", "island", "body_mass_g")
    .pt.by("species", "island")
    .pt.agg(a=["mean", "n"])
)
```

**Output:**

| species   | island    |   n |   body_mass_g |
|:----------|:----------|----:|--------------:|
| Adelie    | Biscoe    |  44 |       3709.66 |
| Adelie    | Dream     |  56 |       3688.39 |
| Adelie    | Torgersen |  52 |       3706.37 |
| Chinstrap | Dream     |  68 |       3733.09 |

```python
# 'not in' — exclude Male penguins via kwargs
(penguins.pt.filter(sex=("not in", ["Male"])).head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |            nan   |           nan   |                 nan |           nan | nan    |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |
| Adelie    | Torgersen |             38.9 |            17.8 |                 181 |          3625 | Female |

## Comparison operators

Comparison filters can be written as string expressions (`body_mass_g="> 5000"`) or operator tuples (`body_mass_g=('>', 5000)`).
Supported comparison operators: `>`, `>=`, `<`, `<=`, `==`, `!=`.

```python
# Filter penguins with body mass greater than 5000g (string operator)
(penguins.pt.filter(body_mass_g="> 5000").head(5))
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex   |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:------|
| Gentoo    | Biscoe   |             50   |            16.3 |                 230 |          5700 | Male  |
| Gentoo    | Biscoe   |             50   |            15.2 |                 218 |          5700 | Male  |
| Gentoo    | Biscoe   |             47.6 |            14.5 |                 215 |          5400 | Male  |
| Gentoo    | Biscoe   |             46.7 |            15.3 |                 219 |          5200 | Male  |
| Gentoo    | Biscoe   |             46.8 |            15.4 |                 215 |          5150 | Male  |

```python
# Tuple operator syntax: ('>', 5000)
(penguins.pt.filter(body_mass_g=(">", 5000)).head(5))
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex   |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:------|
| Gentoo    | Biscoe   |             50   |            16.3 |                 230 |          5700 | Male  |
| Gentoo    | Biscoe   |             50   |            15.2 |                 218 |          5700 | Male  |
| Gentoo    | Biscoe   |             47.6 |            14.5 |                 215 |          5400 | Male  |
| Gentoo    | Biscoe   |             46.7 |            15.3 |                 219 |          5200 | Male  |
| Gentoo    | Biscoe   |             46.8 |            15.4 |                 215 |          5150 | Male  |

```python
# Combine multiple column conditions in one qry call
# Gentoo females with large bills — multi-condition kwargs:
(
    penguins.pt.filter(species="Gentoo", sex="Female", bill_length_mm=">= 45")
    .pt.select("species", "island", "sex", "bill_length_mm", "body_mass_g")
    .head(5)
)
```

**Output:**

| species   | island   | sex    |   bill_length_mm |   body_mass_g |
|:----------|:---------|:-------|-----------------:|--------------:|
| Gentoo    | Biscoe   | Female |             46.1 |          4500 |
| Gentoo    | Biscoe   | Female |             48.7 |          4450 |
| Gentoo    | Biscoe   | Female |             46.5 |          4550 |
| Gentoo    | Biscoe   | Female |             45.4 |          4800 |
| Gentoo    | Biscoe   | Female |             45.5 |          4650 |

## Interval notation
String intervals let you filter a range on the same column without chaining two `.pt.filter()` calls.
`(` / `)` = exclusive bound, `[` / `]` = inclusive bound.

```python
# Open interval — strictly between 3500 and 4500 g via kwargs:
(penguins.pt.filter(body_mass_g="(3500,4500)").head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             39.3 |            20.6 |                 190 |          3650 | Male   |
| Adelie    | Torgersen |             38.9 |            17.8 |                 181 |          3625 | Female |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | nan    |

```python
# Half-open interval — bill_length_mm >= 40 and < 50
(penguins.pt.filter(bill_length_mm="[40,50)").head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | nan    |
| Adelie    | Torgersen |             41.1 |            17.6 |                 182 |          3200 | Female |
| Adelie    | Torgersen |             42.5 |            20.7 |                 197 |          4500 | Male   |
| Adelie    | Torgersen |             46   |            21.5 |                 194 |          4200 | Male   |

```python
# Closed interval — body_mass_g between 3500 and 4000 inclusive
(penguins.pt.filter(body_mass_g="[3500,4000]").head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             39.3 |            20.6 |                 190 |          3650 | Male   |
| Adelie    | Torgersen |             38.9 |            17.8 |                 181 |          3625 | Female |
| Adelie    | Torgersen |             37.8 |            17.3 |                 180 |          3700 | nan    |

```python
# Interval notation also works on STRING columns — alphabetical comparison
# 'island' values: Biscoe, Dream, Torgersen — (Biscoe, Dream] means Dream only
(penguins.pt.filter(island="(Biscoe,Dream]").sample())
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Dream    |             37.6 |            19.3 |                 181 |          3300 | Female |

## String matching and null checks
`startswith`/`endswith`/`contains`/`regex` use pandas' `.str` accessor (missing values never match, `na=False`). `contains`/`regex` both search anywhere in the string (like `re.search`) — `regex` is just `contains` with `regex=True`.

`startswith` and `endswith` also accept a list or tuple of multiple prefixes/suffixes. `isna`/`notna` are one-element tuples since they take no value.

```python
# species starting with 'Ad' — same idea for endswith/contains
(penguins.pt.filter(species=("startswith", "Ad")).head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |            nan   |           nan   |                 nan |           nan | nan    |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |

```python
# Multiple prefixes: species starting with 'Ad' OR 'Ge'
(penguins.pt.filter(species=("startswith", ["Ad", "Ge"])).head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |            nan   |           nan   |                 nan |           nan | nan    |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |

```python
# regex, search-anywhere (like re.search) — species containing a repeated 'o'
(penguins.pt.filter(species=("regex", r"oo")).head(5))
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Gentoo    | Biscoe   |             46.1 |            13.2 |                 211 |          4500 | Female |
| Gentoo    | Biscoe   |             50   |            16.3 |                 230 |          5700 | Male   |
| Gentoo    | Biscoe   |             48.7 |            14.1 |                 210 |          4450 | Female |
| Gentoo    | Biscoe   |             50   |            15.2 |                 218 |          5700 | Male   |
| Gentoo    | Biscoe   |             47.6 |            14.5 |                 215 |          5400 | Male   |

```python
# isna/notna — rows with a missing 'sex' value (one-element tuple, no value needed)
(penguins.pt.filter(sex=("isna",)))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |   sex |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|------:|
| Adelie    | Torgersen |            nan   |           nan   |                 nan |           nan |   nan |
| Adelie    | Torgersen |             34.1 |            18.1 |                 193 |          3475 |   nan |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 |   nan |
| Adelie    | Torgersen |             37.8 |            17.1 |                 186 |          3300 |   nan |
| Adelie    | Torgersen |             37.8 |            17.3 |                 180 |          3700 |   nan |
| Adelie    | Dream     |             37.5 |            18.9 |                 179 |          2975 |   nan |
| Gentoo    | Biscoe    |             44.5 |            14.3 |                 216 |          4100 |   nan |
| Gentoo    | Biscoe    |             46.2 |            14.4 |                 214 |          4650 |   nan |
| Gentoo    | Biscoe    |             47.3 |            13.8 |                 216 |          4725 |   nan |
| Gentoo    | Biscoe    |             44.5 |            15.7 |                 217 |          4875 |   nan |
| Gentoo    | Biscoe    |            nan   |           nan   |                 nan |           nan |   nan |

## Multiple conditions on the same column

Because Python keyword arguments must have unique names, you cannot pass `bill_length_mm='> 40', bill_length_mm='< 50'` in kwargs. With `filter()`, you have multiple intuitive solutions:

1. **Comma-separated string expression**: `"bill_length_mm > 40, bill_length_mm < 50"`
2. **Multiple positional string arguments**: `"bill_length_mm > 40", "bill_length_mm < 50"`
3. **Interval notation**: `bill_length_mm='[40,50)'`
4. **Chained `.pt.filter()` calls**: `.pt.filter(bill_length_mm='> 40').pt.filter(bill_length_mm='< 50')`

```python
# Comma-separated string expression on the same column:
(penguins.pt.filter("bill_length_mm > 40, bill_length_mm < 50").head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | nan    |
| Adelie    | Torgersen |             41.1 |            17.6 |                 182 |          3200 | Female |
| Adelie    | Torgersen |             42.5 |            20.7 |                 197 |          4500 | Male   |
| Adelie    | Torgersen |             46   |            21.5 |                 194 |          4200 | Male   |

```python
# Multiple string arguments:
(penguins.pt.filter("bill_length_mm > 40", "bill_length_mm < 50").head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | nan    |
| Adelie    | Torgersen |             41.1 |            17.6 |                 182 |          3200 | Female |
| Adelie    | Torgersen |             42.5 |            20.7 |                 197 |          4500 | Male   |
| Adelie    | Torgersen |             46   |            21.5 |                 194 |          4200 | Male   |

```python
# Chaining two .pt.filter() calls:
(penguins.pt.filter(bill_length_mm="> 40").pt.filter(bill_length_mm="< 50").head(5))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |             42   |            20.2 |                 190 |          4250 | nan    |
| Adelie    | Torgersen |             41.1 |            17.6 |                 182 |          3200 | Female |
| Adelie    | Torgersen |             42.5 |            20.7 |                 197 |          4500 | Male   |
| Adelie    | Torgersen |             46   |            21.5 |                 194 |          4200 | Male   |

## Helpful typo suggestions

If a column name is misspelled, `filter()` suggests close matches using fuzzy matching to help catch typos immediately.

```python
# Intentional typo 'speceis' raises KeyError with a helpful suggestion
try:
    penguins.pt.filter(speceis="Adelie")
except KeyError as exc:
    print("Caught expected error:", exc)
```

**Output:**
```text
Caught expected error: "unknown column 'speceis' (did you mean 'species'?)"
```

## Real-world pipeline: filter → aggregate

```python
# Tips: weekend dinner table of 2+, spending > $10 — average tip and bill by smoker status
# Using bracket notation [total bill] across qry and agg:
(
    tips.rename(columns={"total_bill": "total bill"})
    .pt.filter("[total bill] > 10", day=["Sat", "Sun"], time="Dinner", size=">= 2")
    .pt.by("smoker")
    .pt.agg("tip = mean, [total bill] = mean, n = n")
)
```

**Output:**

| smoker   |     tip |   total bill |   n |
|:---------|--------:|-------------:|----:|
| Yes      | 3.08772 |      23.2323 |  57 |
| No       | 3.22546 |      20.7059 |  97 |
