# Status of Previous Audits (`review/*.md`)

This report maps the findings from the historical audit documents in `review/` against the current codebase in `pytae` v3.13.3.

---

## 1. Status of Issues from `review/error.md`

| Item | Problem in `review/error.md` | Status in v3.13.3 | Notes |
|:---|:---|:---:|:---|
| 1.1 | REPL `-glimpse` double-prints to stdout | **RESOLVED** | Uses `format_glimpse(df)` directly via `output_fn`. |
| 1.2 | `validate_pipeline()` crashes on fallback extensions | **RESOLVED** | Fixed to call `get_reader(Path(source_str), **kwargs).head(0)`. |
| 1.3 | `.pt.glimpse()` accessor breaks method chaining | **OPEN** | `_BasePtAccessor.glimpse()` returns `self._obj` instead of `DataFrame(self._obj)`. |
| 1.4 | Lazy DataFrame crashes on `.equals()`, `.values`, `.to_numpy()` | **RESOLVED** | Addressed in `dataframe.py`. |
| 1.5 | `pt.long()` and `.pt.long()` reject `r=` parameter | **RESOLVED** | `pt.long()` accepts `r=` and forwards it to `DataFrame.long()`. |
| 1.6 | CLI and REPL fail on Arrow IPC / Feather files | **RESOLVED** | `IpcReader` added and registered in `_READERS` and `_WRITABLE_SUFFIXES`. |
| 1.7 | Duplicate error print in REPL `_cmd_load` | **RESOLVED** | Redundant print call removed. |
| 1.8 | Chaining `-freq <col> -bar` creates duplicate bar column | **OPEN** | `-bar` still appends an extra bar column next to `"Distribution"`. |
| 2.1 | `pyproject.toml` disables `mypy` across 18 source modules | **OPEN** | `ignore_errors = true` still active in `pyproject.toml`. |

---

## 2. Status of Issues from `review/inconsistency.md`

| Item | Problem in `review/inconsistency.md` | Status in v3.13.3 | Notes |
|:---|:---|:---:|:---|
| 1.1 | Single-dash policy violated in Cheatsheet and Help Strings | **PARTIALLY RESOLVED** | Cheatsheet was fixed; `cli_help.py` still advertises `--<flag>`. |
| 1.2 | `-tolerance` advertised in epilog but rejected by parser | **OPEN** | Parser still enforces `-tol` and rejects `-tolerance`. |
| 2.1 | `long()` missing `r=` at top-level | **RESOLVED** | Added to `src/pytae/__init__.py`. |
| 2.2 | `glimpse()` return type inconsistency | **OPEN** | `_BasePtAccessor.glimpse()` still returns raw object. |
| 2.3 | `clean_columns` untyped `**kwargs` | **OPEN** | Untyped `**opts` in accessor and `__init__.py`. |
| 4.1 | `-cols <arg>` substring filtering works in REPL, not CLI | **OPEN** | CLI only accepts `asc`, `desc`, `file`. |

---

## 3. Status of Improvements from `review/code_improvement.md`

| Item | Proposed Refactoring | Status in v3.13.3 |
|:---|:---|:---:|
| 1 | Extract `_BasePtAccessor` for `PolarsPtAccessor` & `PandasPtAccessor` | **DONE** (saved ~210 lines) |
| 3 | Extract shared `_DelimitedReader` base class for `CsvReader` & `TxtReader` | **DONE** (`TxtReader` subclasses `CsvReader`) |
| 4 | Delete unreachable disk-IPC undo/redo snapshot code in REPL | **DONE** (`_capture_session_state_to_disk` deleted) |
| 5 | Delete dead/retired CLI functions | **DONE** |

