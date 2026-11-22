# Pytae CLI Cheat Sheet & Cookbook

The definitive quick-reference guide and recipe cookbook for the `pytae` Unix command-line tool.

---

## 1. ⚡ Quick File Inspection & Metadata

Inspect Parquet, CSV, TSV, JSONL, and SAS7BDAT datasets with zero startup overhead:

```bash
# Print row and column dimensions (zero-cost on Parquet)
pytae data.parquet -shape

# Interactive full-screen terminal data grid browser (sticky headers, arrow/vi navigation, live column sort)
pytae data.parquet -browse

# Preview the first or last 5 rows (custom limit optional)
pytae data.parquet -head
pytae data.parquet -head 10
pytae data.parquet -tail 5

# View column names in file order, or sorted alphabetically
pytae data.parquet -cols
pytae data.parquet -cols asc

# View column data types
pytae data.parquet -dtype

# View null count and missingness per column
pytae data.parquet -nulls
pytae data.parquet -nulls desc

# Transposed overview of columns, dtypes, and sample values
pytae data.parquet -glimpse

# Statistical summary (count, mean, std, min, percentiles, max)
pytae data.parquet -describe

# Compact schema summary (dtypes, null count and %, cardinality)
pytae data.parquet -schema

# Inspect low-level Parquet metadata (row groups, compression, statistics)
pytae data.parquet -meta

# Random sampling (reproducible with -seed; supports count, fraction, or percentage)
pytae data.parquet -sample 10 -seed 42
pytae data.parquet -sample 5%
pytae data.parquet -sample 0.05
```

---

## 2. 🔍 Row Filtering & Slicing (`-filter`)

Filter rows cleanly using operator expressions, ranges, set membership, or column comparisons:

```bash
# Exact match (strict '==' enforced; string values must be quoted with single quotes inside double quotes)
pytae data.parquet -filter "species == 'Gentoo'"
pytae data.parquet -filter "currency == 'CAD' and reporting_date in ['2026-09-30', '2026-08-31']"

# Numeric comparison operators (>, <, >=, <=, !=) and boolean logic (and, or, parens)
pytae data.parquet -filter "body_mass_g > 5000"
pytae data.parquet -filter "body_mass_g >= 3500 and flipper_length_mm < 210"
pytae data.parquet -filter "(species == 'Adelie' or species == 'Chinstrap') and body_mass_g > 4000"

# Column-to-column comparison (reconcile IDs, detect limit breaches)
pytae loans.parquet -filter "exposure > limit"
pytae loans.parquet -filter "tranche_id == deal_id"

# Ranges & Intervals (Option 1 native between or Option 2 multi-condition tuple dicts)
pytae data.parquet -filter "{'body_mass_g': ('between', 3000, 3500)}"
pytae data.parquet -filter "{'body_mass_g': (('>=', 3000), ('<=', 3500))}"
pytae data.parquet -filter "body_mass_g >= 3000 and body_mass_g <= 3500"

# List set membership (in, not in)
pytae data.parquet -filter "species in ['Adelie', 'Chinstrap']"
pytae data.parquet -filter "species not in ['Gentoo']"

# Null checks (universal 'is_null()' / 'is_not_null()' in expressions and dicts; all missing and NaN values normalize to null)
pytae data.parquet -filter "sex.is_not_null()"
pytae data.parquet -filter "sex.is_null()"
pytae data.parquet -filter "{'sex': 'is_null()'}"
pytae data.parquet -filter "{'sex': 'is_not_null()'}"

# Columns with parentheses or spaces
pytae data.parquet -filter "counterparty_class_(irb) == 'Sovereigns'"
pytae data.parquet -filter "[counterparty class (irb)].is_not_null()"

# Inline assertions (validates all rows satisfy conditions; fails fast on violation)
pytae data.parquet -assert "body_mass_g > 0 and id.is_not_null()"
pytae orders.parquet -assert "order_id.is_not_null() and amount >= 0" -o valid.parquet

# Drop rows containing missing values (Zero Data Loss: bare flag defaults to how='all')
pytae data.parquet -dropna                               # Drops only 100% empty rows (how='all')
pytae data.parquet -dropna how=any                       # Drops rows missing ANY column (strict complete cases)
pytae data.parquet -dropna "body_mass_g, sex"            # Drops rows missing body_mass_g OR sex (how='any')
pytae data.parquet -dropna "body_mass_g, sex, how=all"   # Drops rows missing BOTH body_mass_g AND sex (how='all')
```

---

## 3. 🛠 Feature Engineering & Mutation (`-mutate`)

Derive and overwrite columns using vectorized Polars SIMD expressions:

```bash
# Basic arithmetic formulas
pytae data.parquet -mutate "mass_kg = body_mass_g / 1000.0"

# Sequential assignments (later columns reference earlier ones)
pytae data.parquet -mutate "mass_kg = body_mass_g / 1000.0, mass_lbs = mass_kg * 2.20462"

# Conditional branching: if_else(condition, true_val, false_val)
pytae data.parquet -mutate "size = if_else(body_mass_g > 4000, 'Large', 'Small')"

# Multi-condition branching: case_when
pytae data.parquet -mutate "tier = case_when(body_mass_g > 5000, 'Heavy', body_mass_g > 3500, 'Medium', default='Light')"

# Categorical mapping & recoding: map(col, {dict}, default=...)
# (Strict boolean safety: mapping booleans preserves Boolean dtype)
pytae data.parquet -mutate "is_heavy = map(species, {'Gentoo': True}, default=False)"
pytae data.parquet -mutate "region = map(island, {'Biscoe': 'South', 'Dream': 'North'}, default='Other')"

# String functions: .str.lower(), .str.upper(), .str.slice(), .str.replace()
pytae data.parquet -mutate "species_lower = species.str.lower()"

# Unbracketed special-character columns (parentheses, hyphens)
pytae data.parquet -mutate "diff = irba_unsecured_lgd_(1g00) - post_crm_lgd_(2a)"

# Dynamic column referencing via col()
pytae data.parquet -mutate "target_copy = col('body_mass_g') * 1.5"
```

---

## 4. 🎯 Column Selection & Renaming (`-select`, `-rename`)

Select, reorder, and drop columns with flexible pattern matching:

```bash
# Explicit column selection and reordering
pytae data.parquet -select "species,island,body_mass_g"

# Drop columns using exclamation mark negation (!col)
pytae data.parquet -select "!sex,!year"

# Pattern and prefix matching
pytae data.parquet -select "starts_with=bill_"
pytae data.parquet -select "ends_with=_mm"
pytae data.parquet -select "contains=length"

# Select by data type
pytae data.parquet -select "dtype=float"
pytae data.parquet -select "exclude_dtype=string"

# Rename columns (old_name:new_name)
pytae data.parquet -rename "body_mass_g:weight_g,bill_length_mm:beak_len"

# Automated header cleaning (strip whitespace, snake_case, deduplicate)
pytae messy.csv -clean_columns "strip,fill=_,case=lower,dedupe"
```

---

## 5. 📊 In-Terminal Visualizations

Generate instant ASCII/Unicode charts directly in your terminal:

```bash
# Frequency table of a categorical column
pytae data.parquet -freq species

# In-terminal frequency bar chart
pytae data.parquet -freq species -bar

# In-terminal distribution histogram (custom bins optional)
pytae data.parquet -hist body_mass_g
pytae data.parquet -hist body_mass_g:20

# In-terminal scatter plot
pytae data.parquet -scatter "bill_length_mm,bill_depth_mm"

# Correlation matrix
pytae data.parquet -corr

# Generate publication-quality Matplotlib figures headlessly
pytae data.parquet -by species -agg "avg_mass=mean(body_mass_g)" \
  -plot "kind=bar, x=species, y=avg_mass" -finalize "save=chart.png"
```

---

## 6. 📈 Aggregation & Grouping (`-by`, `-agg`)

Perform blazing-fast grouped calculations:

```bash
# Group-by count
pytae data.parquet -by species -count

# Multiple aggregations per group
pytae data.parquet -by species -agg "avg_mass=mean(body_mass_g), max_flipper=max(flipper_length_mm), total=count()"

# Multi-column grouping
pytae data.parquet -by "species,island" -agg "mean_mass=mean(body_mass_g)"

# Deduplicate rows across key columns
pytae data.parquet -distinct "species,island"

# Sort rows by multiple columns with directions
pytae data.parquet -arrange "species asc, body_mass_g desc"

# Sequential -by with single-shot zero-pollution scoping (each -by scopes the next verb, then resets)
pytae sales.parquet -by region -mutate "regional_mean=mean(sales)" -mutate "global_mean=mean(sales)" -by dept -mutate "dept_mean=mean(sales)"

# Top N per group in a single CLI command (e.g. top 2 species by avg body mass for each island)
pytae penguins.parquet -by island,species -agg "avg_mass=mean(body_mass_g)" -arrange "island, avg_mass desc" -by island -head 2
```

---

## 7. 🔄 Reshaping & Pivoting (`-long`, `-wide`, `-pivot`)

Reshape tables without writing complex code:

```bash
# Melt wide table into long form (unpivot): r (id rows), c (header name), v (values)
pytae data.parquet -long "r=species,island, c=metric, v=value"

# Reshape long table back to wide (1-to-1 un-melt): r, c, v
pytae long.parquet -wide "r=species, c=metric, v=value"

# 2D Pivot table with aggregation: r (rows), c (columns), v (values), a (aggregation)
pytae data.parquet -pivot "r=species, c=island, v=body_mass_g, a=mean"

# Explode / unnest list-like or array columns into multiple rows (one element per row)
pytae events.parquet -explode tags
pytae orders.parquet -explode "items,quantities"
```

---

## 8. 🔗 Multi-File Relational Operations (`-join`, `-concat`, `-sql`, `-opts`)

Combine multiple datasets seamlessly with natural positional syntax (`alias=path` or bare paths):

```bash
# Inner, left, right, or outer joins (left & right default to first two frames)
pytae ord=orders.parquet cust=customers.csv \
  -join "on=customer_id, how=left" \
  -head 10

# Stack datasets vertically (concat / union — frames default to all inputs)
pytae a=q1.parquet b=q2.parquet c=q3.parquet -concat -shape

# Stack multiple Excel sheets via targeted -opts
pytae jan=sales.xlsx feb=sales.xlsx -concat -opts "jan:sheet=Jan, feb:sheet=Feb" -shape

# Pass reader options globally or target specific tables
pytae ord=orders.xlsx cust=customers.csv \
  -join "on=cust_id" \
  -opts "ord:sheet=Q1, skiprows=1, cust:skiprows=3"

# Run analytical ANSI SQL directly across named table aliases
pytae s=sales.parquet st=stores.csv \
  -sql "SELECT st.region, SUM(s.amount) as total FROM s JOIN st ON s.store_id = st.id GROUP BY 1 ORDER BY 2 DESC"

# Load globbed multi-file partitions into a named alias
pytae all_parts="parts/*.parquet" st=stores.csv \
  -join "left=all_parts, right=st, on=store_id, how=left"
```

---

## 8b. 🗄️ Direct Database & Cloud Ingestion (`sqlite://`, `duckdb://`, `s3://`, `gcs://`)

Query SQLite/DuckDB databases and cloud data lakes directly with zero-copy Arrow and native lazy pushdown:

```bash
# Query SQLite tables or custom queries
pytae sqlite://app.db:orders -head
pytae sqlite://app.db:"SELECT id, amount FROM orders WHERE amount > 50" -head

# Query DuckDB tables or custom queries
pytae duckdb://analytics.duckdb:customers -head

# Scan cloud data lakes directly with lazy pushdown (s3://, gcs://, gs://)
pytae s3://bucket/data.parquet -filter "status == 'complete'" -head
pytae gcs://bucket/data.parquet -head

# Cross-database relational join across SQLite and DuckDB
pytae o=sqlite://app.db:orders c=duckdb://analytics.duckdb:customers \
  -join "right=c, on=customer_id:cust_id" -head
```

---

## 9. 💾 Format Conversions & Sinks (`-o`)

Convert effortlessly between `.parquet`, `.csv`, `.tsv`, `.dat`, `.jsonl`, `.xlsx`, and `.sas7bdat`:

```bash
# Convert specific Excel sheet to snappy compressed Parquet
pytae sales.xlsx -opts "sheet=Jan" -o jan.parquet

# Convert SAS7BDAT to snappy compressed Parquet
pytae legacy.sas7bdat -o clean.parquet

# Convert Parquet to CSV
pytae data.parquet -o export.csv

# Batch convert all CSV files in a directory to Parquet
pytae "raw/*.csv" -o parquet -out_dir "clean/"

# Specify delimiter or encoding
pytae data.txt -dlim "\t" -encoding latin-1 -o data.parquet

# Copy filtered results directly to system clipboard
pytae data.parquet -filter "species == 'Gentoo'" -head 10 -o clip
```

---

## 10. 🧪 Drift & Difference Detection (`-diff`)

Compare two datasets for schema, row count, null count, and numerical cell drift:

```bash
# Compare schema and values between two files
pytae baseline.parquet -diff current.parquet

# Tolerance threshold for floating-point calculations (absolute & relative)
pytae baseline.parquet -diff current.parquet -tol 1e-4

# Key-aware row alignment (reconcile by primary/composite keys, detect added/removed keys & cell diffs)
pytae baseline.parquet -diff "current.parquet,on=id,tol=1e-4"
pytae baseline.parquet -diff "current.parquet,on=id:cust_id,tol=0.01"

# Compare with custom delimiter or encoding
pytae left.csv -diff right.csv -dlim "," -tol 0.001
```

---

## 11. 🚰 Unix Shell Piping

Integrate seamlessly into standard Unix command-line pipelines:

```bash
# Pipe raw CSV data from standard input (use '-' as path)
cat raw_stream.csv | pytae - -fmt csv -shape

# Pipe through grep, awk, or less
pytae data.parquet -filter "body_mass_g > 4000" | grep "Biscoe" | less

# Shell output redirection
pytae data.parquet -select "species,body_mass_g" -arrange "body_mass_g desc" > top_penguins.txt

# Inspect compressed archives directly
pytae archive.csv.gz -shape -head 5
```

---

## 12. 🎭 Sensitive Data Masking, Aliasing, Encryption & Tokenization (`-mask`, `-unmask`, `-alias`)

Secure, redact, encrypt, tokenize, or replace sensitive/hashed columns with deterministic human-readable aliases:

```bash
# 1. One-way Cryptographic SHA-256 Hashing
pytae users.csv -mask "email=hash, user_id=sha256"

# One-way Hashing with Custom Salt
pytae users.csv -mask "email=hash" -salt "company_secret_salt_2026"

# 2. Character & String Redaction (replaces with '***')
pytae users.csv -mask "ssn=redact, credit_card=redact"

# 3. Readable Deterministic Aliasing (-alias; works on raw values OR opaque hashes)
# Presets: company, name, email, city, alias (default), code
pytae sales.parquet -alias "customer=company, rep=name, email=email" -seed 42
pytae sales.parquet -alias "customer=company" -seed 42 -vault "map.parquet" -o safe.parquet
pytae safe.parquet -unmask "customer" -vault "map.parquet"

# 3. Option 1: Reversible Authenticated Encryption (-key)
# Encrypt sensitive columns using authenticated AES/HMAC stream encryption
pytae users.csv -mask "ssn=encrypt, notes=encrypt" -key "MyStrongSecretPassphrase" -o secure.parquet

# Reversible Decryption with -unmask and -key
pytae secure.parquet -unmask "ssn, notes" -key "MyStrongSecretPassphrase"

# 4. Option 2: Reversible Pseudonym Tokenization with Persistent Vault (-vault)
# Maps unique values to consistent pseudonym tokens (e.g., user_0001) while preserving joins
pytae users.csv -mask "user=tokenize" -vault "user_vault.parquet" -o anonymized.parquet

# De-tokenize back to original values using the vault
pytae anonymized.parquet -unmask "user" -vault "user_vault.parquet"

# Mixed Multi-Column Strategy
pytae customers.csv -mask "email=hash, ssn=encrypt, name=tokenize" -key "SecretKey" -vault "names.parquet" -o clean.parquet
```

---

## 13. 💬 IPython & Jupyter Workbench (`import pytae as pt`)

Just `import pytae as pt` inside IPython or Jupyter — all workbench magics, display formatters, and Tab completions activate automatically:

```python
import pytae as pt

# 1. Load & transform immutably in-process (`%pt` / `%%pt`)
df = pt.sample("penguins")                             # or: df = %pt sales.parquet
heavy = %pt df -filter "body_mass_g > 4000" -arrange "body_mass_g desc"
top = %pt -sql "SELECT island, COUNT(*) AS n FROM df GROUP BY island"

%%pt summary
df
-dropna "body_mass_g"
-by "species, island"
-agg "avg_mass = mean(body_mass_g), n = count()"

# 2. Checkpoints, Strict Restore & Memory Reclaim
%checkpoint raw                  # Ephemeral Arrow IPC snapshot (0 MB RAM)
%checkpoint list                 # List saved checkpoints & disk size
%checkpoint diff df raw          # Compare current `df` vs checkpoint `raw`
%checkpoint rm raw               # Delete a checkpoint (or `*` for all)
%restore [raw]                   # Strict DataFrame rollback + Out/_ scrub + OS RSS trim
%status [df | checkpoint] [-v]   # Tables, shapes, RAM, checkpoints, OS RSS, settings
%free heavy                      # Delete `heavy`, scrub IPython Out/_ cache & trim RAM
%free                            # Scrub stale Out/_ DataFrame refs & trim RAM

# 3. Persistent Display Settings & Clean Export
%set max_rows=20 float_precision=2 comma=true
%set save                        # Persist to ~/.pytae/config.json
%export analysis.py              # Standalone runnable .py (prunes errors, rollbacks, previews)
%export analysis.ipynb           # Jupyter notebook (nbformat v4)
%exit -s analysis.py             # Export and exit IPython cleanly
```

👉 Full guide: [**docs/ipython.md**](ipython.md)

---

## 14. 📖 Documentation Search & MCP Server (`doc`, `mcp`)

Search documentation, CLI flags, Python API verbs, and syntax rules instantly from your terminal or AI coding assistant:

```bash
# Search by keyword or verb
pytae -doc explode
pytae -doc assert
pytae -doc "diff on key"

# Search by concept or natural language (BM25 full-text ranking)
pytae -doc "flatten list"
pytae -doc "schema drift"
pytae -doc "grouped percentiles"

# Launch Model Context Protocol (MCP) server for Copilot, Cursor, or VS Code
pytae -mcp

# Static DSL syntax check (validates pipeline flags and expressions without loading data)
pytae -check pipeline.sh
pytae -check "pytae data.parquet -filter 'amount > 0' -select id,amount"
```

---

## 15. ⚡ Shell Tab Completion (`--install-completion`)

Enable rich tab completion for flags and tabular files in your shell (Zsh, Bash, Fish):

```bash
# Auto-detect $SHELL and install tab completion:
pytae --install-completion

# Output completion script directly to stdout (e.g. for dynamic sourcing):
pytae --completion zsh
pytae --completion bash
pytae --completion fish
```

---

👉 **For Python Library Reference**: See [docs/pytae.md](pytae.md) or import directly via `import pytae as pt`.
