# CLI Feature Guide: Data Masking, Encryption & Tokenization (`-mask`, `-unmask`)

Anonymize, redact, encrypt, or tokenize sensitive PII columns across one-way irreversible and two-way reversible privacy pipelines.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [One-Way Masking](#one-way-masking)
  - [Cryptographic Hashing (`col=hash` / `col=sha256`)](#cryptographic-hashing-colhash--colsha256)
  - [Salted Hashing (`-salt`)](#salted-hashing--salt)
  - [String Redaction (`col=redact`)](#string-redaction-colredact)
- [Reversible Privacy Option 1: Key-Based Authenticated Encryption (`-key`)](#reversible-privacy-option-1-key-based-authenticated-encryption--key)
  - [Encrypting with `-mask "col=encrypt" -key "..."`](#encrypting-with--mask-colencrypt--key-)
  - [Decrypting with `-unmask "col" -key "..."`](#decrypting-with--unmask-col--key-)
- [Reversible Privacy Option 2: Pseudonym Tokenization with Persistent Vault (`-vault`)](#reversible-privacy-option-2-pseudonym-tokenization-with-persistent-vault--vault)
  - [Tokenizing with `-mask "col=tokenize" -vault "..."`](#tokenizing-with--mask-coltokenize--vault-)
  - [De-tokenizing with `-unmask "col" -vault "..."`](#de-tokenizing-with--unmask-col--vault-)
- [Mixed Multi-Column Masking Pipelines](#mixed-multi-column-masking-pipelines)

---

## Overview & Quick Reference

| Flag | Argument | Description |
|---|---|---|
| `-mask` | `"col=method, ..."` | Mask specified columns using `hash`, `sha256`, `redact`, `encrypt`, or `tokenize` |
| `-unmask` | `"col1, col2, ..."` | Revert encrypted or tokenized columns back to original values |
| `-key` | `"secret_password"` | Secret key for authenticated symmetric encryption & decryption |
| `-salt` | `"custom_salt"` | Salt appended to values prior to SHA-256 hashing (prevents rainbow table attacks) |
| `-vault` | `"path/to/vault.parquet"` | File path to persistent tokenization vault (supports `.parquet`, `.csv`, `.ndjson`, `.json`) |

---

## One-Way Masking

One-way masking transformations are irreversible by design. They prevent unauthorized recovery of raw values even if the transformed dataset is shared externally.

### Cryptographic Hashing (`col=hash` / `col=sha256`)

Computes the standard SHA-256 hex digest of non-null values. Null values remain intact.

```bash
# Mask email and user_id using SHA-256
pytae users.csv -mask "email=hash, user_id=sha256"
```

### Salted Hashing (`-salt`)

Appends a secret salt string before hashing, thwarting precomputed rainbow table and dictionary lookup attacks:

```bash
# SHA-256 hash with an organizational salt
pytae users.csv -mask "email=hash" -salt "prod_salt_2026_x89f"
```

### String Redaction (`col=redact`)

Replaces all non-null values in the target column with asterisks (`***`).

```bash
# Redact SSN and phone numbers completely
pytae customers.parquet -mask "ssn=redact, phone=redact"
```

---

## Reversible Privacy Option 1: Key-Based Authenticated Encryption (`-key`)

Key-based encryption performs authenticated symmetric stream encryption (HMAC-SHA256 CTR) with random per-cell initialization vectors (IVs) and cryptographic HMAC integrity verification.

- **Zero External Dependencies**: Operates natively using the Python standard library.
- **Tamper-Resistant**: If ciphertext is modified or the wrong key is supplied during `-unmask`, decryption raises an error rather than emitting corrupted garbage bytes.

### Encrypting with `-mask "col=encrypt" -key "..."`

```bash
# Encrypt SSN and notes columns with a strong secret key
pytae sensitive.csv -mask "ssn=encrypt, notes=encrypt" -key "TopSecretPassphrase42" -o secure.parquet
```

### Decrypting with `-unmask "col" -key "..."`

```bash
# Decrypt the encrypted columns back to plain text
pytae secure.parquet -unmask "ssn, notes" -key "TopSecretPassphrase42" -head 5
```

---

## Reversible Privacy Option 2: Pseudonym Tokenization with Persistent Vault (`-vault`)

Tokenization replaces sensitive entities with clean, format-preserving pseudonym tokens (e.g., `user_0001`, `user_0002`).

- **Preserves Entity Relationships**: Identical values are mapped to identical tokens, preserving frequency counts, group distributions, and join keys across multiple tables.
- **Type-Aware Vault**: The vault persists original column data types (`Int64`, `Float64`, `String`, etc.), so `-unmask` automatically restores the original column back to its native data type.
- **Incremental & Persistent**: Appending new batches against an existing vault reuses existing tokens and assigns subsequent incrementing tokens to novel values.

### Tokenizing with `-mask "col=tokenize" -vault "..."`

```bash
# Tokenize user IDs and persist mapping to user_vault.parquet
pytae transactions.parquet -mask "user_id=tokenize" -vault "user_vault.parquet" -o public_transactions.parquet
```

### De-tokenizing with `-unmask "col" -vault "..."`

```bash
# De-tokenize the anonymized dataset back to original identifiers using the vault
pytae public_transactions.parquet -unmask "user_id" -vault "user_vault.parquet"
```

---

## Mixed Multi-Column Masking Pipelines

Multiple masking strategies can be combined in a single `-mask` command:

```bash
# Hash email, encrypt SSN, and tokenize user name simultaneously
pytae internal_records.csv \
  -mask "email=hash, ssn=encrypt, user_name=tokenize" \
  -salt "audit_salt" \
  -key "SuperSecretKey99" \
  -vault "names_vault.parquet" \
  -o sanitized.parquet
```
