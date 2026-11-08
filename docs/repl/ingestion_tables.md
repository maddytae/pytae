# REPL Guide: Ingestion & Multi-Table Workbench

[← Back to Master Reference](../pytae.md)

This guide covers ingesting files, managing multiple tables simultaneously in RAM, switching active cursors, zero-copy renaming, and relational joins in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Launching the REPL](#launching-the-repl)
- [Ingesting Datasets](#ingesting-datasets)
  - [Variable Assignment (`df = file.parquet`)](#variable-assignment-df--fileparquet)
  - [Reader Options (`-encoding`, `-dlim`, `-nrows`, `-opts`)](#reader-options--encoding--dlim--nrows--opts)
  - [The `load` Keyword](#the-load-keyword)
  - [Glob Ingestion](#glob-ingestion)
  - [Bundled Sample Datasets (`sample:<name>`)](#bundled-sample-datasets-samplename)
- [Multi-Table Workbench Operations](#multi-table-workbench-operations)
  - [Listing Loaded Tables (`status table`)](#listing-loaded-tables-status-table)
  - [Inspecting Table Dimensions without Switching](#inspecting-table-dimensions-without-switching)
  - [Switching Active Tables (`switch <name>`)](#switching-active-tables-switch-name)
  - [Zero-Copy Table Renaming (`rename <old> <new>`)](#zero-copy-table-renaming-rename-old-new)
  - [Subject-First Execution (`<tbl> -<verb>`)](#subject-first-execution-tbl--verb)
  - [Multi-Table Relational Joins (`-join`)](#multi-table-relational-joins--join)
  - [Assigning Results to New Tables](#assigning-results-to-new-tables)

---

## Launching the REPL

Launch the REPL workbench cleanly from the terminal:

```bash
# Launch interactive REPL workbench
pytae -i
```

> [!NOTE]
> `pytae -i` is the dedicated entrypoint for the interactive workbench. Datasets are loaded explicitly inside the REPL with `df = file.parquet`, and persistent project sessions are configured via `set session_name = <name>`. This guarantees that exported session history files contain complete, reproducible ingestion commands.

Upon launching, load a dataset to begin exploring:
```text
pytae> df = penguins.parquet
Loaded penguins.parquet as 'df' (344 rows x 7 cols).
pytae [df: 344x7]> 
```

---

## Ingesting Datasets

### Variable Assignment (`df = file.parquet`)

Load datasets directly into named table variables using standard assignment:

```text
pytae> orders = orders.parquet
Loaded orders.parquet as 'orders' (100,000 rows x 6 cols).
pytae [orders: 100,000x6]> 
```

### Reader Options (`-encoding`, `-dlim`, `-nrows`, `-opts`)

Pass inline format parameters or full reader options directly during assignment:

```text
# Specify Latin-1 encoding, custom semicolon delimiter, and load only the first 5,000 rows
pytae> raw = export.csv -encoding latin1 -dlim ";" -nrows 5000
Loaded export.csv as 'raw' (5,000 rows x 12 cols) [encoding=latin1, sep=;, nrows=5000].

# Load Excel workbooks with default (first) sheet
pytae> sales = sales_2024.xlsx
Loaded sales_2024.xlsx as 'sales' (3,500 rows x 8 cols).

# Specify target sheet name directly inside -opts
pytae> feb = sales_2024.xlsx -opts "sheet=Feb"
Loaded 'feb' from sales_2024.xlsx (3,500 rows x 8 cols).

# Pass multiple reader kwargs using -opts (e.g. sheet, skiprows, header, usecols)
pytae> notes = sales_2024.xlsx -opts "sheet=CustomNotes, skiprows=2, header=0"
Loaded 'notes' from sales_2024.xlsx (1,200 rows x 5 cols).
```

> [!NOTE]
> - Sheet names must strictly be specified via `-opts "sheet=..."`. Colon sheet syntax (`file.xlsx:Sheet`) is not supported to ensure path integrity and eliminate ambiguity.
> - Reader options apply strictly to the specific assignment command on that line. Options do not persist across future assignments, ensuring clean, predictable data loading.

### Direct Variable Assignment with Options

Ingest datasets directly into named tables using standard assignment syntax:

```text
pytae> cust = customers.csv -dlim ","
Loaded customers.csv as 'cust' (15,000 rows x 5 cols) [sep=,].
```

> [!NOTE]
> The legacy `load <path> [as <alias>]` command syntax is deprecated in favor of direct variable assignment (`<alias> = <path>`).

### Glob Ingestion

Ingest multiple partition files matching a glob pattern into a single unified table:

```text
pytae> sales_2025 = "sales_2025/part_*.parquet"
Loaded 12 files matching 'sales_2025/part_*.parquet' as 'sales_2025' (1,200,000 rows x 8 cols).
```

### Bundled Sample Datasets (`sample:<name>`)

Quickly load bundled demo datasets using the explicit `sample:` prefix:

```text
pytae> df = sample:penguins
Loaded penguins.parquet as 'df' (344 rows x 7 cols).

pytae> iris = sample:iris
Loaded iris.parquet as 'iris' (150 rows x 5 cols).
```

Available bundled samples: `penguins`, `iris`, `tips`, `titanic`, `diamonds`, `flights`, `planets`.

---

## Multi-Table Workbench Operations

### Listing Loaded Tables (`status table`)

View active dataset details and all loaded tables in memory, their shapes, and source files:

```text
pytae [orders, cust]> status table
Table          : orders (orders.parquet) [active]
Shape          : 100,000 rows x 6 columns
Table memory   : ~14.20 MB
Status         : active

Loaded Tables (2):
 * orders      : 100,000 rows x 6 cols (orders.parquet) [active]
   cust        : 15,000 rows x 5 cols (customers.csv)
```

Use `status table -v` to inspect column lists and per-table memory footprint:
```text
pytae [orders, cust]> status table -v
Loaded Tables (2):
 * orders      : 100,000 rows x 6 cols (~14.20 MB) (orders.parquet) [active]
       Columns (6): order_id, customer_id, order_date, amount, status, items
   cust        : 15,000 rows x 5 cols (~1.12 MB) (customers.csv)
       Columns (5): customer_id, name, email, signup_date, country
Total Tables: ~15.32 MB | Process RAM: ~128.5 MB
```

> [!NOTE]
> Bare `tables` is disabled in favor of the singular `status table` inspection command.

### Inspecting Table Dimensions without Switching

Typing a bare table name inspects its dimensions without altering the active table cursor:

```text
pytae [orders, cust]> cust
cust: 15,000 rows x 5 cols (tip: 'switch cust' to switch active dataset)
```

### Switching Active Tables (`switch <name>`)

Switch the active cursor to another table using `switch <name>` (e.g. `switch orders`, `switch df`, `switch cust`):

```text
pytae [orders, cust]> switch cust
Switched active dataset to 'cust'. Active shape: (15,000, 5)
pytae [cust: 15,000x5]> 
```

*(Note: The legacy command `use <name>` is deprecated and will be removed in a future release).*

### Zero-Copy Table Renaming (`rename <old> <new>`)

Rename an in-memory dataset via instant $O(1)$ zero-copy pointer reassignment:

```text
pytae [df1, orders]> rename df1 customers
Renamed table 'df1' to 'customers'.
pytae [customers, orders]>
```

All references in the multi-table workbench, table source tracking, and active cursor update instantaneously without copying underlying Arrow memory buffers.

### Subject-First Execution (`<tbl> -<verb>`)

Execute commands directly on non-active tables without switching cursors:

```text
# Inspect cust without switching active table away from orders
pytae [orders, cust]> cust -head 3
pytae [orders, cust]> cust -shape
(15,000, 5)

# Transform cust directly
pytae [orders, cust]> cust -filter "country == 'US'"
-> cust: 9,200 rows x 5 cols
```

### Multi-Table Relational Joins (`-join`)

Join loaded tables on shared key columns:

```text
# Left join cust into orders on customer_id
pytae [orders, cust]> orders -join cust on=customer_id how=left

# Join with different column names on left and right
pytae [orders, cust]> orders -join cust on=cust_id:id how=inner

# Join and export directly to file in one step
pytae [orders, cust]> orders -join cust on=customer_id -o merged.parquet
```

Supported join types: `how=left`, `how=inner`, `how=outer`, `how=semi`, `how=anti`, `how=cross`.

### Assigning Results to New Tables

Create new tables from transformations or joins without modifying the original:

```text
# Create a derived table (orders remains untouched)
pytae [orders, cust]> big_orders = orders -filter "total > 500"
Created 'big_orders' (12,400 rows x 6 cols).

# Assign join result to a new table
pytae [orders, cust, big_orders]> enriched = orders -join cust on=customer_id
Created 'enriched' (100,000 rows x 10 cols).
```
