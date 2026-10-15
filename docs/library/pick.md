# `pick` — Group-Aware Extreme Row Selection

[← Back to Library Reference Hub](../library.md)


`pick` selects the top or bottom N rows (or proportion of rows via `prop=`) ordered by a column, with complete group awareness via `pt.by()`.

| Method | Key Params | Purpose |
|---|---|---|
| `.pt.by(...).pt.pick(col, n=1, prop=None, order="max")` | `col`, `n`, `prop`, `order`, `by` | Pick top or bottom N rows per group |

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

## 1. `pick()` — Top N Records

Retrieve the rows with the highest values in `col`.

```python
# Top 3 heaviest penguins overall
(penguins.pt.pick("body_mass_g", n=3).pt.select("species", "island", "body_mass_g"))
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |

## 2. `pick()` — Bottom N Records

Retrieve the rows with the lowest values in `col`.

```python
# 3 lightest penguins overall
(penguins.pt.pick("body_mass_g", n=3, order="min").pt.select("species", "island", "body_mass_g"))
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Chinstrap | Dream    |          2700 |
| Adelie    | Biscoe   |          2850 |
| Adelie    | Biscoe   |          2850 |

## 3. Group-Aware Slicing (`pt.by()`)

When preceded by `.pt.by(...)`, `pick` and `pick` extract top or bottom N rows **per group**.

```python
# Top heaviest penguin for each species
(penguins.pt.by("species").pt.pick("body_mass_g", n=1).pt.select("species", "island", "body_mass_g"))
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Adelie    | Biscoe   |          4775 |
| Chinstrap | Dream    |          4800 |
| Gentoo    | Biscoe   |          6300 |

```python
# Lightest 2 penguins per island
(penguins.pt.by("island").pt.pick("body_mass_g", n=2, order="min").pt.select("island", "species", "body_mass_g"))
```

**Output:**

| island    | species   |   body_mass_g |
|:----------|:----------|--------------:|
| Biscoe    | Adelie    |          2850 |
| Biscoe    | Adelie    |          2850 |
| Dream     | Chinstrap |          2700 |
| Dream     | Adelie    |          2900 |
| Torgersen | Adelie    |          2900 |
| Torgersen | Adelie    |          3050 |

## 4. Functional Style (`pt.pick`)

`pt.pick(df, ...)` is also available as a standalone functional verb:

```python
# Functional pick overall
pt.pick(tips, "tip", n=1)[["day", "total_bill", "tip"]]
```

**Output:**

| day   |   total_bill |   tip |
|:------|-------------:|------:|
| Sat   |        50.81 |    10 |

## 4. Proportion Slicing with `prop=`

Select a fraction of rows (e.g. `prop=0.1` for top 10%) overall or within each group.

```python
# Top 10% heaviest penguins per species
(penguins.pt.by("species").pt.pick("body_mass_g", prop=0.1))
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex   |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:------|
| Adelie    | Biscoe    |             43.2 |            19   |                 197 |          4775 | Male  |
| Adelie    | Biscoe    |             41   |            20   |                 203 |          4725 | Male  |
| Adelie    | Torgersen |             42.9 |            17.6 |                 196 |          4700 | Male  |
| Adelie    | Torgersen |             39.2 |            19.6 |                 195 |          4675 | Male  |
| Adelie    | Dream     |             39.8 |            19.1 |                 184 |          4650 | Male  |
| Adelie    | Dream     |             39.6 |            18.8 |                 190 |          4600 | Male  |
| Adelie    | Biscoe    |             45.6 |            20.3 |                 191 |          4600 | Male  |
| Adelie    | Torgersen |             42.5 |            20.7 |                 197 |          4500 | Male  |
| Adelie    | Dream     |             37.5 |            18.5 |                 199 |          4475 | Male  |
| Adelie    | Torgersen |             41.8 |            19.4 |                 198 |          4450 | Male  |
| Adelie    | Dream     |             39.6 |            18.1 |                 186 |          4450 | Male  |
| Adelie    | Torgersen |             34.6 |            21.1 |                 198 |          4400 | Male  |
| Adelie    | Dream     |             44.1 |            19.7 |                 196 |          4400 | Male  |
| Adelie    | Biscoe    |             41.3 |            21.1 |                 195 |          4400 | Male  |
| Adelie    | Dream     |             40.3 |            18.5 |                 196 |          4350 | Male  |
| Chinstrap | Dream     |             52   |            20.7 |                 210 |          4800 | Male  |
| Chinstrap | Dream     |             52.8 |            20   |                 205 |          4550 | Male  |
| Chinstrap | Dream     |             53.5 |            19.9 |                 205 |          4500 | Male  |
| Chinstrap | Dream     |             50.8 |            18.5 |                 201 |          4450 | Male  |
| Chinstrap | Dream     |             49.2 |            18.2 |                 195 |          4400 | Male  |
| Chinstrap | Dream     |             54.2 |            20.8 |                 201 |          4300 | Male  |
| Gentoo    | Biscoe    |             49.2 |            15.2 |                 221 |          6300 | Male  |
| Gentoo    | Biscoe    |             59.6 |            17   |                 230 |          6050 | Male  |
| Gentoo    | Biscoe    |             51.1 |            16.3 |                 220 |          6000 | Male  |
| Gentoo    | Biscoe    |             48.8 |            16.2 |                 222 |          6000 | Male  |
| Gentoo    | Biscoe    |             45.2 |            16.4 |                 223 |          5950 | Male  |
| Gentoo    | Biscoe    |             49.8 |            15.9 |                 229 |          5950 | Male  |
| Gentoo    | Biscoe    |             48.4 |            14.6 |                 213 |          5850 | Male  |
| Gentoo    | Biscoe    |             49.3 |            15.7 |                 217 |          5850 | Male  |
| Gentoo    | Biscoe    |             55.1 |            16   |                 230 |          5850 | Male  |
| Gentoo    | Biscoe    |             49.5 |            16.2 |                 229 |          5800 | Male  |
| Gentoo    | Biscoe    |             48.6 |            16   |                 230 |          5800 | Male  |
| Gentoo    | Biscoe    |             50.4 |            15.7 |                 222 |          5750 | Male  |
