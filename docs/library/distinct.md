# Distinct Rows — Removing Duplicate Rows

[← Back to Library Reference Hub](../library.md)


Remove duplicate records across the intermediate DataFrame with full control over column subsets.

`pytae` provides both the method-chaining accessor `df.pt.distinct(*cols, keep='first')` and the functional verb `pt.distinct(df, *cols)`. In the CLI, the equivalent flag is `-distinct` (or `-distinct COLS`).

| Operation | Pytae Method Chain | CLI Equivalent |
|---|---|---|
| All Columns | `df.pt.distinct()` | `-distinct` |
| Specific Columns | `df.pt.distinct('col1', 'col2')` | `-distinct "col1,col2"` |
| Keep Last / None | `df.pt.distinct(keep='last')` | N/A |

---

```python
import pytae as pt
import pandas as pd

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

## 1. Deduplicating Across All Columns (`.pt.distinct()`)

Eliminate identical rows across all selected columns. The index is automatically reset:

```python
# Keep only unique species and island pairs
(penguins.pt.select("species", "island").pt.distinct())
```

**Output:**

| species   | island    |
|:----------|:----------|
| Adelie    | Torgersen |
| Adelie    | Biscoe    |
| Adelie    | Dream     |
| Chinstrap | Dream     |
| Gentoo    | Biscoe    |

## 2. Deduplicating by Specific Identifier Columns

Pass column names to restrict duplicate checks to specific identifiers, keeping the first matching record for all other columns:

```python
# Keep the first recorded penguin for each unique species and island combination
(penguins.pt.select("species", "island", "body_mass_g", "sex").pt.distinct("species", "island"))
```

**Output:**

| species   | island    |   body_mass_g | sex    |
|:----------|:----------|--------------:|:-------|
| Adelie    | Torgersen |          3750 | Male   |
| Adelie    | Biscoe    |          3400 | Female |
| Adelie    | Dream     |          3250 | Female |
| Chinstrap | Dream     |          3500 | Female |
| Gentoo    | Biscoe    |          4500 | Female |

## 3. Chaining in Pipelines

`df.pt.distinct()` flows seamlessly inside multi-step pipelines without dropping out of `.pt`:

```python
# Filter heavy penguins -> select columns -> deduplicate -> arrange
(penguins.pt.filter("body_mass_g > 4000").pt.select("species", "island").pt.distinct().pt.arrange("species", "island"))
```

**Output:**

| species   | island    |
|:----------|:----------|
| Adelie    | Biscoe    |
| Adelie    | Dream     |
| Adelie    | Torgersen |
| Chinstrap | Dream     |
| Gentoo    | Biscoe    |

## 4. Keeping the Last Record (`keep='last'`)

Optionally retain the last occurrence instead of the first:

```python
# Retain the last record for each day and time
(tips.pt.select("day", "time", "total_bill", "tip").pt.distinct("day", "time", keep="last"))
```

**Output:**

| day   | time   |   total_bill |   tip |
|:------|:-------|-------------:|------:|
| Fri   | Dinner |        15.38 |  3    |
| Sun   | Dinner |        15.69 |  1.5  |
| Thur  | Lunch  |        16.47 |  3.23 |
| Fri   | Lunch  |        10.09 |  2    |
| Sat   | Dinner |        17.82 |  1.75 |
| Thur  | Dinner |        18.78 |  3    |

## 5. Functional Style (`pt.distinct`)

Available as a standalone function:

```python
# Functional deduplication
pt.distinct(penguins[["species", "island"]])
```

**Output:**

| species   | island    |
|:----------|:----------|
| Adelie    | Torgersen |
| Adelie    | Biscoe    |
| Adelie    | Dream     |
| Chinstrap | Dream     |
| Gentoo    | Biscoe    |
