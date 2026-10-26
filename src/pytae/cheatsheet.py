"""Pytae CLI Cheat Sheet & Quick-Reference Cookbook.

Provides built-in terminal cheat sheet accessible via `pytae -cheatsheet` or `pytae -examples`.
"""

from __future__ import annotations

CHEATSHEET_TEXT = """\
================================================================================
                      PYTAE CLI CHEAT SHEET & COOKBOOK                          
================================================================================

1. ⚡ QUICK FILE INSPECTION & METADATA
--------------------------------------------------------------------------------
  pytae data.parquet -shape                      # Print (rows, cols)
  pytae data.parquet -head                       # Preview first 5 rows
  pytae data.parquet -head 10                    # Preview first 10 rows
  pytae data.parquet -tail 5                     # Preview last 5 rows
  pytae data.parquet -cols                       # Column names (file order)
  pytae data.parquet -cols asc                   # Column names (alphabetical)
  pytae data.parquet -dtype                      # Column data types
  pytae data.parquet -nulls                      # Missing count per column
  pytae data.parquet -glimpse                    # Transposed overview
  pytae data.parquet -describe                   # Statistical summary
  pytae data.parquet -meta                       # Parquet row groups/compression
  pytae data.parquet -sample 10 -seed 42         # Random sample with seed
  pytae data.parquet -sample -frac 0.05          # Sample 5% fraction of rows

2. 🔍 ROW FILTERING & SLICING (-filter)
--------------------------------------------------------------------------------
  pytae data.parquet -filter "species == 'Gentoo'"
  pytae data.parquet -filter "body_mass_g > 5000"
  pytae data.parquet -filter "body_mass_g >= 3500 and flipper_length_mm < 210"
  pytae data.parquet -filter "(species == 'Adelie' or species == 'Chinstrap') and body_mass_g > 4000"
  pytae loans.parquet -filter "exposure > limit"                  # Column compare
  pytae loans.parquet -filter "tranche_id == deal_id"             # ID equality
  pytae data.parquet -filter "{'body_mass_g': ('between', 3000, 3500)}"     # Option 1 range
  pytae data.parquet -filter "{'body_mass_g': (('>=', 3000), ('<=', 3500))}" # Option 2 range
  pytae data.parquet -filter "species in ['Adelie', 'Chinstrap']" # Set membership
  pytae data.parquet -filter "species not in ['Gentoo']"
  pytae data.parquet -filter "sex.is_not_null()"                 # Missing checks (or {'sex': 'is_null()'})
  pytae data.parquet -filter "score.is_nan()"                    # NaN checks (or {'score': 'is_nan()'})
  pytae data.parquet -filter "counterparty_class_(irb).is_not_null()" # Special columns
  pytae data.parquet -dropna                                      # Drop 100% null rows
  pytae data.parquet -dropna "body_mass_g,sex"

3. 🛠 FEATURE ENGINEERING & MUTATION (-mutate)
--------------------------------------------------------------------------------
  pytae data.parquet -mutate "mass_kg = body_mass_g / 1000.0"
  pytae data.parquet -mutate "kg = body_mass_g / 1000, lbs = kg * 2.20462"
  pytae data.parquet -mutate "size = if_else(body_mass_g > 4000, 'Large', 'Small')"
  pytae data.parquet -mutate "tier = case_when(body_mass_g > 5000, 'H', body_mass_g > 3500, 'M', default='L')"
  pytae data.parquet -mutate "is_gentoo = map(species, {'Gentoo': True}, default=False)"
  pytae data.parquet -mutate "region = map(island, {'Biscoe': 'South'}, default='Other')"
  pytae data.parquet -mutate "species_lower = species.str.lower()"
  pytae data.parquet -mutate "diff = irba_unsecured_lgd_(1g00) - post_crm_lgd_(2a)"

4. 🎯 COLUMN SELECTION & RENAMING (--select, -rename)
--------------------------------------------------------------------------------
  pytae data.parquet --select "species,island,body_mass_g"
  pytae data.parquet --select "!sex,!year"                        # Drop columns
  pytae data.parquet --select "startswith=bill_"                  # Prefix match
  pytae data.parquet --select "endswith=_mm"                      # Suffix match
  pytae data.parquet --select "contains=length"                   # Substring match
  pytae data.parquet --select "dtype=float"                       # Dtype match
  pytae data.parquet -rename "body_mass_g:weight_g"               # Old:new
  pytae messy.csv -clean_columns "strip,fill=_,case=lower,dedupe" # Header hygiene

5. 📊 IN-TERMINAL VISUALIZATIONS
--------------------------------------------------------------------------------
  pytae data.parquet -freq species                                # Frequency table
  pytae data.parquet -freq species -bar                           # ASCII bar chart
  pytae data.parquet -hist body_mass_g                            # Histogram
  pytae data.parquet -hist body_mass_g:20                         # 20-bin histogram
  pytae data.parquet -scatter "bill_length_mm,bill_depth_mm"     # ASCII scatter
  pytae data.parquet -corr                                        # Correlation matrix
  pytae data.parquet -by species -agg "avg=body_mass_g:mean" \\
    -plot "kind=bar, x=species, y=avg" -finalize "save=chart.png" # PNG figure

6. 📈 AGGREGATION & GROUPING (-by, -agg)
--------------------------------------------------------------------------------
  pytae data.parquet -by species -count
  pytae data.parquet -by species -agg "avg_mass=body_mass_g:mean, total=count"
  pytae data.parquet -by "species,island" -agg "mean_mass=body_mass_g:mean"
  pytae data.parquet -distinct "species,island"
  pytae data.parquet -arrange "species asc, body_mass_g desc"

7. 🔄 RESHAPING & PIVOTING (-long, -wide, -pivot)
--------------------------------------------------------------------------------
  pytae data.parquet -long "r=species,island, c=metric, v=val"
  pytae long.parquet -wide "r=species, c=metric, v=val"
  pytae data.parquet -pivot "r=species, c=island, v=body_mass_g, a=mean"

8. 🔗 MULTI-FILE RELATIONAL OPERATIONS (-file, -join, -concat, -sql)
--------------------------------------------------------------------------------
  pytae -file "orders.parquet=ord; customers.csv=cust" \\
    -join "left=ord, right=cust, on=customer_id, how=left" -head 10
  pytae -file "q1.parquet=a; q2.parquet=b" -concat "frames=a,b" -shape
  pytae -file "sales.parquet=s; stores.csv=st" \\
    -sql "SELECT st.region, SUM(s.amount) FROM s JOIN st ON s.store_id = st.id GROUP BY 1"

9. 💾 FORMAT CONVERSIONS & SINKS (-o)
--------------------------------------------------------------------------------
  pytae legacy.sas7bdat -o clean.parquet                          # SAS to Parquet
  pytae data.parquet -o export.csv                                # Parquet to CSV
  pytae "raw/*.csv" -o parquet -out_dir "clean/"                  # Batch convert
  pytae data.txt -dlim "\\t" -encoding latin-1 -o data.parquet
  pytae data.parquet -filter "species == 'Gentoo'" -head 10 -o clip # System clipboard

10. 🧪 DRIFT & DIFFERENCE DETECTION (-diff)
--------------------------------------------------------------------------------
  pytae baseline.parquet -diff current.parquet                    # Schema + cell diff
  pytae baseline.parquet -diff current.parquet -tol 1e-4          # Numerical tolerance
  pytae left.csv -diff right.csv -dlim "," -tol 0.001

11. 🚰 UNIX SHELL PIPING
--------------------------------------------------------------------------------
  cat raw_stream.csv | pytae - -fmt csv -shape                    # Pipe from STDIN
  pytae data.parquet -filter "body_mass_g > 4000" | grep "Biscoe" | less
  pytae data.parquet -select "species,body_mass_g" > top.txt      # Redirect stdout
  pytae archive.csv.gz -shape -head 5                             # Inspect gz stream

12. 🎭 DATA MASKING, ENCRYPTION & TOKENIZATION (-mask, -unmask)
--------------------------------------------------------------------------------
  pytae users.csv -mask "email=hash, ssn=redact"                  # One-way hash & redact
  pytae users.csv -mask "email=hash" -salt "my_salt"              # Salted SHA-256 hash
  pytae users.csv -mask "ssn=encrypt" -key "Secret123"            # Reversible encryption (key)
  pytae users.csv -mask "user=tokenize" -vault "vault.parquet"    # Reversible tokenization (vault)
  pytae secure.parquet -unmask "ssn" -key "Secret123"             # Decrypt with key
  pytae dev.parquet -unmask "user" -vault "vault.parquet"         # De-tokenize with vault

13. 💬 INTERACTIVE REPL SHELL (-i)
--------------------------------------------------------------------------------
  pytae data.parquet -i                                           # Launch REPL with file loaded
  pytae -i                                                        # Launch empty REPL workbench
  pytae data.parquet -filter "sales > 100" -i                     # Pre-filter then enter REPL
  # Inside REPL session:
  #   undo / redo             Revert / re-apply last transformation step
  #   reset                   Restore original dataset from disk (instant O(1))
  #   checkpoint <name>       Save named snapshot across all session tables
  #   rm checkpoint <name>    Delete a saved checkpoint
  #   rm <table_name>         Remove in-memory table (undoable)
  #   restore <name>          Restore entire workbench to named snapshot
  #   -cols [asc|desc]        List column names (file order or sorted)
  #   <cmd> | <shell_cmd>     Pipe output to shell utility (e.g. -cols | grep mass)
  #   -sql "<query>"          Run ANSI SQL across loaded tables
  #   -o <path|clip>          Export active dataset to file or clipboard
  #   Up / Down arrow keys    Recall persistent command history (~/.pytae_history)
  #   -filter, -mutate, etc.  Standard pytae pipeline flags executed in RAM!

Full documentation: https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md
================================================================================
"""
