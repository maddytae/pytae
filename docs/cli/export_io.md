# CLI Feature Guide: File I/O, Export, & Compression

[← Back to CLI Reference Hub](../cli.md)

Export pipeline results, batch-convert datasets, route outputs to dedicated directories (`-out_dir`), stream large files with progress bars (`-progress`), and read/write gzip-compressed and JSON Lines formats.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Supported Formats Matrix](#supported-formats-matrix)
- [Reading from STDIN & Pipes (`-`, `-fmt`)](#reading-from-stdin--pipes---fmt)
- [Export Destinations (`-o`)](#export-destinations--o)
  - [Explicit File Path](#explicit-file-path)
  - [In-Place Format Shorthands](#in-place-format-shorthands)
  - [System Clipboard (`clip`)](#system-clipboard-clip)
- [Target Output Directory (`-out_dir` / `-od`)](#target-output-directory--out_dir---od)
  - [Benefits of `-od` over Explicit Paths](#benefits-of--od-over-explicit-paths)
- [Transparent Compression (`.gz`)](#transparent-compression-gz)
- [JSON Lines Format (`.jsonl`, `.ndjson`)](#json-lines-format-jsonl-ndjson)
- [Delimiters & Encodings (`-dlim`, `-encoding`)](#delimiters--encodings--dlim--encoding)
- [Robust Mixed-Type Parquet Export](#robust-mixed-type-parquet-export)
- [Streaming Progress Bars (`-progress [N]`)](#streaming-progress-bars--progress-n)
- [Batch Conversions with Globbing](#batch-conversions-with-globbing)

---

## Overview & Quick Reference

| Flag | Description | Example |
|---|---|---|
| `-o TARGET` | Output destination (file path, format shorthand, or `clip`) | `-o clean.parquet`, `-o csv`, `-o clip` |
| `-out_dir DIR` / `-od DIR` | Target directory for exported files (requires `-o`) | `-o parquet -out_dir exports/` |
| `-fmt FORMAT` | Input format override when reading from STDIN (`-`) or extensionless files | `-fmt jsonl`, `-fmt csv` |
| `-progress [N]` | Display streaming row progress (default: 200,000 rows/chunk) | `-progress`, `-progress 50000` |
| `-dlim CHAR` | Text field delimiter (`.csv`, `.txt`, `.dat`) | `-dlim "\|"`, `-dlim "\t"` |
| `-encoding ENC` | Text encoding (SAS default `utf-8`, dat default `latin-1`) | `-encoding latin-1` |

---

## Supported Formats Matrix

| Format | Extension | Read | Write | Notes |
|---|---|---|---|---|
| **Parquet** | `.parquet`, `.pq` | ✓ | ✓ | Fast columnar binary format with embedded schema and snappy compression |
| **CSV** | `.csv` | ✓ | ✓ | Standard comma-delimited tabular text |
| **Delimited Text** | `.txt` | ✓ | ✓ | Defaults to tab-delimited (`\t`); customizable via `-dlim` |
| **Pipe-Delimited Data** | `.dat` | ✓ | ✓ | Defaults to pipe-delimited (`\|`) and `latin-1` encoding |
| **JSON Lines** | `.jsonl`, `.ndjson` | ✓ | ✓ | Line-delimited JSON records, streamed in chunks |
| **Compressed Gzip** | `.csv.gz`, `.txt.gz`, `.dat.gz`, `.jsonl.gz` | ✓ | ✓ | Transparent on-the-fly streaming compression and decompression |
| **SAS Dataset** | `.sas7bdat` | ✓ | — | SAS binary dataset format (read-only; export to Parquet or CSV) |

---

## Reading from STDIN & Pipes (`-`, `-fmt`)

`pytae` can read tabular streams directly from standard input (STDIN). With **auto-pipe detection**, you can pipe directly into `pytae` without typing an explicit `-`:

```bash
# Direct pipe (no dash needed!)
cat penguins.csv | pytae -head 5
curl -s https://example.com/events.csv | pytae -by event_type -agg "count=n"

# Explicit dash also fully supported
cat penguins.csv | pytae - -head 5
curl -s https://example.com/events.jsonl | pytae - -fmt jsonl -by event_type -agg "count=n"
```

When reading from STDIN, `pytae` automatically inspects the first chunk to sniff the format (`csv` vs `jsonl`). You can explicitly specify or force the input format using `-fmt`:
- `-fmt csv`
- `-fmt jsonl` / `-fmt ndjson`
- `-fmt txt` / `-fmt tsv`
- `-fmt parquet`

---

## Export Destinations (`-o`)

### Explicit File Path

Write directly to an explicit target filename:

```bash
# Save subset to Parquet
pytae penguins.parquet -select "species,body_mass_g" -o subset.parquet

# Convert SAS7BDAT to Parquet
pytae sales.sas7bdat -o sales.parquet
```

**Output:**
```text
Wrote 344 rows to subset.parquet
```

### In-Place Format Shorthands

Specify just a format name (`csv`, `parquet`, `txt`, `dat`, `jsonl`, `csv.gz`, `jsonl.gz`) to export alongside the source file with its extension changed:

```bash
pytae penguins.parquet -o csv
```

**Output:**
```text
Wrote 344 rows to penguins.csv
```

### System Clipboard (`clip`)

#### Exporting to Clipboard (`-o clip`)
Copies the output table or report directly to the system clipboard (suppressing stdout printing):

```bash
pytae penguins.parquet -head 5 -o clip
```

#### Ingesting from Clipboard (`pytae clip`)
Directly read and analyze tabular data copied to your system clipboard (e.g. from Excel, web tables, or Slack) without creating a temporary file:

```bash
# Copy a table in your browser/Excel, then immediately query it:
pytae clip -head 5
pytae clip -qry "sales > 100" -by region -agg "total = sales:sum"
```

---

## Target Output Directory (`-out_dir` / `-od`)

Direct converted files into a specific folder. Pytae automatically creates the target folder if it does not exist:

```bash
# Export single file to target folder
pytae penguins.parquet -o csv -out_dir processed/

# Using -od alias
pytae raw_data.csv -o parquet -od parquet_lake/
```

**Output:**
```text
Wrote 344 rows to processed/penguins.csv
```

> [!NOTE]
> When running batch exports into `-out_dir`, pytae validates and prevents destination filename collisions across different source folders.

### Benefits of `-od` over Explicit Paths

While providing a full target path directly in `-o` (e.g., `pytae raw.csv -o parquet_lake/raw.parquet`) works well for single files, pairing a format shorthand with `-od` (e.g., `pytae raw.csv -o parquet -od parquet_lake/`) provides substantial advantages:

1. **Mandatory for Batch Conversions & Globs**:
   When converting multiple files at once, specifying an explicit filename in `-o` fails because all incoming datasets would attempt to overwrite the exact same destination file. Using `-od` automatically preserves each file's stem name across the batch:
   ```bash
   # Converts raw/jan.csv -> parquet_lake/jan.parquet, raw/feb.csv -> parquet_lake/feb.parquet, etc.
   pytae "raw/*.csv" -o parquet -od parquet_lake/
   ```

2. **Eliminates Shell Boilerplate in Pipelines**:
   In automated scripts or CI/CD pipelines where input filenames are dynamic variables (`$INPUT_FILE`), you do not need shell manipulation (`basename`, parameter expansion `${f%.*}`) to compute the new path:
   ```bash
   # Without -od: verbose and fragile shell manipulation
   pytae "$INPUT_FILE" -o "parquet_lake/$(basename "${INPUT_FILE%.*}").parquet"

   # With -od: clean and declarative
   pytae "$INPUT_FILE" -o parquet -od parquet_lake/
   ```

3. **Compound Extension & Compression Awareness**:
   Pytae understands multi-part extensions like `.csv.gz` or `.jsonl.gz`. Using `-o parquet -od parquet_lake/` cleanly strips both the `.gz` and `.csv` extensions, generating `parquet_lake/data.parquet` rather than `parquet_lake/data.csv.parquet`.

4. **Automatic Directory Creation & Collision Guarding**:
   Target directories specified in `-od` are automatically created (`mkdir -p`) if they do not already exist. Pytae also verifies that batch inputs from different source directories sharing the same filename do not silently overwrite one another.

#### Summary Comparison

| Capability | Explicit Path (`-o path/name.ext`) | Directory Routing (`-o <format> -od <dir>`) |
|---|---|---|
| **Single known destination** | `pytae raw.csv -o lake/clean.parquet` | `pytae raw.csv -o parquet -od lake/` |
| **Batch / Glob conversions** | ❌ Fails (destination collision error) | `pytae "raw/*.csv" -o parquet -od lake/` |
| **Shell scripts & variables** | Requires `basename` / `${f%.*}` manipulation | Declarative: `pytae "$FILE" -o parquet -od lake/` |
| **Compressed source (`.csv.gz`)** | Manual stem cleanup required | Auto-strips compound extension to `.parquet` |
| **Destination directory** | Auto-creates parent folder | Auto-creates directory tree (`mkdir -p`) |


---

## Transparent Compression (`.gz`)

Read and write gzip-compressed tabular files directly without decompressing intermediate files onto disk:

```bash
# Compress CSV to gzip
pytae large.csv -o large.csv.gz

# Ingest compressed CSV and convert directly to Parquet
pytae large.csv.gz -o parquet

# Export Parquet to compressed JSON Lines
pytae events.parquet -o events.jsonl.gz
```

---

## JSON Lines Format (`.jsonl`, `.ndjson`)

Full chunked streaming support for newline-delimited JSON records:

```bash
# Inspect JSON Lines structure
pytae web_traffic.jsonl -shape -cols

# Convert JSON Lines to Parquet
pytae web_traffic.jsonl -o parquet
```

---

## Delimiters & Encodings (`-dlim`, `-encoding`)

### Delimiter (`-dlim`)

Override field separators for delimited text files:

```bash
# Read semicolon-delimited CSV and convert to Parquet
pytae european_data.csv -dlim ";" -o european_data.parquet

# Export with custom delimiter
pytae data.parquet -dlim "|" -o pipe_separated.txt
```

### Encoding (`-encoding`)

Handle non-UTF-8 character encodings:

```bash
pytae legacy_data.sas7bdat -encoding latin-1 -o modern.parquet
```

---

## Robust Mixed-Type Parquet Export

When converting messy datasets (such as CSV or SAS tables containing mixed strings, integers, and floats within an `object` column) to Parquet, PyArrow typically raises an `ArrowInvalid` conversion error:
```text
pyarrow.lib.ArrowInvalid: Could not convert '0828' with type str: tried to convert to double
```

`pytae` automatically intercepts `ArrowInvalid` during Parquet writes, safely converts the problematic mixed columns to clean strings with a clear `UserWarning`, and completes the export without crashing.

---

## Streaming Progress Bars (`-progress [N]`)

When converting large files with millions of rows, `-progress` shows real-time progress and processes data in memory-efficient chunks:

```bash
# Default chunk size (200,000 rows per chunk)
pytae 50m_rows.csv -o 50m_rows.parquet -progress

# Custom chunk size (50,000 rows per chunk)
pytae 50m_rows.csv -o 50m_rows.parquet -progress 50000
```

**Output:**
```text
writing... 1200000/5000000 rows (24%)
```

---

## Batch Conversions with Globbing

Convert dozens or hundreds of files at once using shell globbing:

```bash
# Convert all CSV files to Parquet in-place
pytae data/*.csv -o parquet

# Batch convert all Parquet files to compressed CSV in an exports directory
pytae data/*.parquet -o csv.gz -out_dir exports/
```

**Output:**
```text
== data/file1.parquet ==
Wrote 100000 rows to exports/file1.csv.gz
== data/file2.parquet ==
Wrote 150000 rows to exports/file2.csv.gz
```
