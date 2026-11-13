"""Format-specific readers exposing a uniform metadata/inspection API.

Each reader avoids loading full row data for shape/columns/dtypes/head where
the file format allows it (parquet, sas7bdat carry that info in a header).
CSV/TXT have no embedded schema, so dtype inspection samples the first
DTYPE_SAMPLE_ROWS rows.
"""

from __future__ import annotations

import importlib.util
import io
import os
import re
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pa_parquet

from pytae.other_utilities import safe_reset_index

DEFAULT_CHUNK_SIZE = 200_000
CHUNK_SIZE = DEFAULT_CHUNK_SIZE
DTYPE_SAMPLE_ROWS = 10_000


def _split_path_suffixes(path: Path) -> tuple[str, str | None]:
    """Return (base_suffix, compression) e.g. ('.csv', 'gzip') or ('.parquet', None)."""
    suffixes = [s.lower() for s in path.suffixes]
    if not suffixes:
        return ("", None)
    if suffixes[-1] == ".gz":
        base = suffixes[-2] if len(suffixes) >= 2 else ""
        return (base, "gzip")
    return (suffixes[-1], None)


def _delimited_dtypes(path: Path, *, sep: str, encoding: str | None, compression: str | None = None) -> pd.Series:
    return pd.read_csv(
        path, sep=sep, encoding=encoding, nrows=DTYPE_SAMPLE_ROWS, low_memory=False, compression=compression
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

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
        if not progress:
            df = self.to_polars(columns=columns, nrows=nrows).to_pandas()
            if "_pt_by" in df.attrs:
                del df.attrs["_pt_by"]
            return df
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
            res = pd.concat(parts, ignore_index=True)
            if "_pt_by" in res.attrs:
                del res.attrs["_pt_by"]
            return res
        empty = self._empty()
        res = empty[columns] if columns else empty
        if "_pt_by" in res.attrs:
            del res.attrs["_pt_by"]
        return res

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        import polars as pl

        return pl.read_parquet(self.path, columns=columns, n_rows=nrows, memory_map=False)

    def to_polars_lazy(self, columns: list[str] | None = None):
        import polars as pl

        lf = pl.scan_parquet(self.path)
        if columns is not None:
            lf = lf.select(columns)
        return lf


class CsvReader:
    _file_kind = "CSV"

    def __init__(
        self,
        path: Path,
        sep: str = ",",
        encoding: str | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        compression: str | None = None,
        **reader_kwargs: Any,
    ) -> None:
        self.path = path
        self.sep = sep
        self.encoding = encoding
        self.chunk_size = chunk_size
        self.compression = compression
        self.reader_kwargs = reader_kwargs

    def shape(self) -> tuple[int, int]:
        n_cols = len(self.columns())
        total = 0
        pd_kwargs = {}
        if "skiprows" in self.reader_kwargs:
            pd_kwargs["skiprows"] = self.reader_kwargs["skiprows"]
        elif "skip_rows" in self.reader_kwargs:
            pd_kwargs["skiprows"] = self.reader_kwargs["skip_rows"]
        for chunk in pd.read_csv(
            self.path,
            sep=self.sep,
            encoding=self.encoding,
            usecols=[0],
            chunksize=self.chunk_size,
            low_memory=False,
            compression=self.compression,
            **pd_kwargs,
        ):
            total += len(chunk)
        return (total, n_cols)

    def columns(self) -> list[str]:
        try:
            pd_kwargs = {}
            if "skiprows" in self.reader_kwargs:
                pd_kwargs["skiprows"] = self.reader_kwargs["skiprows"]
            elif "skip_rows" in self.reader_kwargs:
                pd_kwargs["skiprows"] = self.reader_kwargs["skip_rows"]
            return pd.read_csv(
                self.path,
                sep=self.sep,
                encoding=self.encoding,
                nrows=0,
                low_memory=False,
                compression=self.compression,
                **pd_kwargs,
            ).columns.tolist()
        except pd.errors.EmptyDataError as exc:
            raise ValueError(f"'{self.path.name}' is empty or not a valid {self._file_kind} file") from exc

    def dtypes(self) -> pd.Series:
        return _delimited_dtypes(self.path, sep=self.sep, encoding=self.encoding, compression=self.compression)

    def head(self, n: int) -> pd.DataFrame:
        pd_kwargs = {}
        if "skiprows" in self.reader_kwargs:
            pd_kwargs["skiprows"] = self.reader_kwargs["skiprows"]
        elif "skip_rows" in self.reader_kwargs:
            pd_kwargs["skiprows"] = self.reader_kwargs["skip_rows"]
        return pd.read_csv(
            self.path,
            sep=self.sep,
            encoding=self.encoding,
            nrows=n,
            low_memory=False,
            compression=self.compression,
            **pd_kwargs,
        )

    def tail(self, n: int) -> pd.DataFrame:
        total = self.shape()[0]
        skip = range(1, max(total - n, 0) + 1)  # keep the header (row 0), skip everything before the tail
        return pd.read_csv(
            self.path,
            sep=self.sep,
            encoding=self.encoding,
            skiprows=skip,
            low_memory=False,
            compression=self.compression,
        )

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
        if not progress:
            if not self.reader_kwargs and (self.encoding is None or self.encoding.lower() in ("utf-8", "utf8")):
                try:
                    return self.to_polars(columns=columns, nrows=nrows).to_pandas()
                except Exception:
                    pass
            pd_kwargs = dict(self.reader_kwargs)
            return pd.read_csv(
                self.path,
                sep=self.sep,
                encoding=self.encoding,
                usecols=columns,
                nrows=nrows,
                low_memory=False,
                compression=self.compression,
                **pd_kwargs,
            )
        total = self.shape()[0] if nrows is None else min(nrows, self.shape()[0])
        chunks, done = [], 0
        csize = chunk_size or self.chunk_size
        pd_kwargs = dict(self.reader_kwargs)
        reader = pd.read_csv(
            self.path,
            sep=self.sep,
            encoding=self.encoding,
            usecols=columns,
            chunksize=csize,
            nrows=nrows,
            low_memory=False,
            compression=self.compression,
            **pd_kwargs,
        )
        for chunk in reader:
            chunks.append(chunk)
            done += len(chunk)
            _print_progress(done, total, "reading")
        print()
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns or [])

    def to_polars(
        self,
        columns: list[str] | None = None,
        nrows: int | None = None,
        infer_schema_length: int | None = 10000,
    ):
        import polars as pl

        null_vals = ["", '""', "NA", "NaN", "null", "None", "NULL", "nan", "n/a", "N/A", "<NA>"]
        skip_rows = self.reader_kwargs.get("skip_rows", self.reader_kwargs.get("skiprows", 0))
        if isinstance(skip_rows, int):
            try:
                return pl.read_csv(
                    self.path,
                    separator=self.sep,
                    columns=columns,
                    n_rows=nrows,
                    encoding=self.encoding or "utf8",
                    null_values=null_vals,
                    truncate_ragged_lines=True,
                    infer_schema_length=infer_schema_length,
                    skip_rows=skip_rows,
                )
            except pl.exceptions.ComputeError:
                if infer_schema_length is not None:
                    try:
                        return pl.read_csv(
                            self.path,
                            separator=self.sep,
                            columns=columns,
                            n_rows=nrows,
                            encoding=self.encoding or "utf8",
                            null_values=null_vals,
                            truncate_ragged_lines=True,
                            infer_schema_length=None,
                            skip_rows=skip_rows,
                        )
                    except Exception:
                        pass
                return pl.from_pandas(self.to_dataframe(columns=columns, nrows=nrows))
            except Exception:
                return pl.from_pandas(self.to_dataframe(columns=columns, nrows=nrows))
        return pl.from_pandas(self.to_dataframe(columns=columns, nrows=nrows))

    def to_polars_lazy(self, columns: list[str] | None = None, infer_schema_length: int | None = 10000):
        import polars as pl

        skip_rows = self.reader_kwargs.get("skip_rows", self.reader_kwargs.get("skiprows", 0))
        skip_kw = {"skip_rows": skip_rows} if isinstance(skip_rows, int) else {}
        try:
            lf = pl.scan_csv(
                self.path,
                separator=self.sep,
                encoding=self.encoding or "utf8",
                null_values=["", '""', "NA", "NaN", "null", "None", "NULL", "nan", "n/a", "N/A", "<NA>"],
                truncate_ragged_lines=True,
                infer_schema_length=infer_schema_length,
                **skip_kw,
            )
            if columns is not None:
                lf = lf.select(columns)
            return lf
        except Exception:
            return self.to_polars(columns=columns, infer_schema_length=infer_schema_length).lazy()


class TxtReader(CsvReader):
    """Reads delimited .txt/.dat files (tab-delimited for .txt, pipe-delimited for .dat by default)."""

    _file_kind = "delimited"

    def __init__(
        self,
        path: Path,
        sep: str = "\t",
        encoding: str | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        compression: str | None = None,
        **reader_kwargs: Any,
    ) -> None:
        super().__init__(path, sep=sep, encoding=encoding, chunk_size=chunk_size, compression=compression, **reader_kwargs)


class SasReader:
    """Reads .sas7bdat files. Row count/columns come from the file header,
    so shape/columns are cheap; dtype inspection reads a small sample."""

    def __init__(self, path: Path, encoding: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.path = path
        self.encoding = "latin-1" if encoding is None else encoding
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

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
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

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        import polars as pl

        return pl.from_pandas(self.to_dataframe(columns=columns, nrows=nrows))


class ExcelReader:
    """Reads Excel (.xlsx, .xls, .xlsm, .xlsb) files via pandas and converts to Polars."""

    def __init__(
        self,
        path: Path,
        sheet_name: str | int = 0,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        **reader_kwargs: Any,
    ) -> None:
        self.path = Path(path)
        kwargs = dict(reader_kwargs)
        if "sheet" in kwargs and "sheet_name" not in kwargs:
            sheet_name = kwargs.pop("sheet")
        elif "sheet_name" in kwargs:
            sheet_name = kwargs.pop("sheet_name")
        self.sheet_name = sheet_name
        self.chunk_size = chunk_size
        self.reader_kwargs = kwargs
        self._cached_df: Any = None

    def _load(self) -> Any:
        if self._cached_df is None:
            import pandas as pd

            opts = dict(self.reader_kwargs)
            opts.setdefault("sheet_name", self.sheet_name)
            self._cached_df = pd.read_excel(self.path, **opts)
        return self._cached_df

    def shape(self) -> tuple[int, int]:
        df = self._load()
        return (len(df), len(df.columns))

    def columns(self) -> list[str]:
        df = self._load()
        return [str(c) for c in df.columns]

    def dtypes(self) -> Any:
        df = self._load()
        return df.dtypes

    def sheet_names(self) -> list[str]:
        import pandas as pd

        excel = pd.ExcelFile(self.path)
        return list(excel.sheet_names)

    def head(self, n: int) -> Any:
        df = self._load()
        return df.head(n)

    def tail(self, n: int) -> Any:
        df = self._load()
        return df.tail(n)

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> Any:
        df = self._load()
        if nrows is not None:
            df = df.iloc[:nrows]
        if columns is not None:
            df = df[columns]
        return df

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        import polars as pl

        df = self.to_dataframe(columns=columns, nrows=nrows)
        try:
            return pl.from_pandas(df)
        except Exception:
            df_c = df.copy()
            for col in df_c.columns:
                if df_c[col].dtype == object:
                    df_c[col] = df_c[col].astype(str)
            return pl.from_pandas(df_c)

    def to_polars_lazy(self, columns: list[str] | None = None):
        return self.to_polars(columns=columns).lazy()


class JsonlReader:
    """Reads line-delimited JSON (.jsonl / .ndjson) files."""

    def __init__(
        self,
        path: Path,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        compression: str | None = None,
    ) -> None:
        self.path = path
        self.chunk_size = chunk_size
        self.compression = compression

    def shape(self) -> tuple[int, int]:
        n_cols = len(self.columns())
        total = 0
        for chunk in pd.read_json(
            self.path,
            lines=True,
            chunksize=self.chunk_size,
            compression=self.compression,
        ):
            total += len(chunk)
        return (total, n_cols)

    def columns(self) -> list[str]:
        try:
            cols = pd.read_json(
                self.path,
                lines=True,
                nrows=1,
                compression=self.compression,
            ).columns.tolist()
            if not cols:
                raise ValueError(f"'{self.path.name}' is empty or not a valid JSON Lines file")
            return cols
        except Exception as exc:
            if isinstance(exc, ValueError) and "is empty or not a valid JSON Lines file" in str(exc):
                raise
            raise ValueError(f"'{self.path.name}' is empty or not a valid JSON Lines file") from exc

    def dtypes(self) -> pd.Series:
        return pd.read_json(
            self.path,
            lines=True,
            nrows=DTYPE_SAMPLE_ROWS,
            compression=self.compression,
        ).dtypes

    def head(self, n: int) -> pd.DataFrame:
        if n <= 0:
            return pd.DataFrame(columns=self.columns())
        return pd.read_json(
            self.path,
            lines=True,
            nrows=n,
            compression=self.compression,
        )

    def tail(self, n: int) -> pd.DataFrame:
        df = self.to_dataframe()
        return df.tail(n)

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
        if not progress:
            df = pd.read_json(
                self.path,
                lines=True,
                nrows=nrows,
                compression=self.compression,
            )
            return df[columns] if columns else df
        total = self.shape()[0] if nrows is None else min(nrows, self.shape()[0])
        chunks, done = [], 0
        csize = chunk_size or self.chunk_size
        for chunk in pd.read_json(
            self.path,
            lines=True,
            chunksize=csize,
            nrows=nrows,
            compression=self.compression,
        ):
            chunks.append(chunk)
            done += len(chunk)
            _print_progress(done, total, "reading")
        print()
        df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        return df[columns] if columns else df

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        import polars as pl

        try:
            df = pl.read_ndjson(self.path)
            if nrows is not None:
                df = df.head(nrows)
            if columns is not None:
                df = df.select(columns)
            return df
        except Exception:
            return pl.from_pandas(self.to_dataframe(columns=columns, nrows=nrows))

    def to_polars_lazy(self, columns: list[str] | None = None):
        import polars as pl

        try:
            lf = pl.scan_ndjson(self.path)
            if columns is not None:
                lf = lf.select(columns)
            return lf
        except Exception:
            return self.to_polars(columns=columns).lazy()


class StdinReader:
    """Reader for data piped via STDIN, buffered in memory."""

    def __init__(
        self,
        data: bytes,
        *,
        fmt: str | None = None,
        sep: str | None = None,
        encoding: str | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self.data = data
        self.path = Path("<stdin>")
        self.chunk_size = chunk_size
        self.sep = sep
        self.encoding = encoding
        self.fmt = fmt
        self._df = self._load()

    def _load(self) -> pd.DataFrame:
        if not self.data:
            return pd.DataFrame()
        fmt = (self.fmt or "").lower().strip()
        if fmt in ("parquet", "pq") or (not fmt and self.data.startswith(b"PAR1")):
            return pd.read_parquet(io.BytesIO(self.data))
        if fmt in ("jsonl", "ndjson") or (not fmt and self.data.lstrip()[:1] in (b"{", b"[")):
            return pd.read_json(io.BytesIO(self.data), orient="records", lines=True)
        # Delimited text (CSV, TSV, etc.)
        sep = self.sep
        if sep is None:
            first_line = self.data.split(b"\n", 1)[0]
            if b"\t" in first_line and b"," not in first_line:
                sep = "\t"
            elif b"|" in first_line and b"," not in first_line:
                sep = "|"
            else:
                sep = ","
        compression = "gzip" if self.data.startswith(b"\x1f\x8b") else None
        return pd.read_csv(io.BytesIO(self.data), sep=sep, encoding=self.encoding, compression=compression)

    def shape(self) -> tuple[int, int]:
        return self._df.shape

    def columns(self) -> list[str]:
        return list(self._df.columns)

    def dtypes(self) -> pd.Series:
        return self._df.dtypes

    def head(self, n: int) -> pd.DataFrame:
        return self._df.head(n)

    def tail(self, n: int) -> pd.DataFrame:
        return self._df.tail(n)

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
        out = self._df
        if columns is not None:
            out = out[columns]
        if nrows is not None:
            out = out.iloc[:nrows]
        return out

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        import polars as pl

        return pl.from_pandas(self.to_dataframe(columns=columns, nrows=nrows))

    def to_polars_lazy(self, columns: list[str] | None = None):
        return self.to_polars(columns=columns).lazy()


class DataFrameReader:
    """Reader wrapping an in-memory DataFrame (e.g. from clipboard or memory)."""

    def __init__(self, df: Any, path: Path | str = "<dataframe>") -> None:
        from pytae.dataframe import DataFrame as PytaeDataFrame

        if isinstance(df, PytaeDataFrame):
            df = df._df
        self._df = df
        self.path = Path(str(path))

    def shape(self) -> tuple[int, int]:
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            names = list(self._df.collect_schema().names() if hasattr(self._df, "collect_schema") else self._df.columns)
            return (-1, len(names))
        return self._df.shape

    def columns(self) -> list[str]:
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            return list(self._df.collect_schema().names() if hasattr(self._df, "collect_schema") else self._df.columns)
        return list(self._df.columns)

    def dtypes(self) -> pd.Series:
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            return pd.Series({col: str(dtype) for col, dtype in self._df.schema.items()})
        if isinstance(self._df, pl.DataFrame):
            return self._df.head(0).to_pandas().dtypes
        return self._df.dtypes

    def head(self, n: int) -> Any:
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            return self._df.head(n).collect()
        return self._df.head(n)

    def tail(self, n: int) -> Any:
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            return self._df.tail(n).collect()
        return self._df.tail(n)

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            return self.to_polars(columns=columns, nrows=nrows).to_pandas()
        if isinstance(self._df, pl.DataFrame):
            out_pl = self._df
            if columns is not None:
                out_pl = out_pl.select(columns)
            if nrows is not None:
                out_pl = out_pl.head(nrows)
            return out_pl.to_pandas()
        out = self._df
        if columns is not None:
            out = out[columns]
        if nrows is not None:
            out = out.iloc[:nrows]
        return out

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            lf = self._df
            if nrows is not None:
                lf = lf.head(nrows)
            if columns is not None:
                lf = lf.select(columns)
            return lf.collect()
        df = self._df if isinstance(self._df, pl.DataFrame) else pl.from_pandas(self._df)
        if nrows is not None:
            df = df.head(nrows)
        if columns is not None:
            df = df.select(columns)
        return df

    def to_polars_lazy(self, columns: list[str] | None = None):
        import polars as pl

        if isinstance(self._df, pl.LazyFrame):
            lf = self._df
            if columns is not None:
                lf = lf.select(columns)
            return lf
        return self.to_polars(columns=columns).lazy()


class IpcReader:
    def __init__(self, path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.path = path
        self.chunk_size = chunk_size

    def shape(self) -> tuple[int, int]:
        import polars as pl

        lf = pl.scan_ipc(self.path)
        n_rows = lf.select(pl.len()).collect().item()
        n_cols = len(lf.collect_schema().names())
        return (n_rows, n_cols)

    def columns(self) -> list[str]:
        import polars as pl

        return list(pl.read_ipc_schema(self.path).keys())

    def dtypes(self) -> pd.Series:
        import polars as pl

        return pl.read_ipc(self.path, n_rows=0).to_pandas().dtypes

    def head(self, n: int) -> pd.DataFrame:
        import polars as pl

        if n <= 0:
            return pl.read_ipc(self.path, n_rows=0).to_pandas()
        return pl.read_ipc(self.path, n_rows=n).to_pandas()

    def tail(self, n: int) -> pd.DataFrame:
        import polars as pl

        if n <= 0:
            return pl.read_ipc(self.path, n_rows=0).to_pandas()
        return pl.scan_ipc(self.path).tail(n).collect().to_pandas()

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
        return self.to_polars(columns=columns, nrows=nrows).to_pandas()

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        import polars as pl

        return pl.read_ipc(self.path, columns=columns, n_rows=nrows)

    def to_polars_lazy(self, columns: list[str] | None = None):
        import polars as pl

        lf = pl.scan_ipc(self.path)
        if columns is not None:
            lf = lf.select(columns)
        return lf


class GlobReader:
    """Unified multi-file reader for glob patterns or directories of tabular files."""

    def __init__(
        self,
        path: Path,
        *,
        sep: str | None = None,
        encoding: str | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        sheet_name: str | int | None = None,
        **reader_kwargs: Any,
    ) -> None:
        import glob as _glob

        self.path = path
        self.sep = sep
        self.encoding = encoding
        self.chunk_size = chunk_size
        self.sheet_name = sheet_name
        self.reader_kwargs = dict(reader_kwargs)

        raw_str = str(path.expanduser())
        if path.exists() and path.is_dir():
            candidates: list[Path] = []
            for ext in (
                ".parquet",
                ".pq",
                ".ipc",
                ".arrow",
                ".feather",
                ".csv",
                ".jsonl",
                ".ndjson",
                ".txt",
                ".dat",
                ".xlsx",
                ".xls",
                ".xlsm",
                ".xlsb",
            ):
                found = sorted(path.glob(f"*{ext}"))
                if not found:
                    found = sorted(path.rglob(f"*{ext}"))
                if found:
                    candidates = found
                    break
            if not candidates:
                raise FileNotFoundError(f"no supported data files found in directory: {path}")
            self.files = candidates
        else:
            matches = sorted(Path(p) for p in _glob.glob(raw_str, recursive=True) if Path(p).is_file())
            if not matches:
                raise FileNotFoundError(f"no files matched pattern: {path}")
            self.files = matches

        self._first_reader = get_reader(
            self.files[0],
            sep=sep,
            encoding=encoding,
            chunk_size=chunk_size,
            sheet_name=sheet_name,
            **self.reader_kwargs,
        )

    def shape(self) -> tuple[int, int]:
        lf = self.to_polars_lazy()
        import polars as pl

        rows = int(lf.select(pl.len()).collect().item())
        cols = len(self.columns())
        return (rows, cols)

    def columns(self) -> list[str]:
        return self._first_reader.columns()

    def dtypes(self) -> pd.Series:
        return self._first_reader.dtypes()

    def head(self, n: int) -> pd.DataFrame:
        if n <= 0:
            return self.to_polars(nrows=0).to_pandas()
        return self.to_polars(nrows=n).to_pandas()

    def tail(self, n: int) -> pd.DataFrame:
        if n <= 0:
            return self.to_polars(nrows=0).to_pandas()
        return self.to_polars_lazy().tail(n).collect().to_pandas()

    def to_dataframe(
        self,
        columns: list[str] | None = None,
        progress: bool = False,
        nrows: int | None = None,
        chunk_size: int | None = None,
    ) -> pd.DataFrame:
        return self.to_polars(columns=columns, nrows=nrows).to_pandas()

    def to_polars(self, columns: list[str] | None = None, nrows: int | None = None):
        lf = self.to_polars_lazy(columns=columns)
        if nrows is not None:
            lf = lf.head(nrows)
        return lf.collect()

    def to_polars_lazy(self, columns: list[str] | None = None):
        import polars as pl

        suffix, compression = _split_path_suffixes(self.files[0])
        if compression is None and (self.encoding is None or self.encoding.lower() in ("utf-8", "utf8")):
            try:
                if suffix in (".parquet", ".pq"):
                    lf = pl.scan_parquet(self.files)
                    return lf.select(columns) if columns is not None else lf
                if suffix in (".ipc", ".arrow", ".feather"):
                    lf = pl.scan_ipc(self.files)
                    return lf.select(columns) if columns is not None else lf
                if suffix in (".csv", ".txt", ".dat"):
                    eff_sep = self.sep or (_TXT_DEFAULT_SEP.get(suffix, ","))
                    lf = pl.scan_csv(self.files, separator=eff_sep, infer_schema_length=10000)
                    return lf.select(columns) if columns is not None else lf
                if suffix in (".jsonl", ".ndjson"):
                    lf = pl.scan_ndjson(self.files)
                    return lf.select(columns) if columns is not None else lf
            except Exception:
                pass

        frames = [
            get_reader(
                f,
                sep=self.sep,
                encoding=self.encoding,
                chunk_size=self.chunk_size,
                sheet_name=self.sheet_name,
                **self.reader_kwargs,
            ).to_polars(columns=columns)
            for f in self.files
        ]
        combined = pl.concat(frames, how="diagonal_relaxed")
        return combined.lazy()


_READERS = {
    ".parquet": ParquetReader,
    ".pq": ParquetReader,
    ".ipc": IpcReader,
    ".arrow": IpcReader,
    ".feather": IpcReader,
    ".csv": CsvReader,
    ".txt": TxtReader,
    ".dat": TxtReader,
    ".sas7bdat": SasReader,
    ".jsonl": JsonlReader,
    ".ndjson": JsonlReader,
    ".xlsx": ExcelReader,
    ".xls": ExcelReader,
    ".xlsm": ExcelReader,
    ".xlsb": ExcelReader,
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


def _normalize_source(source: Any, *, _force_nt: bool = False) -> Any:
    """Normalize Git Bash / MSYS paths on Windows when source is a path string, Path, or list of them."""
    if is_db_or_cloud_uri(source):
        return _normalize_uri(source)
    if isinstance(source, (str, Path)):
        from pytae.cli_parsing import normalize_git_bash_path

        return normalize_git_bash_path(str(source), _force_nt=_force_nt)
    elif isinstance(source, (list, tuple)):
        from pytae.cli_parsing import normalize_git_bash_path

        return [normalize_git_bash_path(str(s), _force_nt=_force_nt) for s in source]
    return source


def is_db_or_cloud_uri(s: Any) -> bool:
    """Return True if s is a supported database or cloud storage URI."""
    if not isinstance(s, (str, Path)):
        return False
    s_str = str(s).strip().lower()
    return any(
        s_str.startswith(pfx)
        for pfx in (
            "sqlite://",
            "sqlite:/",
            "duckdb://",
            "duckdb:/",
            "s3://",
            "s3:/",
            "gcs://",
            "gcs:/",
            "gs://",
            "gs:/",
        )
    )


def _normalize_uri(s: str | Path) -> str:
    s_str = str(s).strip()
    for pfx in ("sqlite", "duckdb", "s3", "gcs", "gs"):
        if s_str.lower().startswith(f"{pfx}:///"):
            return s_str
        if s_str.lower().startswith(f"{pfx}://"):
            return s_str
        if s_str.lower().startswith(f"{pfx}:/"):
            rest = s_str[len(pfx) + 1 :]
            if pfx in ("sqlite", "duckdb"):
                return f"{pfx}://{rest}"
            else:
                return f"{pfx}://{rest.lstrip('/')}"
    return s_str


def parse_db_uri(uri: str | Path) -> tuple[str, str, str]:
    """Parse a sqlite:// or duckdb:// URI.

    Returns: (scheme, db_path, target)
      where target is a table name or SQL query string (or empty if omitted).
    """
    clean = _normalize_uri(uri)
    scheme, _, rest = clean.partition("://")
    scheme = scheme.lower()
    if ":" in rest:
        p_part, _, target = rest.rpartition(":")
        if len(p_part) == 1 and p_part.isalpha():
            p_part = rest
            target = ""
    else:
        p_part = rest
        target = ""
    return scheme, p_part.strip(), target.strip()


def read_uri(uri: str | Path, **opts: Any) -> tuple[Path, Any]:
    """Read a dataset from a database (sqlite://, duckdb://) or cloud URI (s3://, gcs://, gs://)."""
    import polars as pl

    clean = _normalize_uri(uri)
    scheme = clean.split("://", 1)[0].lower()

    if scheme == "sqlite":
        import sqlite3

        _, db_path_str, target = parse_db_uri(clean)
        db_path = Path(db_path_str).expanduser()
        if not db_path.exists():
            raise FileNotFoundError(f"SQLite database file not found: {db_path}")

        conn = sqlite3.connect(str(db_path))
        try:
            if not target:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row[0] for row in cursor.fetchall()]
                if len(tables) == 1:
                    target = tables[0]
                elif not tables:
                    raise ValueError(f"SQLite database '{db_path.name}' contains no user tables.")
                else:
                    raise ValueError(
                        f"Table name required for sqlite URI: sqlite://{db_path.name}:<table_name>. "
                        f"Available tables: {', '.join(tables)}"
                    )

            if re.match(r"^\s*select\s+", target, re.IGNORECASE):
                query = target
                tbl_label = "query"
            else:
                query = f'SELECT * FROM "{target}"'
                tbl_label = target

            nrows = opts.pop("nrows", None) or opts.pop("n_rows", None)
            if nrows is not None:
                query = f"{query.rstrip(';')} LIMIT {int(nrows)}"

            df = pl.read_database(query, conn)
            return Path(f"sqlite://{db_path.name}:{tbl_label}"), df
        finally:
            conn.close()

    if scheme == "duckdb":
        try:
            import duckdb
        except ImportError:
            raise ImportError(
                "duckdb is required to read duckdb:// URIs. Install it with: pip install duckdb"
            ) from None

        _, db_path_str, target = parse_db_uri(clean)
        if db_path_str in (":memory:", ""):
            conn = duckdb.connect()
            db_name = ":memory:"
        else:
            db_path = Path(db_path_str).expanduser()
            if not db_path.exists():
                raise FileNotFoundError(f"DuckDB database file not found: {db_path}")
            conn = duckdb.connect(str(db_path), read_only=True)
            db_name = db_path.name

        try:
            if not target:
                cursor = conn.cursor()
                tables = [row[0] for row in cursor.execute("SHOW TABLES").fetchall()]
                if len(tables) == 1:
                    target = tables[0]
                elif not tables:
                    raise ValueError(f"DuckDB database '{db_name}' contains no user tables.")
                else:
                    raise ValueError(
                        f"Table name required for duckdb URI: duckdb://{db_name}:<table_name>. "
                        f"Available tables: {', '.join(tables)}"
                    )

            if re.match(r"^\s*select\s+", target, re.IGNORECASE):
                query = target
                tbl_label = "query"
            else:
                query = f'SELECT * FROM "{target}"'
                tbl_label = target

            nrows = opts.pop("nrows", None) or opts.pop("n_rows", None)
            if nrows is not None:
                query = f"{query.rstrip(';')} LIMIT {int(nrows)}"

            if hasattr(conn, "sql"):
                rel = conn.sql(query)
            elif hasattr(conn, "query"):
                rel = conn.query(query)
            else:
                rel = conn.execute(query)

            if hasattr(rel, "pl"):
                df = rel.pl()
            elif hasattr(rel, "arrow"):
                arrow_obj = rel.arrow()
                arrow_tbl = arrow_obj.read_all() if hasattr(arrow_obj, "read_all") else arrow_obj
                df = pl.from_arrow(arrow_tbl)
            elif hasattr(rel, "to_arrow_table"):
                df = pl.from_arrow(rel.to_arrow_table())
            elif hasattr(rel, "fetch_arrow_table"):
                df = pl.from_arrow(rel.fetch_arrow_table())
            elif hasattr(conn, "fetch_arrow_table"):
                df = pl.from_arrow(conn.fetch_arrow_table())
            elif hasattr(rel, "df"):
                df = pl.from_pandas(rel.df())
            else:
                df = pl.from_pandas(conn.df())
            if not isinstance(df, pl.DataFrame):
                df = pl.DataFrame(df)
            return Path(f"duckdb://{db_name}:{tbl_label}"), df
        finally:
            conn.close()

    if scheme in ("s3", "gcs", "gs"):
        fmt = opts.pop("fmt", opts.pop("format", None))
        low = clean.lower()
        if fmt:
            fmt = fmt.lower().lstrip(".")
        elif any(low.endswith(ext) for ext in (".parquet", ".pq")):
            fmt = "parquet"
        elif any(low.endswith(ext) for ext in (".csv", ".tsv", ".txt", ".dat")):
            fmt = "csv"
        elif any(low.endswith(ext) for ext in (".ipc", ".arrow", ".feather")):
            fmt = "ipc"
        elif any(low.endswith(ext) for ext in (".ndjson", ".jsonl")):
            fmt = "ndjson"
        else:
            fmt = "parquet"

        nrows = opts.pop("nrows", None) or opts.pop("n_rows", None)
        if fmt == "parquet":
            if nrows is not None:
                df = pl.scan_parquet(clean, **opts).head(nrows).collect()
            else:
                df = pl.read_parquet(clean, **opts)
        elif fmt == "csv":
            sep = opts.pop("sep", None) or opts.pop("delimiter", None)
            if sep:
                opts["separator"] = sep
            if nrows is not None:
                opts["n_rows"] = nrows
            df = pl.read_csv(clean, **opts)
        elif fmt == "ipc":
            if nrows is not None:
                df = pl.scan_ipc(clean, **opts).head(nrows).collect()
            else:
                df = pl.read_ipc(clean, **opts)
        elif fmt == "ndjson":
            if nrows is not None:
                df = pl.scan_ndjson(clean, **opts).head(nrows).collect()
            else:
                df = pl.read_ndjson(clean, **opts)
        else:
            raise ValueError(f"Unsupported cloud file format '{fmt}' for URI: {clean}")

        cloud_name = clean.rstrip("/").rpartition("/")[2] or clean
        return Path(cloud_name), df

    raise ValueError(f"Unsupported database/cloud URI scheme: '{scheme}' in '{uri}'")


def scan_uri(uri: str | Path, **opts: Any) -> tuple[Path, Any]:
    """Lazily scan a dataset from a database (sqlite://, duckdb://) or cloud URI (s3://, gcs://, gs://)."""
    import polars as pl

    clean = _normalize_uri(uri)
    scheme = clean.split("://", 1)[0].lower()

    if scheme in ("sqlite", "duckdb"):
        p, df = read_uri(clean, **opts)
        return p, df.lazy()

    if scheme in ("s3", "gcs", "gs"):
        fmt = opts.pop("fmt", opts.pop("format", None))
        low = clean.lower()
        if fmt:
            fmt = fmt.lower().lstrip(".")
        elif any(low.endswith(ext) for ext in (".parquet", ".pq")):
            fmt = "parquet"
        elif any(low.endswith(ext) for ext in (".csv", ".tsv", ".txt", ".dat")):
            fmt = "csv"
        elif any(low.endswith(ext) for ext in (".ipc", ".arrow", ".feather")):
            fmt = "ipc"
        elif any(low.endswith(ext) for ext in (".ndjson", ".jsonl")):
            fmt = "ndjson"
        else:
            fmt = "parquet"

        if fmt == "parquet":
            lf = pl.scan_parquet(clean, **opts)
        elif fmt == "csv":
            sep = opts.pop("sep", None) or opts.pop("delimiter", None)
            if sep:
                opts["separator"] = sep
            lf = pl.scan_csv(clean, **opts)
        elif fmt == "ipc":
            lf = pl.scan_ipc(clean, **opts)
        elif fmt == "ndjson":
            lf = pl.scan_ndjson(clean, **opts)
        else:
            raise ValueError(f"Unsupported cloud file format '{fmt}' for scanning URI: {clean}")

        cloud_name = clean.rstrip("/").rpartition("/")[2] or clean
        return Path(cloud_name), lf

    raise ValueError(f"Unsupported database/cloud URI scheme: '{scheme}' in '{uri}'")


def get_reader(
    path: Path | str,
    *,
    sep: str | None = None,
    encoding: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    sheet_name: str | int | None = None,
    **reader_kwargs: Any,
):
    if is_db_or_cloud_uri(path):
        p, df = read_uri(path, sep=sep, encoding=encoding, chunk_size=chunk_size, sheet_name=sheet_name, **reader_kwargs)
        return DataFrameReader(df, path=p)
    path = Path(_normalize_source(path))
    if (path.exists() and path.is_dir()) or (not path.exists() and any(ch in str(path) for ch in "*?[")):
        return GlobReader(
            path,
            sep=sep,
            encoding=encoding,
            chunk_size=chunk_size,
            sheet_name=sheet_name,
            **reader_kwargs,
        )
    suffix, compression = _split_path_suffixes(path)
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
            module_spec = importlib.util.spec_from_file_location("_pytae_external_connections", module_path)
            if module_spec is None or module_spec.loader is None:
                raise ImportError(f"cannot load connections module from '{module_path}'")
            _EXTERNAL_CONNECTIONS_MODULE = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(_EXTERNAL_CONNECTIONS_MODULE)
        return _EXTERNAL_CONNECTIONS_MODULE.build_yaml_reader(path)
    try:
        cls = _READERS[suffix]
    except KeyError:
        supported = ", ".join(
            sorted((*_READERS, *_YAML_SUFFIXES, ".csv.gz", ".txt.gz", ".dat.gz", ".jsonl.gz", ".ndjson.gz"))
        )
        raise ValueError(f"unsupported file type '{path.suffix or path.name}'; supported: {supported}") from None
    if cls is CsvReader:
        return CsvReader(
            path,
            sep=sep or ",",
            encoding=encoding,
            chunk_size=chunk_size,
            compression=compression,
            **reader_kwargs,
        )
    if cls is TxtReader:
        return TxtReader(
            path,
            sep=sep or _TXT_DEFAULT_SEP[suffix],
            encoding=encoding or _TXT_DEFAULT_ENCODING.get(suffix),
            chunk_size=chunk_size,
            compression=compression,
            **reader_kwargs,
        )
    if cls is JsonlReader:
        return JsonlReader(path, chunk_size=chunk_size, compression=compression)
    if cls is SasReader:
        return SasReader(path, encoding=encoding, chunk_size=chunk_size)
    if cls is ExcelReader:
        sheet = reader_kwargs.pop("sheet_name", sheet_name)
        if sheet is None and "sheet" in reader_kwargs:
            sheet = reader_kwargs.pop("sheet")
        return ExcelReader(path, sheet_name=sheet or 0, chunk_size=chunk_size, **reader_kwargs)
    return cls(path, chunk_size=chunk_size)


# .sas7bdat is intentionally excluded: pandas has no writer for that format.
_WRITABLE_SUFFIXES = (
    ".parquet",
    ".pq",
    ".ipc",
    ".arrow",
    ".feather",
    ".csv",
    ".txt",
    ".dat",
    ".jsonl",
    ".ndjson",
    ".csv.gz",
    ".txt.gz",
    ".dat.gz",
    ".jsonl.gz",
    ".ndjson.gz",
)


def write_dataframe(
    df: Any,
    dest: Path,
    *,
    sep: str | None = None,
    encoding: str | None = None,
    progress: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    index: bool | None = None,
) -> None:
    import polars as pl

    if hasattr(df, "_df") and isinstance(df._df, (pl.DataFrame, pl.LazyFrame)):
        df = df._df

    if isinstance(df, pl.LazyFrame):
        suffix, compression = _split_path_suffixes(dest)
        if suffix in (".parquet", ".pq"):
            try:
                df.sink_parquet(dest)
                return
            except Exception:
                df = df.collect()
        elif suffix in (".ipc", ".arrow", ".feather"):
            try:
                df.sink_ipc(dest)
                return
            except Exception:
                df = df.collect()
        elif suffix == ".csv":
            if compression != "gzip" and (encoding is None or encoding.lower() in ("utf-8", "utf8")):
                try:
                    df.sink_csv(dest, separator=sep or ",")
                    return
                except Exception:
                    df = df.collect()
            else:
                df = df.collect()
        elif suffix in (".jsonl", ".ndjson"):
            if compression is None:
                try:
                    df.sink_ndjson(dest)
                    return
                except Exception:
                    df = df.collect()
            else:
                df = df.collect()
        else:
            df = df.collect()

    if isinstance(df, pl.DataFrame):
        suffix, compression = _split_path_suffixes(dest)
        if progress or (encoding is not None and encoding.lower() not in ("utf-8", "utf8")):
            df = df.to_pandas()
        else:
            if suffix in (".parquet", ".pq"):
                df.write_parquet(dest)
                return
            elif suffix in (".ipc", ".arrow", ".feather"):
                df.write_ipc(dest)
                return
            elif suffix == ".csv":
                df.write_csv(
                    dest,
                    separator=sep or ",",
                    compression="gzip" if compression == "gzip" else "uncompressed",
                )
                return
            elif suffix in _TXT_DEFAULT_SEP:
                df.write_csv(
                    dest,
                    separator=sep or _TXT_DEFAULT_SEP[suffix],
                    compression="gzip" if compression == "gzip" else "uncompressed",
                )
                return
            elif suffix in (".jsonl", ".ndjson"):
                if compression is None:
                    df.write_ndjson(dest)
                    return
                else:
                    df = df.to_pandas()
            else:
                supported = ", ".join(_WRITABLE_SUFFIXES)
                raise ValueError(f"unsupported output type '{suffix or dest.name}'; supported: {supported}")

    if hasattr(df, "attrs") and "_pt_by" in df.attrs:
        df = df.copy(deep=False)
        df.attrs = {k: v for k, v in df.attrs.items() if k != "_pt_by"}
    if index is None:
        index = not (isinstance(getattr(df, "index", None), pd.RangeIndex) and getattr(df.index, "name", None) is None)
    suffix, compression = _split_path_suffixes(dest)
    if suffix in (".parquet", ".pq"):
        _write_parquet(df, dest, progress=progress, chunk_size=chunk_size, index=index)
    elif suffix in (".ipc", ".arrow", ".feather"):
        pl.from_pandas(df).write_ipc(dest)
    elif suffix == ".csv":
        _write_delimited(
            df,
            dest,
            sep=sep or ",",
            encoding=encoding,
            progress=progress,
            chunk_size=chunk_size,
            index=index,
            compression=compression,
        )
    elif suffix in _TXT_DEFAULT_SEP:
        _write_delimited(
            df,
            dest,
            sep=sep or _TXT_DEFAULT_SEP[suffix],
            encoding=encoding or _TXT_DEFAULT_ENCODING.get(suffix),
            progress=progress,
            chunk_size=chunk_size,
            index=index,
            compression=compression,
        )
    elif suffix in (".jsonl", ".ndjson"):
        _write_jsonl(df, dest, progress=progress, chunk_size=chunk_size, compression=compression)
    else:
        supported = ", ".join(_WRITABLE_SUFFIXES)
        raise ValueError(f"unsupported output type '{suffix or dest.name}'; supported: {supported}")


def _write_delimited(
    df: pd.DataFrame,
    dest: Path,
    *,
    sep: str,
    encoding: str | None,
    progress: bool,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    index: bool = False,
    compression: str | None = None,
) -> None:
    total = len(df)
    if not progress or total == 0:
        df.to_csv(dest, sep=sep, encoding=encoding, index=index, compression=compression)
        return
    done = 0
    for start in range(0, total, chunk_size):
        chunk = df.iloc[start : start + chunk_size]
        chunk.to_csv(
            dest,
            sep=sep,
            encoding=encoding,
            index=index,
            mode="w" if start == 0 else "a",
            header=(start == 0),
            compression=compression,
        )
        done += len(chunk)
        _print_progress(done, total, "writing")
    print()


def _write_jsonl(
    df: pd.DataFrame,
    dest: Path,
    *,
    progress: bool,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    compression: str | None = None,
) -> None:
    df = safe_reset_index(df)
    total = len(df)
    if not progress or total == 0:
        df.to_json(dest, orient="records", lines=True, compression=compression)
        return
    done = 0
    for start in range(0, total, chunk_size):
        chunk = df.iloc[start : start + chunk_size]
        chunk.to_json(
            dest,
            orient="records",
            lines=True,
            mode="w" if start == 0 else "a",
            compression=compression,
        )
        done += len(chunk)
        _print_progress(done, total, "writing")
    print()


def _coerce_failing_parquet_column(df: pd.DataFrame, error_msg: str) -> str | None:
    match = re.search(r"Conversion failed for column (.+?) with type object", error_msg)
    if match:
        bad_col = match.group(1).strip()
        if bad_col in df.columns:
            df[bad_col] = df[bad_col].map(lambda v: str(v) if pd.notna(v) else None)
            warnings.warn(
                f"Column '{bad_col}' contained mixed object types; coerced to string for Parquet serialization.",
                UserWarning,
                stacklevel=3,
            )
            return bad_col
    return None


def _write_parquet(
    df: pd.DataFrame,
    dest: Path,
    *,
    progress: bool,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    index: bool = False,
) -> None:
    df_to_write = df
    max_retries = max(len(df.columns), 1)

    if not progress or len(df) == 0:
        for _ in range(max_retries + 1):
            try:
                df_to_write.to_parquet(dest, index=index)
                return
            except Exception as e:
                if df_to_write is df:
                    df_to_write = df.copy()
                if _coerce_failing_parquet_column(df_to_write, str(e)):
                    continue
                raise
        return

    table = None
    for _ in range(max_retries + 1):
        try:
            table = pa.Table.from_pandas(df_to_write, preserve_index=index)
            break
        except Exception as e:
            if df_to_write is df:
                df_to_write = df.copy()
            if _coerce_failing_parquet_column(df_to_write, str(e)):
                continue
            raise

    if table is None:
        table = pa.Table.from_pandas(df_to_write, preserve_index=index)

    total = table.num_rows
    done = 0
    with pa_parquet.ParquetWriter(dest, table.schema) as writer:
        for batch in table.to_batches(max_chunksize=chunk_size):
            writer.write_batch(batch)
            done += batch.num_rows
            _print_progress(done, total, "writing")
    print()


def read(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Read a dataset from a file path, URL, directory glob, list of files, or in-memory object into a pytae.DataFrame.

    Format is automatically detected from the file extension (.parquet, .csv, .tsv, .ipc,
    .feather, .arrow, .ndjson, .jsonl, .json, .xlsx, .sas7bdat). Format can also be explicitly
    specified via the `format=` or `fmt=` keyword argument.

    Examples:
        df = pt.read("data.parquet")
        df = pt.read("data.csv", sep=";")
        df = pt.read(["jan.parquet", "feb.parquet"])
        df = pt.read("lake_dir/")
        df = pt.read("logs/*.parquet")
    """
    import pandas as pd
    import polars as pl

    from pytae.dataframe import DataFrame

    if isinstance(source, DataFrame):
        return source

    if isinstance(source, (pl.DataFrame, pl.LazyFrame, pd.DataFrame)):
        return DataFrame(source)

    # Check for explicit format override
    fmt = kwargs.pop("format", kwargs.pop("fmt", None))

    if isinstance(source, (list, tuple)):
        if not source:
            return DataFrame(pl.DataFrame())
        norm_list = _normalize_source(source)
        first_p = Path(str(norm_list[0]))
        first_ext = ("." + fmt.lower().lstrip(".")) if fmt else first_p.suffix.lower()
        if first_ext in (".parquet", ".pq"):
            return DataFrame(pl.read_parquet([str(s) for s in norm_list], *args, **kwargs))
        elif first_ext in (".ipc", ".arrow", ".feather"):
            return DataFrame(pl.read_ipc([str(s) for s in norm_list], *args, **kwargs))
        else:
            dfs = [read(s, *args, **kwargs) for s in norm_list]
            return DataFrame(pl.concat([d._df for d in dfs]))

    norm_src = _normalize_source(source)
    if is_db_or_cloud_uri(norm_src):
        _, df = read_uri(norm_src, *args, **kwargs)
        return DataFrame(df)

    if fmt:
        fmt = fmt.lower().lstrip(".")
        if fmt in ("parquet", "pq"):
            return _read_parquet_impl(norm_src, *args, **kwargs)
        elif fmt in ("csv", "tsv", "txt"):
            return _read_csv_impl(norm_src, *args, **kwargs)
        elif fmt in ("ipc", "arrow", "feather"):
            return _read_ipc_impl(norm_src, *args, **kwargs)
        elif fmt in ("ndjson", "jsonl"):
            return _read_ndjson_impl(norm_src, *args, **kwargs)
        elif fmt == "json":
            return _read_json_impl(norm_src, *args, **kwargs)
        elif fmt in ("xlsx", "xls", "excel"):
            return _read_excel_impl(norm_src, *args, **kwargs)

    if isinstance(norm_src, (str, Path)):
        p = Path(norm_src)
        if p.exists() and p.is_dir():
            # Check for parquet partition lake directory
            if next(p.rglob("*.parquet"), None) is not None:
                try:
                    return DataFrame(pl.read_parquet(norm_src, *args, **kwargs))
                except Exception:
                    pass
            return get_reader(p, **kwargs).to_dataframe()

        if any(ch in str(norm_src) for ch in "*?["):
            return get_reader(p, **kwargs).to_dataframe()

        suffix, _ = _split_path_suffixes(p)
        if suffix in (".parquet", ".pq"):
            return _read_parquet_impl(norm_src, *args, **kwargs)
        elif suffix in (".csv", ".tsv", ".txt", ".dat"):
            return _read_csv_impl(norm_src, *args, **kwargs)
        elif suffix in (".ipc", ".arrow", ".feather"):
            return _read_ipc_impl(norm_src, *args, **kwargs)
        elif suffix in (".ndjson", ".jsonl"):
            return _read_ndjson_impl(norm_src, *args, **kwargs)
        elif suffix == ".json":
            return _read_json_impl(norm_src, *args, **kwargs)
        elif suffix in (".xlsx", ".xls"):
            return _read_excel_impl(norm_src, *args, **kwargs)
        elif suffix == ".sas7bdat":
            return get_reader(p, **kwargs).to_dataframe()
        else:
            try:
                return get_reader(p, **kwargs).to_dataframe()
            except Exception:
                return _read_csv_impl(norm_src, *args, **kwargs)

    return DataFrame(norm_src)


def scan(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Lazily scan a dataset from a file path, glob, or list of files into a lazy pytae.DataFrame.

    Format is automatically detected from the file extension (.parquet, .csv, .tsv, .ipc,
    .arrow, .feather, .ndjson, .jsonl).

    Examples:
        df = pt.scan("data.parquet")
        df = pt.scan("logs/*.csv")
        df = pt.scan(["day1.parquet", "day2.parquet"])
    """
    import polars as pl

    from pytae.dataframe import DataFrame

    if isinstance(source, DataFrame):
        return source if source.is_lazy else DataFrame(source._df.lazy())

    if isinstance(source, pl.LazyFrame):
        return DataFrame(source)

    if isinstance(source, pl.DataFrame):
        return DataFrame(source.lazy())

    fmt = kwargs.pop("format", kwargs.pop("fmt", None))

    if isinstance(source, (list, tuple)):
        if not source:
            return DataFrame(pl.LazyFrame())
        norm_list = _normalize_source(source)
        first_p = Path(str(norm_list[0]))
        first_ext = ("." + fmt.lower().lstrip(".")) if fmt else first_p.suffix.lower()
        if first_ext in (".parquet", ".pq"):
            return DataFrame(pl.scan_parquet([str(s) for s in norm_list], *args, **kwargs))
        elif first_ext in (".csv", ".tsv", ".txt", ".dat"):
            if first_ext == ".tsv" and "separator" not in kwargs and "sep" not in kwargs:
                kwargs["separator"] = "\t"
            if "sep" in kwargs and "separator" not in kwargs:
                kwargs["separator"] = kwargs.pop("sep")
            kwargs.setdefault("infer_schema_length", 10000)
            return DataFrame(pl.scan_csv([str(s) for s in norm_list], *args, **kwargs))
        elif first_ext in (".ipc", ".arrow", ".feather"):
            return DataFrame(pl.scan_ipc([str(s) for s in norm_list], *args, **kwargs))
        elif first_ext in (".ndjson", ".jsonl"):
            return DataFrame(pl.scan_ndjson([str(s) for s in norm_list], *args, **kwargs))
        else:
            lazy_dfs = [scan(s, *args, **kwargs) for s in norm_list]
            return DataFrame(pl.concat([d._df for d in lazy_dfs]))

    norm_src = _normalize_source(source)
    if is_db_or_cloud_uri(norm_src):
        _, lf = scan_uri(norm_src, *args, **kwargs)
        return DataFrame(lf)
    p = Path(norm_src) if isinstance(norm_src, (str, Path)) else None

    if p and p.exists() and p.is_dir():
        # Check for parquet partition lake directory
        if next(p.rglob("*.parquet"), None) is not None:
            try:
                return DataFrame(pl.scan_parquet(norm_src, *args, **kwargs))
            except Exception:
                pass

    suffix = ("." + fmt.lower().lstrip(".")) if fmt else (p.suffix.lower() if p else "")

    if suffix in (".parquet", ".pq"):
        return DataFrame(pl.scan_parquet(norm_src, *args, **kwargs))
    elif suffix in (".csv", ".tsv", ".txt", ".dat"):
        if suffix == ".tsv" and "separator" not in kwargs and "sep" not in kwargs:
            kwargs["separator"] = "\t"
        if suffix in (".txt", ".dat") and "separator" not in kwargs and "sep" not in kwargs and p and p.exists():
            try:
                first_line = p.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
                if "\t" in first_line and "," not in first_line:
                    kwargs["separator"] = "\t"
            except Exception:
                pass
        if "sep" in kwargs and "separator" not in kwargs:
            kwargs["separator"] = kwargs.pop("sep")
        kwargs.setdefault("infer_schema_length", 10000)
        return DataFrame(pl.scan_csv(norm_src, *args, **kwargs))
    elif suffix in (".ipc", ".arrow", ".feather"):
        return DataFrame(pl.scan_ipc(norm_src, *args, **kwargs))
    elif suffix in (".ndjson", ".jsonl"):
        return DataFrame(pl.scan_ndjson(norm_src, *args, **kwargs))
    else:
        try:
            return DataFrame(get_reader(p or Path(str(norm_src)), **kwargs).to_polars_lazy())
        except Exception:
            return DataFrame(pl.scan_csv(norm_src, *args, **kwargs))


def write(df: Any, target: Any, **kwargs: Any) -> Any:
    """Universal destination function for exporting or converting a dataset."""
    from pytae.dataframe import DataFrame
    if isinstance(df, DataFrame):
        return df.to(target, **kwargs)
    return DataFrame(df).to(target, **kwargs)


def to(df: Any, target: Any, **kwargs: Any) -> Any:
    """Universal destination function for exporting or converting a dataset."""
    return write(df, target, **kwargs)


def _read_csv_impl(source: Any, *args: Any, **kwargs: Any) -> Any:
    import polars as pl

    from pytae.dataframe import DataFrame
    kwargs.setdefault("infer_schema_length", 10000)
    try:
        return DataFrame(pl.read_csv(source, *args, **kwargs))
    except pl.exceptions.ComputeError:
        if kwargs.get("infer_schema_length") is not None:
            kwargs["infer_schema_length"] = None
            return DataFrame(pl.read_csv(source, *args, **kwargs))
        raise


def _read_parquet_impl(source: Any, *args: Any, **kwargs: Any) -> Any:
    import polars as pl

    from pytae.dataframe import DataFrame
    kwargs.setdefault("memory_map", False)
    return DataFrame(pl.read_parquet(source, *args, **kwargs))


def _read_ndjson_impl(source: Any, *args: Any, **kwargs: Any) -> Any:
    import polars as pl

    from pytae.dataframe import DataFrame
    return DataFrame(pl.read_ndjson(source, *args, **kwargs))


def _read_json_impl(source: Any, *args: Any, **kwargs: Any) -> Any:
    import polars as pl

    from pytae.dataframe import DataFrame
    return DataFrame(pl.read_json(source, *args, **kwargs))


def _read_ipc_impl(source: Any, *args: Any, **kwargs: Any) -> Any:
    import polars as pl

    from pytae.dataframe import DataFrame
    return DataFrame(pl.read_ipc(source, *args, **kwargs))


def _read_excel_impl(source: Any, *args: Any, **kwargs: Any) -> Any:
    import pandas as pd

    from pytae.dataframe import DataFrame
    return DataFrame(pd.read_excel(source, *args, **kwargs))


# Deprecated legacy readers / scanners
def read_csv(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.read() instead."""
    import warnings
    warnings.warn("pt.read_csv() is deprecated; use universal pt.read() instead.", DeprecationWarning, stacklevel=2)
    return _read_csv_impl(_normalize_source(source), *args, **kwargs)


def read_parquet(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.read() instead."""
    import warnings
    warnings.warn("pt.read_parquet() is deprecated; use universal pt.read() instead.", DeprecationWarning, stacklevel=2)
    return _read_parquet_impl(_normalize_source(source), *args, **kwargs)


def read_ndjson(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.read() instead."""
    import warnings
    warnings.warn("pt.read_ndjson() is deprecated; use universal pt.read() instead.", DeprecationWarning, stacklevel=2)
    return _read_ndjson_impl(_normalize_source(source), *args, **kwargs)


def read_json(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.read() instead."""
    import warnings
    warnings.warn("pt.read_json() is deprecated; use universal pt.read() instead.", DeprecationWarning, stacklevel=2)
    return _read_json_impl(_normalize_source(source), *args, **kwargs)


def read_ipc(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.read() instead."""
    import warnings
    warnings.warn("pt.read_ipc() is deprecated; use universal pt.read() instead.", DeprecationWarning, stacklevel=2)
    return _read_ipc_impl(_normalize_source(source), *args, **kwargs)


def read_excel(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.read() instead."""
    import warnings
    warnings.warn("pt.read_excel() is deprecated; use universal pt.read() instead.", DeprecationWarning, stacklevel=2)
    return _read_excel_impl(_normalize_source(source), *args, **kwargs)


def read_database(query: Any, connection: Any = None, *args: Any, **kwargs: Any) -> Any:
    """Read SQL query results or database URI into a pytae.DataFrame (wraps polars.read_database)."""
    from pytae.dataframe import DataFrame

    if connection is None and isinstance(query, (str, Path)) and is_db_or_cloud_uri(query):
        _, df = read_uri(query, *args, **kwargs)
        return DataFrame(df)
    import polars as pl

    return DataFrame(pl.read_database(query, connection, *args, **kwargs))


def scan_csv(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.scan() instead."""
    import warnings
    warnings.warn("pt.scan_csv() is deprecated; use universal pt.scan() instead.", DeprecationWarning, stacklevel=2)
    return scan(source, *args, format="csv", **kwargs)


def scan_parquet(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.scan() instead."""
    import warnings
    warnings.warn("pt.scan_parquet() is deprecated; use universal pt.scan() instead.", DeprecationWarning, stacklevel=2)
    return scan(source, *args, format="parquet", **kwargs)


def scan_ndjson(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.scan() instead."""
    import warnings
    warnings.warn("pt.scan_ndjson() is deprecated; use universal pt.scan() instead.", DeprecationWarning, stacklevel=2)
    return scan(source, *args, format="ndjson", **kwargs)


def scan_ipc(source: Any, *args: Any, **kwargs: Any) -> Any:
    """Deprecated: Use universal pt.scan() instead."""
    import warnings
    warnings.warn("pt.scan_ipc() is deprecated; use universal pt.scan() instead.", DeprecationWarning, stacklevel=2)
    return scan(source, *args, format="ipc", **kwargs)
