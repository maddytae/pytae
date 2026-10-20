"""Command line tool for inspecting tabular files (parquet/csv/txt/sas7bdat) and converting between formats."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from pytae.cli_parsing import (
    expand_paths,
    parse_concat_arg,
    parse_file_arg,
    parse_filter,
    parse_fraction,
    parse_head_limit,
    parse_join_arg,
    parse_list_order,
    parse_positive_int,
    parse_rename,
    parse_select_spec,
)
from pytae.cli_pipeline import (
    _OrderedAppend,
    _OrderedFlag,
    _OrderedStore,
    _OrderedValue,
)
from pytae.cli_run import (
    NON_DF_TERMINAL_OPS,
    _encoding_error_message,
    _fail,
    _process_path,
)
from pytae.readers import get_reader

try:
    __version__ = _pkg_version("pytae")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

_DATA_SUFFIXES = frozenset(
    (".parquet", ".pq", ".csv", ".txt", ".dat", ".sas7bdat", ".jsonl", ".ndjson", ".gz", ".yaml", ".yml")
)
_FORMAT_SHORTHANDS = frozenset(
    (
        "csv",
        "parquet",
        "pq",
        "txt",
        "dat",
        "jsonl",
        "ndjson",
        "csv.gz",
        "txt.gz",
        "dat.gz",
        "jsonl.gz",
        "ndjson.gz",
    )
)


def _is_path_like(token: str) -> bool:
    if token == "-":
        return True
    if token.startswith("-"):
        return False
    if any(ch in token for ch in "*?[]"):
        return True
    if "/" in token or "\\" in token:
        return True
    p = Path(token)
    if p.exists():
        return True
    if p.suffix.lower() in _DATA_SUFFIXES:
        return True
    return False


_CLI_FLAGS = {
    "-version",
    "--version",
    "-cheatsheet",
    "--cheatsheet",
    "-examples",
    "--examples",
    "-head",
    "--head",
    "-tail",
    "--tail",
    "-shape",
    "--shape",
    "-cols",
    "--cols",
    "-dtype",
    "--dtype",
    "-nulls",
    "--nulls",
    "-describe",
    "--describe",
    "-meta",
    "--meta",
    "-diff",
    "--diff",
    "-distinct",
    "--distinct",
    "-count",
    "--count",
    "-sample",
    "--sample",
    "-seed",
    "--seed",
    "-frac",
    "--frac",
    "-arrange",
    "--arrange",
    "-by",
    "--by",
    "-nrows",
    "--nrows",
    "-limit",
    "--limit",
    "-select",
    "--select",
    "-agg",
    "--agg",
    "-fillna",
    "--fillna",
    "-dropna",
    "--dropna",
    "-glimpse",
    "--glimpse",
    "-clean_columns",
    "--clean_columns",
    "-long",
    "--long",
    "-wide",
    "--wide",
    "-pivot",
    "--pivot",
    "-o",
    "--output",
    "-out_dir",
    "--out_dir",
    "-od",
    "--out-dir",
    "-dlim",
    "--dlim",
    "-encoding",
    "--encoding",
    "-rename",
    "--rename",
    "-file",
    "--file",
    "-filter",
    "--filter",
    "-mutate",
    "--mutate",
    "-sql",
    "--sql",
    "-join",
    "--join",
    "-concat",
    "--concat",
    "-progress",
    "--progress",
    "-time",
    "--time",
    "-pretty",
    "--pretty",
    "-pager",
    "--pager",
    "-round",
    "--round",
    "-tol",
    "--tol",
    "-tolerance",
    "--tolerance",
    "-h",
    "--help",
    "-fmt",
    "--fmt",
    "-freq",
    "--freq",
    "-hist",
    "--hist",
    "-bar",
    "--bar",
    "-scatter",
    "--scatter",
    "-corr",
    "--corr",
    "-plot",
    "--plot",
    "-finalize",
    "--finalize",
}


def _normalize_cli_args(argv: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-progress", "--progress"):
            if i + 1 < len(argv):
                nxt = argv[i + 1]
                try:
                    int(nxt)
                    out.append(arg)
                    out.append(nxt)
                    i += 2
                    continue
                except ValueError:
                    out.append("--progress=200000")
                    i += 1
                    continue
            else:
                out.append("--progress=200000")
                i += 1
                continue
        elif arg in ("-time", "--time"):
            if i + 1 < len(argv):
                nxt = argv[i + 1]
                try:
                    int(nxt)
                    out.append(arg)
                    out.append(nxt)
                    i += 2
                    continue
                except ValueError:
                    if nxt.startswith("-") or _is_path_like(nxt) or nxt == "clip":
                        out.append("--time=1")
                        i += 1
                        continue
                    out.append(arg)
                    out.append(nxt)
                    i += 2
                    continue
            else:
                out.append("--time=1")
                i += 1
                continue
        elif arg in ("-select", "--select") and "=" not in arg:
            if i + 1 < len(argv):
                nxt = argv[i + 1]
                if nxt.startswith("-") and nxt not in _CLI_FLAGS:
                    out.append(f"--select={nxt}")
                    i += 2
                    continue
        out.append(arg)
        i += 1
    return out


def _is_stdin_piped() -> bool:
    """Check if standard input is attached to a real pipe or redirected stream."""
    stdin = sys.stdin
    # If pytest is capturing stdin without input provided, DontReadFromInput is used
    if getattr(stdin, "__class__", None) and stdin.__class__.__module__.startswith("_pytest"):
        return False
    try:
        if stdin.isatty():
            return False
        fileno = getattr(stdin, "fileno", None)
        if fileno is not None:
            try:
                import os

                return not os.isatty(fileno())
            except Exception:
                pass
        return True
    except Exception:
        return False


class _CheatsheetAction(argparse.Action):
    """Custom action to print terminal cheatsheet and exit."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = argparse.SUPPRESS,
        default: Any = argparse.SUPPRESS,
        help: str | None = None,
    ) -> None:
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        from pytae.cheatsheet import CHEATSHEET_TEXT

        sys.stdout.write(CHEATSHEET_TEXT)
        parser.exit(0)


class PytaeParser(argparse.ArgumentParser):
    """Custom parser that normalizes optional-value flags such as -progress and negative -select specs."""

    def parse_known_args(  # type: ignore[override]
        self,
        args: Sequence[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> tuple[argparse.Namespace, list[str]]:
        if args is None:
            args = sys.argv[1:]
        normalized = _normalize_cli_args(list(args))
        return super().parse_known_args(normalized, namespace)


def build_parser() -> argparse.ArgumentParser:
    parser = PytaeParser(
        prog="pytae",
        description="Inspect and convert parquet/csv/txt/dat/sas7bdat files (glob patterns convert multiple files at once), or read a Databricks table / remote SSH file via a .yaml connection config.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "path",
        nargs="*",
        default=None,
        help="path to a .parquet, .csv, .txt, .dat, or .sas7bdat file, "
        "'clip' to read from system clipboard, "
        "a .yaml/.yml connection config (Databricks table or remote SSH file), "
        "or glob patterns/multiple files for batch operations; "
        "omit when piping from stdin or using -file with -join/-concat/-sql",
    )
    parser.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-cheatsheet",
        "--cheatsheet",
        "-examples",
        "--examples",
        action=_CheatsheetAction,
        help="print CLI quick-reference cheat sheet and cookbook recipes",
    )
    parser.add_argument(
        "-head",
        "--head",
        nargs="?",
        const=5,
        type=parse_head_limit,
        default=None,
        metavar="LIMIT",
        action=_OrderedValue,
        help="print the first N rows or proportion, group-aware with -by (default 5)",
    )
    parser.add_argument(
        "-tail",
        "--tail",
        nargs="?",
        const=5,
        type=parse_head_limit,
        default=None,
        metavar="LIMIT",
        action=_OrderedValue,
        help="print the last N rows or proportion, group-aware with -by (default 5)",
    )
    parser.add_argument("-shape", "--shape", action=_OrderedFlag, help="print (rows, cols)")
    parser.add_argument(
        "-cols",
        "--cols",
        nargs="?",
        const="file",
        default=None,
        metavar="ORDER",
        type=parse_list_order,
        action=_OrderedValue,
        help="print column names; optional asc|desc sorts names (default: file order)",
    )
    parser.add_argument(
        "-dtype",
        "--dtype",
        nargs="?",
        const="file",
        default=None,
        metavar="ORDER",
        type=parse_list_order,
        action=_OrderedValue,
        help="print column dtypes; optional asc|desc sorts by name (default: file order)",
    )
    parser.add_argument(
        "-nulls",
        "--nulls",
        nargs="?",
        const="file",
        default=None,
        metavar="ORDER",
        type=parse_list_order,
        action=_OrderedValue,
        help="print null/NaN count per column; optional asc|desc sorts by name (default: file order)",
    )
    parser.add_argument(
        "-describe",
        "--describe",
        dest="describe",
        action=_OrderedFlag,
        help="print pandas describe() summary (count/mean/std/min/quartiles/max)",
    )
    parser.add_argument(
        "-glimpse",
        "--glimpse",
        dest="glimpse",
        action=_OrderedFlag,
        help="print a transposed overview of DataFrame columns, dtypes, and sample values",
    )
    parser.add_argument(
        "-meta",
        "--meta",
        dest="meta",
        action=_OrderedFlag,
        help="display Parquet metadata (row groups, column statistics, compression, schema) without loading data",
    )
    parser.add_argument(
        "-diff",
        "--diff",
        dest="diff",
        default=None,
        metavar="PATH",
        action=_OrderedStore,
        help="compare schema and contents against another dataset file (use -tol or -tolerance to set a numeric threshold)",
    )
    parser.add_argument(
        "-freq",
        "--freq",
        dest="freq",
        action=_OrderedStore,
        default=None,
        metavar="COLUMN",
        help="render horizontal frequency bars with counts and percentages for a categorical column",
    )
    parser.add_argument(
        "-hist",
        "--hist",
        dest="hist",
        action=_OrderedStore,
        default=None,
        metavar="COLUMN[:BINS]",
        help="render an in-terminal distribution histogram for a numeric column (e.g. -hist mass or -hist mass:10)",
    )
    parser.add_argument(
        "-bar",
        "--bar",
        dest="bar",
        nargs="?",
        const="",
        default=None,
        metavar="SPEC",
        action=_OrderedValue,
        help="render in-terminal horizontal bars for metric values, "
        'e.g. -bar, -bar avg_mass, -bar "island:avg_mass", or -bar "avg_mass,limit=(0,5000),pct=true"',
    )
    parser.add_argument(
        "-scatter",
        "--scatter",
        dest="scatter",
        nargs="?",
        const="",
        default=None,
        metavar="SPEC",
        action=_OrderedValue,
        help="render an in-terminal 2D Braille scatter plot for two numeric columns, "
        'e.g. -scatter, -scatter "x:y", or -scatter "x:y,width=60,height=20"',
    )
    parser.add_argument(
        "-corr",
        "--corr",
        dest="corr",
        nargs="?",
        const="",
        default=None,
        metavar="SPEC",
        action=_OrderedValue,
        help="render pairwise correlation matrix or ranked pairs for numeric columns, "
        'e.g. -corr, -corr pairs, -corr "target=body_mass_g", or -corr "pairs,method=spearman"',
    )
    parser.add_argument(
        "-distinct",
        "--distinct",
        dest="distinct",
        nargs="?",
        const="",
        default=None,
        metavar="SPEC",
        action=_OrderedValue,
        help='drop duplicate rows, optionally restricted to specific columns and keep mode, e.g. -distinct, -distinct "col1,col2", or -distinct "keep=last"',
    )
    parser.add_argument(
        "-count",
        "--count",
        dest="count",
        nargs="?",
        const="",
        default=None,
        metavar="SPEC",
        action=_OrderedValue,
        help="count occurrences of unique combinations of columns (or rows per group if after -by), "
        'e.g. -count species, -count "species,island", or -count "species,sort=false,name=total"',
    )
    parser.add_argument(
        "-sample",
        "--sample",
        nargs="?",
        const=5,
        type=parse_positive_int,
        default=None,
        metavar="N",
        action=_OrderedValue,
        help="print N randomly sampled rows (default 5)",
    )
    parser.add_argument(
        "-seed",
        "--seed",
        dest="seed",
        type=int,
        default=None,
        metavar="N",
        help="random seed for -sample, for reproducible rows (default: random each run)",
    )
    parser.add_argument(
        "-frac",
        "--frac",
        dest="frac",
        type=parse_fraction,
        default=None,
        metavar="P",
        help="sample a fraction of rows instead of a count (0 < P <= 1, e.g. 0.1 for 10 percent); "
        "requires -sample and overrides its N",
    )
    parser.add_argument(
        "-arrange",
        "--arrange",
        dest="arrange",
        default=None,
        metavar="SPEC",
        action=_OrderedStore,
        help='sort rows by one or more columns with direction, e.g. -arrange "species,mass desc"',
    )
    parser.add_argument(
        "-by",
        "--by",
        dest="by",
        default=None,
        metavar="COLUMNS",
        help="grouping columns (comma-separated), e.g. -by species or -by 'species,island'. "
        "Used by -agg, -mutate, -head, -tail.",
    )
    parser.add_argument(
        "-nrows",
        "--nrows",
        "-limit",
        "--limit",
        dest="nrows",
        type=parse_positive_int,
        default=None,
        metavar="N",
        help="cap the number of rows loaded (default: no cap)",
    )
    parser.add_argument(
        "--select",
        "-select",
        dest="select",
        action=_OrderedAppend,
        default=None,
        metavar="SPEC",
        help="restrict columns at this point in the pipeline (union of tokens in one SPEC): "
        "names, start:end slices, !negated names/slices (!col, -col, ~col), and key=value (dtype, "
        "contains, startswith, endswith, regex, exclude_dtype); repeat to filter remaining columns, "
        'including after -agg/-long/-wide, e.g. -select "!species" or -select "contains=bill"',
    )
    parser.add_argument(
        "-agg",
        "--agg",
        dest="agg",
        nargs="?",
        const="sum",
        default=None,
        metavar="AGGFUNC",
        action=_OrderedValue,
        help="aggregate numeric columns using pytae agg; if -by is given, groups by those columns; "
        "without -by, computes a whole-table summary (grand total). "
        "Accepts a name (mean), a comma list (mean,sum,count), or column mappings "
        "(v1 = sum, total = v1:sum, n = count). Defaults to sum.",
    )
    parser.add_argument(
        "-fillna",
        "--fillna",
        dest="fillna",
        nargs="?",
        const=".",
        default=None,
        metavar="SPEC",
        action=_OrderedValue,
        help="fill missing values using pytae fillna(): scalar fill value (e.g. 0 or '.'), "
        "column mapping (e.g. 'a:0, b:N/A'), or 'val, col1, col2' (e.g. '0, a, b')",
    )
    parser.add_argument(
        "-dropna",
        "--dropna",
        dest="dropna",
        nargs="?",
        const="",
        default=None,
        metavar="COLS",
        action=_OrderedValue,
        help="drop rows containing missing values (bare -dropna drops completely empty rows; "
        '-dropna "col1,col2" drops rows where specified columns are missing; '
        "-dropna how=any drops rows where any column is missing)",
    )
    parser.add_argument(
        "-clean_columns",
        "--clean_columns",
        dest="clean_columns",
        action=_OrderedStore,
        metavar="KEY=VALUE,...",
        help="clean column header names, in order strip -> strip_special -> squeeze -> "
        "fill -> case -> dedupe: strip/squeeze/strip_special/dedupe are bools (bare "
        'key means true, e.g. "strip"), fill[=STR] replaces whitespace in a header '
        "(bare \"fill\" defaults to '_', omit entirely for no fill), "
        "case=lower|upper|proper (always needs a value); e.g. "
        '"strip,fill,case=lower" or "fill=\'$\',case=proper,dedupe=true"',
    )
    parser.add_argument(
        "-long",
        "--long",
        dest="long",
        nargs="?",
        const="",
        default=None,
        metavar="KEY=VALUE,...",
        action=_OrderedValue,
        help="melt numeric columns to long form (pytae long()); defaults c=variable, v=value; e.g. c=metric,v=reading",
    )
    parser.add_argument(
        "-wide",
        "--wide",
        dest="wide",
        nargs="?",
        const="",
        default=None,
        metavar="KEY=VALUE,...",
        action=_OrderedValue,
        help="pivot long form to wide for 1-to-1 reshaping (pytae wide()); defaults c=variable, v=value; "
        "for aggregation or 2D contingency tables, use -pivot",
    )
    parser.add_argument(
        "-pivot",
        "--pivot",
        dest="pivot",
        nargs="?",
        const="",
        default=None,
        metavar="KEY=VALUE,...",
        action=_OrderedValue,
        help="2-D pivot table (pytae pivot()); r=row_cols (optional), c=col_cols "
        "(optional), v=value_cols (optional; defaults to counts), a=aggfunc (default sum; n=size), "
        'dropna=false (default), f_v=val; e.g. -pivot "r=Region,c=Year,v=Sales,a=sum"',
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        default=None,
        metavar="TARGET",
        help="output destination: a file path (e.g. 'out.csv', 'out.parquet'), "
        "a format for in-place or batch conversion ('csv', 'parquet', 'txt', 'dat', 'jsonl', 'csv.gz', 'jsonl.gz'), "
        "or 'clip'/'clipboard' to copy to system clipboard",
    )
    parser.add_argument(
        "-out_dir",
        "--out_dir",
        "-od",
        "--out-dir",
        dest="out_dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="target directory for exported files (created if it does not exist); requires -o/--output",
    )
    parser.add_argument(
        "-fmt",
        "--fmt",
        dest="fmt",
        default=None,
        metavar="FORMAT",
        help="input format when reading from STDIN or extensionless files: csv, parquet, jsonl, txt, tsv",
    )
    parser.add_argument(
        "-dlim",
        "--dlim",
        dest="dlim",
        default=None,
        metavar="CHAR",
        help="field delimiter for reading/writing .csv/.txt/.dat (default: ',' for .csv, "
        "tab for .txt, '|' for .dat); not used for .parquet or .sas7bdat",
    )
    parser.add_argument(
        "-encoding",
        "--encoding",
        dest="encoding",
        default=None,
        metavar="ENC",
        help="text encoding for .csv/.txt/.dat/.sas7bdat, e.g. latin-1 "
        "(default: latin-1 for .sas7bdat and .dat, pandas infer for .csv/.txt); "
        "not used for .parquet",
    )
    parser.add_argument(
        "-rename",
        "--rename",
        dest="rename",
        action=_OrderedAppend,
        default=None,
        metavar="OLD:NEW,...",
        help='rename columns at this point in the pipeline (or during conversion), e.g. "old_a:new_a,old_b:new_b"',
    )
    parser.add_argument(
        "-file",
        "--file",
        dest="file",
        default=None,
        metavar="PATH=ALIAS;...",
        help="load multiple named files for -join/-concat/-sql, instead of the positional path; "
        "';'-separated entries, each PATH=ALIAS optionally followed by "
        ",dlim=/,encoding= overrides for that file, e.g. "
        "\"data1.parquet=df1; data2.parquet=df2,encoding='latin-1'\"; "
        "requires -join, -concat, or -sql as the first operation, and can't be "
        "combined with the positional path",
    )
    parser.add_argument(
        "-filter",
        "--filter",
        dest="filter",
        action=_OrderedAppend,
        default=None,
        metavar="CONDITIONS",
        help="filter rows at this point in the pipeline using pytae filter(); conditions like \"col = 'val', col > 5\"",
    )
    parser.add_argument(
        "-mutate",
        "--mutate",
        dest="mutate",
        action=_OrderedAppend,
        default=None,
        metavar="SPEC",
        help="create/overwrite columns at this point in the pipeline using pytae mutate(); "
        '"new_col = expression" or multi-column "(col1, col2) = _ * 2" entries, comma-separated; '
        "the expression is pandas eval() syntax and column names in it must stay unquoted, e.g. "
        '"bmi = body_mass_g / bill_length_mm ** 2" or "(startswith=bill_) = _ / 10"',
    )
    parser.add_argument(
        "-sql",
        "--sql",
        dest="sql",
        action=_OrderedAppend,
        default=None,
        metavar="QUERY",
        help="run a SQL query (via Polars SQLContext) against the current view at this point in "
        "the pipeline; the view is queryable as table `data`; standard SQL identifier "
        'quoting applies (double quotes for names with spaces, e.g. "col a"; single '
        "quotes are string literals, not identifiers), e.g. "
        '"select \\"col a\\" from data where \\"col a\\" > 10"; '
        "in -file/-join mode, may be used instead of -join as the first op, with "
        'every -file alias queryable by its own name (e.g. "select * from df1 '
        'inner join df2 on df1.\\"col a\\" = df2.cola") — `data` becomes queryable '
        "too once something later in the pipeline has produced a current view",
    )
    parser.add_argument(
        "-join",
        "--join",
        dest="join",
        action=_OrderedAppend,
        default=None,
        metavar="KEY=VALUE,...",
        help="join two frames into the pipeline (Polars join()); repeatable, to fold in "
        "one more file at a time; must be the first op when using -file (unless -sql/"
        "-concat starts it instead); key=value tokens: left=/right= (required — -file "
        "aliases, or 'data' for the pipeline's current result so far), "
        "on= (required; shared column name(s), or 'left:right' pairs if they "
        "differ between sides — quote on= if it has more than one column/pair, e.g. "
        "\"on='col a:cola,colb:colb'\"), how= (optional, default 'inner': "
        "inner/left/right/full/semi/anti/cross), validate= (optional, e.g. 1:1, 1:m)",
    )
    parser.add_argument(
        "-concat",
        "--concat",
        dest="concat",
        action=_OrderedAppend,
        default=None,
        metavar="KEY=VALUE,...",
        help="stack frames row-wise into the pipeline (Polars concat()); repeatable; must be the first op when using -file "
        "(unless -sql/-join starts it instead); key=value tokens: frames= (required) "
        "an ordered comma-separated list of -file aliases (or 'data' for the pipeline's "
        "current result so far), quoted since it has internal commas, e.g. "
        "\"frames='df1,df2,df3'\"",
    )
    parser.add_argument(
        "-plot",
        "--plot",
        dest="plot",
        action=_OrderedStore,
        default=None,
        metavar="SPEC",
        help='render visualization using pytae Plotter; e.g. -plot "kind=scatter, x=col1, y=col2"',
    )
    parser.add_argument(
        "-finalize",
        "--finalize",
        dest="finalize",
        default=None,
        metavar="SPEC",
        help='layout/legend options for -plot, e.g. -finalize "consolidate_legends=True, style=True"',
    )
    parser.add_argument(
        "-progress",
        "--progress",
        nargs="?",
        const=200_000,
        type=parse_positive_int,
        default=None,
        metavar="N",
        help="show row-count progress while converting large files (default: 200000 rows per chunk; optional N sets chunk size)",
    )
    parser.add_argument(
        "-time",
        "--time",
        dest="time",
        nargs="?",
        const=1,
        type=parse_positive_int,
        default=None,
        metavar="N",
        help="measure and print pipeline execution time (default: 1 run; optional N runs the pipeline N times and reports avg/min/max/total)",
    )
    parser.add_argument(
        "-pretty",
        "--pretty",
        action="store_true",
        help="[deprecated] table formatting is now automatically detected (boxed table for terminal, bare unbordered for pipes)",
    )
    parser.add_argument(
        "-pager",
        "--pager",
        action="store_true",
        help="pipe long table or inspect outputs through system pager ($PAGER or less)",
    )
    parser.add_argument(
        "-round",
        "--round",
        dest="round_ndigits",
        type=int,
        default=None,
        metavar="N",
        help="round numeric columns to N decimal places before printing/copying; "
        "non-numeric columns are left unchanged",
    )
    parser.add_argument(
        "-tol",
        "--tol",
        "-tolerance",
        "--tolerance",
        dest="tol",
        type=float,
        default=None,
        metavar="N",
        help="numeric difference tolerance / threshold for dataset comparison (-diff); "
        "e.g. -tol 0.001 or -tolerance 1e-4",
    )
    return parser


def _format_duration_ms(secs: float) -> str:
    ms = secs * 1000.0
    if secs >= 1.0:
        return f"{ms:.2f} ms ({secs:.3f} s)"
    return f"{ms:.2f} ms"


def _format_timing_summary(durations: list[float]) -> str:
    n = len(durations)
    if n <= 1:
        d = durations[0] if durations else 0.0
        return f"Elapsed (1 run): {_format_duration_ms(d)}"
    total = sum(durations)
    avg = total / n
    mn = min(durations)
    mx = max(durations)
    return (
        f"Elapsed ({n} runs): avg {_format_duration_ms(avg)} | "
        f"min {_format_duration_ms(mn)} | "
        f"max {_format_duration_ms(mx)} | "
        f"total {_format_duration_ms(total)}"
    )


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else list(argv)

    # Check for static DSL syntax check subcommand: `pytae check [paths...]` or `pytae -check [paths...]`
    if raw_argv and raw_argv[0] in ("check", "-check", "--check"):
        from pytae.validation import run_cli_check

        return run_cli_check(raw_argv[1:])

    # Check for keyword-specific help: `pytae -help <keyword>` or `pytae -h <keyword>`
    if len(raw_argv) >= 2 and raw_argv[0] in ("-h", "--help", "-help") and not raw_argv[1].startswith("-"):
        from pytae.cli_help import get_keyword_help

        topic = raw_argv[1]
        msg = get_keyword_help(topic)
        print(msg)
        return 0

    parser = build_parser()

    retired_redirects = [
        (("-query", "--query", "-qry", "--qry"), "'-qry' has been removed; use '-filter' instead"),
        (("-unique", "--unique"), "'-unique' has been removed; use '-distinct' instead"),
        (("-dedupe", "--dedupe"), "'-dedupe' has been removed; use '-distinct' instead"),
        (("-sort_by", "--sort_by", "-sort", "--sort"), "'-sort_by' has been deprecated; use '-arrange' instead"),
        (("-agg_df", "--agg_df"), "'-agg_df' has been removed; use '-agg' instead"),
        (("-to_clip", "--to_clip"), "'-to_clip' has been removed; use '-o clip' or '-o clipboard' instead"),
        (("-convert", "--convert"), "'-convert' has been removed; use '-o <filename>' or '-o <format>' instead"),
        (("-slice_max", "--slice_max"), "'-slice_max' has been removed; use '-arrange ... -head N' instead"),
        (
            ("-slice_min", "--slice_min"),
            "'-slice_min' has been removed; use '-arrange ... -tail N' (or '-arrange ... desc -head N') instead",
        ),
        (
            ("-pick", "--pick"),
            "'-pick' has been removed; use '-arrange ... -head N' (or '-by ... -arrange ... -head N') instead",
        ),
        (("-group_by", "--group_by", "-groupby", "--groupby"), "'-group_by' has been removed; use '-by' instead"),
        (("-handle_missing", "--handle_missing"), "'-handle_missing' has been removed; use '-fillna' instead"),
        (("-fill_null", "--fill_null"), "'-fill_null' has been removed; use '-fillna' instead"),
        (("-fill_nan", "--fill_nan"), "'-fill_nan' has been removed; use '-fillna' instead"),
        (("-drop_nulls", "--drop_nulls"), "'-drop_nulls' has been removed; use '-dropna' instead"),
        (("-drop_na", "--drop_na"), "'-drop_na' has been removed; use '-dropna' instead"),
        (("-value_counts", "--value_counts"), "'-value_counts' has been removed; use '-freq' instead"),
        (("-info", "--info"), "'-info' has been removed; use '-glimpse' instead"),
        (
            ("-replace_values", "--replace_values"),
            "'-replace_values' has been removed; use '-mutate' with map() or .str.replace() instead",
        ),
    ]
    for aliases, msg in retired_redirects:
        if any(arg in aliases for arg in raw_argv):
            parser.error(msg)

    args, extras = parser.parse_known_args(argv)
    if extras:
        if args.file is None:
            path_extras = [e for e in extras if _is_path_like(e)]
            if path_extras:
                if args.path is None:
                    args.path = []
                elif not isinstance(args.path, list):
                    args.path = [args.path]
                args.path.extend(path_extras)
                extras = [e for e in extras if not _is_path_like(e)]

        if extras:
            msg = f"unrecognized arguments: {' '.join(extras)}"
            if extras and all(not e.startswith("-") for e in extras):
                # likely an unquoted value with a space (e.g. a column name) split by the
                # shell into separate argv tokens -- the whole spec needs one pair of quotes
                msg += (
                    "\nIf this is part of a value with a space (e.g. a column name), wrap the "
                    'whole spec in quotes, e.g. -select "col a,col b" -- see docs/detailed_docs/cli/select.md.'
                )
            parser.error(msg)

    has_progress = args.progress is not None
    chunk_size = args.progress or 200_000
    args.progress = has_progress
    args.chunk_size = chunk_size

    op_order = getattr(args, "op_order", [])
    last_idx = len(op_order) - 1
    for idx, op in enumerate(op_order):
        if op in NON_DF_TERMINAL_OPS and idx != last_idx:
            parser.error(
                f"-{op} does not return a DataFrame/Series, so no flag may follow it "
                f"(except '-o clip'; matches pandas: you can't chain another call off "
                f"df.shape/df.columns/df.dtypes/df.glimpse())"
            )

    out_target = str(args.output).strip() if args.output is not None else None
    args.output = out_target
    is_clip = out_target is not None and out_target.lower() in ("clip", "clipboard")
    is_file = out_target is not None and not is_clip

    if args.out_dir is not None:
        if args.output is None:
            parser.error("-out_dir requires -o/--output")
        if is_clip:
            parser.error("-out_dir cannot be used with '-o clip'")
        args.out_dir.mkdir(parents=True, exist_ok=True)

    if is_file and any(op in NON_DF_TERMINAL_OPS for op in op_order):
        bad_op = next(op for op in op_order if op in NON_DF_TERMINAL_OPS)
        parser.error(
            f"-{bad_op} does not produce a tabular DataFrame, so it cannot be exported to a file; "
            f"use '-o clip' or view in terminal"
        )

    raw_paths = args.path if isinstance(args.path, list) else ([args.path] if args.path else [])

    if args.meta and args.file is not None:
        parser.error("-meta cannot be used with -file")
    if args.join and args.file is None:
        parser.error("-join requires -file")
    if args.concat and args.file is None:
        parser.error("-concat requires -file")
    if args.file is not None:
        if raw_paths:
            parser.error("-file/-join can't be combined with a positional path; list every input via -file instead")
        if not op_order or op_order[0] not in ("join", "sql", "concat"):
            parser.error("-file requires -join, -concat, or -sql as its first operation")
        if is_file and out_target is not None and out_target.lower() in _FORMAT_SHORTHANDS:
            parser.error(f"-o {out_target}: in -file/-join mode, an explicit output file path is required")
    elif not raw_paths:
        if _is_stdin_piped():
            raw_paths = ["-"]
            args.path = ["-"]
        else:
            parser.error("the following arguments are required: path")

    show_all = not any(
        [
            args.shape,
            args.cols,
            args.dtype,
            args.nulls,
            args.describe,
            args.glimpse,
            args.distinct is not None,
            args.count is not None,
            args.freq is not None,
            args.hist is not None,
            args.bar is not None,
            args.scatter is not None,
            args.corr is not None,
            args.head is not None,
            args.tail is not None,
            args.sample is not None,
            args.arrange is not None,
            args.agg is not None,
            args.fillna is not None,
            args.dropna is not None,
            args.long is not None,
            args.wide is not None,
            args.pivot is not None,
            args.select,
            args.filter,
            args.mutate,
            args.sql,
            args.rename,
            args.clean_columns is not None,
            args.join,
            args.concat,
            args.meta,
            args.diff is not None,
            args.plot is not None,
        ]
    )

    wants_df = any(
        [
            args.cols,
            args.dtype,
            args.nulls,
            args.describe,
            show_all,
            args.distinct is not None,
            args.count is not None,
            args.freq is not None,
            args.hist is not None,
            args.bar is not None,
            args.corr is not None,
            args.head is not None,
            args.tail is not None,
            args.sample is not None,
            args.arrange is not None,
            args.agg is not None,
            args.fillna is not None,
            args.dropna is not None,
            args.long is not None,
            args.wide is not None,
            args.pivot is not None,
            args.clean_columns is not None,
            args.join,
            args.concat,
            args.plot is not None,
        ]
    )
    if is_clip and args.shape and wants_df:
        parser.error(
            "-o clip can't combine -shape (not a DataFrame/Series) with a DataFrame-producing flag "
            "like -head/-tail/-cols/-dtype/-nulls/-describe/-distinct/-count/-sample/-arrange/"
            "-agg/-fillna/-long/-wide/-pivot/-clean_columns/-join/-concat/-freq/-hist/-bar/-corr/-plot; "
            "run -shape separately"
        )
    if (
        args.by is not None
        and args.agg is None
        and not args.mutate
        and args.head is None
        and args.tail is None
        and args.count is None
    ):
        parser.error("-by requires -agg, -mutate, -head, -tail, or -count")
    if args.frac is not None and args.sample is None:
        parser.error("-frac requires -sample")
    if args.tol is not None and args.diff is None:
        parser.error("-tol requires -diff")

    rename_specs = [parse_rename(raw) for raw in (args.rename or [])]
    select_specs = [parse_select_spec(raw) for raw in (args.select or [])]
    filter_specs = [parse_filter(raw) for raw in (args.filter or [])]
    mutate_specs = list(args.mutate or [])
    sql_specs = list(args.sql or [])
    join_specs = [parse_join_arg(raw) for raw in (args.join or [])]
    concat_specs = [parse_concat_arg(raw) for raw in (args.concat or [])]

    paths: list[Path] = []
    batch = False
    if args.file is None:
        if not raw_paths:
            parser.error("the following arguments are required: path")
        paths = expand_paths(raw_paths)
        batch = len(paths) > 1

        if batch and args.output is not None:
            if is_clip:
                parser.error("-o clip cannot be used with multiple matched files")
            if out_target is not None and out_target.lower() not in _FORMAT_SHORTHANDS:
                parser.error(
                    "-o/--output with multiple matched files requires a format (e.g. '-o csv' or '-o parquet'), "
                    "not a single file path"
                )
            assert out_target is not None
            fmt = out_target.lower()
            ext = ".parquet" if fmt == "pq" else f".{fmt}"
            dest_map: dict[Path, Path] = {}
            for p in paths:
                clean_name = p.name[:-3] if p.name.lower().endswith(".gz") else p.name
                dest_name = f"{Path(clean_name).stem}{ext}"
                dest = (
                    (args.out_dir / dest_name).resolve()
                    if args.out_dir is not None
                    else p.with_name(dest_name).resolve()
                )
                if dest in dest_map:
                    parser.error(
                        f"-o {out_target}: multiple input files resolve to the same destination path '{dest}': "
                        f"'{dest_map[dest]}' and '{p}'"
                    )
                dest_map[dest] = p

    def _execute_once() -> int:
        if args.file is not None:
            frames: dict[str, Any] = {}
            for entry in parse_file_arg(args.file):
                entry_path = Path(entry["path"])
                if not entry_path.exists():
                    parser.error(f"-file: file not found: {entry_path}")
                try:
                    reader = get_reader(
                        entry_path, sep=entry["dlim"], encoding=entry["encoding"], chunk_size=args.chunk_size or 200_000
                    )
                except ValueError as exc:
                    parser.error(f"-file: {exc}")
                try:
                    if args.progress:
                        frames[entry["alias"]] = reader.to_dataframe(
                            nrows=args.nrows, progress=args.progress, chunk_size=args.chunk_size or 200_000
                        )
                    else:
                        frames[entry["alias"]] = reader.to_polars(nrows=args.nrows)
                except UnicodeError as exc:
                    parser.error(_encoding_error_message(entry_path, entry["encoding"], exc))
                except Exception as exc:
                    if "utf-8" in str(exc).lower():
                        parser.error(
                            _encoding_error_message(
                                entry_path, entry["encoding"], UnicodeDecodeError("utf-8", b"", 0, 1, str(exc))
                            )
                        )
                    parser.error(f"-file: {exc}")
            failed = _process_path(
                None,
                args,
                parser,
                False,
                show_all=show_all,
                select_specs=select_specs,
                filter_specs=filter_specs,
                mutate_specs=mutate_specs,
                sql_specs=sql_specs,
                rename_specs=rename_specs,
                frames=frames,
                join_specs=join_specs,
                concat_specs=concat_specs,
            )
            return 1 if failed else 0

        code = 0
        for path in paths:
            if batch:
                print(f"== {path} ==")
            try:
                failed = _process_path(
                    path,
                    args,
                    parser,
                    batch,
                    show_all=show_all,
                    select_specs=select_specs,
                    filter_specs=filter_specs,
                    mutate_specs=mutate_specs,
                    sql_specs=sql_specs,
                    rename_specs=rename_specs,
                )
            except UnicodeError as exc:
                failed = _fail(parser, batch, _encoding_error_message(path, args.encoding, exc))
            if failed:
                code = 1
        return code

    if args.time is None:
        return _execute_once()

    import contextlib
    import io as _io
    import time as _time

    runs = args.time
    durations: list[float] = []
    exit_code = 0
    for run_idx in range(runs):
        t0 = _time.perf_counter()
        if run_idx == 0:
            exit_code = _execute_once()
        else:
            with contextlib.redirect_stdout(_io.StringIO()):
                exit_code = _execute_once()
        durations.append(_time.perf_counter() - t0)
        if exit_code != 0:
            break
    if exit_code == 0:
        print(_format_timing_summary(durations))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
