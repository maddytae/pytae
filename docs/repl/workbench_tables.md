# REPL Guide: Ingestion, Multi-Table Management & Shell Navigation

[← Back to REPL Hub](README.md) | [Master Reference](../pytae.md)

This guide covers launching the interactive workbench, ingesting files and sample datasets, managing multiple tables simultaneously in RAM, zero-copy renaming, subject-first execution, table deallocation, and interactive shell navigation in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Launching the REPL](#launching-the-repl)
- [Ingesting Datasets](#ingesting-datasets)
  - [Variable Assignment (`df = file.parquet`)](#variable-assignment-df--fileparquet)
  - [Reader Options (`-encoding`, `-dlim`, `-nrows`, `-opts`)](#reader-options--encoding--dlim--nrows--opts)
  - [Excel Workbooks & Sheet Selection](#excel-workbooks--sheet-selection)
  - [Multi-File Glob Ingestion](#multi-file-glob-ingestion)
  - [Windows & Git Bash Path Formats (`/c/Users/...`, `//c/...`)](#windows--git-bash-path-formats-cusers-c)
  - [Bundled Sample Datasets (`sample:<name>`)](#bundled-sample-datasets-samplename)
- [Multi-Table Workbench Operations](#multi-table-workbench-operations)
  - [Inspecting Loaded Tables (`status table`)](#inspecting-loaded-tables-status-table)
  - [Quick Dimension Inspection without Switching](#quick-dimension-inspection-without-switching)
  - [Switching the Active Table Cursor (`switch <name>`)](#switching-the-active-table-cursor-switch-name)
  - [Zero-Copy Table Renaming (`rename <old> <new>`)](#zero-copy-table-renaming-rename-old-new)
  - [Subject-First Execution (`<tbl> -<verb>`)](#subject-first-execution-tbl--verb)
  - [Removing Tables & OS Memory Trimming (`rm table <name>`)](#removing-tables--os-memory-trimming-rm-table-name)
- [Interactive Shell Navigation & Ergonomics](#interactive-shell-navigation--ergonomics)
  - [Prompt Structure & Telemetry](#prompt-structure--telemetry)
  - [Context-Aware Tab Autocompletion](#context-aware-tab-autocompletion)
  - [Persistent Arrow-Key History](#persistent-arrow-key-history)
  - [Multiline Command Drafting & Line Continuations (`\`)](#multiline-command-drafting--line-continuations-)
  - [Unix Shell Integration (`|`)](#unix-shell-integration-)
  - [Terminal Keyboard Shortcuts](#terminal-keyboard-shortcuts)

---

## Launching the REPL

Launch the interactive workbench by invoking `pytae` with the `-i` flag:

```bash
# Launch empty workbench
pytae -i

# Launch workbench and preload an existing pipeline script
pytae -i sample.pt
```

> [!NOTE]
> `pytae -i` does not preload data files directly on launch (e.g. `pytae -i orders.parquet customers.csv`). Only an empty workbench (`pytae -i`) or an existing native pipeline script (`pytae -i sample.pt`) can be launched. Datasets are loaded interactively inside the workbench using assignment syntax (`orders = orders.parquet`), ensuring exported replay scripts remain 100% reproducible and self-contained.

---

## Ingesting Datasets

### Variable Assignment (`df = file.parquet`)

Load datasets directly into named table variables using standard assignment syntax:

```text
pytae> orders = orders.parquet
Loaded orders.parquet as 'orders' (100,000 rows x 6 cols).
pytae [orders: 100,000x6]> 
```

The table is immediately read into memory via Polars SIMD Arrow buffers and becomes the active table.

> [!NOTE]
> The legacy syntax `load <path> [as <alias>]` is deprecated in favor of direct variable assignment (`<alias> = <path>`).

### Reader Options (`-encoding`, `-dlim`, `-nrows`, `-opts`)

Pass format parameters or full reader options directly during assignment:

```text
# Specify Latin-1 encoding, semicolon delimiter, and load only the first 5,000 rows
pytae> raw = export.csv -encoding latin1 -dlim ";" -nrows 5000
Loaded export.csv as 'raw' (5,000 rows x 12 cols) [encoding=latin1, sep=;, nrows=5000].

# Custom comma delimiter
pytae> cust = customers.csv -dlim ","
Loaded customers.csv as 'cust' (15,000 rows x 5 cols) [sep=,].
```

Reader options apply strictly to the specific assignment command on that line and do not pollute future operations.

### Excel Workbooks & Sheet Selection

Ingest Excel spreadsheets (`.xlsx`, `.xls`, `.xlsm`):

```text
# Load first sheet by default
pytae> sales = sales_2024.xlsx
Loaded sales_2024.xlsx as 'sales' (3,500 rows x 8 cols).

# Specify target sheet name via -opts
pytae> feb = sales_2024.xlsx -opts "sheet=Feb"
Loaded 'feb' from sales_2024.xlsx (3,500 rows x 8 cols).

# Combine options (sheet, skiprows, header, usecols)
pytae> notes = sales_2024.xlsx -opts "sheet=CustomNotes, skiprows=2, header=0"
Loaded 'notes' from sales_2024.xlsx (1,200 rows x 5 cols).
```

> [!NOTE]
> Sheet names must strictly be specified via `-opts "sheet=..."`. Colon sheet syntax (`file.xlsx:Sheet`) is not supported to ensure path integrity across local and network filesystems.

### Multi-File Glob Ingestion

Ingest multiple partition files matching a glob pattern into a single unified table:

```text
pytae> sales_2025 = "sales_2025/part_*.parquet"
Loaded 12 files matching 'sales_2025/part_*.parquet' as 'sales_2025' (1,200,000 rows x 8 cols).
```

### Direct Database & Cloud Ingestion (`sqlite://`, `duckdb://`, `s3://`, `gcs://`)

Load tables or execute direct queries from SQLite, DuckDB, or cloud data lakes into the workbench:

```text
# SQLite eager table ingestion
pytae> orders = sqlite://app.db:orders
Loaded app.db:orders as 'orders' (100,000 rows x 5 cols).

# SQLite custom query ingestion
pytae> top_orders = sqlite://app.db:SELECT id, amount FROM orders WHERE amount > 50
Loaded app.db:query as 'top_orders' (12,450 rows x 2 cols).

# DuckDB eager table ingestion (zero-copy via Apache Arrow)
pytae> customers = duckdb://analytics.duckdb:customers
Loaded analytics.duckdb:customers as 'customers' (25,000 rows x 4 cols).

# Lazy scan with projection and filter pushdown
pytae> lake = scan s3://my-bucket/lake/events.parquet
Scanned events.parquet as 'lake' (lazy, 18 cols).

pytae> orders_lazy = scan sqlite://app.db:orders
Scanned app.db:orders as 'orders_lazy' (lazy, 5 cols).
```

<a id="windows--git-bash-path-formats-cusers-c"></a>
### Windows, UNC & Git Bash Path Formats (`/c/Users/...`, `//c/...`, `\\server\share\...`)

On Windows, Git Bash (MSYS2), and WSL environments, path conventions often vary. Pytae seamlessly normalizes Git Bash drive mounts (`/c/path/file.parquet` and `//c/path/file.parquet`), WSL mounts (`/mnt/c/...`), Cygwin mounts (`/cygdrive/c/...`), and UNC network shares directly into valid Windows filesystem paths (`C:/path/file.parquet`), whether passed bare or quoted:

```text
# Unquoted Git Bash path
pytae> orders = /c/Users/maddy/orders.parquet
Loaded orders.parquet as 'orders' (100,000 rows x 6 cols).

# Quoted Git Bash path
pytae> cust = "//c/Users/maddy/customers.csv"
Loaded customers.csv as 'cust' (15,000 rows x 5 cols).

# Standard Windows paths with drive letter
pytae> sales = "C:/Users/maddy/sales.parquet"
Loaded sales.parquet as 'sales' (50,000 rows x 8 cols).

# Windows UNC Network Share
pytae> network_deals = "\\server\share\rwa_data\deals.parquet"
Loaded deals.parquet as 'network_deals' (85,000 rows x 12 cols).
```

### Supported Path Formats Summary

| Environment / Format | Example Syntax | Normalized By Pytae To |
| :--- | :--- | :--- |
| **Windows Backslash** | `C:\data\orders.parquet`<br>`r"Z:\OSFI\...\*.parquet"` | `C:/data/orders.parquet`<br>`Z:/OSFI/.../*.parquet` |
| **Windows Forward Slash** | `C:/data/orders.parquet` | `C:/data/orders.parquet` |
| **Windows UNC Shares** | `\\server\share\data.parquet` | `//server/share/data.parquet` |
| **Git Bash (Single Slash)** | `/c/Users/maddy/orders.parquet` | `C:/Users/maddy/orders.parquet` |
| **Git Bash (Double Slash)** | `//c/Users/maddy/orders.parquet` | `C:/Users/maddy/orders.parquet` |
| **WSL Mounts** | `/mnt/c/Users/maddy/orders.parquet` | `C:/Users/maddy/orders.parquet` |
| **Cygwin Mounts** | `/cygdrive/c/Users/maddy/orders.parquet` | `C:/Users/maddy/orders.parquet` |
| **POSIX / macOS / Linux** | `/Users/maddy/data.parquet`, `~/data.parquet` | Local filesystem path |
| **Relative & Globs** | `data/*.parquet`, `./sub/**/*.csv` | Expanded glob match list |
| **Sample Datasets** | `sample:penguins`, `sample:tips` | Bundled parquet files |

If a path does not exist on disk, Pytae reports a clean diagnostic rather than inadvertently declaring a string session variable.

<a id="bundled-sample-datasets-samplename"></a>
### Bundled Sample Datasets (`sample:<name>`)

Instantly load bundled demo datasets using the explicit `sample:` prefix:

```text
pytae> df = sample:penguins
Loaded penguins.parquet as 'df' (344 rows x 7 cols).

pytae> tips = sample:tips
Loaded tips.parquet as 'tips' (244 rows x 7 cols).
```

Available bundled samples include: `penguins`, `iris`, `tips`, `titanic`, `diamonds`, `flights`, and `planets`.

---

## Multi-Table Workbench Operations

The Pytae REPL is a full multi-table environment capable of holding multiple independent DataFrames in RAM simultaneously.

### Inspecting Loaded Tables (`status table`)

View the active table and a complete inventory of all loaded tables, their shapes, and source files:

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

Use `status table -v` for column lists and detailed memory breakdowns:

```text
pytae [orders, cust]> status table -v
Loaded Tables (2):
 * orders      : 100,000 rows x 6 cols (~14.20 MB) (orders.parquet) [active]
       Columns (6): order_id, customer_id, order_date, amount, status, items
   cust        : 15,000 rows x 5 cols (~1.12 MB) (customers.csv)
       Columns (5): customer_id, name, email, signup_date, country
Total Tables: ~15.32 MB | Process RAM: ~128.5 MB
```

### Quick Dimension Inspection without Switching

Typing a bare table name inspects its dimensions without altering the active table cursor:

```text
pytae [orders, cust]> cust
cust: 15,000 rows x 5 cols (tip: 'switch cust' to switch active dataset)
```

<a id="switching-the-active-table-cursor-switch-name"></a>
### Switching the Active Table Cursor (`switch <name>`)

Switch the active cursor to another table using `switch <name>`:

```text
pytae [orders, cust]> switch cust
Switched active dataset to 'cust'. Active shape: (15,000, 5)
pytae [cust: 15,000x5]> 
```

> [!NOTE]
> The legacy command `use <name>` has been deprecated and removed in favor of `switch <name>`.

<a id="zero-copy-table-renaming-rename-old-new"></a>
### Zero-Copy Table Renaming (`rename <old> <new>`)

Rename an in-memory dataset via instant $O(1)$ zero-copy pointer reassignment:

```text
pytae [df1, orders]> rename df1 customers
Renamed table 'df1' to 'customers'.
pytae [customers, orders]>
```

All references in the workbench and cursor tracking update instantaneously without copying underlying Arrow memory buffers.

<a id="subject-first-execution-tbl--verb"></a>
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

<a id="removing-tables--os-memory-trimming-rm-table-name"></a>
### Removing Tables & OS Memory Trimming (`rm table <name>`)

Purge tables from memory when they are no longer needed:

```text
# Remove specific table by variable name
pytae [df1, df2]> rm table df1
Removed table 'df1'. Switched active dataset to 'df2'.

# Remove all loaded tables at once
pytae [orders, cust, big_orders]> rm table *
Removed all 3 loaded tables. No tables remain loaded.
```

#### Immediate OS Page Trimming
Unlike standard Python shells that retain freed pages in heap memory pools:
1. **Zero Lingering References**: `rm table` purges all internal references (`self.tables`, `self.orig_tables`, and `self.initial_tables`).
2. **OS Memory Trimming**: Pytae immediately triggers memory reclamation:
   - **Linux**: Calls `libc.malloc_trim(0)` to unmap freed arenas back to the OS.
   - **macOS**: Calls internal Mach task reclamation (`mach_task_basic_info`).
   - **Windows**: Calls `SetProcessWorkingSetSize(-1, -1)` and `K32EmptyWorkingSet` to flush freed working set pages.

---

## Interactive Shell Navigation & Ergonomics

### Prompt Structure & Telemetry

The REPL prompt dynamically reflects the active workbench state:

- **Single Table**: `pytae [orders: 100,000x6]>` displays the active table name and dimensions.
- **Multiple Tables**: `pytae [orders*, cust]>` shows loaded tables with `*` indicating the active cursor.
- **Dirty State**: `pytae [orders*]>` shows `*` next to a table modified since the last checkpoint.

### Context-Aware Tab Autocompletion

The Pytae REPL provides comprehensive `readline` autocompletion with clean in-place candidate preview:

- **In-Place Ephemeral Preview**: Displays matching candidates directly underneath the prompt and clears cleanly upon selection, avoiding duplicate prompt lines or terminal scrollback clutter.
- **Top-Level Verbs**: Press `[Tab]` at an empty prompt to view top-level commands (`switch`, `rename`, `rm`, `checkpoint`, `restore`, `export`, `status`, `set`, etc.).
- **Flags**: Type `-` and press `[Tab]` to autocomplete CLI pipeline verbs (`-filter`, `-mutate`, `-select`, `-arrange`, `-pivot`, `-browse`, etc.).
- **Table Names**: Autocompletes loaded table names after `switch `, `rename `, `diff `, and `rm table `.
- **Column Names**: Inside pipeline flags (`-select `, `-filter `, `-by `, `-arrange `), autocompletes column names from the active table.
- **File Paths & URIs**: Autocompletes local filesystem files, directories, and connection strings during assignment (`df = `).
- **SQL & Python Context**: Contextually autocompletes SQL keywords, table names, and column names inside `sql { ... }`, and Python environment variables, methods/attributes (`df.h`, `pl.col`), builtins, and keywords inside `py { ... }`.
- **Settings**: Autocompletes configuration keys and values after `set ` (e.g. `set comma = ` $\to$ `on`, `off`).

### Persistent Arrow-Key History

The REPL maintains persistent command history saved in `~/.pytae_history`. Use <kbd>↑</kbd> and <kbd>↓</kbd> arrow keys to recall previous commands. Multi-line commands containing `\` continuations are cleanly flattened into single lines for smooth arrow navigation.

### Multiline Command Drafting & Line Continuations (`\`)

For complex pipelines or multi-step queries, span commands across multiple lines using a trailing backslash (`\`):

```text
pytae [orders]> -filter "amount > 1000 and status == 'shipped'" \
... -mutate "tax = amount * 0.08" \
... -select "order_id,customer_id,tax,amount" \
... -head 5
```

- **Smart Line Splitting**: Pressing <kbd>Shift+Enter</kbd> (or <kbd>Enter</kbd> immediately following a `\`) splits the input at the cursor position and drops down to the continuation prompt (`... `).
- **Inline Continuation Collapsing**: Commands containing inline `\` line continuations (e.g. `-s species \ -s island`) are seamlessly collapsed into a unified command string prior to execution.
- **Multidimensional Arrow Navigation**: Pressing <kbd>↑</kbd> and <kbd>↓</kbd> inside a multiline command navigates across lines within your multi-line buffer before cycling through command history.
- **Clean History Logging**: Multiline commands are stored in session history and `~/.pytae_history` as clean, unified single-line commands without stray backslashes.

### Unix Shell Integration (`|`)

Pipe any REPL output directly to standard Unix terminal tools:

```text
# Search column names with grep
pytae [df: 344x7]> -cols | grep mass
body_mass_g

# Search sorted columns on a specific table
pytae [orders, cust]> orders -cols asc | grep id
customer_id
order_id

# Count preview rows with wc
pytae [df: 344x7]> -head 50 | wc -l
54
```

*Note: Pipe characters inside quotes or brackets (e.g. `-filter "a | b"` or regexes) are parsed as expression logic rather than shell pipes.*

### Terminal Keyboard Shortcuts

| Shortcut | Action |
|:---|:---|
| <kbd>Ctrl+A</kbd> / <kbd>Home</kbd> | Move cursor to the beginning of the line |
| <kbd>Ctrl+E</kbd> / <kbd>End</kbd> | Move cursor to the end of the line |
| <kbd>Ctrl+K</kbd> | Cut from cursor to the end of the line |
| <kbd>Ctrl+U</kbd> | Clear the current line |
| <kbd>Ctrl+C</kbd> | Abort the active multi-line input buffer or long-running query |
| <kbd>Ctrl+D</kbd> | Exit the REPL session cleanly |
| <kbd>Tab</kbd> | Trigger context-aware autocompletion |
