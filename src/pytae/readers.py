"""Format-specific readers exposing a uniform metadata/inspection API.

Each reader avoids loading full row data for shape/columns/dtypes/head where
the file format allows it (parquet, sas7bdat carry that info in a header).
CSV/TXT have no embedded schema, so dtype inspection samples the first
DTYPE_SAMPLE_ROWS rows.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pa_parquet

DEFAULT_CHUNK_SIZE = 200_000
CHUNK_SIZE = DEFAULT_CHUNK_SIZE
DTYPE_SAMPLE_ROWS = 10_000


def _delimited_dtypes(path: Path, *, sep: str, encoding: str | None) -> pd.Series:
    return pd.read_csv(
        path, sep=sep, encoding=encoding, nrows=DTYPE_SAMPLE_ROWS, low_memory=False
    ).dtypes


def _print_progress(done: int, total: int | None, label: str) -> None:
    if total:
        pct = min(100, int(done * 100 / total))
        print(f"\r{label}... {done}/{total} rows ({pct}%)", end="", flush=True)
    else:
        print(f"\r{label}... {done} rows", end="", flush=True)


class ParquetReader:
    def __init__(self, path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.path = path
        self.chunk_size = chunk_size
        self._pf = pa_parquet.ParquetFile(path)

    def shape(self) -> tuple[int, int]:
        md = self._pf.metadata
        return (md.num_rows, md.num_columns)

    def columns(self) -> list[str]:
        return list(self._pf.schema_arrow.names)

    def dtypes(self) -> pd.Series:
        return self._pf.schema_arrow.empty_table().to_pandas().dtypes

    def _empty(self) -> pd.DataFrame:
        return self._pf.schema_arrow.empty_table().to_pandas()

    def head(self, n: int) -> pd.DataFrame:
        if n <= 0 or self._pf.metadata.num_rows == 0:
            return self._empty()
        batch = next(self._pf.iter_batches(batch_size=n), None)
        if batch is None:
            return self._empty()
        return batch.to_pandas().head(n)

    def tail(self, n: int) -> pd.DataFrame:
        total = self._pf.metadata.num_rows
        if n <= 0 or total == 0:
            return self._empty()
        skip = max(total - n, 0)
        parts, seen = [], 0
        for batch in self._pf.iter_batches(batch_size=max(n, 1)):
            start_in_batch = max(0, skip - seen)
            if start_in_batch < batch.num_rows:
                parts.append(batch.to_pandas().iloc[start_in_batch:])
            seen += batch.num_rows
        df = pd.concat(parts, ignore_index=True) if parts else self._empty()
        return df.tail(n)

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None,
                     chunk_size: int | None = None) -> pd.DataFrame:
        if not progress and nrows is None:
            return pd.read_parquet(self.path, columns=columns)
        total = self._pf.metadata.num_rows
        limit = total if nrows is None else min(nrows, total)
        csize = chunk_size or self.chunk_size
        parts, done = [], 0
        for batch in self._pf.iter_batches(batch_size=csize, columns=columns):
            remaining = limit - done
            if remaining <= 0:
                break
            chunk = batch.to_pandas().iloc[:remaining]
            parts.append(chunk)
            done += len(chunk)
            if progress:
                _print_progress(done, limit, "reading")
        if progress:
            print()
        if parts:
            return pd.concat(parts, ignore_index=True)
        empty = self._empty()
        return empty[columns] if columns else empty


class CsvReader:
    def __init__(self, path: Path, sep: str = ",", encoding: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.path = path
        self.sep = sep
        self.encoding = encoding
        self.chunk_size = chunk_size

    def shape(self) -> tuple[int, int]:
        n_cols = len(self.columns())
        total = 0
        for chunk in pd.read_csv(
            self.path, sep=self.sep, encoding=self.encoding, usecols=[0], chunksize=self.chunk_size, low_memory=False
        ):
            total += len(chunk)
        return (total, n_cols)

    def columns(self) -> list[str]:
        try:
            return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=0, low_memory=False).columns.tolist()
        except pd.errors.EmptyDataError as exc:
            raise ValueError(f"'{self.path.name}' is empty or not a valid CSV file") from exc

    def dtypes(self) -> pd.Series:
        return _delimited_dtypes(self.path, sep=self.sep, encoding=self.encoding)

    def head(self, n: int) -> pd.DataFrame:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=n, low_memory=False)

    def tail(self, n: int) -> pd.DataFrame:
        total = self.shape()[0]
        skip = range(1, max(total - n, 0) + 1)  # keep the header (row 0), skip everything before the tail
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, skiprows=skip, low_memory=False)

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None,
                     chunk_size: int | None = None) -> pd.DataFrame:
        if not progress:
            return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns, nrows=nrows,
                               low_memory=False)
        total = self.shape()[0] if nrows is None else min(nrows, self.shape()[0])
        chunks, done = [], 0
        csize = chunk_size or self.chunk_size
        reader = pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns,
                      chunksize=csize, nrows=nrows, low_memory=False)
        for chunk in reader:
            chunks.append(chunk)
            done += len(chunk)
            _print_progress(done, total, "reading")
        print()
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns or [])


class TxtReader:
    """Reads delimited .txt/.dat files (tab-delimited for .txt, pipe-delimited for .dat by default)."""

    def __init__(self, path: Path, sep: str = "\t", encoding: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.path = path
        self.sep = sep
        self.encoding = encoding
        self.chunk_size = chunk_size

    def shape(self) -> tuple[int, int]:
        n_cols = len(self.columns())
        total = 0
        for chunk in pd.read_csv(
            self.path, sep=self.sep, encoding=self.encoding, usecols=[0], chunksize=self.chunk_size, low_memory=False
        ):
            total += len(chunk)
        return (total, n_cols)

    def columns(self) -> list[str]:
        try:
            return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=0, low_memory=False).columns.tolist()
        except pd.errors.EmptyDataError as exc:
            raise ValueError(f"'{self.path.name}' is empty or not a valid delimited file") from exc

    def dtypes(self) -> pd.Series:
        return _delimited_dtypes(self.path, sep=self.sep, encoding=self.encoding)

    def head(self, n: int) -> pd.DataFrame:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=n, low_memory=False)

    def tail(self, n: int) -> pd.DataFrame:
        total = self.shape()[0]
        skip = range(1, max(total - n, 0) + 1)  # keep the header (row 0), skip everything before the tail
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, skiprows=skip, low_memory=False)

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None,
                     chunk_size: int | None = None) -> pd.DataFrame:
        if not progress:
            return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns, nrows=nrows,
                               low_memory=False)
        total = self.shape()[0] if nrows is None else min(nrows, self.shape()[0])
        chunks, done = [], 0
        csize = chunk_size or self.chunk_size
        reader = pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns,
                      chunksize=csize, nrows=nrows, low_memory=False)
        for chunk in reader:
            chunks.append(chunk)
            done += len(chunk)
            _print_progress(done, total, "reading")
        print()
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns or [])


class SasReader:
    """Reads .sas7bdat files. Row count/columns come from the file header,
    so shape/columns are cheap; dtype inspection reads a small sample."""

    def __init__(self, path: Path, encoding: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.path = path
        self.encoding = "utf-8" if encoding is None else encoding
        self.chunk_size = chunk_size

    def _open(self):
        return pd.read_sas(self.path, format="sas7bdat", encoding=self.encoding, iterator=True)

    def shape(self) -> tuple[int, int]:
        with self._open() as reader:
            return (reader.row_count, len(reader.column_names))

    def columns(self) -> list[str]:
        with self._open() as reader:
            return [str(name) for name in reader.column_names]

    def dtypes(self) -> pd.Series:
        with self._open() as reader:
            sample = reader.read(min(100, reader.row_count))
        return sample.dtypes

    def head(self, n: int) -> pd.DataFrame:
        with self._open() as reader:
            return reader.read(n)

    def tail(self, n: int) -> pd.DataFrame:
        with self._open() as reader:
            total = reader.row_count
            skip = max(total - n, 0)
            if skip:
                reader.read(skip)  # advance past rows we don't need
            return reader.read(min(n, total))

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None,
                     chunk_size: int | None = None) -> pd.DataFrame:
        if not progress and nrows is None:
            df = pd.read_sas(self.path, format="sas7bdat", encoding=self.encoding)
            return df[columns] if columns else df
        with self._open() as reader:
            total = reader.row_count if nrows is None else min(nrows, reader.row_count)
            chunks, done = [], 0
            csize = chunk_size or self.chunk_size
            while done < total:
                chunk = reader.read(min(csize, total - done))
                if chunk is None or len(chunk) == 0:
                    break
                chunks.append(chunk)
                done += len(chunk)
                if progress:
                    _print_progress(done, total, "reading")
        if progress:
            print()
        df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        return df[columns] if columns else df


_READERS = {
    ".parquet": ParquetReader,
    ".pq": ParquetReader,
    ".csv": CsvReader,
    ".txt": TxtReader,
    ".dat": TxtReader,
    ".sas7bdat": SasReader,
}

# YAML connection configs (Databricks / SSH) are handled by the isolated pytae.connections
# module, loaded lazily so the core package never imports its optional dependencies.
_YAML_SUFFIXES = (".yaml", ".yml")
_EXTERNAL_CONNECTIONS_MODULE = None

# default field separator for TxtReader-backed suffixes (.txt/.dat)
_TXT_DEFAULT_SEP = {".txt": "\t", ".dat": "|"}

# default text encoding for TxtReader-backed suffixes; only .dat has one (.txt still
# falls through to pandas' own encoding inference, i.e. None)
_TXT_DEFAULT_ENCODING = {".dat": "latin-1"}


def get_reader(path: Path, *, sep: str | None = None, encoding: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE):
    suffix = path.suffix.lower()
    if suffix in _YAML_SUFFIXES:
        global _EXTERNAL_CONNECTIONS_MODULE
        if _EXTERNAL_CONNECTIONS_MODULE is None:
            conn_env = os.environ.get("PYTAE_CONNECTIONS_PATH")
            if not conn_env:
                raise FileNotFoundError(
                    "connection reader not configured; set the PYTAE_CONNECTIONS_PATH environment "
                    "variable to a connections.py file"
                )
            module_path = Path(conn_env).expanduser()
            if not module_path.is_file():
                raise FileNotFoundError(
                    "connection reader not found; set PYTAE_CONNECTIONS_PATH to a connections.py file "
                    f"(looked for '{module_path}')"
                )
            module_spec = importlib.util.spec_from_file_location(
                "_pytae_external_connections", module_path
            )
            if module_spec is None or module_spec.loader is None:
                raise ImportError(f"cannot load connections module from '{module_path}'")
            _EXTERNAL_CONNECTIONS_MODULE = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(_EXTERNAL_CONNECTIONS_MODULE)
        return _EXTERNAL_CONNECTIONS_MODULE.build_yaml_reader(path)
    try:
        cls = _READERS[suffix]
    except KeyError:
        supported = ", ".join(sorted((*_READERS, *_YAML_SUFFIXES)))
        raise ValueError(f"unsupported file type '{path.suffix or path.name}'; supported: {supported}") from None
    if cls is CsvReader:
        return CsvReader(path, sep=sep or ",", encoding=encoding, chunk_size=chunk_size)
    if cls is TxtReader:
        return TxtReader(
            path,
            sep=sep or _TXT_DEFAULT_SEP[suffix],
            encoding=encoding or _TXT_DEFAULT_ENCODING.get(suffix),
            chunk_size=chunk_size,
        )
    if cls is SasReader:
        return SasReader(path, encoding=encoding, chunk_size=chunk_size)
    return cls(path, chunk_size=chunk_size)


# .sas7bdat is intentionally excluded: pandas has no writer for that format.
_WRITABLE_SUFFIXES = (".parquet", ".pq", ".csv", ".txt", ".dat")


def write_dataframe(df: pd.DataFrame, dest: Path, *, sep: str | None = None, encoding: str | None = None,
                     progress: bool = False, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
    suffix = dest.suffix.lower()
    if suffix in (".parquet", ".pq"):
        _write_parquet(df, dest, progress=progress, chunk_size=chunk_size)
    elif suffix == ".csv":
        _write_delimited(df, dest, sep=sep or ",", encoding=encoding, progress=progress, chunk_size=chunk_size)
    elif suffix in _TXT_DEFAULT_SEP:
        _write_delimited(
            df, dest,
            sep=sep or _TXT_DEFAULT_SEP[suffix],
            encoding=encoding or _TXT_DEFAULT_ENCODING.get(suffix),
            progress=progress,
            chunk_size=chunk_size,
        )
    else:
        supported = ", ".join(_WRITABLE_SUFFIXES)
        raise ValueError(f"unsupported output type '{suffix or dest.name}'; supported: {supported}")


def _write_delimited(df: pd.DataFrame, dest: Path, *, sep: str, encoding: str | None, progress: bool,
                     chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
    total = len(df)
    if not progress or total == 0:
        df.to_csv(dest, sep=sep, encoding=encoding, index=False)
        return
    done = 0
    for start in range(0, total, chunk_size):
        chunk = df.iloc[start:start + chunk_size]
        chunk.to_csv(dest, sep=sep, encoding=encoding, index=False, mode="w" if start == 0 else "a", header=(start == 0))
        done += len(chunk)
        _print_progress(done, total, "writing")
    print()


def _write_parquet(df: pd.DataFrame, dest: Path, *, progress: bool, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
    if not progress or len(df) == 0:
        df.to_parquet(dest, index=False)
        return
    table = pa.Table.from_pandas(df, preserve_index=False)
    total = table.num_rows
    done = 0
    with pa_parquet.ParquetWriter(dest, table.schema) as writer:
        for batch in table.to_batches(max_chunksize=chunk_size):
            writer.write_batch(batch)
            done += batch.num_rows
            _print_progress(done, total, "writing")
    print()