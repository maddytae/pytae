# pytae

R-style chaining on pandas, plus a CLI for inspecting and converting tabular files (`.parquet`, `.csv`, `.txt`, `.sas7bdat`).

## Install

```bash
pip install pytae          # CLI + DataFrame methods (pandas ≥ 2.0, pyarrow ≥ 15)
pip install pytae[plot]    # matplotlib — only needed for Plotter
```

Requires **Python ≥ 3.10** and **pandas ≥ 2.0**.

```bash
pip install -e ".[dev]"    # local checkout
pytest
```

## Docs

- [CLI](docs/CLI.md)
- [Library](docs/LIBRARY.md)
