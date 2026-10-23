from pathlib import Path

import pandas as pd
import polars as pl
import pytest

import pytae as pt
from pytae.mask import parse_mask_spec, parse_unmask_spec


def test_parse_mask_spec():
    assert parse_mask_spec("email=hash, ssn=redact") == {"email": "hash", "ssn": "redact"}
    assert parse_mask_spec("email:hash, ssn:encrypt") == {"email": "hash", "ssn": "encrypt"}
    assert parse_mask_spec("email, ssn", default_method="hash") == {"email": "hash", "ssn": "hash"}
    assert parse_mask_spec({"email": "sha256", "user": "token"}) == {"email": "hash", "user": "tokenize"}
    assert parse_mask_spec(email="encrypt", ssn="redact") == {"email": "encrypt", "ssn": "redact"}

    with pytest.raises(ValueError, match="unknown mask method 'banana'"):
        parse_mask_spec("email=banana")


def test_parse_unmask_spec():
    assert parse_unmask_spec("email, ssn") == ["email", "ssn"]
    assert parse_unmask_spec(["email", "ssn"]) == ["email", "ssn"]
    assert parse_unmask_spec("email", "ssn") == ["email", "ssn"]


def test_mask_one_way_hash_and_salt():
    df = pt.DataFrame(
        {
            "email": ["alice@td.com", "bob@td.com", None],
            "id": [1, 2, None],
        }
    )

    # Default hash without salt
    m1 = df.mask("email=hash")
    assert m1["email"][0] is not None
    assert len(m1["email"][0]) == 64  # SHA-256 hex length
    assert m1["email"][2] is None  # Preserves null

    # Hash with salt
    m2 = df.mask("email=hash", salt="custom_salt")
    assert m2["email"][0] != m1["email"][0]
    assert m2["email"][2] is None

    # Determinism: same value produces same hash
    m_dup = df.mask("email=hash", salt="custom_salt")
    assert m_dup["email"][0] == m2["email"][0]


def test_mask_one_way_redact():
    df = pt.DataFrame(
        {
            "ssn": ["123-45-6789", "987-65-4321", None],
            "notes": ["secret A", "secret B", None],
        }
    )

    m = df.mask("ssn=redact, notes=redact")
    assert m["ssn"].to_list() == ["***", "***", None]
    assert m["notes"].to_list() == ["***", "***", None]

    # Custom redact string
    m_custom = df.mask("ssn=redact", redact_val="[CONFIDENTIAL]")
    assert m_custom["ssn"].to_list() == ["[CONFIDENTIAL]", "[CONFIDENTIAL]", None]


def test_mask_option_1_key_encrypt_and_unmask():
    df = pt.DataFrame(
        {
            "user": ["Alice", "Bob", None],
            "ssn": ["111-22-3333", "444-55-6666", None],
        }
    )

    key = "TestSecretKey!2026"
    masked = df.mask("user=encrypt, ssn=encrypt", key=key)

    # Values are scrambled
    assert masked["user"][0] != "Alice"
    assert masked["user"][1] != "Bob"
    assert masked["user"][2] is None

    # Unmask with correct key
    unmasked = masked.unmask("user, ssn", key=key)
    assert unmasked["user"].to_list() == ["Alice", "Bob", None]
    assert unmasked["ssn"].to_list() == ["111-22-3333", "444-55-6666", None]

    # Unmask with WRONG key raises clear error
    with pytest.raises(ValueError, match="decryption failed"):
        masked.unmask("user", key="WrongPassword")


def test_mask_option_2_vault_tokenize_and_unmask(tmp_path: Path):
    vault_file = tmp_path / "vault.parquet"

    df = pt.DataFrame(
        {
            "name": ["Alice", "Bob", "Alice", None],
            "emp_id": [101, 102, 101, None],
        }
    )

    # Tokenize name and emp_id
    masked = df.mask("name=tokenize, emp_id=tokenize", vault=vault_file)
    assert vault_file.exists()

    # Repeated values get identical tokens
    assert masked["name"][0] == masked["name"][2]
    assert masked["name"][0] != masked["name"][1]
    assert masked["name"][3] is None

    # Check vault file content
    vault_df = pl.read_parquet(vault_file)
    assert set(vault_df.columns) == {"column", "token", "original", "dtype"}
    assert len(vault_df) == 4  # 2 unique names + 2 unique emp_ids

    # Unmask from vault restores exact values and types
    unmasked = masked.unmask("name, emp_id", vault=vault_file)
    assert unmasked["name"].to_list() == ["Alice", "Bob", "Alice", None]
    assert unmasked["emp_id"].to_list() == [101, 102, 101, None]


def test_mask_option_2_vault_incremental_append(tmp_path: Path):
    vault_file = tmp_path / "vault.json"

    # Batch 1
    df1 = pt.DataFrame({"name": ["Alice", "Bob"]})
    m1 = df1.mask("name=tokenize", vault=vault_file)
    tok_alice = m1["name"][0]
    tok_bob = m1["name"][1]

    # Batch 2 (contains Alice again + new user Charlie)
    df2 = pt.DataFrame({"name": ["Alice", "Charlie"]})
    m2 = df2.mask("name=tokenize", vault=vault_file)

    # Alice gets the exact same token from batch 1
    assert m2["name"][0] == tok_alice
    # Charlie gets a new token distinct from Alice and Bob
    assert m2["name"][1] not in (tok_alice, tok_bob)

    # Both batches unmask cleanly
    unm1 = m1.unmask("name", vault=vault_file)
    unm2 = m2.unmask("name", vault=vault_file)
    assert unm1["name"].to_list() == ["Alice", "Bob"]
    assert unm2["name"].to_list() == ["Alice", "Charlie"]


def test_mask_combined_options(tmp_path: Path):
    vault_file = tmp_path / "multi_vault.parquet"
    key = "MultiPass456"

    df = pt.DataFrame(
        {
            "user": ["Alice", "Bob"],
            "ssn": ["111", "222"],
            "email": ["a@a.com", "b@b.com"],
            "notes": ["note 1", "note 2"],
        }
    )

    # Combine all 4 methods: tokenize, encrypt, hash, redact
    masked = df.mask(
        "user=tokenize, ssn=encrypt, email=hash, notes=redact",
        key=key,
        vault=vault_file,
    )

    assert masked["user"][0].startswith("user_")
    assert masked["ssn"][0] != "111"
    assert len(masked["email"][0]) == 64
    assert masked["notes"].to_list() == ["***", "***"]

    # Unmask both user (via vault) and ssn (via key) in a single call
    unmasked = masked.unmask("user, ssn", key=key, vault=vault_file)
    assert unmasked["user"].to_list() == ["Alice", "Bob"]
    assert unmasked["ssn"].to_list() == ["111", "222"]
    # email and notes remain safely masked
    assert len(unmasked["email"][0]) == 64
    assert unmasked["notes"].to_list() == ["***", "***"]


def test_mask_pandas_accessor(tmp_path: Path):
    pdf = pd.DataFrame(
        {
            "name": ["Alice", "Bob"],
            "ssn": ["111", "222"],
        }
    )

    key = "PandasKey789"
    # df.pt.mask
    m_pt = pdf.pt.mask("name=hash, ssn=encrypt", key=key)
    assert len(m_pt["name"][0]) == 64

    # df.pt.unmask
    unm_pt = m_pt.pt.unmask("ssn", key=key)
    assert list(unm_pt["ssn"]) == ["111", "222"]


def test_mask_validation_errors():
    df = pt.DataFrame({"name": ["Alice"]})

    # Encrypt without key
    with pytest.raises(ValueError, match="requires -key/--key"):
        df.mask("name=encrypt")

    # Tokenize without vault
    with pytest.raises(ValueError, match="requires -vault/--vault"):
        df.mask("name=tokenize")

    # Unmask without key or vault
    with pytest.raises(ValueError, match="requires -key/--key .* and/or -vault/--vault"):
        df.unmask("name")
