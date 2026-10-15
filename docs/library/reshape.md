# `long` / `wide` — Pure 1-to-1 Reshaping

[← Back to Library Reference Hub](../library.md)


`long` melts numeric columns to rows. `wide` spreads a column's values into headers.

| Method | Key params | Purpose |
|---|---|---|
| `.pt.long(cols=None, id_vars=None, c='variable', v='value')` | `cols`, `id_vars`, `c`, `v` | wide → long (melt) |
| `.pt.wide(r=None, c='variable', v='value')` | `r`, `c`, `v` | long → wide (pure 1:1 unmelt) |

They are designed to work together as a **strictly complementary 1-to-1 reshaping pair**.

> **Note on Aggregation:**
> `wide()` is strictly for 1-to-1 structural reshaping without aggregation. If your data contains duplicate row/column keys and requires summarization (`mean`, `sum`, `count`/`n`), use [**`pt.pivot`**](pivot.md).

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")
flights = pt.sample("flights")
healthexp = pt.sample("healthexp")

flights.head()
```

**Output:**

|   year | month   |   passengers |
|-------:|:--------|-------------:|
|   1949 | Jan     |          112 |
|   1949 | Feb     |          118 |
|   1949 | Mar     |          132 |
|   1949 | Apr     |          129 |
|   1949 | May     |          121 |

## 1. `long` — Melt Columns to Rows

Melts all numeric columns to rows by default, preserving non-numeric columns as row identifiers:

```python
# Melt numeric columns into (variable, value) pairs
(penguins.pt.select("species", "bill_length_mm", "bill_depth_mm").pt.long().head())
```

**Output:**

| species   | variable       |   value |
|:----------|:---------------|--------:|
| Adelie    | bill_length_mm |    39.1 |
| Adelie    | bill_length_mm |    39.5 |
| Adelie    | bill_length_mm |    40.3 |
| Adelie    | bill_length_mm |   nan   |
| Adelie    | bill_length_mm |    36.7 |

```python
# Customize target column names for variable and value
(flights.pt.long(c="metric", v="value").head())
```

**Output:**

| month   | metric   |   value |
|:--------|:---------|--------:|
| Jan     | year     |    1949 |
| Feb     | year     |    1949 |
| Mar     | year     |    1949 |
| Apr     | year     |    1949 |
| May     | year     |    1949 |

```python
# Explicit id_vars: specify which columns remain fixed
(healthexp.pt.long(id_vars=["Year", "Country"], c="Metric", v="Amount").head())
```

**Output:**

|   Year | Country       | Metric       |   Amount |
|-------:|:--------------|:-------------|---------:|
|   1970 | Germany       | Spending_USD |  252.311 |
|   1970 | France        | Spending_USD |  192.143 |
|   1970 | Great Britain | Spending_USD |  123.993 |
|   1970 | Japan         | Spending_USD |  150.437 |
|   1970 | USA           | Spending_USD |  326.961 |

## 2. `wide` — Pure 1-to-1 Unmelting

Pivots categorical values in column `c` into column headers, pulling cell values from `v`. Every `(r, c)` combination must be unique.

```python
# flights has exactly one row per year + month: perfect 1-to-1 unmelt
flights_wide = flights.pt.wide(c="month", v="passengers")
flights_wide.head()
```

**Output:**

|   year |   Jan |   Feb |   Mar |   Apr |   May |   Jun |   Jul |   Aug |   Sep |   Oct |   Nov |   Dec |
|-------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
|   1949 |   112 |   118 |   132 |   129 |   121 |   135 |   148 |   148 |   136 |   119 |   104 |   118 |
|   1950 |   115 |   126 |   141 |   135 |   125 |   149 |   170 |   170 |   158 |   133 |   114 |   140 |
|   1951 |   145 |   150 |   178 |   163 |   172 |   178 |   199 |   199 |   184 |   162 |   146 |   166 |
|   1952 |   171 |   180 |   193 |   181 |   183 |   218 |   230 |   242 |   209 |   191 |   172 |   194 |
|   1953 |   196 |   196 |   236 |   235 |   229 |   243 |   264 |   272 |   237 |   211 |   180 |   201 |

```python
# Explicit row identifier parameter (r=)
demo_long = pd.DataFrame({"id": [1, 2, 3], "quarter": ["Q1", "Q2", "Q3"], "sales": [100, 200, 300]})
demo_long.pt.wide(r="id", c="quarter", v="sales")
```

**Output:**

|   id |   Q1 |   Q2 |   Q3 |
|-----:|-----:|-----:|-----:|
|    1 |  100 |  nan |  nan |
|    2 |  nan |  200 |  nan |
|    3 |  nan |  nan |  300 |

## 3. Strict 1-to-1 Reshaping Guarantees

If your DataFrame contains duplicate row/column pairs, `wide()` refuses to silently aggregate and raises a clear error directing you to `pt.pivot()`:

```python
# penguins has multiple individuals per (island, species), so wide() halts:
try:
    penguins.pt.wide(r="island", c="species", v="body_mass_g")
except ValueError as e:
    print("Error caught successfully:")
    print(e)
```

**Output:**
```text
Error caught successfully:
wide() encountered duplicate entries for row 'r' ['island'] and column 'species'. wide() is strictly for 1-to-1 reshaping without aggregation. Use pt.pivot() / -pivot to summarize or aggregate duplicate entries.
```

To summarize duplicate keys across dimensions, use [`pt.pivot`](pivot.md) instead:

```python
# Proper aggregation with pt.pivot:
penguins.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |  3709.66 |      nan    |  5076.02 |
| Dream     |  3688.39 |     3733.09 |   nan    |
| Torgersen |  3706.37 |      nan    |   nan    |

## 4. Round-Trip Reshaping (`long` ↔ `wide`)

Because `long` and `wide` are strict bijections, a DataFrame can be unpivoted to long format and seamlessly restored to its original structure:

```python
# Start with wide flights
wide_orig = flights.pt.wide(c="month", v="passengers")

# 1. Melt to long
long_form = wide_orig.pt.long(c="month", v="passengers", id_vars=["year"])

# 2. Reshape back to wide
wide_restored = long_form.pt.wide(r="year", c="month", v="passengers")

# 3. Verify exact match (aligning column order)
pd.testing.assert_frame_equal(wide_orig[wide_restored.columns], wide_restored)
print("Round-trip verified: wide_orig matches wide_restored perfectly!")
wide_restored.head()
```

**Output:**

|   year |   Apr |   Aug |   Dec |   Feb |   Jan |   Jul |   Jun |   Mar |   May |   Nov |   Oct |   Sep |
|-------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
|   1949 |   129 |   148 |   118 |   118 |   112 |   148 |   135 |   132 |   121 |   104 |   119 |   136 |
|   1950 |   135 |   170 |   140 |   126 |   115 |   170 |   149 |   141 |   125 |   114 |   133 |   158 |
|   1951 |   163 |   199 |   166 |   150 |   145 |   199 |   178 |   178 |   172 |   146 |   162 |   184 |
|   1952 |   181 |   242 |   194 |   180 |   171 |   230 |   218 |   193 |   183 |   172 |   191 |   209 |
|   1953 |   235 |   272 |   201 |   196 |   196 |   264 |   243 |   236 |   229 |   180 |   211 |   237 |
