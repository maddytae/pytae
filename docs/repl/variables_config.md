# REPL Guide: Session Variables (`@var`), Settings & User Preferences

[← Back to REPL Hub](README.md) | [Master Reference](../pytae.md)

This guide covers defining session parameters and constants (`@var`), traversing nested configuration dictionaries, parameterizing pipeline filters and queries, configuring display options with `set`, persisting settings across sessions via `set save`, and system status telemetry in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Session Variables & Parameters (`@var`)](#session-variables--parameters-var)
  - [Defining Variables (`<name> = <literal>`)](#defining-variables-name--literal)
  - [Supported Data Types](#supported-data-types)
  - [Traversing Nested Dictionaries & Lists (`@cfg.key`, `@cfg[idx]`)](#traversing-nested-dictionaries--lists-cfgkey-cfgidx)
  - [Using Variables in Pipeline Verbs (`-filter`, `-mutate`, `-sql`)](#using-variables-in-pipeline-verbs--filter--mutate--sql)
  - [Inspecting Variables (`status var`, `status var <name>`)](#inspecting-variables-status-var-status-var-name)
  - [Deleting Variables (`rm var <name>`, `rm var *`)](#deleting-variables-rm-var-name-rm-var-)
  - [Namespace Protection: Tables vs. Variables](#namespace-protection-tables-vs-variables)
- [Display Preferences & Configuration (`set`, `set save`)](#display-preferences--configuration-set-set-save)
  - [Querying Active Settings (`set`)](#querying-active-settings-set)
  - [Available Display Options](#available-display-options)
  - [Persisting Settings to Disk (`set save`, `~/.pytae/config.json`)](#persisting-settings-to-disk-set-save-pytaeconfigjson)
- [Session Status & Diagnostics (`status`, `status -v`)](#session-status--diagnostics-status-status--v)

---

## Session Variables & Parameters (`@var`)

In complex data wrangling pipelines, hardcoding magic numbers or string literals across multiple queries leads to fragile scripts. Pytae allows you to declare typed session parameters that can be safely referenced across all CLI flags and SQL statements.

### Defining Variables (`@name = <literal>` or `<name> = <literal>`)

Assign any literal directly at the prompt using either explicit `@name = ...` or bare `name = ...`:

```text
# Explicit variable definition with @ (unambiguous)
pytae> @threshold = 5000
Set @threshold = 5000 (int)

pytae> @path = "Z:\data\historic_data\*.parquet"
Set @path = 'Z:\\data\\historic_data\\*.parquet' (str)

# Raw strings for Windows paths (avoids escape sequences)
pytae> path = r"C:\Users\data\*.parquet"
Set @path = 'C:\\Users\\data\\*.parquet' (str)

# Numeric scalars
pytae> tax_rate = 0.0825
Set @tax_rate = 0.0825 (float)

# String parameters
pytae> target_status = 'completed'
Set @target_status = 'completed' (str)

# Lists & Collections
pytae> target_countries = ['US', 'CA', 'UK']
Set @target_countries = ['US', 'CA', 'UK'] (list)
```

> [!TIP]
> When assigning file or directory paths to variables, prefixing with `@` (e.g. `@path = "..."`) or using raw strings (`path = r"..."`) ensures Pytae stores the path as a session variable rather than attempting to load it as an in-memory table.

### Ingestion from Path Variables (`df = @path`, `df = scan @path`)

Once a path is saved in a session variable, you can load or lazily scan datasets directly using the `@var` reference:

```text
pytae> @source = "sales_2026_*.parquet"
Set @source = 'sales_2026_*.parquet' (str)

# Load into table 'df'
pytae> df = @source
Loaded sales_2026_*.parquet as 'df' (120,000 rows x 12 cols).

# Or scan lazily
pytae> lazy_df = scan @source
Scanned sales_2026_*.parquet as 'lazy_df' (lazy, 12 cols).
```

### Supported Data Types

Pytae session variables support standard JSON-serializable primitives and collections:
- **Integers**: `min_rows = 100`
- **Floating-point numbers**: `tax_rate = 0.0825`
- **Strings**: `env = 'production'`
- **Booleans**: `is_active = True`
- **Lists**: `priority_tiers = ['Gold', 'Platinum']`
- **Dictionaries**: `config = {"cutoff": 1000, "region": "North"}`

### Traversing Nested Dictionaries & Lists (`@cfg.key`, `@cfg[idx]`)

Define hierarchical configuration blocks and traverse them using dot notation or index brackets:

```text
pytae> thresholds = {"high": 10000, "medium": 5000, "low": 1000}
Set @thresholds = {'high': 10000, 'medium': 5000, 'low': 1000} (dict)

# Inspect specific subkey
pytae> @thresholds.high
10000

# Inspect list index
pytae> tiers = ['bronze', 'silver', 'gold']
pytae> @tiers[2]
'gold'
```

### Using Variables in Pipeline Verbs (`-filter`, `-mutate`, `-sql`)

Inject session variables directly into pipeline filter expressions, column derivations, and SQL queries:

```text
# 1. Use in -filter
pytae [orders]> -filter "amount >= @threshold and country in @target_countries"

# 2. Use in -mutate
pytae [orders]> orders = -mutate "gross_amount = amount * (1 + @tax_rate)"

# 3. Use in ANSI SQL
pytae [orders]> -sql "SELECT * FROM orders WHERE amount > @thresholds.medium"
```

Variables are substituted at query compile time, ensuring full Polars SIMD optimization without Python interpreter overhead.

### Inspecting Variables (`status var`, `status var <name>`)

```text
# List all defined variables
pytae> status var
Session Variables (3 defined):
  * @threshold        : 5000 (int)
  * @tax_rate         : 0.0825 (float)
  * @target_countries : ['US', 'CA', 'UK'] (list)

# Inspect a specific variable
pytae> status var threshold
Variable: @threshold
Type    : int
Value   : 5000
```

### Deleting Variables (`rm var <name>`, `rm var *`)

```text
# Delete a single variable
pytae> rm var threshold
Removed variable @threshold.

# Delete all session variables
pytae> rm var *
Cleared all session variables.
```

### Namespace Protection: Tables vs. Variables

Pytae strictly enforces separate namespaces for DataFrames and scalar variables:
- If a table named `df` exists, assigning `df = 10` is rejected with an error directing you to choose a distinct variable name or remove the table first via `rm table df`.
- Table names cannot start with `@` (e.g. `@orders = ...` is invalid syntax).
- This separation guarantees that variables can never accidentally overwrite or shadow active in-memory tables.

---

## Display Preferences & Configuration (`set`, `set save`)

Customize terminal output formatting, floating-point precision, and display truncation.

### Querying Active Settings (`set`)

Running `set` with no arguments prints the current configuration:

```text
pytae> set
max_rows        = 10 (options: <int>, default)
max_cols        = all (options: <int>, all, default)
float_precision = auto (options: <int>, auto, default)
comma           = off (options: on, off)
(Tip: Run 'set save' to persist settings across REPL sessions)
```

Query a specific key using `set <key>`:

```text
pytae> set max_rows
max_rows        = 10 (options: <int>, default)
```

### Available Display Options

| Option | Aliases | Allowed Values | Default | Description |
|:---|:---|:---|:---|:---|
| **`max_rows`** | `rows` | `<int>`, `default` | `10` | Maximum rows printed in tabular previews. |
| **`max_cols`** | `cols` | `<int>`, `all`, `default` | `all` | Maximum columns printed in wide tables before truncating. |
| **`float_precision`** | `precision` | `<int>`, `auto`, `default`| `auto` | Decimal places shown for floating-point values. |
| **`comma`** | — | `on`, `off` | `off` | Format large numbers with thousands separators (`1,234,567`). |

Multiple settings can be combined on a single line:

```text
pytae> set max_rows = 25, comma = on, float_precision = 2
```

### Persisting Settings to Disk (`set save`, `~/.pytae/config.json`)

On initial startup, Pytae automatically creates `~/.pytae/config.json` with sensible defaults. To permanently save your active display preferences across all future REPL sessions, run:

```text
pytae> set save
Saved configuration to /Users/username/.pytae/config.json.
```

On subsequent launches, the REPL automatically reads `~/.pytae/config.json`:

```json
{
  "max_rows": 25,
  "max_cols": "all",
  "float_precision": 2,
  "comma": "on"
}
```

---

## Session Status & Diagnostics (`status`, `status -v`)

Run bare `status` to inspect high-level telemetry for the active session:

```text
pytae [orders, cust*]> status
=== REPL Session Status ===
Active Table  : cust (500 rows x 4 cols, ~0.02 MB)
Loaded Tables : 2 tables [orders, cust*] (~0.12 MB in memory)
Variables     : 2 defined [@tax_rate, @threshold]
Checkpoints   : 2 saved (latest: baseline) [42.1 KB ephemeral disk, 0 MB RAM]
Process RAM   : ~148.2 MB (PID 64919)
------------------------------------------------------------
(Tip: Use 'status table [name]' for table details, 'status checkpoint [name]' for checkpoints, 'status var [name]' for variables)
```

Run `status -v` for verbose details including per-table schemas, column counts, variable values, checkpoint paths, history log file paths, and memory statistics:

```text
pytae [orders, cust*]> status -v
=== REPL Session Status ===
Active Table  : cust (500 rows x 4 cols, ~0.02 MB)
Loaded Tables : 2 tables [orders, cust*] (~0.12 MB in memory)
  - orders   : 1,000 rows x 8 cols (~0.10 MB) (source: orders.parquet)
  - cust [active]: 500 rows x 4 cols (~0.02 MB) (source: customers.csv)
Variables     : 2 defined [@tax_rate, @threshold]
  * @tax_rate     : 0.0825 (float)
  * @threshold    : 5000 (int)
Checkpoints   : 2 saved (latest: baseline) [42.1 KB ephemeral disk, 0 MB RAM]
  - baseline    : ephemeral IPC created 2026-11-08 00:00:00 (2 tables)
History Log   : ~/.pytae/history/history_20261108_000000.txt
Settings      : max_rows=25, max_cols=all, float_precision=2, comma=on
Process RAM   : ~148.2 MB (PID 64919)
```
