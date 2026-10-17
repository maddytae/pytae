# CLI Feature Guide: SQL Engine

[← Back to Master Reference](../../pytae.md)

Execute full analytical SQL queries directly against tabular files and in-memory pipeline views via Polars SQLContext using `-sql`.

---

## Contents

- [Overview & Architecture](#overview--architecture)
- [Basic Queries Against Table `data`](#basic-queries-against-table-data)
- [Aggregations & Grouping](#aggregations--grouping)
- [Window Functions](#window-functions)
- [Common Table Expressions (CTEs)](#common-table-expressions-ctes)
- [Columns With Spaces & Identifier Quoting](#columns-with-spaces--identifier-quoting)
- [Reading SQL From File (`@query.sql`)](#reading-sql-from-file-querysql)
- [Multi-File SQL Joins](#multi-file-sql-joins)

---

## Overview & Architecture

Pytae integrates the native Polars SQL engine (`SQLContext`) to provide zero-copy, vectorized SQL execution directly against your data without external dependencies:
- In single-file pipelines, the current dataset view is queryable as table **`data`**.
- In multi-file mode (`-file`), each file alias (e.g. `df1`, `df2`) is queryable directly by name.
- SQL can be inserted at any point in the pipeline and chained with other pytae flags.

---

## Basic Queries Against Table `data`

Filter and select columns with standard SQL syntax:

```bash
pytae penguins.parquet -sql "select species, island, body_mass_g from data where body_mass_g > 5500" -head 3
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5550 |

---

## Aggregations & Grouping

Perform group aggregations, aliases, and ordering:

```bash
pytae penguins.parquet \
  -sql "select species, count(*) as count, round(avg(body_mass_g), 1) as avg_mass from data group by species order by avg_mass desc"
```

**Output:**

| species   |   count |   avg_mass |
|:----------|--------:|-----------:|
| Gentoo    |     124 |     5076   |
| Chinstrap |      68 |     3733.1 |
| Adelie    |     152 |     3700.7 |

---

## Window Functions

Run analytical window functions such as `ROW_NUMBER()`, `RANK()`, or running totals:

```bash
# Top 2 heaviest penguins per species
pytae penguins.parquet \
  -sql "select species, body_mass_g, row_number() over (partition by species order by body_mass_g desc) as rnk from data where body_mass_g is not null" \
  -filter "rnk <= 2"
```

**Output:**

| species   |   body_mass_g |   rnk |
|:----------|--------------:|------:|
| Adelie    |          4775 |     1 |
| Adelie    |          4725 |     2 |
| Chinstrap |          4800 |     1 |
| Chinstrap |          4550 |     2 |
| Gentoo    |          6300 |     1 |
| Gentoo    |          6050 |     2 |

---

## Common Table Expressions (CTEs)

Complex multi-step queries with `WITH` clauses work seamlessly:

```bash
pytae penguins.parquet -sql "
  with summary as (
    select species, avg(body_mass_g) as avg_mass
    from data
    where body_mass_g is not null
    group by species
  )
  select * from summary order by avg_mass desc
"
```

**Output:**

| species   |   avg_mass |
|:----------|-----------:|
| Gentoo    |    5076.02 |
| Chinstrap |    3733.09 |
| Adelie    |    3700.66 |

---

## Columns With Spaces & Identifier Quoting

Standard SQL quoting applies:
- Column names with spaces must be escaped with escaped double quotes `\"col a\"` or brackets `[col a]`.
- String literals must use single quotes `'val'`.

```bash
pytae data.parquet -sql "select \"body mass g\", \"bill length mm\" from data where species = 'Adelie'"
```

---

## Reading SQL From File (`@query.sql`)

For long or reusable queries, place the SQL query in a `.sql` file:

```sql
-- analysis.sql
SELECT
    species,
    island,
    COUNT(*) AS total_penguins,
    ROUND(AVG(body_mass_g), 2) AS mean_weight
FROM data
WHERE sex IS NOT NULL
GROUP BY species, island
ORDER BY mean_weight DESC;
```

Execute via:
```bash
pytae penguins.parquet -sql @analysis.sql
```

**Output:**

| species | island | total_penguins | mean_weight |
|:---|:---|---:|---:|
| Gentoo | Biscoe | 119 | 5092.44 |
| Chinstrap | Dream | 68 | 3733.09 |
| Adelie | Biscoe | 44 | 3709.66 |
| Adelie | Torgersen | 47 | 3708.51 |
| Adelie | Dream | 55 | 3701.36 |

---

## Multi-File SQL Joins

In `-file` mode, combine disparate datasets using standard SQL `JOIN`:

```bash
pytae -file "customers.csv=c; orders.parquet=o" \
  -sql "select c.customer_id, c.name, count(o.order_id) as num_orders, sum(o.amount) as total_spent from c left join o on c.customer_id = o.customer_id group by c.customer_id, c.name order by c.customer_id"
```

**Output:**

| customer_id | name | num_orders | total_spent |
|---:|:---|---:|---:|
| 1 | Alice | 2 | 400.0 |
| 2 | Bob | 1 | 300.0 |
| 3 | Charlie | 0 | NaN |
