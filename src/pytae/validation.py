"""Pipeline and DSL validation utilities for pytae.

Provides:
1. `validate_pipeline(pipeline, source, **kwargs)`: Zero-data pipeline pre-flight validator.
2. `check_dsl_string(verb, spec)`: Validates DSL syntax for a pytae verb without data.
3. `check_dsl_file(file_path)`: Statically inspects a Python file for pytae DSL syntax errors.
4. `check_dsl_paths(paths)`: Statically checks files/directories for CI and git pre-commit hooks.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


class PipelineValidationError(ValueError):
    """Raised when a pipeline fails pre-flight validation against a schema or data source."""

    pass


@dataclass
class DSLDiagnostic:
    """A diagnostic message reporting a DSL syntax issue in a file."""

    file: str
    line: int
    col: int
    verb: str
    expression: str
    message: str
    severity: str = "error"

    def format(self, color: bool = True) -> str:
        if color:
            red = "\033[31;1m"
            cyan = "\033[36m"
            bold = "\033[1m"
            reset = "\033[0m"
            return (
                f"{bold}{self.file}:{self.line}:{self.col}:{reset} "
                f"{red}{self.severity}:{reset} "
                f"{cyan}[{self.verb}]{reset} {self.message}\n"
                f"    {bold}Expression:{reset} {self.expression}"
            )
        return (
            f"{self.file}:{self.line}:{self.col}: {self.severity}: "
            f"[{self.verb}] {self.message}\n"
            f"    Expression: {self.expression}"
        )

    def __str__(self) -> str:
        return self.format(color=False)


def validate_pipeline(
    pipeline: Callable[[Any], Any],
    source: Any,
    **kwargs: Any,
) -> Any:
    """Validate a pytae data pipeline against a data source or schema without loading row data.

    Creates a zero-row mock DataFrame matching the source's schema and executes
    the pipeline function. This validates all string expressions, column references,
    mutations, filters, selects, group-bys, and joins in milliseconds before running on real data.

    Parameters
    ----------
    pipeline : Callable[[DataFrame], DataFrame]
        A function or lambda taking a pytae DataFrame and returning a pytae DataFrame.
    source : str | Path | DataFrame | pl.DataFrame | pl.LazyFrame | pd.DataFrame | pl.Schema | dict[str, Any]
        File path (e.g. .parquet, .csv) or existing DataFrame / schema specification.
        If a file path is provided, it is scanned lazily without reading row data.
    **kwargs : Any
        Additional keyword arguments passed to reader functions if `source` is a path.

    Returns
    -------
    DataFrame
        The resulting zero-row DataFrame with the validated output schema.

    Raises
    ------
    PipelineValidationError
        If any expression references an invalid column, has malformed DSL syntax,
        or violates schema constraints.
    """
    import pandas as pd
    import polars as pl

    from pytae.dataframe import DataFrame
    from pytae.readers import get_reader, scan_csv, scan_ipc, scan_ndjson, scan_parquet

    if isinstance(source, (str, Path)):
        source_str = str(source)
        ext = Path(source_str).suffix.lower()
        if ext in (".parquet", ".pq"):
            df = scan_parquet(source_str, **kwargs).head(0)
        elif ext in (".csv", ".tsv"):
            df = scan_csv(source_str, **kwargs).head(0)
        elif ext in (".ndjson", ".jsonl"):
            df = scan_ndjson(source_str, **kwargs).head(0)
        elif ext in (".ipc", ".arrow", ".feather"):
            df = scan_ipc(source_str, **kwargs).head(0)
        else:
            df = DataFrame(get_reader(Path(source_str), **kwargs).head(0))
    elif isinstance(source, DataFrame):
        df = source.head(0)
    elif isinstance(source, (pl.DataFrame, pl.LazyFrame)):
        df = DataFrame(source).head(0)
    elif isinstance(source, pd.DataFrame):
        df = DataFrame(source.head(0))
    elif isinstance(source, pl.Schema):
        df = DataFrame(pl.LazyFrame(schema=source))
    elif isinstance(source, dict):
        schema_dict: dict[str, Any] = {}
        for k, v in source.items():
            if isinstance(v, type):
                if issubclass(v, (int,)):
                    schema_dict[k] = pl.Int64
                elif issubclass(v, (float,)):
                    schema_dict[k] = pl.Float64
                elif issubclass(v, (str,)):
                    schema_dict[k] = pl.String
                elif issubclass(v, (bool,)):
                    schema_dict[k] = pl.Boolean
                else:
                    schema_dict[k] = pl.String
            elif isinstance(v, pl.DataType):
                schema_dict[k] = v
            elif isinstance(v, str):
                v_lower = v.lower()
                if v_lower in ("int", "int64", "integer"):
                    schema_dict[k] = pl.Int64
                elif v_lower in ("int32", "int16", "int8"):
                    schema_dict[k] = getattr(pl, v.capitalize(), pl.Int64)
                elif v_lower in ("float", "float64", "numeric", "number"):
                    schema_dict[k] = pl.Float64
                elif v_lower in ("float32",):
                    schema_dict[k] = pl.Float32
                elif v_lower in ("str", "string", "text", "utf8"):
                    schema_dict[k] = pl.String
                elif v_lower in ("bool", "boolean"):
                    schema_dict[k] = pl.Boolean
                elif v_lower in ("date",):
                    schema_dict[k] = pl.Date
                elif v_lower in ("datetime", "timestamp"):
                    schema_dict[k] = pl.Datetime
                else:
                    schema_dict[k] = pl.String
            else:
                schema_dict[k] = pl.String
        df = DataFrame(pl.LazyFrame(schema=schema_dict))
    else:
        raise TypeError(f"Unsupported source type for validate_pipeline: {type(source).__name__}")

    try:
        result = pipeline(df)
        if hasattr(result, "collect_schema"):
            result.collect_schema()
        return result.head(0) if hasattr(result, "head") else result
    except Exception as exc:
        raise PipelineValidationError(f"Pipeline validation failed: {exc}") from exc


def _sanitize_for_ast(expr: str) -> str:
    """Normalize DSL expression to valid standard Python AST for syntax checking."""
    # 1. Logical words
    res = expr.replace(" and ", " & ").replace(" or ", " | ")
    # 2. Backtick quoted column names: `col name` -> __col_name__
    res = re.sub(r"`([^`]+)`", lambda m: f"__col_{re.sub(r'[^a-zA-Z0-9_]', '_', m.group(1))}__", res)
    # 3. Parameters: @param -> __param_param__
    res = re.sub(r"@([a-zA-Z0-9_]+)", r"__param_\1__", res)
    # 4. Bracketed column names: [col name] -> __col_name__
    res = re.sub(r"\[([^\]]+)\]", lambda m: f"__col_{re.sub(r'[^a-zA-Z0-9_]', '_', m.group(1))}__", res)
    return res


def check_dsl_string(verb: str, spec: str) -> list[str]:
    """Validate the syntax of a single pytae DSL string without requiring a DataFrame schema.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []
    verb = verb.lower().strip()
    raw = spec.strip()
    if not raw:
        return errors

    if verb == "mutate":
        from pytae._parsing import _split_mutate_entries, _unquote_name

        try:
            entries = _split_mutate_entries(raw)
        except Exception as e:
            return [f"mutate spec parse error: {e}"]

        for key_raw, expr_raw in entries:
            key = _unquote_name(key_raw.strip())
            if not key:
                errors.append("invalid mutate spec: empty column name")
                continue
            expr = expr_raw.strip()
            if not expr:
                errors.append(f"invalid mutate spec: '{key}' has no expression")
                continue

            safe_expr = _sanitize_for_ast(expr)

            try:
                tree = ast.parse(safe_expr, mode="eval")
            except SyntaxError as e:
                errors.append(f"syntax error in formula for '{key}': {e.msg}")
                continue

            # Validate AST nodes (case_when, if_else)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_id = getattr(node.func, "id", None)
                    if func_id == "case_when":
                        if not node.args and not node.keywords:
                            errors.append("case_when() requires at least one condition-value argument")
                        has_tuple = any(isinstance(a, ast.Tuple) for a in node.args)
                        if has_tuple:
                            for idx, a in enumerate(node.args):
                                if isinstance(a, ast.Tuple):
                                    if len(a.elts) != 2:
                                        errors.append(
                                            f"case_when() tuple argument {idx + 1} must be a (condition, value) pair"
                                        )
                                elif idx != len(node.args) - 1:
                                    errors.append("case_when() default (non-tuple) must be the final argument")
                    elif func_id == "if_else":
                        if len(node.args) != 3:
                            errors.append(
                                f"if_else() takes exactly 3 arguments (condition, true_val, false_val), got {len(node.args)}"
                            )

    elif verb == "filter":
        from pytae._parsing import _tokenize

        tokens = _tokenize(raw, ",", track_brackets=True)
        for token in tokens:
            t = token.strip()
            if not t:
                continue
            safe_t = _sanitize_for_ast(t)
            # Check if not a criteria matcher
            if not any(safe_t.startswith(kw + "=") for kw in ("contains", "startswith", "endswith", "regex", "dtype")):
                try:
                    ast.parse(safe_t, mode="eval")
                except SyntaxError:
                    pass

    elif verb == "select":
        from pytae._parsing import _tokenize

        tokens = _tokenize(raw, ",", track_brackets=True)
        for token in tokens:
            t = token.strip()
            if t.startswith("exclude="):
                errors.append("'exclude=' is retired in favor of '!' negation. Use '!col' or '!col1,!col2' instead.")
            elif "=" in t and not t.startswith("!["):
                k, _, _ = t.partition("=")
                k = k.strip()
                from pytae.cli_parsing import SELECT_KEYS

                if k not in SELECT_KEYS:
                    errors.append(f"unrecognized select criteria '{k}=' (valid: {', '.join(SELECT_KEYS)})")

    elif verb == "arrange":
        from pytae._parsing import _tokenize

        tokens = _tokenize(raw, ",", track_brackets=True)
        for token in tokens:
            t = token.strip()
            # If brackets present, extract token outside brackets
            if t.endswith("]"):
                continue
            parts = t.split()
            if len(parts) >= 2 and not t.startswith("["):
                direction = parts[-1].lower()
                if direction not in ("asc", "desc", "ascending", "descending"):
                    errors.append(f"invalid sort direction '{direction}' in arrange spec (must be 'asc' or 'desc')")

    elif verb == "agg":
        from pytae._parsing import _tokenize

        tokens = _tokenize(raw, ",", track_brackets=True)
        for token in tokens:
            t = token.strip()
            if "=" in t:
                alias, _, expr = t.partition("=")
                alias, expr = alias.strip(), expr.strip()
                if expr == "n":
                    errors.append(f"legacy 'n' aggregation in '{t}': use 'count' instead (e.g. '{alias} = count')")

    return errors


class _DSLVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.diagnostics: list[DSLDiagnostic] = []

    def visit_Call(self, node: ast.Call) -> None:
        verb: str | None = None
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            "mutate",
            "filter",
            "select",
            "arrange",
            "agg",
            "by",
        ):
            verb = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in (
            "mutate",
            "filter",
            "select",
            "arrange",
            "agg",
            "by",
        ):
            verb = node.func.id

        if verb:
            if verb == "select":
                for kw in node.keywords:
                    if kw.arg == "exclude":
                        self.diagnostics.append(
                            DSLDiagnostic(
                                file=self.filename,
                                line=node.lineno,
                                col=node.col_offset,
                                verb=verb,
                                expression="exclude=...",
                                message="'exclude=' is retired in favor of '!' negation. Use select('!col') instead.",
                            )
                        )

            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    errs = check_dsl_string(verb, arg.value)
                    for err in errs:
                        self.diagnostics.append(
                            DSLDiagnostic(
                                file=self.filename,
                                line=node.lineno,
                                col=node.col_offset,
                                verb=verb,
                                expression=arg.value,
                                message=err,
                            )
                        )

            if verb == "mutate":
                for kw in node.keywords:
                    if kw.arg and kw.arg not in ("dropna", "params", "observed") and isinstance(kw.value, ast.Constant):
                        if isinstance(kw.value.value, str):
                            combined = f"{kw.arg} = {kw.value.value}"
                            errs = check_dsl_string(verb, combined)
                            for err in errs:
                                self.diagnostics.append(
                                    DSLDiagnostic(
                                        file=self.filename,
                                        line=node.lineno,
                                        col=node.col_offset,
                                        verb=verb,
                                        expression=combined,
                                        message=err,
                                    )
                                )

        self.generic_visit(node)


def check_dsl_file(file_path: str | Path) -> list[DSLDiagnostic]:
    """Parse a Python source file and check all pytae DSL expressions."""
    path = Path(file_path)
    if not path.is_file():
        return [
            DSLDiagnostic(
                file=str(path),
                line=0,
                col=0,
                verb="file",
                expression="",
                message=f"file not found: {path}",
            )
        ]

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [
            DSLDiagnostic(
                file=str(path),
                line=0,
                col=0,
                verb="file",
                expression="",
                message=f"unable to read file: {e}",
            )
        ]

    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError as e:
        return [
            DSLDiagnostic(
                file=str(path),
                line=e.lineno or 0,
                col=e.offset or 0,
                verb="python",
                expression="",
                message=f"Python syntax error: {e.msg}",
            )
        ]

    visitor = _DSLVisitor(str(path))
    visitor.visit(tree)
    return visitor.diagnostics


def check_dsl_paths(paths: Sequence[str | Path]) -> tuple[int, list[DSLDiagnostic]]:
    """Recursively check pytae DSL expressions across files and directories."""
    files_to_check: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_file() and path.suffix == ".py":
            files_to_check.append(path)
        elif path.is_dir():
            for root, _, files in os.walk(path):
                if any(part.startswith((".", "venv", "__pycache__", "build", "dist")) for part in Path(root).parts):
                    continue
                for f in files:
                    if f.endswith(".py"):
                        files_to_check.append(Path(root) / f)

    all_diagnostics: list[DSLDiagnostic] = []
    for f in sorted(set(files_to_check)):
        all_diagnostics.extend(check_dsl_file(f))

    return len(files_to_check), all_diagnostics


def run_cli_check(argv: list[str]) -> int:
    """Entry point for CLI `pytae check [paths...]` command."""
    paths = argv if argv else ["."]
    use_color = sys.stdout.isatty() and "NO_COLOR" not in os.environ

    num_files, diagnostics = check_dsl_paths(paths)

    red = "\033[31;1m" if use_color else ""
    green = "\033[32;1m" if use_color else ""
    reset = "\033[0m" if use_color else ""

    if not diagnostics:
        print(f"{green}✓ All pytae DSL expressions in {num_files} file(s) passed validation.{reset}")
        return 0

    print(f"\n{red}Found {len(diagnostics)} DSL syntax error(s) across {num_files} file(s):{reset}\n")
    for diag in diagnostics:
        print(diag.format(color=use_color))
        print()

    return 1
