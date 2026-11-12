# REPL Guide: SQL & Python Interop (Ephemeral Python Sandboxing)

[← Back to REPL Hub](README.md) | [Master Reference](../pytae.md)

This guide covers ANSI SQL querying across loaded tables, embedded Python execution (`py <expr>`), the **Ephemeral Python Sandboxing architecture**, and explicit `.to_pytae()` table registration in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [ANSI SQL across Tables (`sql { ... }`)](#ansi-sql-across-tables-sql----)
  - [Explicit Table Names in SQL](#explicit-table-names-in-sql)
  - [Non-Destructive Preview vs. Assignment (`res = sql { ... }`)](#non-destructive-preview-vs-assignment-res--sql----)
  - [Cross-Table SQL Joins](#cross-table-sql-joins)
  - [Multi-Line SQL Queries](#multi-line-sql-queries)
- [Python Execution (`py { ... }`)](#python-execution-py----)
  - [Single-Line Evaluation](#single-line-evaluation)
  - [Multi-Line `py { ... }` Block Mode](#multi-line-py-----block-mode)
  - [Pre-Loaded Libraries (`pd`, `pl`, `pt`, `DataFrame`)](#pre-loaded-libraries-pd-pl-pt-dataframe)
  - [Session-Wide Persistent Imports & Functions](#session-wide-persistent-imports--functions)
  - [Accessing Pytae Session Variables (`@var` -> `var`)](#accessing-pytae-session-variables-var---var)
- [Ephemeral Python Sandboxing & RAM Isolation](#ephemeral-python-sandboxing--ram-isolation)
  - [The Design Philosophy: Ephemeral Data vs. Persistent Logic](#the-design-philosophy-ephemeral-data-vs-persistent-logic)
  - [Immediate Garbage Collection & Memory Zeroing](#immediate-garbage-collection--memory-zeroing)
  - [Explicit `.to_pytae()` Table Registration](#explicit-to_pytae-table-registration)
  - [Rejection of Bare `.pt` Accessor Proxies](#rejection-of-bare-pt-accessor-proxies)
  - [In-Place Active Table Mutation](#in-place-active-table-mutation)
- [Comprehensive Real-World Walkthrough](#comprehensive-real-world-walkthrough)

---

## ANSI SQL across Tables (`sql { ... }`)

Pytae embeds a native Polars `SQLContext` directly into the REPL, allowing you to run standard ANSI SQL queries across all loaded tables without copying data into an external database engine like SQLite or DuckDB.

### Explicit Table Names in SQL

All loaded tables in the workbench are registered into the SQL catalog using their exact table variable names (`df`, `orders`, `cust`, etc.). Unlike one-shot CLI usage (`pytae file.parquet -sql "... FROM data"`), there is no automatic `data` alias in the REPL because every table already has an explicit name:

```text
pytae [orders: 100,000x6]> sql { SELECT status, count(*) AS n, sum(amount) AS total FROM orders GROUP BY 1 ORDER BY total DESC }
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

### Non-Destructive Preview vs. Assignment (`res = sql { ... }`)

- **Bare `sql { ... }`**: Executes the query non-destructively and prints a formatted table preview (like `-head`). Your active table in RAM remains untouched.
- **Assigned `<var> = sql { ... }`**: Assigns the SQL query result into a new or existing workbench table variable:

```text
pytae [orders, cust]> top_customers = sql { SELECT customer_id, sum(amount) as ltv FROM orders GROUP BY 1 HAVING ltv > 5000 ORDER BY ltv DESC }
Created 'top_customers' from SQL query (342 rows x 2 cols).

pytae [orders, cust, top_customers]> 
```

### Cross-Table SQL Joins

Execute complex relational SQL joins across multiple independent tables held in RAM:

```text
pytae [orders, cust]> sql { SELECT c.country, count(o.order_id) as orders_count, avg(o.amount) as avg_amount FROM orders o LEFT JOIN cust c ON o.customer_id = c.customer_id GROUP BY 1 ORDER BY orders_count DESC }
```

### Multi-Line SQL Queries

Opening `sql {` (or `<var> = sql {`) automatically enters multi-line block mode (`... ` prompt with 4-space auto-indentation). Arbitrary blank lines, `-- comments`, single quotes `'...'`, and double-quoted column identifiers `"..."` work naturally without escaping. Type `}` to execute:

```text
pytae [orders, cust]> summary = sql {
...     SELECT
...         c.country,
...         count(*) AS total_orders,
...         round(sum(o.amount), 2) AS gross_revenue
...     FROM orders o
...     JOIN cust c ON o.customer_id = c.customer_id
...     WHERE o.status = 'completed'
...     GROUP BY c.country
...     ORDER BY gross_revenue DESC
... }
Created 'summary' from SQL query (18 rows x 3 cols).
```

---

## Python Execution (`py { ... }`)

The REPL allows direct execution of arbitrary Python code when complex procedural logic, regex algorithms, or scientific libraries (`scipy`, `sklearn`, `numpy`) are required. All Python execution is enclosed in `{ ... }`.

### Single-Line Evaluation

Execute a one-liner Python statement using the `py { ... }` syntax:

```text
# Inspect Python environment or standard library
pytae> py { import sys; print(sys.version) }
3.13.1 (main, Dec  3 2024)

# Mathematical evaluation
pytae> py { import math; [math.factorial(x) for x in range(1, 6)] }
[1, 2, 6, 24, 120]
```

### Multi-Line `py { ... }` Block Mode

Open multi-line block mode with `py {`. The prompt changes to `... `, providing automatic indentation (+4 spaces on `:`). Arbitrary blank lines are permitted within the block without triggering early execution. Type `}` on a newline to complete and run:

```text
pytae [orders]> py {
... import numpy as np
... rates = np.array([0.05, 0.08, 0.12])
... print("Mean rate:", rates.mean())
... }
Mean rate: 0.08333333333333333
```

### Pre-Loaded Libraries (`pd`, `pl`, `pt`, `DataFrame`)

To maximize interactive ergonomics, Pytae automatically pre-loads the core data stack directly into every `py { ... }` scope:

| Pre-Loaded Symbol | Library / Object | Description |
|:---|:---|:---|
| `pd` | `pandas` | Complete Pandas library (`pd.Series`, `pd.DataFrame`, `pd.to_datetime`) |
| `pl` | `polars` | Complete Polars library (`pl.col`, `pl.lit`, `pl.concat`, `pl.Series`) |
| `pt` | `pytae` | Core Pytae module (`pt.read`, `pt.scan`, `pt.DataFrame`) |
| `DataFrame` | `pytae.DataFrame` | Pytae table wrapper class |
| `df` | `pytae.DataFrame` | Active table wrapped as a Pytae DataFrame |
| `pldf` | `polars.DataFrame` | Active table as a raw underlying Polars DataFrame |

You never need to run `import pandas as pd` or `import polars as pl` — they are available immediately out of the box:

```text
pytae> py { pd.Series([10, 20, 30, 40]).describe() }
count     4.000000
mean     25.000000
std      12.909944
min      10.000000
25%      17.500000
50%      25.000000
75%      32.500000
max      40.000000
dtype: float64
```

### Session-Wide Persistent Imports & Functions

In Pytae, **all imports and custom definitions persist throughout the entire REPL session**. 

Once you import a module or symbol in any `py { ... }` block, it is retained in the session environment and remains directly accessible in all subsequent `py { ... }` blocks until you `exit` the shell. You do **not** need to re-import libraries or re-define helper functions across blocks.

#### 1. Persistent Module Imports
Import any standard library or third-party package once:

```text
# Block 1: Import once
pytae> py {
... import math
... from scipy.stats import norm
... }

# Block 2: Directly accessible in later blocks!
pytae> py {
... print("Z-score p-value:", norm.cdf(1.96))
... print("Square root:    ", math.sqrt(144))
... }
Z-score p-value: 0.9750021048517795
Square root:     12.0
```

#### 2. Persistent Custom Functions & Classes
User-defined functions, lambdas, and classes also persist across blocks and retain full access to their imported module dependencies:

```text
# Block 1: Define domain logic or helper functions
pytae> py {
... import math
... def haversine(lat1, lon1, lat2, lon2):
...     r = 6371.0
...     phi1, phi2 = math.radians(lat1), math.radians(lat2)
...     dphi = math.radians(lat2 - lat1)
...     dlam = math.radians(lon2 - lon1)
...     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
...     return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))
... }

# Block 2: Call the function across the session
pytae> py {
... dist_km = haversine(40.7128, -74.0060, 51.5074, -0.1278)
... print(f"NYC to London: {dist_km:,.1f} km")
... }
NYC to London: 5,570.2 km
```

#### 3. Deletion and Overwriting (`del`)
- **Explicit Removal**: If you wish to explicitly unload or remove an imported module or custom function from the session environment, run `del <name>` inside any `py { ... }` block:
  ```text
  pytae> py { del haversine }
  ```
- **Reassignment**: If a function or module name is reassigned to non-callable scratch data (e.g. `haversine = 123`), it is automatically evicted from the persistent environment upon block exit.

### Accessing Pytae Session Variables (`@var` -> `var`)

Session variables defined with `@var = ...` in the REPL (e.g. `@path`, `@threshold`) are automatically injected into `py` blocks **as bare Python identifiers without the `@` prefix** (`path`, `threshold`):

```text
# 1. Define variable in Pytae
pytae> @data_dir = r"Z:\Finance\RiskModels\Data\HistoricalExtracts"

# 2. Access in Python without '@'
pytae> py {
... import glob, polars as pl
... files = glob.glob(data_dir + r"\*.parquet")
... dfs = [pl.read_parquet(f, columns=['reporting_date', 'rwa_amount']) for f in files]
... comb_df = DataFrame(pl.concat(dfs))
... }
Registered active table 'comb_df' (250,000 rows x 2 cols).
```

> [!NOTE]
> In standard Python syntax, `@` is not a valid identifier prefix (`@path` raises a Python `SyntaxError`). Always omit the `@` when referencing variables inside Python expressions. For full details, see [Session Variables Guide](variables_config.md#accessing-session-variables-in-python-py-blocks).

---

## Ephemeral Python Sandboxing & RAM Isolation

### The Design Philosophy: Ephemeral Data vs. Persistent Logic

In standard interactive shells (such as IPython or Jupyter), every variable created in Python lingers in the global namespace indefinitely, causing memory leaks that bloat process RSS.

Pytae balances **interactive convenience** with **strict memory hygiene** through a clear separation of concerns:

1. **Persistent Logic**:
   - Imported modules (`types.ModuleType`), functions (`types.FunctionType`, callables), and classes (`type`) **persist** throughout the REPL session so you only import once.
2. **Ephemeral Data**:
   - Intermediate variables, scratch lists, dictionaries, numbers, NumPy arrays, and unassigned dataframes are **immediately purged from RAM** upon block completion.
   - `gc.collect()` is explicitly executed.
   - Kernel page trimming (`libc.malloc_trim(0)` on Linux, `mach_task` on macOS, `K32EmptyWorkingSet` on Windows) is triggered after every block to return resident heap pages back to the operating system.
3. **Explicit Workbench Tables**:
   - Only tables explicitly registered via `.to_pytae()`, assigned directly from a Pytae `DataFrame` (e.g. `k = df.head(10)`), or assigned back to active `df` are promoted into the Pytae table registry and preserved in exported `.pt`/`.py` scripts.

### Immediate Garbage Collection & Memory Zeroing

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   EPHEMERAL PYTHON SANDBOXING ARCHITECTURE                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. INGEST SCOPE   │ Pre-loads pd, pl, pt, active tables, session vars, & persistent env.│
│ 2. EXECUTE SCRIPT │ User imports libraries, defines functions, trains ML models, etc.   │
│ 3. BLOCK COMPLETE │ Python execution ends.                                             │
│ 4. PRESERVE LOGIC │ Modules, custom functions, and classes saved into session env.     │
│ 5. RAM FLUSH      │ Scratch data & arrays destroyed. gc.collect() invoked.             │
│ 6. OS PAGE TRIM   │ OS kernel frees virtual memory pages. Process RSS resets to 0 MB.  │
│ 7. EXPLICIT HANDOFF│ ONLY tables explicitly registered via .to_pytae() persist in REPL.│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Explicit `.to_pytae()` Table Registration

To promote a Python DataFrame into the active Pytae workbench, you **must explicitly call `.to_pytae('<table_name>')`**:

```text
pytae [orders]> py {
... # Heavy computation inside Python
... df = orders.to_polars()
... df = df.with_columns(log_amount = pl.col("amount").log())
... # Register back to Pytae:
... pt.DataFrame(df).to_pytae("orders_log")
... }
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
pytae [orders: 100,000x6]> py {
... clean_orders = orders.filter("amount > 0").arrange("amount desc")
... clean_orders.to_pytae("orders")
... }
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
pytae [df: 226x7]> summary = sql { SELECT day, time, avg(tip) as avg_tip, count(*) as count FROM df GROUP BY 1, 2 }
Created 'summary' from SQL query (6 rows x 4 cols).

# 4. Fit statistical regression in Python using Scipy (import persists!)
pytae [df, summary]> py {
... from scipy.stats import linregress
... x = df['total_bill'].to_list()
... y = df['tip'].to_list()
... res = linregress(x, y)
... print(f"Slope: {res.slope:.4f}, R-squared: {res.rvalue**2:.4f}")
... }
Slope: 0.1065, R-squared: 0.4497

# Notice: All scipy arrays and regression objects are purged; process RAM remains flat!
pytae [df, summary]> status
Process RAM   : ~132.1 MB (PID 84912)

# 5. Use the previously imported linregress function later without re-importing!
pytae [df, summary]> py {
... subset = df.filter("sex == 'Female'")
... female_res = linregress(subset['total_bill'].to_list(), subset['tip'].to_list())
... print(f"Female slope: {female_res.slope:.4f}")
... }
Female slope: 0.1132
```
