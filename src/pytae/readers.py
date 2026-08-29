
"""Format-specific readers exposing a uniform metadata/inspection API.

Each reader avoids loading full row data for shape/columns/dtypes/head where
the file format allows it (parquet, sas7bdat carry that info in a header).
CSV has no embedded schema, so dtype inspection reads the file.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pa_parquet

CHUNK_SIZE = 200_000


def _print_progress(done: int, total: int | None, label: str) -> None:
    if total:
        pct = min(100, int(done * 100 / total))
        print(f"\r{label}... {done}/{total} rows ({pct}%)", end="", flush=True)
    else:
        print(f"\r{label}... {done} rows", end="", flush=True)


class ParquetReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._pf = pa_parquet.ParquetFile(path)

    def shape(self) -> tuple[int, int]:
        md = self._pf.metadata
        return (md.num_rows, md.num_columns)

    def columns(self) -> list[str]:
        return list(self._pf.schema_arrow.names)

    def dtypes(self) -> pd.Series:
        return self._pf.schema_arrow.empty_table().to_pandas().dtypes

    def head(self, n: int) -> pd.DataFrame:
        batch = next(self._pf.iter_batches(batch_size=n))
        return batch.to_pandas().head(n)

    def tail(self, n: int) -> pd.DataFrame:
        total = self._pf.metadata.num_rows
        skip = max(total - n, 0)
        parts, seen = [], 0
        for batch in self._pf.iter_batches(batch_size=max(n, 1)):
            start_in_batch = max(0, skip - seen)
            if start_in_batch < batch.num_rows:
                parts.append(batch.to_pandas().iloc[start_in_batch:])
            seen += batch.num_rows
        df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        return df.tail(n)

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None) -> pd.DataFrame:
        if not progress and nrows is None:
            return pd.read_parquet(self.path, columns=columns)
        total = self._pf.metadata.num_rows
        limit = total if nrows is None else min(nrows, total)
        parts, done = [], 0
        for batch in self._pf.iter_batches(batch_size=CHUNK_SIZE, columns=columns):
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
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=columns or [])


class CsvReader:
    def __init__(self, path: Path, sep: str = ",", encoding: str | None = None) -> None:
        self.path = path
        self.sep = sep
        self.encoding = encoding

    def shape(self) -> tuple[int, int]:
        with open(self.path, "rb") as fh:
            rows = sum(1 for _ in fh) - 1  # exclude header line
        return (max(rows, 0), len(self.columns()))

    def columns(self) -> list[str]:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=0, low_memory=False).columns.tolist()

    def dtypes(self) -> pd.Series:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, low_memory=False).dtypes

    def head(self, n: int) -> pd.DataFrame:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=n, low_memory=False)

    def tail(self, n: int) -> pd.DataFrame:
        total = self.shape()[0]
        skip = range(1, max(total - n, 0) + 1)  # keep the header (row 0), skip everything before the tail
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, skiprows=skip, low_memory=False)

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None) -> pd.DataFrame:
        if not progress:
            return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns, nrows=nrows,
                               low_memory=False)
        total = self.shape()[0] if nrows is None else min(nrows, self.shape()[0])
        chunks, done = [], 0
        reader = pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns,
                      chunksize=CHUNK_SIZE, nrows=nrows, low_memory=False)
        for chunk in reader:
            chunks.append(chunk)
            done += len(chunk)
            _print_progress(done, total, "reading")
        print()
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns or [])


class TxtReader:
    """Reads delimited .txt files (tab-delimited by default)."""

    def __init__(self, path: Path, sep: str = "\t", encoding: str | None = None) -> None:
        self.path = path
        self.sep = sep
        self.encoding = encoding

    def shape(self) -> tuple[int, int]:
        with open(self.path, "rb") as fh:
            rows = sum(1 for _ in fh) - 1  # exclude header line
        return (max(rows, 0), len(self.columns()))

    def columns(self) -> list[str]:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=0, low_memory=False).columns.tolist()

    def dtypes(self) -> pd.Series:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, low_memory=False).dtypes

    def head(self, n: int) -> pd.DataFrame:
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, nrows=n, low_memory=False)

    def tail(self, n: int) -> pd.DataFrame:
        total = self.shape()[0]
        skip = range(1, max(total - n, 0) + 1)  # keep the header (row 0), skip everything before the tail
        return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, skiprows=skip, low_memory=False)

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None) -> pd.DataFrame:
        if not progress:
            return pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns, nrows=nrows,
                               low_memory=False)
        total = self.shape()[0] if nrows is None else min(nrows, self.shape()[0])
        chunks, done = [], 0
        reader = pd.read_csv(self.path, sep=self.sep, encoding=self.encoding, usecols=columns,
                      chunksize=CHUNK_SIZE, nrows=nrows, low_memory=False)
        for chunk in reader:
            chunks.append(chunk)
            done += len(chunk)
            _print_progress(done, total, "reading")
        print()
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns or [])


class SasReader:
    """Reads .sas7bdat files. Row count/columns come from the file header,
    so shape/columns are cheap; dtype inspection reads a small sample."""

    def __init__(self, path: Path, encoding: str | None = None) -> None:
        self.path = path
        self.encoding = encoding

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

    def to_dataframe(self, columns: list[str] | None = None, progress: bool = False, nrows: int | None = None) -> pd.DataFrame:
        if not progress and nrows is None:
            df = pd.read_sas(self.path, format="sas7bdat", encoding=self.encoding)
            return df[columns] if columns else df
        with self._open() as reader:
            total = reader.row_count if nrows is None else min(nrows, reader.row_count)
            chunks, done = [], 0
            while done < total:
                chunk = reader.read(min(CHUNK_SIZE, total - done))
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
    ".sas7bdat": SasReader,
}


def get_reader(path: Path, *, sep: str | None = None, encoding: str | None = None):
    try:
        cls = _READERS[path.suffix.lower()]
    except KeyError:
        supported = ", ".join(sorted(_READERS))
        raise ValueError(f"unsupported file type '{path.suffix or path.name}'; supported: {supported}") from None
    if cls is CsvReader:
        return CsvReader(path, sep=sep or ",", encoding=encoding)
    if cls is TxtReader:
        return TxtReader(path, sep=sep or "\t", encoding=encoding)
    if cls is SasReader:
        return SasReader(path, encoding=encoding)
    return cls(path)


# .sas7bdat is intentionally excluded: pandas has no writer for that format.
_WRITABLE_SUFFIXES = (".parquet", ".pq", ".csv", ".txt")


def write_dataframe(df: pd.DataFrame, dest: Path, *, sep: str | None = None, encoding: str | None = None,
                     progress: bool = False) -> None:
    suffix = dest.suffix.lower()
    if suffix in (".parquet", ".pq"):
        _write_parquet(df, dest, progress=progress)
    elif suffix == ".csv":
        _write_delimited(df, dest, sep=sep or ",", encoding=encoding, progress=progress)
    elif suffix == ".txt":
        _write_delimited(df, dest, sep=sep or "\t", encoding=encoding, progress=progress)
    else:
        supported = ", ".join(_WRITABLE_SUFFIXES)
        raise ValueError(f"unsupported output type '{suffix or dest.name}'; supported: {supported}")


def _write_delimited(df: pd.DataFrame, dest: Path, *, sep: str, encoding: str | None, progress: bool) -> None:
    total = len(df)
    if not progress or total == 0:
        df.to_csv(dest, sep=sep, encoding=encoding, index=False)
        return
    done = 0
    for start in range(0, total, CHUNK_SIZE):
        chunk = df.iloc[start:start + CHUNK_SIZE]
        chunk.to_csv(dest, sep=sep, encoding=encoding, index=False, mode="w" if start == 0 else "a", header=(start == 0))
        done += len(chunk)
        _print_progress(done, total, "writing")
    print()


def _write_parquet(df: pd.DataFrame, dest: Path, *, progress: bool) -> None:
    if not progress or len(df) == 0:
        df.to_parquet(dest, index=False)
        return
    table = pa.Table.from_pandas(df, preserve_index=False)
    total = table.num_rows
    done = 0
    with pa_parquet.ParquetWriter(dest, table.schema) as writer:
        for batch in table.to_batches(max_chunksize=CHUNK_SIZE):
            writer.write_batch(batch)
            done += batch.num_rows
            _print_progress(done, total, "writing")
    print()