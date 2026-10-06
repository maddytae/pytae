# CLI Feature Guide: Other Utilities & Miscellaneous Commands

[← Back to CLI Reference Hub](../cli.md)

Essential utilities, convenience flags, pipeline modifiers, and miscellaneous commands that complement core analytical verbs.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Reading Row Caps (`-nrows`, `-limit`)](#reading-row-caps--nrows--limit)
- [Delimiters & Encodings (`-dlim`, `-encoding`)](#delimiters--encodings--dlim--encoding)
- [Clipboard Export (`-o clip`)](#clipboard-export--o-clip)
- [Formatting & Visual Modifiers (`-pretty`, `-round`)](#formatting--visual-modifiers--pretty--round)
- [Execution Progress (`-progress`)](#execution-progress--progress)
- [Terminal Paging (`-pager`)](#terminal-paging--pager)
- [Version & Help (`-version`, `--help`)](#version--help--version---help)

---

## Overview & Quick Reference

| Flag | Category | Syntax / Value | Description |
|---|---|---|---|
| `-nrows N` / `-limit N` | Input I/O | Integer (e.g. `1000`) | Caps number of rows read from disk during file load |
| `-dlim STR` | Input I/O | Delimiter string (e.g. `","`, `"\t"`, `"|"`) | Custom delimiter for CSV/text files (overrides autodetection) |
| `-encoding STR` | Input I/O | Encoding name (e.g. `"utf-8"`, `"latin1"`) | File character encoding |
| `-o clip` | Output I/O | Sentinel `clip` | Copies final pipeline DataFrame directly to system clipboard as TSV |
| `-pretty` | Formatting | Flag | Formats terminal tables with Markdown borders (`df.to_markdown()`) |
| `-round N` | Formatting | Integer decimals (e.g. `2`) | Rounds floating-point numbers to N decimal places |
| `-pager` | Output | Flag | Displays terminal output through an interactive pager (`pydoc.pager`) |
| `-progress` | Diagnostics | Flag | Displays live row count and percentage progress status during file operations |
| `-version` / `--version` | Meta | Flag | Displays pytae version information and exits |
| `-h` / `--help` | Meta | Flag | Displays full CLI flags usage and documentation |

---

## Reading Row Caps (`-nrows`, `-limit`)

When working with very large CSVs, text files, or datasets where you only need a quick initial sample, `-nrows` (or its alias `-limit`) stops reading the file after N rows, saving RAM and CPU time:

```bash
# Read only the first 1,000 rows from a huge CSV
pytae huge_transactions.csv -nrows 1000 -shape

# Combine with analytical verbs
pytae huge_log.txt -nrows 50000 -qry "status >= 400" -by endpoint -agg "n=n"
```

> **Note:** Unlike `-head 10` (which filters rows in the execution pipeline after the table is parsed), `-nrows` restricts row ingestion at read time from disk.

---

## Delimiters & Encodings (`-dlim`, `-encoding`)

While `pytae` automatically infers formats (`.parquet`, `.csv`, `.tsv`, `.jsonl`, `.sas7bdat`), `-dlim` and `-encoding` allow granular control over unconventional or legacy files:

```bash
# Pipe-delimited text file
pytae records.dat -dlim "|" -shape

# Tab-delimited file with explicit latin1 encoding
pytae export.txt -dlim "\t" -encoding latin1 -head 5
```

---

## Clipboard Export (`-o clip`)

Quickly copy transformed data directly to your operating system's clipboard for pasting into spreadsheets (Excel, Google Sheets) or chat:

```bash
# Filter, summarize, and copy to clipboard as clean TSV
pytae penguins.parquet \
  -by species \
  -agg "avg_mass=body_mass_g:mean, count=n" \
  -o clip
```

---

## Formatting & Visual Modifiers (`-pretty`, `-round`)

Control numeric and table formatting on stdout without modifying underlying data:

```bash
# Round floating-point averages to 2 decimals
pytae penguins.parquet -by species -agg "mean=body_mass_g:mean" -round 2

# Render output as a clean GitHub-flavored Markdown bordered table
pytae sales.parquet -by region -agg "total=revenue:sum" -pretty
```

---

## Execution Progress (`-progress`)

Enable live row-count status reporting (`reading... X/Y rows (Z%)` / `writing... X/Y rows (Z%)`) when parsing, processing, or exporting large datasets:

```bash
pytae raw_events.csv -progress -o lake_events.parquet
```

---

## Terminal Paging (`-pager`)

When viewing wide tables or hundreds of inspection rows on terminal, pipe through the interactive pager (`pydoc.pager`) without manually appending `| less`:

```bash
pytae transactions.parquet -describe -pager
```

---

## Version & Help (`-version`, `-help`)

Inspect version, access full command-line help, or query dedicated keyword help:

```bash
# Check version
pytae -version

# Full command-line reference
pytae -help

# Keyword-specific help with focused syntax, options, and copy-pasteable examples:
pytae -help sql
pytae -help mutate
pytae -help qry
pytae -help agg
pytae -help pivot
pytae -help select
```

