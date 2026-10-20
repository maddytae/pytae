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
# Exact match (string values must be enclosed in quotes)
pytae data.parquet -filter "species = 'Gentoo'"

# Numeric comparison operators (>, <, >=, <=, !=)
pytae data.parquet -filter "body_mass_g > 5000"
pytae data.parquet -filter "body_mass_g >= 3500, flipper_length_mm < 210"

# Column-to-column comparison (reconcile IDs, detect limit breaches)
pytae loans.parquet -filter "exposure > col(limit)"
pytae loans.parquet -filter "tranche_id == col(deal_id)"

# Inclusive interval ranges [min, max]
pytae data.parquet -filter "body_mass_g = [3000, 3500]"

# List set membership
pytae data.parquet -filter "species = ['Adelie', 'Chinstrap']"
pytae data.parquet -filter "species not in ['Gentoo']"

# Null checks (methods or SQL syntax)
pytae data.parquet -filter "sex.notna()"
pytae data.parquet -filter "sex is not null"
pytae data.parquet -filter "sex.is_null()"

# Columns with parentheses or spaces
pytae data.parquet -filter "counterparty_class_(irb) == 'Sovereigns'"
pytae data.parquet -filter "[counterparty class (irb)].notna()"

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

# Drop columns with negative prefix (-col)
pytae data.parquet --select "-sex,-year"

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
# Melt wide table into long form (unpivot)
pytae data.parquet -long "id=species,island; names_to=metric, values_to=value"

# Pivot long table into wide form
pytae long.parquet -wide "id=species; names_from=metric, values_from=value"

# 2D Pivot table with aggregation
pytae data.parquet -pivot "index=species, columns=island, values=body_mass_g, agg=mean"
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

👉 **For Python Library Reference**: See [docs/pytae.md](pytae.md) or import directly via `import pytae as pt`.
