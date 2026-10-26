# Pytae CLI Cheat Sheet & Cookbook

The definitive quick-reference guide and recipe cookbook for the `pytae` Unix command-line tool.

---

## 1. ⚡ Quick File Inspection & Metadata

Inspect Parquet, CSV, TSV, JSONL, and SAS7BDAT datasets with zero startup overhead:

```bash
# Print row and column dimensions (zero-cost on Parquet)
pytae data.parquet -shape

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

# Inspect low-level Parquet metadata (row groups, compression, statistics)
pytae data.parquet -meta

# Random sampling (reproducible with -seed)
pytae data.parquet -sample 10 -seed 42
pytae data.parquet -sample -frac 0.05
```

---

## 2. 🔍 Row Filtering & Slicing (`-filter`)

Filter rows cleanly using operator expressions, ranges, set membership, or column comparisons:

```bash
# Exact match (strict '==' enforced; string values must be quoted)
pytae data.parquet -filter "species == 'Gentoo'"

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

# Null and NaN checks (universal 'is_null()' / 'is_nan()' in expressions and dicts)
pytae data.parquet -filter "sex.is_not_null()"
pytae data.parquet -filter "sex.is_null()"
pytae data.parquet -filter "{'sex': 'is_null()'}"
pytae data.parquet -filter "score.is_nan()"
pytae data.parquet -filter "score.is_not_nan()"
pytae data.parquet -filter "{score: is_nan()}"

# Columns with parentheses or spaces
pytae data.parquet -filter "counterparty_class_(irb) == 'Sovereigns'"
pytae data.parquet -filter "[counterparty class (irb)].is_not_null()"

# Drop rows containing missing values
pytae data.parquet -dropna
pytae data.parquet -dropna "body_mass_g,sex"
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

## 4. 🎯 Column Selection & Renaming (`--select`, `-rename`)

Select, reorder, and drop columns with flexible pattern matching:

```bash
# Explicit column selection and reordering
pytae data.parquet --select "species,island,body_mass_g"

# Drop columns using exclamation mark negation (!col)
pytae data.parquet --select "!sex,!year"

# Pattern and prefix matching
pytae data.parquet --select "startswith=bill_"
pytae data.parquet --select "endswith=_mm"
pytae data.parquet --select "contains=length"

# Select by data type
pytae data.parquet --select "dtype=float"
pytae data.parquet --select "exclude_dtype=string"

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
pytae data.parquet -by species -agg "avg_mass=body_mass_g:mean" \
  -plot "kind=bar, x=species, y=avg_mass" -finalize "save=chart.png"
```

---

## 6. 📈 Aggregation & Grouping (`-by`, `-agg`)

Perform blazing-fast grouped calculations:

```bash
# Group-by count
pytae data.parquet -by species -count

# Multiple aggregations per group
pytae data.parquet -by species -agg "avg_mass=body_mass_g:mean, max_flipper=flipper_length_mm:max, total=count"

# Multi-column grouping
pytae data.parquet -by "species,island" -agg "mean_mass=body_mass_g:mean"

# Deduplicate rows across key columns
pytae data.parquet -distinct "species,island"

# Sort rows by multiple columns with directions
pytae data.parquet -arrange "species asc, body_mass_g desc"
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
```

---

## 8. 🔗 Multi-File Relational Operations (`-file`, `-join`, `-sql`)

Combine multiple datasets without touching Python:

```bash
# Inner, left, right, or outer joins
pytae -file "orders.parquet=ord; customers.csv=cust" \
  -join "left=ord, right=cust, on=customer_id, how=left" \
  -head 10

# Stack datasets vertically (concat / union)
pytae -file "q1.parquet=a; q2.parquet=b; q3.parquet=c" \
  -concat "frames=a,b,c" -shape

# Run analytical ANSI SQL across files
pytae -file "sales.parquet=s; stores.csv=st" \
  -sql "SELECT st.region, SUM(s.amount) as total FROM s JOIN st ON s.store_id = st.id GROUP BY 1 ORDER BY 2 DESC"
```

---

## 9. 💾 Format Conversions & Sinks (`-o`)

Convert effortlessly between `.parquet`, `.csv`, `.tsv`, `.dat`, `.jsonl`, and `.sas7bdat`:

```bash
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

## 12. 🎭 Sensitive Data Masking, Encryption & Tokenization (`-mask`, `-unmask`)

Secure, redact, encrypt, or tokenize sensitive PII columns across one-way and reversible workflows:

```bash
# 1. One-way Cryptographic SHA-256 Hashing
pytae users.csv -mask "email=hash, user_id=sha256"

# One-way Hashing with Custom Salt
pytae users.csv -mask "email=hash" -salt "company_secret_salt_2026"

# 2. Character & String Redaction (replaces with '***')
pytae users.csv -mask "ssn=redact, credit_card=redact"

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

## 13. 💬 Interactive REPL Shell (`-i`)

Stateful interactive data manipulation environment with in-memory execution and undo/redo history:

```bash
# Launch interactive REPL with a dataset pre-loaded
pytae data.parquet -i

# Launch empty REPL workbench
pytae -i

# Pre-filter dataset and drop directly into interactive REPL
pytae data.parquet -filter "sales > 100" -i

# Inside the REPL prompt:
# 1. State Management & Undo
undo                 # Revert last transformation
redo                 # Re-apply last undone transformation
reset                # Restore original dataset from disk (instant O(1))
history              # Show history of applied pipeline steps
checkpoint v1        # Save snapshot of all tables in session
rm checkpoint v1     # Delete a saved checkpoint
restore v1           # Restore entire workbench to named snapshot
rm df                # Remove active table from memory (or rm df1 / rm -all, undoable)
status               # Show active dataset shape, columns, and memory

# 2. Pipeline Execution & Inspection (RAM-speed with zero file re-reads)
pytae> -filter "species == 'Gentoo'"
pytae> -mutate "mass_kg = body_mass_g / 1000.0"
pytae> -by species -agg "mean_kg=mass_kg:mean, n=count"
pytae> -select "species,island,mass_kg"
pytae> -arrange "mass_kg desc"
pytae> -cols asc                                             # Column names sorted alphabetically
pytae> -cols | grep mass                                     # Pipe command output to shell utility

# 3. Direct Query Engines & Export
pytae> -sql "SELECT species, AVG(body_mass_g) FROM df GROUP BY 1"
pytae> py df.shape
pytae> -o clean.parquet
pytae> -o clip                                               # Copy active table to system clipboard
# Up / Down arrow keys recall persistent command history (~/.pytae_history)
```

---

👉 **For Python Library Reference**: See [docs/pytae.md](pytae.md) or import directly via `import pytae as pt`.
