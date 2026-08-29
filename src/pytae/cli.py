"""Command line tool for inspecting tabular files (parquet/csv/txt/sas7bdat) and converting between formats."""

from __future__ import annotations

import argparse
import ast
import difflib
import glob
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

import pandas as pd

from pytae.agg_df import agg_df  # noqa: F401  — registers pd.DataFrame.agg_df
from pytae.other_utilities import group_x, handle_missing  # noqa: F401
from pytae.qry import qry  # noqa: F401
from pytae.readers import get_reader, write_dataframe
from pytae.select import select  # noqa: F401

try:
    __version__ = _pkg_version("pytae")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


def _apply_round(df: pd.DataFrame, ndigits: int | None) -> pd.DataFrame:
    """Round numeric columns to ndigits; non-numeric columns pass through unchanged."""
    return df.round(ndigits) if ndigits is not None else df


def _format_table(df: pd.DataFrame, *, index: bool = False, pretty: bool = False) -> str:
    """Render a DataFrame as standard pandas text, or a markdown/bordered table when pretty=True."""
    if not pretty:
        return df.to_string(index=index)
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return df.to_string(index=index)


def _copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard via pbcopy/clip/xclip; warns on stderr if none is available."""
    if sys.platform == "darwin":
        cmd = ["pbcopy"]
    elif sys.platform == "win32":
        cmd = ["clip"]
    else:
        cmd = ["xclip", "-selection", "clipboard"]
    try:
        subprocess.run(cmd, input=text.encode(), check=True)
    except (OSError, subprocess.CalledProcessError):
        print("pytae: unable to copy to clipboard (no clipboard utility found)", file=sys.stderr)


SELECT_KEYS = ("dtype", "exclude_dtype", "contains", "startswith", "endswith", "regex")


def parse_columns(raw: str) -> list[str]:
    """Parse a column list like "'col a','col b'" or "col_a,col_b" into a list of names."""
    raw = raw.strip()
    try:
        parsed = ast.literal_eval(f"[{raw}]")
        cols = list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
        return [str(c).strip() for c in cols]
    except (ValueError, SyntaxError):
        return [c.strip().strip("'\"") for c in raw.split(",") if c.strip()]


def _split_select_tokens(raw: str) -> list[str]:
    """Split a -select spec on commas, respecting single or double quotes."""
    tokens: list[str] = []
    buf: list[str] = []
    quote = None
    for ch in raw:
        if quote:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in "'\"":
            quote = ch
        elif ch == ",":
            token = "".join(buf).strip()
            if token:
                tokens.append(token)
            buf = []
        else:
            buf.append(ch)
    token = "".join(buf).strip()
    if token:
        tokens.append(token)
    return tokens


def parse_select_spec(raw: str) -> tuple[list[str], dict]:
    """Parse -select into positional names/slices and select() kwargs.

    Tokens without '=' are column names or start:end slices. Tokens like
    dtype=numeric / contains=bill / regex=^flip become kwargs. Repeated keys
    become a list. Union of all tokens, matching df.select().
    """
    tokens = _split_select_tokens(raw)
    names: list[str] = []
    kwargs: dict = {}
    for token in tokens:
        if "=" in token:
            key, _, value = token.partition("=")
            key = key.strip()
            value = value.strip()
            if key in SELECT_KEYS:
                if not value:
                    raise SystemExit(f"-select: {key}= needs a value")
                if key in kwargs:
                    prev = kwargs[key]
                    kwargs[key] = (prev if isinstance(prev, list) else [prev]) + [value]
                else:
                    kwargs[key] = value
                continue
        names.append(token)
    if not names and not kwargs:
        raise SystemExit("-select: expected column names and/or key=value tokens")
    if "exclude_dtype" in kwargs and (names or len(kwargs) > 1):
        raise SystemExit("-select: exclude_dtype cannot be combined with other selection criteria")
    return names, kwargs


def _select_unknown_names(tokens: list[str], available: list[str]) -> list[str]:
    """Exact-name tokens (and slice endpoints) that are not in the file."""
    unknown: list[str] = []
    for token in tokens:
        if ":" in token:
            start, end = token.split(":", 1)
            start, end = start.strip(), end.strip()
            if start and start not in available:
                unknown.append(start)
            if end and end not in available:
                unknown.append(end)
        elif token not in available:
            unknown.append(token)
    return unknown


def unknown_columns_message(flag: str, requested: list[str], available: list[str]) -> str:
    """Build an 'unknown column(s)' error message, suggesting a close match for likely typos."""
    unknown = [c for c in requested if c not in available]
    parts = []
    for c in unknown:
        close = difflib.get_close_matches(c, available, n=1)
        parts.append(f"'{c}'" + (f" (did you mean '{close[0]}'?)" if close else ""))
    return f"{flag}: unknown column(s): {', '.join(parts)}"


def parse_rename(raw: str) -> dict[str, str]:
    """Parse a rename mapping like "old_a:new_a,old_b:new_b" into a dict."""
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise SystemExit(f"invalid --rename mapping '{pair}'; expected old:new")
        old, new = pair.split(":", 1)
        mapping[old.strip()] = new.strip()
    return mapping


def expand_paths(pattern: str) -> list[Path]:
    """Expand a glob pattern (e.g. "data/*.parquet") into matching paths, or wrap a plain path as-is."""
    if any(ch in pattern for ch in "*?["):
        matches = sorted(Path(p) for p in glob.glob(pattern))
        if not matches:
            raise SystemExit(f"no files matched pattern: {pattern}")
        return matches
    return [Path(pattern)]


def parse_qry(raw: str) -> dict:
    """Parse a --qry dict literal like "{'col': ('>', 5), 'other': ['a','b']}"."""
    try:
        conditions = ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f"invalid --qry conditions: {exc}") from exc
    if not isinstance(conditions, dict):
        raise SystemExit("--qry expects a dict literal, e.g. \"{'col': ('>', 5)}\"")
    return conditions


def parse_agg(raw: str):
    """Parse an --agg_df aggfunc value: bare string ('sum'), list literal, or dict literal."""
    raw = raw.strip()
    if not (raw.startswith(("{", "[", "'", '"'))):
        return raw
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f"invalid --agg_df value: {exc}") from exc


def parse_group_agg(raw: str) -> dict:
    """Parse an --agg (explicit) dict literal, e.g. "{'col':'sum'}" or "{'col':('out_name','sum')}"."""
    try:
        spec = ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f"invalid --agg value: {exc}") from exc
    if not isinstance(spec, dict):
        raise SystemExit("--agg expects a dict literal, e.g. \"{'col': 'sum'}\" or \"{'col': ('out_name', 'sum')}\"")
    return spec


def parse_group_x_arg(raw: str) -> tuple[str, str | None]:
    """Parse a --group_x value like "n" or "mean:body_mass_g" into (aggfunc, value_col)."""
    raw = raw.strip()
    if ":" in raw:
        aggfunc, value_col = raw.split(":", 1)
        return aggfunc.strip(), value_col.strip()
    return raw, None


def parse_bool_text(raw: str) -> bool:
    """Parse a required true/false text flag value into bool."""
    lowered = raw.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise argparse.ArgumentTypeError("expected 'true' or 'false'")


def parse_list_order(raw: str) -> str:
    """Parse optional listing order for -cols/-dtype/-nulls: asc or desc.

    'file' is the internal sentinel used when the flag is present with no value
    (argparse 3.14 type-converts const).
    """
    lowered = str(raw).strip().lower()
    if lowered in ("asc", "desc", "file"):
        return lowered
    raise argparse.ArgumentTypeError("expected 'asc' or 'desc'")


def _list_order_names(names, order):
    if order == "asc":
        return sorted(names)
    if order == "desc":
        return sorted(names, reverse=True)
    return list(names)


def _list_order_index(series: pd.Series, order) -> pd.Series:
    if order == "asc":
        return series.sort_index(ascending=True)
    if order == "desc":
        return series.sort_index(ascending=False)
    return series


def _apply_query(df: pd.DataFrame, query: str | None) -> pd.DataFrame:
    if not query:
        return df
    try:
        return df.query(query)
    except Exception as exc:
        raise SystemExit(f"invalid --query expression: {exc}") from exc


def _fail(parser: argparse.ArgumentParser, batch: bool, msg: str) -> bool:
    """Abort immediately outside batch mode; in batch mode, warn on stderr and signal failure instead."""
    if not batch:
        parser.error(msg)
    print(f"pytae: {msg}", file=sys.stderr)
    return True


def cmd_convert(
    df: pd.DataFrame,
    source: Path,
    output: Path | None,
    *,
    rename: dict[str, str] | None = None,
    sep: str | None = None,
    encoding: str | None = None,
    progress: bool = False,
) -> None:
    if rename:
        df = df.rename(columns=rename)
    dest = output if output is not None else source.with_suffix(".csv")
    if dest.resolve() == source.resolve():
        raise SystemExit(f"refusing to overwrite the source file '{source}'; pass -o/--output to choose a different path")
    try:
        write_dataframe(df, dest, sep=sep, encoding=encoding, progress=progress)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Wrote {len(df)} rows to {dest}")


class _Pipeline:
    """-select/-query/-qry define the starting view. -head/-tail/-sample narrow
    it further, and every operator that runs afterwards (including another
    -head/-tail/-sample, -stats, -nulls, -cols, -dtype, -shape, -convert, -agg_df, -agg) sees
    that narrowed view. Schema-only ops (-cols/-dtype/-shape) avoid loading
    row data until something actually requires it.
    """

    def __init__(self, reader, *, select, select_kwargs, query, qry, nrows, progress) -> None:
        self._reader = reader
        self._select = select            # list[str] | None — positional names/slices
        self._select_kwargs = select_kwargs  # pytae select() kwargs: dtype, contains, etc.
        self._query = query
        self._qry = qry
        self._nrows = nrows
        self._progress = progress
        self._df: pd.DataFrame | None = None

    def _needs_full_load(self) -> bool:
        if self._query or self._qry or self._select_kwargs:
            return True
        if self._select and any(":" in token for token in self._select):
            return True
        return False

    def dataframe(self) -> pd.DataFrame:
        if self._df is None:
            # load all columns when filters may reference columns outside the select list
            read_cols = self._select if not self._needs_full_load() else None
            df = self._reader.to_dataframe(columns=read_cols, nrows=self._nrows, progress=self._progress)
            df = _apply_query(df, self._query)
            if self._qry:
                df = df.qry(self._qry)
            if self._select is not None or self._select_kwargs:
                try:
                    df = df.select(*(self._select or []), **self._select_kwargs)
                except ValueError as exc:
                    raise SystemExit(f"-select: {exc}") from exc
            self._df = df
        return self._df

    def columns(self) -> list[str]:
        if self._df is not None:
            return list(self._df.columns)
        if self._needs_full_load():
            return list(self.dataframe().columns)
        return list(self._select) if self._select else self._reader.columns()

    def dtypes(self) -> pd.Series:
        if self._df is not None:
            return self._df.dtypes
        if self._needs_full_load():
            return self.dataframe().dtypes
        dtypes = self._reader.dtypes()
        return dtypes[self._select] if self._select else dtypes

    def shape(self) -> tuple[int, int]:
        if self._df is not None:
            return self._df.shape
        if self._needs_full_load():
            return self.dataframe().shape
        rows = self._reader.shape()[0]
        cols = len(self._select) if self._select else self._reader.shape()[1]
        return (rows, cols)

    def head(self, n: int) -> pd.DataFrame:
        if self._df is None and not self._needs_full_load():
            df = self._reader.head(n)
            if self._select:
                df = df.select(*self._select)
        else:
            df = self.dataframe().head(n)
        self._df = df
        return df

    def tail(self, n: int) -> pd.DataFrame:
        if self._df is None and not self._needs_full_load():
            df = self._reader.tail(n)
            if self._select:
                df = df.select(*self._select)
        else:
            df = self.dataframe().tail(n)
        self._df = df
        return df

    def sample(self, n: int) -> pd.DataFrame:
        df = self.dataframe()
        n = min(n, len(df))
        sampled = df.sample(n=n) if n else df.iloc[0:0]
        self._df = sampled
        return sampled


class _OrderedFlag(argparse.Action):
    """Boolean flag (like store_true) that also records its dest in namespace.op_order, in CLI order."""

    def __init__(self, option_strings, dest, **kwargs) -> None:
        super().__init__(option_strings, dest, nargs=0, default=False, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, True)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]


class _OrderedValue(argparse.Action):
    """Optional-value flag (nargs='?') that also records its dest in namespace.op_order, in CLI order."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, self.const if values is None else values)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]


class _OrderedStore(argparse.Action):
    """Required-value flag (nargs=default) that also records its dest in namespace.op_order, in CLI order."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, values)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]


class _OrderedSortBy(argparse.Action):
    """-sort_by COLUMNS [asc|desc]; records dest in op_order. Default direction is asc."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        values = list(values)
        order = "asc"
        if len(values) >= 2 and values[-1] in ("asc", "desc"):
            order = values.pop()
        if len(values) != 1:
            raise argparse.ArgumentError(
                self, "expected a column list, optionally followed by 'asc' or 'desc'"
            )
        setattr(namespace, self.dest, values[0])
        setattr(namespace, "sort_by_order", order)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytae",
        description="Inspect and convert parquet/csv/txt/sas7bdat files (glob patterns convert multiple files at once).",
        allow_abbrev=False,
    )
    parser.add_argument("path", help="path to a .parquet, .csv, .txt, or .sas7bdat file, "
                                      "or a glob pattern like 'data/*.parquet' for batch conversion")
    parser.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-head", "--head", nargs="?", const=5, type=int, default=None, metavar="N",
                         action=_OrderedValue, help="print the first N rows (default 5)")
    parser.add_argument("-tail", "--tail", nargs="?", const=5, type=int, default=None, metavar="N",
                         action=_OrderedValue, help="print the last N rows (default 5)")
    parser.add_argument("-shape", "--shape", action=_OrderedFlag, help="print (rows, cols)")
    parser.add_argument("-cols", "--cols", nargs="?", const="file", default=None, metavar="ORDER",
                         type=parse_list_order, action=_OrderedValue,
                         help="print column names; optional asc|desc sorts names (default: file order)")
    parser.add_argument("-dtype", "--dtype", nargs="?", const="file", default=None, metavar="ORDER",
                         type=parse_list_order, action=_OrderedValue,
                         help="print column dtypes; optional asc|desc sorts by name (default: file order)")
    parser.add_argument("-nulls", "--nulls", nargs="?", const="file", default=None, metavar="ORDER",
                         type=parse_list_order, action=_OrderedValue,
                         help="print null/NaN count per column; optional asc|desc sorts by name (default: file order)")
    parser.add_argument("-stats", "--stats", "-describe", "--describe", dest="describe", action=_OrderedFlag,
                         help="print numeric summary stats (min/max/mean/etc.)")
    parser.add_argument("-value_counts", "--value_counts", dest="value_counts", action=_OrderedFlag,
                         help="show pandas value_counts across current working columns (use -select to choose columns)")
    parser.add_argument("-unique", "--unique", dest="unique", action=_OrderedFlag,
                         help="drop duplicate rows and print unique rows")
    parser.add_argument("-sample", "--sample", nargs="?", const=5, type=int, default=None, metavar="N",
                         action=_OrderedValue, help="print N randomly sampled rows (default 5)")
    parser.add_argument("-sort_by", "--sort_by", dest="sort_by", nargs="+", default=None, metavar="COLUMNS",
                         action=_OrderedSortBy,
                         help="sort rows by column(s), comma-separated; optional asc|desc (default: asc)")
    parser.add_argument("-group_by", "--group_by", dest="group_by", default=None, metavar="COLUMNS",
                         help="explicit group-by columns for -agg or -group_x (comma-separated), e.g. \"'col_a','col_b'\"")
    parser.add_argument("-nrows", "--nrows", "-limit", "--limit", dest="nrows", type=int, default=None, metavar="N",
                         help="cap the number of rows loaded (default: no cap)")
    parser.add_argument("--select", "-select", dest="select", default=None, metavar="SPEC",
                         help="restrict columns (union of tokens): names, start:end slices, and key=value "
                              "(dtype, contains, startswith, endswith, regex, exclude_dtype), "
                              "e.g. \"species,contains=bill,dtype=numeric\"")
    parser.add_argument("-convert", "--convert", dest="convert",
                         action=_OrderedFlag,
                         help="convert to another format (.parquet/.csv/.txt, inferred from -o's extension, "
                              "defaults to .csv); use -select to restrict columns")
    parser.add_argument("-agg_df", "--agg_df", dest="agg_df", nargs="?", const="sum", default=None,
                         metavar="AGGFUNC", action=_OrderedValue,
                         help="aggregate using pytae agg_df; auto-detects group columns (non-numeric); "
                              "defaults to 'sum' when no value given; "
                              "accepts string ('mean'), list (\"['sum','mean']\"), or dict (\"{'col':'sum','n':'n'}\")")
    parser.add_argument("-agg", "--agg", dest="agg", metavar="AGGSPEC", action=_OrderedStore,
                         help="aggregate using explicit -group_by columns and pandas groupby/agg; dict literal "
                              "mapping column to aggfunc, or to (output_name, aggfunc), e.g. "
                              "\"{'amount': 'sum'}\" or \"{'amount': ('total', 'sum')}\"; requires -group_by")
    parser.add_argument("-group_x", "--group_x", dest="group_x", nargs="?", const="n", default=None,
                         metavar="AGGFUNC[:VALUE_COL]", action=_OrderedValue,
                         help="broadcast a group aggregate back to every row using pytae group_x(); defaults to "
                              "'n' (group size); use \"aggfunc:value_col\" (e.g. \"max:body_mass_g\") to "
                              "broadcast another aggregate; uses -group_by columns, or auto-detects (non-numeric) if omitted")
    parser.add_argument("-handle_missing", "--handle_missing", dest="handle_missing", nargs="?", const=".", default=None,
                         metavar="FILL", action=_OrderedValue,
                         help="fill NaN using pytae handle_missing(): FILL (default '.') for object/category "
                              "columns, 0 for numeric columns")
    parser.add_argument("-dropna", "--dropna", dest="dropna", type=parse_bool_text, default=True,
                         metavar="BOOL",
                         help="for -agg_df, -agg, and -value_counts: include NA keys when false; accepts true or false (default: true)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                         help="output path; its extension picks the format (default: .csv alongside the source file)")
    parser.add_argument("-dlim", "--dlim", dest="dlim", default=None, metavar="CHAR",
                         help="field delimiter for reading/writing .csv/.txt/.sas7bdat (default: ',' for .csv, tab for .txt); not used for .parquet")
    parser.add_argument("-encoding", "--encoding", dest="encoding", default=None, metavar="ENC",
                         help="text encoding for .csv/.txt/.sas7bdat, e.g. latin-1 (default: utf-8/infer); not used for .parquet")
    parser.add_argument("-rename", "--rename", dest="rename", default=None, metavar="OLD:NEW,...",
                         help="rename columns during conversion, e.g. \"old_a:new_a,old_b:new_b\"")
    parser.add_argument("-query", "--query", dest="query", default=None, metavar="EXPR",
                         help="filter rows using a pandas query expression, e.g. \"col > 5\" "
                            "(applies to -head/-tail/-nulls/-describe/-sample/-convert/-agg_df/-agg/-value_counts)")
    parser.add_argument("-qry", "--qry", dest="qry", default=None, metavar="CONDITIONS",
                         help="filter rows using pytae qry per-column conditions as a dict literal, e.g. "
                              "\"{'col': ('>', 5), 'other': ['a', 'b']}\" (combinable with -query; "
                            "applies to -head/-tail/-nulls/-describe/-sample/-convert/-agg_df/-agg/-value_counts)")
    parser.add_argument("-progress", "--progress", action="store_true",
                         help="show row-count progress while converting large files")
    parser.add_argument("-pretty", "--pretty", action="store_true",
                         help="render tables as a bordered markdown table instead of plain pandas text")
    parser.add_argument("-round", "--round", dest="round_ndigits", type=int, default=None, metavar="N",
                         help="round numeric columns to N decimal places before printing/copying; "
                              "non-numeric columns are left unchanged")
    parser.add_argument("-to_clip", "--to_clip", action="store_true",
                         help="also copy the result to the system clipboard: real tab-separated data "
                              "for DataFrame/Series output (-head/-tail/-nulls/-cols/etc.), plain text for -shape "
                              "(cannot combine -shape with a DataFrame-producing flag)")
    return parser


def _process_path(
    path: Path,
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    batch: bool,
    *,
    show_all: bool,
    select_cols: list[str] | None,
    select_kwargs: dict,
    qry_conditions: dict | None,
    rename_map: dict[str, str] | None,
) -> bool:
    """Run every requested display/-convert/-agg action against one file. Returns True if an error occurred."""
    if not path.exists():
        return _fail(parser, batch, f"file not found: {path}")

    try:
        reader = get_reader(path, sep=args.dlim, encoding=args.encoding)
    except ValueError as exc:
        return _fail(parser, batch, str(exc))

    if select_cols:
        unknown = _select_unknown_names(select_cols, reader.columns())
        if unknown:
            return _fail(parser, batch, unknown_columns_message("-select", unknown, reader.columns()))

    pipeline = _Pipeline(
        reader, select=select_cols, select_kwargs=select_kwargs, query=args.query, qry=qry_conditions,
        nrows=args.nrows, progress=args.progress,
    )

    clip_action = None
    emit_stdout = not args.to_clip

    if show_all:
        df = _apply_round(pipeline.dataframe(), args.round_ndigits)
        if emit_stdout:
            print(_format_table(df, pretty=args.pretty))
        if args.to_clip:
            clip_action = lambda d=df: d.to_clipboard(index=False)

    op_order = getattr(args, "op_order", [])
    dataframe_output_ops = {"describe", "head", "tail", "sample", "agg_df", "agg", "value_counts", "unique", "sort_by", "group_x", "handle_missing"}

    def should_print_df_op(current_op: str, later_ops: list[str]) -> bool:
        if not emit_stdout:
            return False
        if current_op not in dataframe_output_ops:
            return True
        # Only print the final DataFrame-style operation in a chain.
        return not any(op in dataframe_output_ops for op in later_ops)

    for idx, op in enumerate(op_order):
        later_ops = op_order[idx + 1:]
        if op == "shape":
            shape_str = str(pipeline.shape())
            if emit_stdout:
                print(shape_str)
            if args.to_clip:
                clip_action = lambda s=shape_str: _copy_to_clipboard(s)
        elif op == "cols":
            names = _list_order_names(pipeline.columns(), args.cols)
            if emit_stdout:
                for name in names:
                    print(name)
            if args.to_clip:
                clip_action = lambda n=names: pd.Series(n).to_clipboard(index=False, header=False)
        elif op == "dtype":
            dtypes = _list_order_index(pipeline.dtypes(), args.dtype)
            if emit_stdout:
                print(dtypes.to_string())
            if args.to_clip:
                clip_action = lambda s=dtypes: s.to_clipboard()
        elif op == "nulls":
            nulls = _list_order_index(pipeline.dataframe().isna().sum(), args.nulls)
            if emit_stdout:
                print(nulls.to_string())
            if args.to_clip:
                clip_action = lambda s=nulls: s.to_clipboard()
        elif op == "describe":
            described = _apply_round(pipeline.dataframe().describe(), args.round_ndigits)
            if should_print_df_op(op, later_ops):
                print(_format_table(described, index=True, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=described: d.to_clipboard(index=True)
        elif op == "value_counts":
            source_df = pipeline.dataframe()
            value_count_cols = list(source_df.columns)

            if len(value_count_cols) == 1:
                col = value_count_cols[0]
                result = source_df[col].value_counts(dropna=args.dropna).rename("count").reset_index()
                result.columns = [col, "count"]
            else:
                result = source_df.value_counts(subset=value_count_cols, dropna=args.dropna).rename("count").reset_index()
            result = _apply_round(result, args.round_ndigits)
            pipeline._df = result
            if should_print_df_op(op, later_ops):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "unique":
            unique_df = _apply_round(pipeline.dataframe().drop_duplicates().reset_index(drop=True), args.round_ndigits)
            pipeline._df = unique_df
            if should_print_df_op(op, later_ops):
                print(_format_table(unique_df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=unique_df: d.to_clipboard(index=False)
        elif op == "head":
            df = _apply_round(pipeline.head(args.head), args.round_ndigits)
            if should_print_df_op(op, later_ops):
                print(_format_table(df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "tail":
            df = _apply_round(pipeline.tail(args.tail), args.round_ndigits)
            if should_print_df_op(op, later_ops):
                print(_format_table(df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "sample":
            sampled = _apply_round(pipeline.sample(args.sample), args.round_ndigits)
            n = len(sampled)
            if should_print_df_op(op, later_ops):
                print(_format_table(sampled, pretty=args.pretty) if n else "(no rows)")
            if args.to_clip and n:
                clip_action = lambda d=sampled: d.to_clipboard(index=False)
        elif op == "sort_by":
            source_df = pipeline.dataframe()
            sort_cols = parse_columns(args.sort_by)
            if any(c not in source_df.columns for c in sort_cols):
                return _fail(parser, batch, unknown_columns_message("-sort_by", sort_cols, list(source_df.columns)))
            ascending = getattr(args, "sort_by_order", "asc") != "desc"
            sorted_df = _apply_round(source_df.sort_values(by=sort_cols, ascending=ascending).reset_index(drop=True), args.round_ndigits)
            pipeline._df = sorted_df
            if should_print_df_op(op, later_ops):
                print(_format_table(sorted_df, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=sorted_df: d.to_clipboard(index=False)
        elif op == "agg_df":
            aggfunc = parse_agg(args.agg_df)
            result = _apply_round(pipeline.dataframe().agg_df(aggfunc=aggfunc, dropna=args.dropna), args.round_ndigits)
            pipeline._df = result
            if should_print_df_op(op, later_ops):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "agg":
            if not args.group_by:
                return _fail(parser, batch, "-agg requires -group_by")
            source_df = pipeline.dataframe()
            group_cols = parse_columns(args.group_by)
            if any(c not in source_df.columns for c in group_cols):
                return _fail(parser, batch, unknown_columns_message("-group_by", group_cols, list(source_df.columns)))
            agg_spec = parse_group_agg(args.agg)
            named_agg = {}
            for col, spec in agg_spec.items():
                out_name, aggfunc = spec if isinstance(spec, tuple) and len(spec) == 2 else (col, spec)
                if col not in source_df.columns:
                    return _fail(parser, batch, unknown_columns_message("-agg", [col], list(source_df.columns)))
                named_agg[out_name] = pd.NamedAgg(column=col, aggfunc=aggfunc)
            result = source_df.groupby(group_cols, dropna=args.dropna, observed=True, as_index=False).agg(**named_agg)
            result = _apply_round(result, args.round_ndigits)
            pipeline._df = result
            if should_print_df_op(op, later_ops):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "group_x":
            source_df = pipeline.dataframe()
            aggfunc, value_col = parse_group_x_arg(args.group_x)
            group_cols = parse_columns(args.group_by) if args.group_by else None
            if group_cols and any(c not in source_df.columns for c in group_cols):
                return _fail(parser, batch, unknown_columns_message("-group_by", group_cols, list(source_df.columns)))
            if value_col and value_col not in source_df.columns:
                return _fail(parser, batch, unknown_columns_message("-group_x", [value_col], list(source_df.columns)))
            result = _apply_round(
                source_df.group_x(group=group_cols, dropna=args.dropna, observed=True, aggfunc=aggfunc, value=value_col),
                args.round_ndigits,
            )
            pipeline._df = result
            if should_print_df_op(op, later_ops):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "handle_missing":
            result = _apply_round(pipeline.dataframe().handle_missing(fillna=args.handle_missing), args.round_ndigits)
            pipeline._df = result
            if should_print_df_op(op, later_ops):
                print(_format_table(result, pretty=args.pretty))
            if args.to_clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "convert":
            cmd_convert(
                pipeline.dataframe(), path, args.output,
                rename=rename_map, sep=args.dlim, encoding=args.encoding, progress=args.progress,
            )

    if args.to_clip and clip_action is not None:
        clip_action()

    return False


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    show_all = not any([args.shape, args.cols, args.dtype, args.nulls, args.describe,
                         args.value_counts, args.unique, args.head is not None,
                         args.tail is not None, args.sample is not None, args.sort_by is not None,
                         args.convert, args.agg_df is not None, args.agg is not None,
                         args.group_x is not None, args.handle_missing is not None])

    wants_df = any([args.cols, args.dtype, args.nulls, args.describe, show_all,
                     args.value_counts, args.unique, args.head is not None,
                     args.tail is not None, args.sample is not None, args.sort_by is not None,
                     args.agg_df is not None, args.agg is not None,
                     args.group_x is not None, args.handle_missing is not None])
    if args.to_clip and args.shape and wants_df:
        parser.error("-to_clip can't combine -shape (not a DataFrame/Series) with a DataFrame-producing flag "
                     "like -head/-tail/-cols/-dtype/-nulls/-describe/-value_counts/-unique/-sample/-sort_by/"
                     "-agg_df/-agg/-group_x/-handle_missing; run -shape separately")
    if args.agg_df is not None and args.agg is not None:
        parser.error("-agg_df and -agg can't be combined; choose one")
    if args.group_by is not None and args.agg is None and args.group_x is None:
        parser.error("-group_by requires -agg or -group_x")

    paths = expand_paths(args.path)
    if len(paths) > 1 and args.output is not None:
        parser.error("-o/--output cannot be used with multiple matched files; each output path is derived automatically")

    rename_map = parse_rename(args.rename) if args.rename else None
    if args.select:
        select_cols, select_kwargs = parse_select_spec(args.select)
    else:
        select_cols, select_kwargs = None, {}
    qry_conditions = parse_qry(args.qry) if args.qry else None
    batch = len(paths) > 1
    exit_code = 0

    for path in paths:
        if batch:
            print(f"== {path} ==")
        if _process_path(path, args, parser, batch, show_all=show_all, select_cols=select_cols,
                          select_kwargs=select_kwargs, qry_conditions=qry_conditions, rename_map=rename_map):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())