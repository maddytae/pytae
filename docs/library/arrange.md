# `arrange` — Row Sorting & Ordering

[← Back to Library Reference Hub](../library.md)


`arrange` orders DataFrame rows by one or more columns with full support for descending orders (`desc`, `-col`), global `ascending=` overrides, and bracket notation for columns with spaces (`[col name]`).

| Method | Key Params | Purpose |
|---|---|---|
| `.pt.arrange(*cols, ascending=None, na_last=True)` | `*cols`, `ascending`, `na_last` | Sort rows ascending / descending |

---

```python
import pytae as pt

penguins = pt.sample_data["penguins"]
tips = pt.sample_data["tips"]
penguins.head(3)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

## 1. `arrange()` — Basic Sorting

By default, `.pt.arrange()` sorts in ascending order.

```python
# Sort ascending by body mass
(penguins.pt.arrange("body_mass_g").pt.select("species", "island", "body_mass_g").head(5))
```

**Output:**

| species   | island    |   body_mass_g |
|:----------|:----------|--------------:|
| Chinstrap | Dream     |          2700 |
| Adelie    | Biscoe    |          2850 |
| Adelie    | Biscoe    |          2850 |
| Adelie    | Torgersen |          2900 |
| Adelie    | Dream     |          2900 |

## 2. Descending Order: `desc` keyword and `-` shorthand

Specify descending order either by appending `desc` or prefixing the column name with `-`.

```python
# Using explicit 'desc'
(penguins.pt.arrange("body_mass_g desc").pt.select("species", "island", "body_mass_g").head(5))
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |
| Gentoo    | Biscoe   |          6000 |
| Gentoo    | Biscoe   |          5950 |

```python
# Using leading minus '-' shorthand
(penguins.pt.arrange("-body_mass_g").pt.select("species", "island", "body_mass_g").head(5))
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |
| Gentoo    | Biscoe   |          6000 |
| Gentoo    | Biscoe   |          5950 |

## 3. Multi-Column Sorting

Pass multiple column specifications either as separate arguments or as a comma-separated string.

```python
# Multi-column: species ascending, body_mass_g descending
(penguins.pt.arrange("species", "body_mass_g desc").pt.select("species", "island", "body_mass_g").head(6))
```

**Output:**

| species   | island    |   body_mass_g |
|:----------|:----------|--------------:|
| Adelie    | Biscoe    |          4775 |
| Adelie    | Biscoe    |          4725 |
| Adelie    | Torgersen |          4700 |
| Adelie    | Torgersen |          4675 |
| Adelie    | Dream     |          4650 |
| Adelie    | Dream     |          4600 |

```python
# Comma-separated string with shorthand minus
(penguins.pt.arrange("species, -body_mass_g").pt.select("species", "island", "body_mass_g").head(6))
```

**Output:**

| species   | island    |   body_mass_g |
|:----------|:----------|--------------:|
| Adelie    | Biscoe    |          4775 |
| Adelie    | Biscoe    |          4725 |
| Adelie    | Torgersen |          4700 |
| Adelie    | Torgersen |          4675 |
| Adelie    | Dream     |          4650 |
| Adelie    | Dream     |          4600 |

## 4. Column Names with Spaces (`[col name]`)

Columns with spaces are cleanly referenced using square brackets `[col name]`.

```python
# Rename column to include spaces
spaced_penguins = penguins.rename(columns={"bill_length_mm": "bill length mm"})

# Sort by bracketed column name descending
(spaced_penguins.pt.arrange("[bill length mm] desc").pt.select("species", "[bill length mm]").head(5))
```

**Output:**

| species   |   bill length mm |
|:----------|-----------------:|
| Gentoo    |             59.6 |
| Chinstrap |             58   |
| Gentoo    |             55.9 |
| Chinstrap |             55.8 |
| Gentoo    |             55.1 |

## 5. Functional Style (`pt.arrange`)

Available as standalone functional verb `pt.arrange(df, ...)`:

```python
# Functional arrange
top_tips = pt.arrange(tips, "-tip")
top_tips[["total_bill", "tip", "day"]].head(4)
```

**Output:**

|   total_bill |   tip | day   |
|-------------:|------:|:------|
|        50.81 | 10    | Sat   |
|        48.33 |  9    | Sat   |
|        39.42 |  7.58 | Sat   |
|        48.27 |  6.73 | Sat   |
