# CLI Feature Guide: Data Masking, Aliasing, Encryption & Tokenization (`-mask`, `-unmask`, `-alias`)

Anonymize, redact, encrypt, tokenize, or replace sensitive/hashed columns with deterministic human-readable aliases across one-way and two-way reversible privacy pipelines.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [One-Way Masking](#one-way-masking)
  - [Cryptographic Hashing (`col=hash` / `col=sha256`)](#cryptographic-hashing-colhash--colsha256)
  - [Salted Hashing (`-salt`)](#salted-hashing--salt)
  - [String Redaction (`col=redact`)](#string-redaction-colredact)
- [Readable Deterministic Aliasing (`-alias`)](#readable-deterministic-aliasing--alias)
  - [Two-Team Workflow: Team A (`-mask`) ↔ Team B (`-alias` + `-unmask`)](#two-team-workflow-team-a--mask--team-b--alias---unmask)
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
| `-unmask` | `"col1, col2, ..."` | Revert encrypted, tokenized, or vault-aliased columns back to original values |
| `-alias` | `"col=preset, ..."` | Replace raw or hashed values with deterministic readable aliases (`company`, `name`, `email`, `city`, `alias`, `code`) |
| `-seed` | `42` | Deterministic seed for `-alias` (rotate aliases per project while keeping joins consistent) |
| `-key` | `"secret_password"` | Secret key for authenticated symmetric encryption & decryption |
| `-salt` | `"custom_salt"` | Salt appended to values prior to SHA-256 hashing or aliasing |
| `-vault` | `"path/to/vault.parquet"` | File path to persistent vault for `-mask "col=tokenize"` or `-alias` (supports `.parquet`, `.csv`, `.ndjson`, `.json`) |

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

## Readable Deterministic Aliasing (`-alias`)

Cryptographic hashes (`78797397...`) are safe, but awkward to discuss in reviews or presentations. `-alias` maps either **raw values** or **already-hashed values** into deterministic, human-readable names using built-in zero-dependency presets:

| Preset | Aliases | Example Output |
|---|---|---|
| `company` | `org`, `corp` | `Good Weather Corp`, `Silver Cedar LLC`, `Bright Harbor Group` |
| `name` | `person` | `Jordan Brooks`, `Maya Lin`, `Liam Mercer` |
| `email` | `mail` | `jordan.brooks@goodweather.example` |
| `city` | `place`, `region` | `Northbrook`, `Clearwater`, `Westfield` |
| `alias` *(default)* | `friendly`, `readable`, `product` | `Calm River`, `Amber Falcon`, `Swift Pine` |
| `code` | `short`, `id` | `A7K-492`, `M3P-815` |

- **Deterministic & Join-Safe**: With the same `-seed` / `-salt`, `"Apple Inc."` (or its hash) maps to the exact same readable alias across every table (`orders`, `customers`, `invoices`).
- **Auto-Disambiguates Collisions**: If two distinct values ever collide on the same phrase, Pytae automatically appends a deterministic suffix (`Good Weather Corp 2`) so distinct entities never silently merge.
- **Optionally Reversible with `-vault`**: Pass `-vault map.parquet` to persist the mapping so existing `-unmask <col> -vault map.parquet` restores the original values.

```bash
# Readable aliases for presentations (deterministic with -seed)
pytae sales.parquet -alias "customer=company, rep=name, email=email, loc=city" -seed 42

# Turn opaque hashes into readable names
pytae hashed_sales.parquet -alias "cust_hash=company, acct_hash=code" -seed 7

# Reversible readable aliases (unmask later with -unmask -vault)
pytae sales.parquet -alias "customer=company" -seed 42 -vault map.parquet -o safe.parquet
pytae safe.parquet -unmask "customer" -vault map.parquet
```

Python / IPython API:
```python
safe = df.alias("customer=company, rep=name", seed=42)
safe = pt.alias(df, customer="company", vault="map.parquet", seed=42)
```

### Two-Team Workflow: Team A (`-mask`) ↔ Team B (`-alias` + `-unmask`)

A common enterprise pattern separates **data protection** (Team A) from **readable analysis** (Team B) without ever exposing raw PII:

```bash
# 1. Team A (Data Owner): mask raw customer names (one-way hash OR reversible encrypt/tokenize)
pytae raw_sales.parquet -mask "customer=hash" -salt "team_a_secret" -o shared_masked.parquet
# -> Team A sends `shared_masked.parquet` (containing hashes like `78797397...`) to Team B

# 2. Team B (Analytics): turn opaque hashes into readable company names + save Team B's vault
pytae shared_masked.parquet \
  -alias "customer=company" -seed 42 -vault team_b_alias_vault.parquet \
  -o working_readable.parquet
# -> Team B analyzes and presents cleanly ("Good Weather Corp is our #1 customer")

# 3. Team B (Handoff back to Team A): restore exact original hashes before sending results back
pytae team_b_results.parquet \
  -unmask "customer" -vault team_b_alias_vault.parquet \
  -o handoff_to_team_a.parquet
# -> Team A receives `handoff_to_team_a.parquet` with the original hashes (or encrypted/tokenized
#    values) intact, ready to join back to internal tables or `-unmask` with Team A's own key/vault.
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
