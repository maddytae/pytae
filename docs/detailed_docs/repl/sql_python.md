# REPL Guide: SQL & Python Interop (Model A RAM Isolation)

[← Back to Master Reference](../../pytae.md)

This guide covers ANSI SQL querying across loaded tables, embedded Python execution (`py <expr>`), the **Model A RAM Isolation architecture**, and explicit `.to_pytae()` table conversion in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [ANSI SQL across Tables (`-sql`)](#ansi-sql-across-tables--sql)
  - [Explicit Table Names in SQL](#explicit-table-names-in-sql)
  - [Cross-Table SQL Joins](#cross-table-sql-joins)
  - [SQL Variable Assignment (`df3 = -sql "..."`)](#sql-variable-assignment-df3---sql-)
- [Python Execution (`py <expr>`)](#python-execution-py-expr)
  - [Single-Line Evaluation](#single-line-evaluation)
  - [Bare `py` Multi-Line Block Mode](#bare-py-multi-line-block-mode)
- [Model A Architecture & RAM Isolation](#model-a-architecture--ram-isolation)
  - [The Design Philosophy](#the-design-philosophy)
  - [Immediate Garbage Collection & Memory Zeroing](#immediate-garbage-collection--memory-zeroing)
  - [Explicit `.to_pytae()` Table Registration](#explicit-to_pytae-table-registration)
  - [Rejection of Bare `.pt` Accessor Proxies](#rejection-of-bare-pt-accessor-proxies)
  - [In-Place Active Table Mutation](#in-place-active-table-mutation)

---

## ANSI SQL across Tables (`-sql`)

### Explicit Table Names in SQL

In the REPL, every dataset in memory is registered in Polars `SQLContext` under its exact user-assigned variable name (e.g. `df`, `df2`, `orders`, `cust`), alongside saved checkpoints. No synthetic aliases (`this`, `self`, `data`) are registered, guaranteeing pure ANSI SQL and eliminating variable shadowing:

```text
# Self-contained single-table queries
pytae [customers]> -sql "SELECT country, COUNT(*) as n FROM customers GROUP BY country"
```

### Cross-Table SQL Joins

All loaded tables can be joined and queried simultaneously using standard ANSI SQL syntax:

```text
pytae [orders, cust]> -sql "SELECT orders.order_id, cust.name, orders.total FROM orders JOIN cust ON orders.cust_id = cust.id WHERE orders.total > 200"
shape: (1,240, 3)
┌──────────┬─────────────┬────────┐
│ order_id ┆ name        ┆ total  │
│ ---      ┆ ---         ┆ ---    │
│ i64      ┆ str         ┆ f64    │
╞══════════╪═════════════╪════════╡
│ 1001     ┆ Jane Doe    ┆ 245.50 │
│ 1004     ┆ John Smith  ┆ 512.00 │
└──────────┴─────────────┴────────┘
```

### SQL Variable Assignment (`df3 = -sql "..."`)

Assign SQL query results directly to new or existing tables:

```text
pytae [orders, cust]> high_value = -sql "SELECT * FROM orders WHERE total > 1000"
Created 'high_value' from SQL query (520 rows x 6 cols).
```

---

## Python Execution (`py <expr>`)

The `py` command executes arbitrary Python logic directly within the REPL session:

### Single-Line Evaluation

```text
pytae [df: 344x7]> py pldf.group_by("species").len()
shape: (3, 2)
┌───────────┬─────┐
│ species   ┆ len │
│ ---       ┆ --- │
│ str       ┆ u32 │
╞═══════════╪═════╡
│ Adelie    ┆ 152 │
│ Gentoo    ┆ 124 │
│ Chinstrap ┆ 68  │
└───────────┴─────┘
```

The execution scope automatically provides:
- `df`: The active table as a `pytae.DataFrame`.
- `pldf`: The active table as a raw `polars.DataFrame`.
- `pl`: The Polars module.
- `pt`: The Pytae module and constructor.
- `DataFrame`: The Pytae `DataFrame` class.
- All loaded workbench tables as named `pytae.DataFrame` objects.
- All defined session variables (`@var`).

### Bare `py` Multi-Line Block Mode

Entering bare `py` initiates Python block mode. You can write multi-line Python code, loops, functions, and statements, terminating the block by pressing Enter on an empty line:

```text
pytae [df: 344x7]> py
... for species, sub_df in pldf.group_by("species"):
...     print(f"Species: {species[0]} has {len(sub_df)} records")
... 
Species: Adelie has 152 records
Species: Gentoo has 124 records
Species: Chinstrap has 68 records
```

---

## Model A Architecture & RAM Isolation

### The Design Philosophy

Pytae's Python bridge is designed as an **extensibility escape hatch** for algorithms or third-party libraries (e.g. specialized pandas features, SciPy, scikit-learn) not directly native to Pytae.

Under **Model A**:
1. **Isolated Execution**: Python execution scope is temporary and ephemeral.
2. **RAM Zeroing**: As soon as `py` finishes, all intermediate Python objects, pandas DataFrames, numpy arrays, and scratch variables are **immediately deallocated and purged from RAM**.
3. **Explicit Conversion Only**: The only objects preserved in the REPL session are tables explicitly converted to native Pytae DataFrames via `.to_pytae()`.

### Immediate Garbage Collection & Memory Zeroing

If you run:
```text
pytae [df: 344x7]> py temp_pd = df.to_pandas()
pytae [df: 344x7]> py temp_pd
pytae Python Error: name 'temp_pd' is not defined
```
Notice:
- `temp_pd` was an unconverted pandas DataFrame.
- It was NOT registered into the Pytae table workbench.
- It was immediately garbage-collected and reclaimed from memory upon exit.
- Typing `temp_pd` at the REPL prompt cleanly reports:
  ```text
  pytae: 'temp_pd' is not recognized as a command, table, or flag. Use 'status table' to list loaded tables.
  ```

### Explicit `.to_pytae()` Table Registration

To persist a derived table in the Pytae REPL workbench, explicitly convert it using `.to_pytae()`:

```text
# 1. Convert to pandas, perform pandas-specific operations, and convert back
pytae [df: 344x7]> py k = df.to_pandas(); k["body_mass_kg"] = k["body_mass_g"] / 1000.0; k = k.to_pytae()
Registered table 'k' (344 rows x 8 cols).

# 2. 'k' is now a first-class Pytae table in the workbench
pytae [df: 344x7]> k -cols
species
island
bill_length_mm
bill_depth_mm
flipper_length_mm
body_mass_g
sex
body_mass_kg

# 3. Target 'k' or switch to it
pytae [df: 344x7]> k -head 3
pytae [df: 344x7]> switch k
Switched active dataset to 'k'. Active shape: (344, 8)
```

### Rejection of Bare `.pt` Accessor Proxies

Pytae strictly rejects registering bare accessor proxies (`df.to_pandas().pt`) as tables:

```text
pytae [df: 344x7]> py m = df.to_pandas().pt
pytae: 'm' is an accessor proxy, not a Pytae table. Use 'm = m.to_pytae()' to register as a table.
```

- **Why**: `.pt` is an accessor namespace proxy (`PandasPtAccessor`) designed for method chaining (`k.pt.filter(...)`), not a concrete table.
- **The Standard**: Calling `k.to_pytae()` explicitly creates a native, clean, flat `pytae.DataFrame` with full SIMD acceleration.

### In-Place Active Table Mutation

To update the active table in place using Python:

```text
pytae [df: 344x7]> py df = df.to_pandas().dropna().to_pytae()
Updated active table 'df' (333 rows x 7 cols).

pytae [df: 333x7]> -shape
(333, 7)
```
