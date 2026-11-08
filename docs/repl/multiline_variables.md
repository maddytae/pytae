# REPL Guide: Multi-Line Input & Session Variables (`@var`)

[← Back to Master Reference](../pytae.md)

This guide covers multi-line continuation, unclosed query buffers, session parameters (`@var`), nested configuration dictionaries, and safe JSON serialization in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [Multi-Line Input & Continuation](#multi-line-input--continuation)
  - [Pipeline Line Continuation (`\`)](#pipeline-line-continuation-)
  - [Multi-Line SQL Queries](#multi-line-sql-queries)
  - [Multi-Line Data Structures](#multi-line-data-structures)
  - [Bare `py` Python Block Mode](#bare-py-python-block-mode)
  - [Aborting Multi-Line Buffers (`Ctrl+C`)](#aborting-multi-line-buffers-ctrlc)
- [Session Variables & Parameters (`@var`)](#session-variables--parameters-var)
  - [Defining Variables (`<name> = <literal>`)](#defining-variables-name--literal)
  - [Supported Types & Safety Guarantees](#supported-types--safety-guarantees)
  - [Inspection & Key Traversal (`@var`, `@var.key`, `@var[idx]`)](#inspection--key-traversal-var-varkey-varidx)
  - [Using Variables in Pipelines (`-filter`, `-mutate`, `-sql`)](#using-variables-in-pipelines--filter--mutate--sql)
  - [Listing & Deleting Variables (`status var`, `rm var`)](#listing--deleting-variables-status-var-rm-var)
  - [Checkpoint & Session Persistence (`vars.json`)](#checkpoint--session-persistence-varsjson)
  - [Namespace Isolation & Collision Prevention](#namespace-isolation--collision-prevention)

---

## Multi-Line Input & Continuation

The REPL supports multi-line inputs across pipelines, SQL queries, session variables, and Python blocks. When input is incomplete, the prompt switches to a clean `... ` continuation prompt:

### Pipeline Line Continuation (`\`)

Long analytical pipelines can be split across multiple lines using a trailing backslash `\`:

```text
pytae [df: 344x7]> df = -filter "species == 'Gentoo'" \
...   -mutate "kg = body_mass_g / 1000.0" \
...   -select "species, island, kg" \
...   -arrange "kg desc"
Updated 'df' (124 rows x 3 cols).
```

### Multi-Line SQL Queries

Complex ANSI SQL queries can span multiple lines using unclosed double or single quotes:

```text
pytae [df: 344x7]> -sql "
...   SELECT
...     species,
...     island,
...     AVG(body_mass_g) AS avg_mass,
...     COUNT(*) AS n
...   FROM df
...   GROUP BY species, island
...   ORDER BY avg_mass DESC
... "
```
This syntax also works for SQL table assignment (`summary = -sql "..."`).

### Multi-Line Data Structures

Dictionaries and lists can be authored across multiple lines using unclosed brackets or braces:

```text
pytae> cfg = {
...   "min_mass": 3200,
...   "island": "Biscoe",
...   "species": ["Gentoo", "Adelie"]
... }
Assigned variable @cfg = {'min_mass': 3200, 'island': 'Biscoe', 'species': ['Gentoo', 'Adelie']}
```

### Bare `py` Python Block Mode

Entering bare `py` initiates Python block mode. You can write multi-line Python code, loops, functions, and statements, terminating the block with an empty line (pressing Enter on an empty line):

```text
pytae [df: 344x7]> py
... for species, sub_df in pldf.group_by("species"):
...     print(f"Species: {species[0]} has {len(sub_df)} records")
... 
Species: Adelie has 152 records
Species: Gentoo has 124 records
Species: Chinstrap has 68 records
```

### Aborting Multi-Line Buffers (`Ctrl+C`)

Pressing `Ctrl+C` while in a multi-line continuation prompt immediately cancels the current input buffer, prints `^C`, and returns to the active single-line REPL prompt (`pytae> `) without executing any partial code.

---

## Session Variables & Parameters (`@var`)

The Pytae REPL provides lightweight session parameters and variables without Python runtime overhead or fragile object pickling. You can define constants, threshold limits, lists, and configuration dictionaries, reference them cleanly inside `-filter`, `-mutate`, and `-sql` expressions using the `@` prefix, and have them automatically saved and restored with checkpoints.

### Defining Variables (`<name> = <literal>`)

Assign JSON-serializable primitives (`int`, `float`, `str`, `bool`, `list`, `dict`, `None`) directly in the REPL:

```text
# Scalar numbers and strings
pytae> min_mass = 3500
Set @min_mass = 3500

pytae> label = "Gentoo"
Set @label = 'Gentoo'

pytae> factor = 1.25
Set @factor = 1.25

# Lists and collections
pytae> target_species = ['Gentoo', 'Adelie']
Set @target_species = ['Gentoo', 'Adelie']

# Dictionaries and nested configs
pytae> cfg = {'min_mass': 3200, 'island': 'Biscoe', 'limits': {'depth': 15.0}}
Set @cfg = {'min_mass': 3200, 'island': 'Biscoe', 'limits': {'depth': 15.0}}
```

### Supported Types & Safety Guarantees

Variables are strictly restricted to JSON-serializable primitives:
- **Primitives**: `int`, `float`, `str`, `bool`, `None`
- **Sequences**: `list` (tuples are converted to lists)
- **Mappings**: `dict` (keys must be strings)

Arbitrary Python class instances, lambda functions, and unpicklable objects are disallowed. This guarantees 100% portability, fast disk I/O, and zero dependency on Python pickle.

### Inspection & Key Traversal (`var`, `@var`, `var.key`, `var[idx]`)

Type any variable name (either bare or prefixed with `@`) to evaluate its current value and data type without mutating workbench state. Nested dictionary keys and list indices can be accessed using standard dot (`.`) or bracket (`[]`) notation:

```text
# Bare variable evaluation (prints raw value)
pytae> min_mass
3500

pytae> cfg.island
'Biscoe'

# @-prefixed variable evaluation (prints raw value)
pytae> @min_mass
3500

pytae> @target_species[0]
'Gentoo'

pytae> @cfg.min_mass
3200

pytae> @cfg['island']
'Biscoe'

pytae> @cfg.limits.depth
15.0
```

If an undefined variable or key is referenced, Pytae prints an informative error:
```text
pytae> @unknown
pytae: variable '@unknown' is not defined. Use 'status var' to view defined variables.
```

### Using Variables in Pipelines (`-filter`, `-mutate`, `-sql`)

Use `@var` in pipeline expressions across filters, mutations, and SQL queries:

```text
# Scalar threshold filter
pytae [df: 344x7]> df = -filter "body_mass_g > @min_mass"

# List membership filter
pytae [df: 344x7]> df = -filter "species in @target_species"

# Dictionary lookup / nested config filter
pytae [df: 344x7]> df = -filter "body_mass_g > @cfg.min_mass and island == @cfg['island']"

# Feature mutation using scalar parameter
pytae [df: 344x7]> df = -mutate "kg = body_mass_g / @factor"

# ANSI SQL query with parameterized variables
pytae [df: 344x7]> -sql "SELECT species, AVG(body_mass_g) as avg_mass FROM df WHERE body_mass_g > @min_mass GROUP BY 1"
```

### Listing & Deleting Variables (`status var`, `rm var`)

#### Listing Variables (`status var`)
```text
pytae> status var
Session Variables (3):
  * @min_mass         : 3500 (int)
  * @target_species   : ['Gentoo', 'Adelie'] (list)
  * @cfg              : {'min_mass': 3200, 'island': 'Biscoe'} (dict)
```

Use `status var -v` for verbose metadata including the raw formatted JSON output:
```text
pytae> status var -v
Session Variables (3):
  * @min_mass         : 3500 (int)
  * @target_species   : ['Gentoo', 'Adelie'] (list)
  * @cfg              : {'min_mass': 3200, 'island': 'Biscoe'} (dict)

Raw JSON:
{
  "min_mass": 3500,
  "target_species": [
    "Gentoo",
    "Adelie"
  ],
  "cfg": {
    "min_mass": 3200,
    "island": "Biscoe"
  }
}
```

Inspect an individual variable in detail with `status var <name>`:
```text
pytae> status var cfg
Variable '@cfg':
  Type  : dict
  Length: 2
  Value :
{
  "min_mass": 3200,
  "island": "Biscoe"
}
```

#### Deleting Variables (`rm var <name>`, `rm var *`)
```text
# Delete a specific variable
pytae> rm var min_mass
Removed variable '@min_mass'.

# Delete all session variables at once
pytae> rm var *
Removed all session variables (2 removed).
```

### Checkpoint & Script Export
1. When you run `checkpoint <name>`, Pytae saves all in-memory variables alongside active table states.
2. When you run `restore [name]`, Pytae restores the exact variable snapshot from the checkpoint.
3. Variable assignments are preserved across pipeline exports (`export script pipeline.pt`), ensuring parameter thresholds and configuration values replay faithfully.

```text
pytae [df]> min_mass = 4500
Set @min_mass = 4500

pytae [df]> checkpoint baseline
Saved checkpoint 'baseline' (1 tables: df, 1 variables: @min_mass).

pytae [df]> rm var *
Removed all session variables (1 removed).

pytae [df]> restore baseline
Restored checkpoint 'baseline' (1 tables: df; active: df, 1 variables: @min_mass).

pytae [df]> @min_mass
@min_mass = 4500 (int)
```

### Namespace Isolation & Collision Prevention

To guarantee predictable execution and prevent confusing state collisions:
1. **Reserved Command Protection**: Variable names cannot match built-in verbs or REPL commands (`filter`, `select`, `mutate`, `status`, `checkpoint`, `restore`, etc.).
2. **Table / Variable Collision Prevention**:
   - Assigning a variable with the name of an existing table produces an explicit error:
     `pytae: '<name>' is already an active table; cannot assign as a variable. Use 'rm table <name>' first.`
   - Assigning a table or loading a dataset with the name of an existing variable produces an explicit error:
     `pytae: '<name>' is already a session variable; cannot assign as a table. Use 'rm var <name>' first.`
   - Renaming a table to match an existing variable is similarly rejected.
3. **No `@` Prefix in Definitions**: Variables must be defined bare (`min_spend = 50.0`). Attempting to define a variable with a leading `@` (`@min_spend = 50.0`) is strictly rejected with educational guidance:
   `pytae: session variables must be defined without '@' (use 'min_spend = ...'; '@' is for referencing like '@min_spend').`
