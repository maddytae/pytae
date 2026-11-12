# REPL Guide: Session Variables (`@var`), Settings & User Preferences

[← Back to REPL Hub](README.md) | [Master Reference](../pytae.md)

This guide covers defining session parameters and constants (`@var`), traversing nested configuration dictionaries, parameterizing pipeline filters and queries, configuring display options with `set`, persisting settings across sessions via `set save`, and system status telemetry in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Session Variables & Parameters (`@var`)](#session-variables--parameters-var)
  - [Defining Variables (`<name> = <literal>`)](#defining-variables-name--literal)
  - [Supported Data Types](#supported-data-types)
  - [Traversing Nested Dictionaries & Lists (`@cfg.key`, `@cfg[idx]`)](#traversing-nested-dictionaries--lists-cfgkey-cfgidx)
  - [Using Variables in Pipeline Verbs (`-filter`, `-mutate`, `sql { ... }`)](#using-variables-in-pipeline-verbs--filter--mutate-sql----)
  - [Accessing Session Variables in Python (`py` blocks)](#accessing-session-variables-in-python-py-blocks)
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

### The Universal `@` Rule: Tables vs. Variables

To keep the REPL mental model clean and unambiguous:

| Scope | Rule | Example |
| :--- | :--- | :--- |
| **Session Variables** | **Always prefix LHS with `@`** | `@threshold = 5000`<br>`@path = "Z:\data\*.parquet"`<br>`@regions = ['North', 'West']` |
| **Tables (DataFrames)** | **Always bare on LHS (no `@`)** | `df = orders.parquet`<br>`sales = sample:tips`<br>`heavy = df -filter "mass > 5000"` |
| **Referencing Variables** | **Always use `@`** | `-filter "amount > @threshold"`<br>`df = @path`<br>`lazy_df = scan @path` |

> [!TIP]
> Bare scalar definitions (e.g. `threshold = 5000`) continue to work as a silent fallback, but the recommended convention is to always use `@` on the left-hand side (`@threshold = 5000`).

### Defining Variables

Assign any literal directly at the prompt using the `@name = ...` syntax:

```text
# Numeric scalars (integers, floats)
pytae> @threshold = 5000
Set @threshold = 5000 (int)

pytae> @tax_rate = 0.0825
Set @tax_rate = 0.0825 (float)

# String parameters & labels
pytae> @target_status = 'completed'
Set @target_status = 'completed' (str)

# Lists & Collections
pytae> @target_countries = ['US', 'CA', 'UK']
Set @target_countries = ['US', 'CA', 'UK'] (list)

# Configuration dictionaries
pytae> @cfg = {'min_mass': 3500, 'island': 'Biscoe', 'limit': 100}
Set @cfg = {'min_mass': 3500, 'island': 'Biscoe', 'limit': 100} (dict)
```

---

### Supported Path Formats Across Shells & OSs

Pytae automatically normalizes and recognizes all operating system and shell path formats across Windows (CMD, PowerShell, Git Bash, MSYS2, Cygwin, WSL) and Unix (macOS, Linux):

| Shell / Environment | Format Example | Syntax | Notes |
| :--- | :--- | :--- | :--- |
| **Windows Backslash (CMD / PowerShell)** | `C:\Users\maddy\data\orders.parquet`<br>`Z:\OSFI\...\historic_data\*.parquet` | `@p = r"Z:\OSFI\...\*.parquet"`<br>or `@p = "C:\\data\\orders.parquet"` | Raw string `r"..."` prevents backslash escape issues (e.g. `\u` in `\uspc`). |
| **Windows Forward Slash** | `C:/Users/maddy/data/orders.parquet` | `@p = "C:/Users/maddy/data/orders.parquet"` | Cross-platform friendly; avoids all escape characters. |
| **Windows UNC Network Shares** | `\\server\share\data\orders.parquet`<br>`//server/share/data/orders.parquet` | `@p = r"\\server\share\data\orders.parquet"` | Full support for Windows shared network drives and UNC paths. |
| **Git Bash / MSYS (Single Slash)** | `/c/Users/maddy/data/orders.parquet`<br>`/z/OSFI/.../data.parquet` | `@p = "/c/Users/maddy/data/orders.parquet"` | Automatically translates `/c/...` to `C:/...` on Windows. |
| **Git Bash / MSYS (Double Slash)** | `//c/Users/maddy/data/orders.parquet` | `@p = "//c/Users/maddy/data/orders.parquet"` | Supported for Git Bash scripts that use double slashes to prevent POSIX path expansion. |
| **WSL (Windows Subsystem for Linux)** | `/mnt/c/Users/maddy/data/orders.parquet` | `@p = "/mnt/c/Users/maddy/data/orders.parquet"` | Automatically resolves `/mnt/c/...` mounts on Windows. |
| **Cygwin** | `/cygdrive/c/Users/maddy/data/orders.parquet` | `@p = "/cygdrive/c/Users/maddy/data/orders.parquet"` | Automatically resolves `/cygdrive/c/...` mounts on Windows. |
| **macOS / Linux / POSIX** | `/Users/maddy/data/orders.parquet`<br>`~/data/orders.parquet` | `@p = "~/data/orders.parquet"` | Tilde (`~`) home expansion and absolute POSIX paths supported natively. |
| **Relative & Multi-File Globs** | `data/*.parquet`<br>`sales_2026_*.parquet` | `@p = "data/*.parquet"` | Matches multiple partitioned parquet or CSV files. |
| **Sample Datasets** | `sample:penguins`, `sample:tips`, `sample:titanic` | `@p = "sample:penguins"` | Built-in sample datasets bundled with Pytae. |

---

### Ingestion from Path Variables (`df = @path`, `df = scan @path`)

Once a path is saved in a session variable, you can load or lazily scan datasets directly using the `@var` reference:

```text
# 1. Define the path variable
pytae> @rwa_path = r"Z:\OSFI\Data Sources for Historical RWA\Project\rwa_data\input_tables\uspc_calc_extract\historic_data\*.parquet"
Set @rwa_path = 'Z:\\OSFI\\Data Sources for Historical RWA\\Project\\rwa_data\\input_tables\\uspc_calc_extract\\historic_data\\*.parquet' (str)

# 2. Load eagerly into memory as table 'df'
pytae> df = @rwa_path
Loaded *.parquet as 'df' (250,000 rows x 18 cols).

# 3. Or scan lazily without loading into RAM
pytae> lazy_df = scan @rwa_path
Scanned *.parquet as 'lazy_df' (lazy, 18 cols).

# 4. Git Bash path ingestion
pytae> @gb_path = "/c/Users/maddy/downloads/customers.csv"
pytae> customers = @gb_path -dlim "," -encoding utf-8
Loaded customers.csv as 'customers' (15,000 rows x 5 cols).
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

### Using Variables in Pipeline Verbs (`-filter`, `-mutate`, `sql { ... }`)

Inject session variables directly into pipeline filter expressions, column derivations, and SQL queries:

```text
# 1. Use in -filter
pytae [orders]> -filter "amount >= @threshold and country in @target_countries"

# 2. Use in -mutate
pytae [orders]> orders = -mutate "gross_amount = amount * (1 + @tax_rate)"

# 3. Use in ANSI SQL
pytae [orders]> sql { SELECT * FROM orders WHERE amount > @thresholds.medium }
```

Variables are substituted at query compile time, ensuring full Polars SIMD optimization without Python interpreter overhead.

### Accessing Session Variables in Python (`py` blocks)

When you define a session variable in Pytae (`@var = ...`), Pytae automatically injects it into the isolated execution scope of `py` blocks **as a native Python variable without the `@` prefix** (`var`).

> [!IMPORTANT]
> **The `@` Rule Across Modes:**
> - **In Pytae REPL commands**: Always use `@var` (`@path = ...`, `df = @path`, `-filter "amount >= @threshold"`). The `@` tells Pytae that the identifier is a session parameter rather than a dataset or file name.
> - **In Python (`py` blocks)**: Always use bare `var` (`path`, `threshold`). In Python grammar, `@` is not a valid identifier character and will cause a `SyntaxError: invalid syntax` if included in an expression like `glob.glob(@path)`.

#### Example: Globbing and Loading Multi-File Partitions from a Network Drive

Suppose you define a directory path on a Windows network share or local drive:

```text
# 1. Define the base path as a raw string session variable in Pytae
pytae> @data_dir = r"Z:\Finance\RiskModels\Data\HistoricalExtracts"
```

You can now work with this path in two ways:

##### Way 1: Direct Pytae 1-Liner (Recommended — No Python or imports required)
Pytae's universal reader natively resolves wildcards and globs across partitions:

```text
# Ingest all matching parquet files, select columns, and combine in one shot
pytae> @extract_glob = r"Z:\Finance\RiskModels\Data\HistoricalExtracts\*.parquet"
pytae> comb_df = @extract_glob -select "reporting_date, rwa_amount"
Loaded *.parquet as 'comb_df' (250,000 rows x 2 cols).
```

##### Way 2: Inside a `py` Multi-Line Block (Using Polars & glob)
If you require custom procedural transformations, access the variable inside `py` as `data_dir` (without `@`):

```text
pytae> py {
... import glob
... import polars as pl
... 
... # Notice: 'data_dir' is used without '@' inside Python!
... files = glob.glob(data_dir + r"\*.parquet")
... dfs = [pl.read_parquet(f, columns=['reporting_date', 'rwa_amount']) for f in files]
... 
... # Wrap the concatenated result with DataFrame() to register it as an active Pytae table
... comb_df = DataFrame(pl.concat(dfs))
... }
Registered active table 'comb_df' (250,000 rows x 2 cols).
```

Once the block exits, `comb_df` is fully registered in your Pytae session and ready for normal REPL operations (`-filter`, `-mutate`, `save`, `diff`, etc.).

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
syntax_highlight = on (options: on, off)
theme            = default (options: default, monokai, dracula, nord, light, minimal)
(Tip: Run 'set save' to persist settings across REPL sessions)
```

Query a specific key using `set <key>` (running `set theme` also prints a live colored preview of all available themes):

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
| **`syntax_highlight`** | `highlight` | `on`, `off` | `on` | Live ANSI syntax highlighting across Pytae DSL, `sql { ... }`, `py { ... }`, and prompts. |
| **`theme`** | `color_theme` | `default`, `monokai`, `dracula`, `nord`, `light`, `minimal` | `default` | Syntax highlighting color palette (run `set theme` for live visual samples). |

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
  "comma": "on",
  "syntax_highlight": "on",
  "theme": "monokai"
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
