# REPL Guide: SQL & Python Interop (Ephemeral Python Sandboxing)

[← Back to REPL Hub](README.md) | [Master Reference](../pytae.md)

This guide covers ANSI SQL querying across loaded tables, embedded Python execution (`py <expr>`), the **Ephemeral Python Sandboxing architecture**, and explicit `.to_pytae()` table registration in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [ANSI SQL across Tables (`-sql`)](#ansi-sql-across-tables--sql)
  - [Explicit Table Names in SQL](#explicit-table-names-in-sql)
  - [Cross-Table SQL Joins](#cross-table-sql-joins)
  - [SQL Variable Assignment (`df3 = -sql "..."`)](#sql-variable-assignment-df3---sql-)
  - [Multi-Line SQL Queries](#multi-line-sql-queries)
- [Python Execution (`py <expr>`)](#python-execution-py-expr)
  - [Single-Line Evaluation](#single-line-evaluation)
  - [Bare `py` Multi-Line Block Mode](#bare-py-multi-line-block-mode)
- [Ephemeral Python Sandboxing & RAM Isolation](#ephemeral-python-sandboxing--ram-isolation)
  - [The Design Philosophy](#the-design-philosophy)
  - [Immediate Garbage Collection & Memory Zeroing](#immediate-garbage-collection--memory-zeroing)
  - [Explicit `.to_pytae()` Table Registration](#explicit-to_pytae-table-registration)
  - [Rejection of Bare `.pt` Accessor Proxies](#rejection-of-bare-pt-accessor-proxies)
  - [In-Place Active Table Mutation](#in-place-active-table-mutation)
- [Comprehensive Real-World Walkthrough](#comprehensive-real-world-walkthrough)

---

## ANSI SQL across Tables (`-sql`)

Pytae embeds a native Polars `SQLContext` directly into the REPL, allowing you to run standard ANSI SQL queries across all loaded tables without copying data into an external database engine like SQLite or DuckDB.

### Explicit Table Names in SQL

All loaded tables in the workbench are registered into the SQL catalog using their exact table variable names:

```text
pytae [orders: 100,000x6]> -sql "SELECT status, count(*) AS n, sum(amount) AS total FROM orders GROUP BY 1 ORDER BY total DESC"
shape: (4, 3)
┌───────────┬───────┬────────────┐
│ status    ┆ n     ┆ total      │
│ ---       ┆ ---   ┆ ---        │
│ str       ┆ i64   ┆ f64        │
╞═══════════╪═══════╪════════════╡
│ completed ┆ 74200 ┆ 8421095.50 │
│ pending   ┆ 15100 ┆ 1420550.00 │
│ refunded  ┆  6200 ┆  510200.00 │
│ disputed  ┆  4500 ┆  380120.00 │
└───────────┴───────┴────────────┘
```

### Cross-Table SQL Joins

Execute complex relational SQL joins across multiple independent tables held in RAM:

```text
pytae [orders, cust]> -sql "SELECT c.country, count(o.order_id) as orders_count, avg(o.amount) as avg_amount FROM orders o LEFT JOIN cust c ON o.customer_id = c.customer_id GROUP BY 1 ORDER BY orders_count DESC"
```

### SQL Variable Assignment (`df3 = -sql "..."`)

Assign SQL query outputs directly into new or existing table variables:

```text
pytae [orders, cust]> top_customers = -sql "SELECT customer_id, sum(amount) as ltv FROM orders GROUP BY 1 HAVING ltv > 5000 ORDER BY ltv DESC"
Created 'top_customers' (342 rows x 2 cols).

pytae [orders, cust, top_customers]> 
```

### Multi-Line SQL Queries

Queries containing unclosed quotes automatically open a multi-line continuation prompt:

```text
pytae [orders, cust]> summary = -sql "
...> SELECT 
...>   c.country,
...>   count(*) AS total_orders,
...>   round(sum(o.amount), 2) AS gross_revenue
...> FROM orders o
...> JOIN cust c ON o.customer_id = c.customer_id
...> WHERE o.status = 'completed'
...> GROUP BY c.country
...> ORDER BY gross_revenue DESC
...> "
Created 'summary' (18 rows x 3 cols).
```

---

## Python Execution (`py <expr>`)

The REPL allows direct execution of arbitrary Python code when complex procedural logic, regex algorithms, or scientific libraries (`scipy`, `sklearn`, `numpy`) are required.

### Single-Line Evaluation

Execute a one-liner Python statement using the `py` prefix:

```text
# Inspect Python environment or standard library
pytae> py import sys; print(sys.version)
3.13.1 (main, Dec  3 2024)

# Mathematical evaluation
pytae> py import math; [math.factorial(x) for x in range(1, 6)]
[1, 2, 6, 24, 120]
```

### Bare `py` Multi-Line Block Mode

Typing bare `py` (or `py:`) opens a dedicated Python block editor that collects multiple statements and executes them together when you enter `end`:

```text
pytae [orders]> py
... import numpy as np
... rates = np.array([0.05, 0.08, 0.12])
... print("Mean rate:", rates.mean())
... end
Mean rate: 0.08333333333333333
```

### Accessing Pytae Session Variables (`@var` -> `var`)

Session variables defined with `@var = ...` in the REPL (e.g. `@path`, `@threshold`) are automatically injected into `py` blocks **as bare Python identifiers without the `@` prefix** (`path`, `threshold`):

```text
# 1. Define variable in Pytae
pytae> @data_dir = r"Z:\Finance\RiskModels\Data\HistoricalExtracts"

# 2. Access in Python without '@'
pytae> py
... import glob, polars as pl
... files = glob.glob(data_dir + r"\*.parquet")
... dfs = [pl.read_parquet(f, columns=['reporting_date', 'rwa_amount']) for f in files]
... comb_df = DataFrame(pl.concat(dfs))
... end
Registered active table 'comb_df' (250,000 rows x 2 cols).
```

> [!NOTE]
> In standard Python syntax, `@` is not a valid identifier prefix (`@path` raises a Python `SyntaxError`). Always omit the `@` when referencing variables inside Python expressions. For full details, see [Session Variables Guide](variables_config.md#accessing-session-variables-in-python-py-blocks).

---

## Ephemeral Python Sandboxing & RAM Isolation

### The Design Philosophy

In standard interactive shells (such as IPython or Jupyter), every variable created in Python lingers in the global namespace indefinitely, creating memory leaks that bloat process RSS.

Pytae implements the **Ephemeral Python Sandboxing Architecture**:
1. When entering Python mode (`py <expr>` or multi-line `py`), Pytae injects all active tables as standard `pytae.DataFrame` objects into an **isolated local dictionary**.
2. Python execution occurs within this sandboxed scope.
3. Upon block completion, Pytae immediately executes a clean-up sweep:
   - Intermediate variables, large NumPy arrays, and scratch tensors created in Python are **immediately dropped**.
   - `gc.collect()` is explicitly called.
   - Kernel page trimming (`libc.malloc_trim(0)` on Linux, `mach_task` on macOS, `K32EmptyWorkingSet` on Windows) is triggered to release resident heap pages back to the operating system.

### Immediate Garbage Collection & Memory Zeroing

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   EPHEMERAL PYTHON SANDBOXING ARCHITECTURE                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. INGEST TABLES  │ Active Pytae tables exposed as read-only references in py dict.    │
│ 2. EXECUTE SCRIPT │ User trains ML models, allocates 2 GB scratch tensors, etc.        │
│ 3. BLOCK COMPLETION│ Python execution ends.                                            │
│ 4. RAM FLUSH      │ Scratch namespace destroyed. gc.collect() invoked.                 │
│ 5. OS PAGE TRIM   │ OS kernel frees virtual memory pages. Process RSS resets to 0 MB.  │
│ 6. EXPLICIT HANDOFF│ ONLY tables explicitly registered via .to_pytae() persist in REPL.│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Explicit `.to_pytae()` Table Registration

To promote a Python DataFrame into the active Pytae workbench, you **must explicitly call `.to_pytae('<table_name>')`**:

```text
pytae [orders]> py
... # Heavy computation inside Python
... df = orders.to_polars()
... df = df.with_columns(log_amount = pl.col("amount").log())
... # Register back to Pytae:
... pt.DataFrame(df).to_pytae("orders_log")
... end
Registered table 'orders_log' in Pytae workbench.

pytae [orders, orders_log]> 
```

### Rejection of Bare `.pt` Accessor Proxies

To prevent memory leaks and ambiguous pointer references across the C-Python boundary:
- Tables inside the `py` block must be explicitly converted using `.to_pytae()`.
- Unassigned or bare Python variables (`x = 100`) do not persist in Pytae's `@variable` registry.
- Tables cannot be accidentally overwritten without an explicit assignment or registration.

### In-Place Active Table Mutation

If you wish to mutate the currently active table using Python logic:

```text
pytae [orders: 100,000x6]> py
... clean_orders = orders.filter("amount > 0").arrange("amount desc")
... clean_orders.to_pytae("orders")
... end
Updated active table 'orders' (98,420 rows x 6 cols).
```

---

## Comprehensive Real-World Walkthrough

Combining Pytae CLI verbs, ANSI SQL, and embedded Python into a unified workflow:

```text
# 1. Ingest dataset
pytae> df = sample:tips
Loaded tips.parquet as 'df' (244 rows x 7 cols).

# 2. Filter using CLI verbs
pytae [df: 244x7]> df = -filter "total_bill > 10"

# 3. Aggregate using ANSI SQL
pytae [df: 226x7]> summary = -sql "SELECT day, time, avg(tip) as avg_tip, count(*) as count FROM df GROUP BY 1, 2"
Created 'summary' (6 rows x 4 cols).

# 4. Fit statistical regression in Python using Scipy
pytae [df, summary]> py
... from scipy.stats import linregress
... x = df['total_bill'].to_list()
... y = df['tip'].to_list()
... res = linregress(x, y)
... print(f"Slope: {res.slope:.4f}, R-squared: {res.rvalue**2:.4f}")
... end
Slope: 0.1065, R-squared: 0.4497

# Notice: All scipy arrays and regression objects are purged; process RAM remains flat!
pytae [df, summary]> status
Process RAM   : ~132.1 MB (PID 84912)
```
