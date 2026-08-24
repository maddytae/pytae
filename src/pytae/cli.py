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
import pytae  # registers .select(), .qry(), .agg_df() on pd.DataFrame

from pytae.readers import get_reader, write_dataframe

try:
    __version__ = _pkg_version("pytae")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


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


def parse_columns(raw: str) -> list[str]:
    """Parse a column list like "'col a','col b'" or "col_a,col_b" into a list of names."""
    raw = raw.strip()
    try:
        parsed = ast.literal_eval(f"[{raw}]")
        cols = list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
        return [str(c).strip() for c in cols]
    except (ValueError, SyntaxError):
        return [c.strip().strip("'\"") for c in raw.split(",") if c.strip()]


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
    """Parse an --agg aggfunc value: bare string ('sum'), list literal, or dict literal."""
    raw = raw.strip()
    if not (raw.startswith(("{", "[", "'", '"'))):
        return raw
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f"invalid --agg value: {exc}") from exc


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
    -head/-tail/-sample, -describe, -nulls, -cols, -dtype, -shape, -csv, -agg) sees
    that narrowed view. Schema-only ops (-cols/-dtype/-shape) avoid loading
    row data until something actually requires it.
    """

    def __init__(self, reader, *, select, query, qry, nrows, progress) -> None:
        self._reader = reader
        self._select = select      # list[str] | None — passed to reader for parquet read-time optimisation
        self._query = query
        self._qry = qry
        self._nrows = nrows
        self._progress = progress
        self._df: pd.DataFrame | None = None

    def dataframe(self) -> pd.DataFrame:
        if self._df is None:
            df = self._reader.to_dataframe(columns=self._select, nrows=self._nrows, progress=self._progress)
            df = _apply_query(df, self._query)
            if self._qry:
                df = df.qry(self._qry)
            self._df = df
        return self._df

    def columns(self) -> list[str]:
        if self._df is not None:
            return list(self._df.columns)
        if self._query or self._qry:
            return list(self.dataframe().columns)
        return list(self._select) if self._select else self._reader.columns()

    def dtypes(self) -> pd.Series:
        if self._df is not None:
            return self._df.dtypes
        if self._query or self._qry:
            return self.dataframe().dtypes
        dtypes = self._reader.dtypes()
        return dtypes[self._select] if self._select else dtypes

    def shape(self) -> tuple[int, int]:
        if self._df is not None:
            return self._df.shape
        if self._query or self._qry:
            return self.dataframe().shape
        rows = self._reader.shape()[0]
        cols = len(self._select) if self._select else self._reader.shape()[1]
        return (rows, cols)

    def head(self, n: int) -> pd.DataFrame:
        if self._df is None and not (self._query or self._qry):
            df = self._reader.head(n)
            if self._select:
                df = df.select(self._select)
        else:
            df = self.dataframe().head(n)
        self._df = df
        return df

    def tail(self, n: int) -> pd.DataFrame:
        if self._df is None and not (self._query or self._qry):
            df = self._reader.tail(n)
            if self._select:
                df = df.select(self._select)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytae",
        description="Inspect and convert parquet/csv/txt/sas7bdat files (glob patterns convert multiple files at once).",
    )
    parser.add_argument("path", help="path to a .parquet, .csv, .txt, or .sas7bdat file, "
                                      "or a glob pattern like 'data/*.parquet' for batch conversion")
    parser.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-head", "--head", nargs="?", const=5, type=int, default=None, metavar="N",
                         action=_OrderedValue, help="print the first N rows (default 5)")
    parser.add_argument("-tail", "--tail", nargs="?", const=5, type=int, default=None, metavar="N",
                         action=_OrderedValue, help="print the last N rows (default 5)")
    parser.add_argument("-shape", "--shape", action=_OrderedFlag, help="print (rows, cols)")
    parser.add_argument("-cols", "--cols", action=_OrderedFlag, help="print column names")
    parser.add_argument("-dtype", "--dtype", action=_OrderedFlag, help="print column dtypes")
    parser.add_argument("-nulls", "--nulls", action=_OrderedFlag, help="print null/NaN count per column")
    parser.add_argument("-describe", "--describe", "-stats", "--stats", dest="describe", action=_OrderedFlag,
                         help="print numeric summary stats (min/max/mean/etc.)")
    parser.add_argument("-sample", "--sample", nargs="?", const=5, type=int, default=None, metavar="N",
                         action=_OrderedValue, help="print N randomly sampled rows (default 5)")
    parser.add_argument("-nrows", "--nrows", "-limit", "--limit", dest="nrows", type=int, default=None, metavar="N",
                         help="cap the number of rows loaded for -nulls/-describe/-sample/-csv (default: no cap)")
    parser.add_argument("--select", "-select", dest="select", default=None, metavar="COLUMNS",
                         help="restrict columns using pytae select; pass a comma-separated list "
                              "e.g. \"'col a','col b'\" (applied to -head/-tail/-nulls/-describe/-sample/-csv)")
    parser.add_argument("-sort", "--sort", choices=["asc", "desc", "none"], default="asc",
                         help="column order for -cols/-dtype/-nulls: asc (default), desc, or none (file's original order)")
    parser.add_argument("-csv", "--csv", "-convert", "--convert", dest="convert",
                         action=_OrderedFlag,
                         help="convert to another format (.parquet/.csv/.txt, inferred from -o's extension, "
                              "defaults to .csv); use -select to restrict columns")
    parser.add_argument("-agg", "--agg", dest="agg", nargs="?", const="sum", default=None,
                         metavar="AGGFUNC", action=_OrderedValue,
                         help="aggregate using pytae agg_df; defaults to 'sum' when no value given; "
                              "accepts string ('mean'), list (\"['sum','mean']\"), or dict (\"{'col':'sum','n':'n'}\")")
    parser.add_argument("-o", "--output", type=Path, default=None,
                         help="output path; its extension picks the format (default: .csv alongside the source file)")
    parser.add_argument("-dlim", "--dlim", dest="dlim", default=None, metavar="CHAR",
                         help="field delimiter for reading/writing .csv/.txt/.sas7bdat (default: ',' for .csv, tab for .txt); not used for .parquet")
    parser.add_argument("-encoding", "--encoding", dest="encoding", default=None, metavar="ENC",
                         help="text encoding for reading/writing csv/txt/sas7bdat, e.g. latin-1 (default: utf-8/infer)")
    parser.add_argument("-rename", "--rename", dest="rename", default=None, metavar="OLD:NEW,...",
                         help="rename columns during conversion, e.g. \"old_a:new_a,old_b:new_b\"")
    parser.add_argument("-query", "--query", dest="query", default=None, metavar="EXPR",
                         help="filter rows using a pandas query expression, e.g. \"col > 5\" "
                              "(applies to -head/-tail/-nulls/-describe/-sample/-csv/-agg)")
    parser.add_argument("-qry", "--qry", dest="qry", default=None, metavar="CONDITIONS",
                         help="filter rows using pytae qry per-column conditions as a dict literal, e.g. "
                              "\"{'col': ('>', 5), 'other': ['a', 'b']}\" (combinable with -query; "
                              "applies to -head/-tail/-nulls/-describe/-sample/-csv/-agg)")
    parser.add_argument("-progress", "--progress", action="store_true",
                         help="show row-count progress while converting large files")
    parser.add_argument("-pretty", "--pretty", action="store_true",
                         help="render tables as a bordered markdown table instead of plain pandas text")
    parser.add_argument("-clip", "--clip", action="store_true",
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
    qry_conditions: dict | None,
    rename_map: dict[str, str] | None,
) -> bool:
    """Run every requested display/-csv/-agg action against one file. Returns True if an error occurred."""
    if not path.exists():
        return _fail(parser, batch, f"file not found: {path}")

    try:
        reader = get_reader(path, sep=args.dlim, encoding=args.encoding)
    except ValueError as exc:
        return _fail(parser, batch, str(exc))

    if select_cols and any(c not in reader.columns() for c in select_cols):
        return _fail(parser, batch, unknown_columns_message("-select", select_cols, reader.columns()))

    pipeline = _Pipeline(
        reader, select=select_cols, query=args.query, qry=qry_conditions,
        nrows=args.nrows, progress=args.progress,
    )

    clip_action = None

    if show_all:
        df = pipeline.dataframe()
        print(_format_table(df, pretty=args.pretty))
        if args.clip:
            clip_action = lambda d=df: d.to_clipboard(index=False)

    for op in getattr(args, "op_order", []):
        if op == "shape":
            shape_str = str(pipeline.shape())
            print(shape_str)
            if args.clip:
                clip_action = lambda s=shape_str: _copy_to_clipboard(s)
        elif op == "cols":
            names = pipeline.columns()
            if args.sort != "none":
                names = sorted(names, reverse=(args.sort == "desc"))
            for name in names:
                print(name)
            if args.clip:
                clip_action = lambda n=names: pd.Series(n).to_clipboard(index=False, header=False)
        elif op == "dtype":
            dtypes = pipeline.dtypes()
            if args.sort != "none":
                dtypes = dtypes.sort_index(ascending=(args.sort == "asc"))
            print(dtypes.to_string())
            if args.clip:
                clip_action = lambda s=dtypes: s.to_clipboard()
        elif op == "nulls":
            nulls = pipeline.dataframe().isna().sum()
            if args.sort != "none":
                nulls = nulls.sort_index(ascending=(args.sort == "asc"))
            print(nulls.to_string())
            if args.clip:
                clip_action = lambda s=nulls: s.to_clipboard()
        elif op == "describe":
            described = pipeline.dataframe().describe()
            print(_format_table(described, index=True, pretty=args.pretty))
            if args.clip:
                clip_action = lambda d=described: d.to_clipboard(index=True)
        elif op == "head":
            df = pipeline.head(args.head)
            print(_format_table(df, pretty=args.pretty))
            if args.clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "tail":
            df = pipeline.tail(args.tail)
            print(_format_table(df, pretty=args.pretty))
            if args.clip:
                clip_action = lambda d=df: d.to_clipboard(index=False)
        elif op == "sample":
            sampled = pipeline.sample(args.sample)
            n = len(sampled)
            print(_format_table(sampled, pretty=args.pretty) if n else "(no rows)")
            if args.clip and n:
                clip_action = lambda d=sampled: d.to_clipboard(index=False)
        elif op == "agg":
            aggfunc = parse_agg(args.agg)
            result = pipeline.dataframe().agg_df(aggfunc=aggfunc)
            print(_format_table(result, pretty=args.pretty))
            if args.clip:
                clip_action = lambda d=result: d.to_clipboard(index=False)
        elif op == "convert":
            cmd_convert(
                pipeline.dataframe(), path, args.output,
                rename=rename_map, sep=args.dlim, encoding=args.encoding, progress=args.progress,
            )

    if args.clip and clip_action is not None:
        clip_action()

    return False


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    show_all = not any([args.shape, args.cols, args.dtype, args.nulls, args.describe,
                         args.head is not None, args.tail is not None, args.sample is not None,
                         args.convert, args.agg is not None])

    wants_df = any([args.cols, args.dtype, args.nulls, args.describe, show_all,
                     args.head is not None, args.tail is not None, args.sample is not None,
                     args.agg is not None])
    if args.clip and args.shape and wants_df:
        parser.error("-clip can't combine -shape (not a DataFrame/Series) with a DataFrame-producing flag "
                     "like -head/-tail/-cols/-dtype/-nulls/-describe/-sample/-agg; run -shape separately")

    paths = expand_paths(args.path)
    if len(paths) > 1 and args.output is not None:
        parser.error("-o/--output cannot be used with multiple matched files; each output path is derived automatically")

    rename_map = parse_rename(args.rename) if args.rename else None
    select_cols = parse_columns(args.select) if args.select else None
    qry_conditions = parse_qry(args.qry) if args.qry else None
    batch = len(paths) > 1
    exit_code = 0

    for path in paths:
        if batch:
            print(f"== {path} ==")
        if _process_path(path, args, parser, batch, show_all=show_all, select_cols=select_cols,
                          qry_conditions=qry_conditions, rename_map=rename_map):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
