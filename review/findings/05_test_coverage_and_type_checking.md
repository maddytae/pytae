# Test Coverage and Type Checking Finding

This report audits test coverage, static analysis configuration (`mypy`), and linting across the repository.

---

## 1. Mypy Configuration in `pyproject.toml`

### Description
In `pyproject.toml`, lines 68–80 contain:
```toml
[[tool.mypy.overrides]]
module = [
  "pytae.accessor",
  "pytae.dataframe",
  "pytae.polars_engine",
  "pytae.repl",
  ...
]
ignore_errors = true
```
Because of these overrides, running `mypy src/pytae` reports `Success: no issues found in 20 source files`, but in reality, static type checking is disabled across 18 of the 20 source modules!

### Recommendation
Gradually type-check core modules (starting with `accessor.py`, `select.py`, `readers.py`) and remove them from the `ignore_errors = true` list so regressions are caught at compile time.

---

## 2. Test Suite Status
- Total passing tests: **975 tests** across 37 test files.
- All tests execute in ~34 seconds via `pytest -q`.
- Two minor `UserWarning` instances related to `FigureCanvasAgg` being non-interactive in headless CI environments (`test_plotter.py` and `test_cli_enhancements.py`).
