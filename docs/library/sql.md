# `sql` — Reference

[← Back to Library Reference Hub](../library.md)


Run DuckDB SQL directly over a DataFrame. The current frame is registered as table **`data`**.
Optional extra: `pip install 'pytae[sql]'` (pulls in `duckdb`).

| Call style | Meaning |
|---|---|
| `pt.sql(df, query)` | Function form; the passed frame is table `data` |
| `df.pt.sql(query)` | Accessor form; chains with pandas / other `pt` methods |
| `pt.sql(df, query, extra=other)` | Register extra frames as additional tables (like CLI `-file` aliases) |

The name `data` is reserved for the current frame — an extra frame cannot be named `data`.
Column names with spaces need double quotes inside the query: `"bill length mm"`.

---

```python
import pandas as pd
import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
titanic = pt.sample_data['titanic']
penguins.head(3)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

## Function form — current frame is table `data`

```python
# The passed DataFrame is registered as the table `data`
pt.sql(
    penguins,
    'select species, avg(body_mass_g) as avg_mass, count(*) as n '
    'from data group by species order by species'
)
```

**Output:**

| species   |   avg_mass |   n |
|:----------|-----------:|----:|
| Adelie    |    3700.66 | 152 |
| Chinstrap |    3733.09 |  68 |
| Gentoo    |    5076.02 | 124 |

## Accessor form — `df.pt.sql(...)`

Same query engine, but chains naturally off any DataFrame.

```python
# `data` inside the query refers to the frame the accessor is called on
(
    penguins
    .pt.sql("select * from data where species = 'Adelie'")
    .head()
)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |            nan   |           nan   |                 nan |           nan | nan    |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |

## Spaced column names — double quotes, brackets `[col]`, or backticks

SQL standard uses double quotes for identifiers with spaces. `pytae` also accepts SQL-style square brackets `[col a]` and backticks (both converted to standard SQL double quotes before querying DuckDB):

```python
spaced = pd.DataFrame({'col a': [1, 20, 3], 'col b': ['x', 'y', 'z']})

# Double quotes, brackets, and backticks all work
pt.sql(spaced, 'select [col a], `col b` from data where [col a] > 2')
```

**Output:**

|   col a | col b   |
|--------:|:--------|
|      20 | y       |
|       3 | z       |

## Extra frames — joins across DataFrames

Pass additional DataFrames as keyword arguments; each becomes a table of that name.

```python
left = pd.DataFrame({'id': [1, 2, 3], 'x': ['a', 'b', 'c']})
right = pd.DataFrame({'id': [1, 3], 'y': ['p', 'q']})

# `left` is `data`; `right` is registered under the keyword name `extra`
pt.sql(left, 'select data.id, x, y from data inner join extra using (id)', extra=right)
```

**Output:**

|   id | x   | y   |
|-----:|:----|:----|
|    1 | a   | p   |
|    3 | c   | q   |

## Chaining — mix SQL with pandas and other `pt` methods

```python
# SQL to aggregate, then a plain pandas method, then another pt accessor call
(
    tips
    .pt.sql('select day, time, sum(total_bill) as bill, sum(tip) as tip from data group by day, time')
    .sort_values('bill', ascending=False)
    .pt.mutate(tip_pct='tip / bill * 100')
)
```

**Output:**

| day   | time   |    bill |    tip |   tip_pct |
|:------|:-------|--------:|-------:|----------:|
| Sat   | Dinner | 1778.4  | 260.4  |   14.6424 |
| Sun   | Dinner | 1627.16 | 247.39 |   15.2038 |
| Thur  | Lunch  | 1077.55 | 168.83 |   15.668  |
| Fri   | Dinner |  235.96 |  35.28 |   14.9517 |
| Fri   | Lunch  |   89.92 |  16.68 |   18.5498 |
| Thur  | Dinner |   18.78 |   3    |   15.9744 |

## Loading queries from an external file — `@query.txt`

Just like the CLI (`pytae data.parquet -sql @query.txt`), you can pass `@path.txt` to execute SQL queries directly from a file:

```python
import os
with open('query_demo.txt', 'w') as f:
    f.write('select species, avg(body_mass_g) as avg_mass from data group by species order by avg_mass desc')

out = penguins.pt.sql('@query_demo.txt')
if os.path.exists('query_demo.txt'):
    os.remove('query_demo.txt')
out
```

**Output:**

| species   |   avg_mass |
|:----------|-----------:|
| Gentoo    |    5076.02 |
| Chinstrap |    3733.09 |
| Adelie    |    3700.66 |

## Analytical SQL: Window Functions, CTEs, and Multi-Table Joins

DuckDB supports full ANSI SQL features including window functions, common table expressions (CTEs), and joining external frames passed via keyword arguments:

```python
# 1. Window Functions (Ranking penguins within species by body mass)
ranked_penguins = pt.sql(penguins, '''
    select species, sex, island, body_mass_g,
           dense_rank() over (partition by species order by body_mass_g desc) as rank_in_species
    from data
    where body_mass_g is not null
    limit 10
''')
display(ranked_penguins)

# 2. Common Table Expressions (CTEs)
day_summary = pt.sql(tips, '''
    with stats as (
        select day, avg(total_bill) as avg_bill, avg(tip) as avg_tip, count(*) as n
        from data
        group by day
    )
    select day, round(avg_bill, 2) as avg_bill, round(avg_tip, 2) as avg_tip,
           round(avg_tip / avg_bill * 100, 1) as tip_pct, n
    from stats
    order by avg_bill desc
''')
display(day_summary)

# 3. Multi-Table Join with extra DataFrame
df_classes = pd.DataFrame({'pclass': [1, 2, 3], 'class_name': ['First Class', 'Second Class', 'Third Class']})
titanic_joined = pt.sql(titanic, '''
    select d.sex, c.class_name, round(avg(d.survived) * 100, 1) as survival_rate_pct, count(*) as total_passengers
    from data d
    inner join classes c on d.pclass = c.pclass
    group by d.sex, c.class_name
    order by c.class_name, d.sex
''', classes=df_classes)
display(titanic_joined)
```

**Output:**

| species   | sex   | island    |   body_mass_g |   rank_in_species |
|:----------|:------|:----------|--------------:|------------------:|
| Adelie    | Male  | Biscoe    |          4775 |                 1 |
| Adelie    | Male  | Biscoe    |          4725 |                 2 |
| Adelie    | Male  | Torgersen |          4700 |                 3 |
| Adelie    | Male  | Torgersen |          4675 |                 4 |
| Adelie    | Male  | Dream     |          4650 |                 5 |
| Adelie    | Male  | Dream     |          4600 |                 6 |
| Adelie    | Male  | Biscoe    |          4600 |                 6 |
| Adelie    | Male  | Torgersen |          4500 |                 7 |
| Adelie    | Male  | Dream     |          4475 |                 8 |
| Adelie    | Male  | Dream     |          4450 |                 9 |

| day   |   avg_bill |   avg_tip |   tip_pct |   n |
|:------|-----------:|----------:|----------:|----:|
| Sun   |      21.41 |      3.26 |      15.2 |  76 |
| Sat   |      20.44 |      2.99 |      14.6 |  87 |
| Thur  |      17.68 |      2.77 |      15.7 |  62 |
| Fri   |      17.15 |      2.73 |      15.9 |  19 |

| sex    | class_name   |   survival_rate_pct |   total_passengers |
|:-------|:-------------|--------------------:|-------------------:|
| female | First Class  |                96.8 |                 94 |
| male   | First Class  |                36.9 |                122 |
| female | Second Class |                92.1 |                 76 |
| male   | Second Class |                15.7 |                108 |
| female | Third Class  |                50   |                144 |
| male   | Third Class  |                13.5 |                347 |
