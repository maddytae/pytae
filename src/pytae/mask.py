"""Data masking, redaction, key-based authenticated encryption, and tokenization for Pytae."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

import polars as pl

_DEFAULT_SALT = b"pytae_mask_salt"
_VALID_METHODS = ("hash", "sha256", "redact", "encrypt", "tokenize", "token")


# =============================================================================
# 1. Symmetric Key-Based Authenticated Encryption (Option 1)
# =============================================================================


def _encrypt_val(val: Any, key: str) -> str | None:
    if val is None:
        return None
    val_str = str(val)
    salt = _DEFAULT_SALT
    k_enc = hashlib.sha256(key.encode("utf-8") + salt + b":enc").digest()
    k_mac = hashlib.sha256(key.encode("utf-8") + salt + b":mac").digest()
    nonce = os.urandom(12)
    data = val_str.encode("utf-8")
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(data):
        keystream.extend(hashlib.sha256(k_enc + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    ciphertext = bytes(b ^ k for b, k in zip(data, keystream[: len(data)]))
    tag = hmac.new(k_mac, nonce + ciphertext, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(nonce + tag + ciphertext).decode("ascii")


def _decrypt_val(val: Any, key: str) -> str | None:
    if val is None:
        return None
    token = str(val)
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        if len(raw) < 28:
            raise ValueError("invalid encrypted token length")
        nonce, tag, ciphertext = raw[:12], raw[12:28], raw[28:]
        salt = _DEFAULT_SALT
        k_enc = hashlib.sha256(key.encode("utf-8") + salt + b":enc").digest()
        k_mac = hashlib.sha256(key.encode("utf-8") + salt + b":mac").digest()
        expected_tag = hmac.new(k_mac, nonce + ciphertext, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("invalid key or corrupted ciphertext")
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ciphertext):
            keystream.extend(hashlib.sha256(k_enc + nonce + counter.to_bytes(4, "big")).digest())
            counter += 1
        plaintext = bytes(b ^ k for b, k in zip(ciphertext, keystream[: len(ciphertext)]))
        return plaintext.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"decryption failed: {exc}") from exc


def _hash_val(val: Any, salt: str | None = None) -> str | None:
    if val is None:
        return None
    s = f"{salt or ''}{val}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# =============================================================================
# 2. Vault-Based Tokenization (Option 2)
# =============================================================================


def _load_vault(vault_path: Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Load vault mapping: {col_name: {original_str: token_str}} and {col_name: dtype_str}."""
    if not vault_path.exists():
        return {}, {}
    suffix = vault_path.suffix.lower()
    if suffix in (".parquet", ".pq"):
        vdf = pl.read_parquet(vault_path)
    elif suffix == ".csv":
        vdf = pl.read_csv(vault_path)
    elif suffix in (".jsonl", ".ndjson"):
        vdf = pl.read_ndjson(vault_path)
    elif suffix == ".json":
        with open(vault_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                col_map: dict[str, dict[str, str]] = {}
                dtypes: dict[str, str] = {}
                if "mappings" in data and isinstance(data["mappings"], dict):
                    col_map = data["mappings"]
                    dtypes = data.get("dtypes", {})
                else:
                    col_map = data
                return col_map, dtypes
            vdf = pl.DataFrame(data)
    else:
        vdf = pl.read_parquet(vault_path)

    col_map = {}
    dtypes = {}
    if "column" in vdf.columns and "token" in vdf.columns and "original" in vdf.columns:
        has_dtype = "dtype" in vdf.columns
        for row in vdf.iter_rows(named=True):
            c = str(row["column"])
            tok = str(row["token"])
            orig = str(row["original"])
            col_map.setdefault(c, {})[orig] = tok
            if has_dtype and row.get("dtype"):
                dtypes[c] = str(row["dtype"])
    return col_map, dtypes


def _save_vault(
    vault_map: dict[str, dict[str, str]],
    dtypes: dict[str, str],
    vault_path: Path,
) -> None:
    """Save vault mapping: {col_name: {original_str: token_str}}."""
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = vault_path.suffix.lower()
    records = []
    for col, mapping in vault_map.items():
        dt = dtypes.get(col, "String")
        for orig, tok in mapping.items():
            records.append({"column": col, "token": tok, "original": orig, "dtype": dt})

    if suffix == ".json":
        data = {"mappings": vault_map, "dtypes": dtypes}
        with open(vault_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return

    vdf = pl.DataFrame(
        records,
        schema={"column": pl.String, "token": pl.String, "original": pl.String, "dtype": pl.String},
    )
    if suffix in (".parquet", ".pq"):
        vdf.write_parquet(vault_path)
    elif suffix == ".csv":
        vdf.write_csv(vault_path)
    elif suffix in (".jsonl", ".ndjson"):
        vdf.write_ndjson(vault_path)
    else:
        vdf.write_parquet(vault_path)


# =============================================================================
# 3. Spec Parsers
# =============================================================================


def parse_mask_spec(
    spec: Any = None,
    *args: Any,
    default_method: str = "hash",
    **kwargs: Any,
) -> dict[str, str]:
    """Parse mask specification into a {column_name: method} mapping."""
    mapping: dict[str, str] = {}

    if spec is not None:
        if isinstance(spec, dict):
            for k, v in spec.items():
                mapping[str(k).strip()] = str(v).strip().lower()
        elif isinstance(spec, str):
            parts = [p.strip() for p in spec.split(",") if p.strip()]
            for p in parts:
                if "=" in p:
                    col, m = p.split("=", 1)
                elif ":" in p:
                    col, m = p.split(":", 1)
                else:
                    col, m = p, default_method
                mapping[col.strip()] = m.strip().lower()
        elif isinstance(spec, (list, tuple, set)):
            for item in spec:
                mapping[str(item).strip()] = default_method
        else:
            mapping[str(spec).strip()] = default_method

    for arg in args:
        if isinstance(arg, str):
            mapping[arg.strip()] = default_method
        elif isinstance(arg, (list, tuple)):
            for sub in arg:
                mapping[str(sub).strip()] = default_method

    for k, v in kwargs.items():
        if k not in ("key", "salt", "vault", "redact_val", "method"):
            mapping[k.strip()] = str(v).strip().lower()

    method_kwarg = kwargs.get("method")
    if method_kwarg is not None:
        target_m = str(method_kwarg).strip().lower()
        for col, m in list(mapping.items()):
            if m == default_method:
                mapping[col] = target_m

    normalized: dict[str, str] = {}
    for col, m in mapping.items():
        m_clean = m.lower()
        if m_clean in ("sha256", "hash", "sha-256"):
            normalized[col] = "hash"
        elif m_clean in ("redact", "mask", "blur"):
            normalized[col] = "redact"
        elif m_clean in ("encrypt", "enc", "aes"):
            normalized[col] = "encrypt"
        elif m_clean in ("tokenize", "token", "pseudonym", "vault"):
            normalized[col] = "tokenize"
        else:
            valid_str = ", ".join(repr(x) for x in ("hash", "redact", "encrypt", "tokenize"))
            raise ValueError(f"unknown mask method '{m}' for column '{col}'; expected one of: {valid_str}")

    return normalized


def parse_unmask_spec(cols: Any = None, *args: Any) -> list[str]:
    """Parse unmask column specification into a list of column names."""
    out: list[str] = []
    if cols is not None:
        if isinstance(cols, str):
            out.extend([c.strip() for c in cols.split(",") if c.strip()])
        elif isinstance(cols, (list, tuple, set)):
            out.extend([str(c).strip() for c in cols if str(c).strip()])
        else:
            out.append(str(cols).strip())

    for arg in args:
        if isinstance(arg, str):
            out.extend([c.strip() for c in arg.split(",") if c.strip()])
        elif isinstance(arg, (list, tuple, set)):
            out.extend([str(c).strip() for c in arg if str(c).strip()])

    return out


# =============================================================================
# 4. Polars Execution Engines
# =============================================================================


def mask_polars(
    df: Any,
    spec: dict[str, str],
    *,
    key: str | None = None,
    salt: str | None = None,
    vault: str | Path | None = None,
    redact_val: str = "***",
) -> Any:
    """Mask specified columns in a Polars DataFrame or LazyFrame."""
    if not spec:
        return df

    needs_key = any(m == "encrypt" for m in spec.values())
    if needs_key and not key:
        raise ValueError("-mask with method='encrypt' requires -key/--key for authenticated encryption")

    needs_vault = any(m == "tokenize" for m in spec.values())
    if needs_vault and not vault:
        raise ValueError("-mask with method='tokenize' requires -vault/--vault to store tokenization mapping")

    vault_path = Path(vault) if vault is not None else None
    vault_map: dict[str, dict[str, str]] = {}
    vault_dtypes: dict[str, str] = {}
    if vault_path is not None:
        vault_map, vault_dtypes = _load_vault(vault_path)

    exprs: list[pl.Expr] = []
    vault_updated = False

    for col, method in spec.items():
        if method == "hash":
            expr = pl.col(col).map_elements(lambda x, s=salt: _hash_val(x, s), return_dtype=pl.String).alias(col)
            exprs.append(expr)
        elif method == "redact":
            expr = pl.when(pl.col(col).is_not_null()).then(pl.lit(redact_val)).otherwise(None).alias(col)
            exprs.append(expr)
        elif method == "encrypt":
            assert key is not None
            expr = pl.col(col).map_elements(lambda x, k=key: _encrypt_val(x, k), return_dtype=pl.String).alias(col)
            exprs.append(expr)
        elif method == "tokenize":
            assert vault_path is not None
            # Retrieve unique non-null values for column
            col_series = (
                df.select(pl.col(col).drop_nulls()).collect()[col]
                if isinstance(df, pl.LazyFrame)
                else df[col].drop_nulls()
            )
            orig_dtype_str = str(col_series.dtype)
            vault_dtypes[col] = orig_dtype_str
            col_map = vault_map.setdefault(col, {})

            # Assign new tokens to unseen unique values
            for val in col_series.unique().to_list():
                val_str = str(val)
                if val_str not in col_map:
                    new_token = f"{col}_{len(col_map) + 1:04d}"
                    col_map[val_str] = new_token
                    vault_updated = True

            # In Polars, replace_strict works with string mapping.
            # Cast column to string first if it wasn't string.
            col_as_str = pl.col(col).cast(pl.String)
            expr = col_as_str.replace_strict(col_map, default=col_as_str).alias(col)
            exprs.append(expr)
        else:
            raise ValueError(f"unsupported mask method: {method}")

    if vault_updated and vault_path is not None:
        _save_vault(vault_map, vault_dtypes, vault_path)

    return df.with_columns(exprs)


def unmask_polars(
    df: Any,
    cols: list[str],
    *,
    key: str | None = None,
    vault: str | Path | None = None,
) -> Any:
    """Unmask / decrypt / de-tokenize specified columns in a Polars DataFrame or LazyFrame."""
    if not cols:
        return df

    if not key and not vault:
        raise ValueError("-unmask requires -key/--key (for encryption) and/or -vault/--vault (for tokenization)")

    vault_path = Path(vault) if vault is not None else None
    vault_map: dict[str, dict[str, str]] = {}
    vault_dtypes: dict[str, str] = {}
    if vault_path is not None:
        vault_map, vault_dtypes = _load_vault(vault_path)

    exprs: list[pl.Expr] = []
    for col in cols:
        if vault_path is not None and col in vault_map:
            # Reverse mapping: token -> original
            col_map = vault_map[col]
            rev_map = {tok: orig for orig, tok in col_map.items()}
            expr = pl.col(col).cast(pl.String).replace_strict(rev_map, default=pl.col(col))

            # If original dtype was integer or float, restore dtype
            dt_str = vault_dtypes.get(col, "").lower()
            if "int" in dt_str or dt_str.startswith("i") or dt_str.startswith("u"):
                expr = expr.cast(pl.Int64)
            elif "float" in dt_str or dt_str.startswith("f"):
                expr = expr.cast(pl.Float64)
            elif "bool" in dt_str:
                expr = expr.cast(pl.Boolean)

            exprs.append(expr.alias(col))
        elif key is not None:
            expr = pl.col(col).map_elements(lambda x, k=key: _decrypt_val(x, k), return_dtype=pl.String).alias(col)
            exprs.append(expr)
        else:
            raise ValueError(
                f"-unmask: column '{col}' not found in vault '{vault_path}', and no -key provided for decryption"
            )

    return df.with_columns(exprs)


# =============================================================================
# 5. Top-Level Library Functions
# =============================================================================


def mask(
    df: Any,
    spec: Any = None,
    *args: Any,
    key: str | None = None,
    salt: str | None = None,
    vault: str | Path | None = None,
    redact_val: str = "***",
    **kwargs: Any,
) -> Any:
    """Mask sensitive columns in a DataFrame or LazyFrame.

    Supports:
    - method="hash" (one-way SHA-256 cryptographic hash, with optional salt)
    - method="redact" (replaces non-null values with "***")
    - method="encrypt" (reversible authenticated encryption with key)
    - method="tokenize" (reversible pseudonym tokenization with vault mapping file)

    Examples:
        pt.mask(df, "email=hash, ssn=redact")
        pt.mask(df, email="encrypt", ssn="encrypt", key="Secret123")
        pt.mask(df, user="tokenize", vault="vault.parquet")
    """
    from pytae.dataframe import DataFrame

    if key is not None and not kwargs.get("method"):
        default_m = "encrypt"
    elif vault is not None and not kwargs.get("method"):
        default_m = "tokenize"
    else:
        default_m = "hash"

    mapping = parse_mask_spec(spec, *args, default_method=default_m, **kwargs)

    is_pt = isinstance(df, DataFrame)
    underlying = df._df if is_pt else df

    if isinstance(underlying, (pl.DataFrame, pl.LazyFrame)):
        res = mask_polars(underlying, mapping, key=key, salt=salt, vault=vault, redact_val=redact_val)
        return DataFrame(res) if is_pt else res

    import pandas as pd

    if isinstance(underlying, pd.DataFrame):
        pl_df = pl.from_pandas(underlying)
        res_pl = mask_polars(pl_df, mapping, key=key, salt=salt, vault=vault, redact_val=redact_val)
        res_pd = res_pl.to_pandas()
        return DataFrame(res_pd) if is_pt else res_pd

    raise TypeError(f"mask() expected a DataFrame, got {type(df).__name__}")


def unmask(
    df: Any,
    cols: Any = None,
    *args: Any,
    key: str | None = None,
    vault: str | Path | None = None,
    **kwargs: Any,
) -> Any:
    """Unmask / decrypt / de-tokenize columns in a DataFrame.

    Examples:
        pt.unmask(df, "email, ssn", key="Secret123")
        pt.unmask(df, "user", vault="vault.parquet")
        pt.unmask(df, "user, ssn", key="Secret123", vault="vault.parquet")
    """
    from pytae.dataframe import DataFrame

    col_list = parse_unmask_spec(cols, *args)
    if not col_list and kwargs:
        col_list = list(kwargs.keys())

    is_pt = isinstance(df, DataFrame)
    underlying = df._df if is_pt else df

    if isinstance(underlying, (pl.DataFrame, pl.LazyFrame)):
        res = unmask_polars(underlying, col_list, key=key, vault=vault)
        return DataFrame(res) if is_pt else res

    import pandas as pd

    if isinstance(underlying, pd.DataFrame):
        pl_df = pl.from_pandas(underlying)
        res_pl = unmask_polars(pl_df, col_list, key=key, vault=vault)
        res_pd = res_pl.to_pandas()
        return DataFrame(res_pd) if is_pt else res_pd

    raise TypeError(f"unmask() expected a DataFrame, got {type(df).__name__}")
