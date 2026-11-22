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
- [Banking Risk & Finance Use Cases (With Before → After Examples)](#banking-risk--finance-use-cases-with-before--after-examples)
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
| `-salt` | `"custom_salt"` | Salt appended to values prior to SHA-256 hashing (`-mask "col=hash"`) |
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

- **Deterministic & Join-Safe**: With the same `-seed`, `"Oracle Corp."` (or its hash) maps to the exact same readable alias across every table (`orders`, `customers`, `invoices`).
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

---

## Banking Risk & Finance Use Cases (With Before → After Examples)

### 1. Redact — CCAR / CECL Data-Quality Debugging (`-mask "col=redact"`)
Strip PII and free-text credit memos before sending a loan tape to IT or a vendor to debug an RWA or ECL mismatch (preserving null vs. populated checks):

```bash
pytae loan_tape.parquet \
  -mask "guarantor_ssn=redact, borrower_address=redact, underwriting_comments=redact" \
  -o debug_loan_tape.parquet
```

| | `guarantor_ssn` | `underwriting_comments` | `ead_usd` |
|---|---|---|---|
| **Before** | `123-45-6789` | `Covenant waiver approved by CCO` | `12,500,000` |
| **After** | `***` | `***` | `12,500,000` |
| *(Null row)* | `null` → `null` | `null` → `null` | `4,200,000` |

---

### 2. Salted Hash — IFRS 9 / CECL Multi-Year Vintage Tracking (`-mask "col=hash" -salt`)
Hash `customer_name` deterministically across quarterly snapshots so Stage 1 → 2 → 3 migrations and cross-desk concentrations can be joined without storing real borrower identities in the modeling lake:

```bash
# Same secret salt across Q1 and Q2 keeps customers joinable
pytae q1_2026.parquet -mask "customer_name=hash" -salt "$RISK_VINTAGE_SALT" -o lake/q1_2026.parquet
pytae q2_2026.parquet -mask "customer_name=hash" -salt "$RISK_VINTAGE_SALT" -o lake/q2_2026.parquet

# Join Q1 and Q2 in the modeling lake to inspect stage migration
pytae q1=lake/q1_2026.parquet q2=lake/q2_2026.parquet \
  -join "left=q1, right=q2, on=customer_name, how=inner" \
  -filter "stage_left != stage_right" -head 20
```

| | `customer_name` | `stage` | `pd` |
|---|---|---|---|
| **Before (Q1)** | `Oracle Corp.` | `1` | `0.008` |
| **After (Q1)** | `9f4c2a8b1d7e...6c03` | `1` | `0.008` |
| **Before (Q2)** | `Oracle Corp.` | `2` | `0.041` |
| **After (Q2)** | `9f4c2a8b1d7e...6c03` *(identical → joins cleanly)* | `2` | `0.041` |

---

### 3. Authenticated Encryption — Watchlist & Special Assets Memos (`-mask "col=encrypt" -key`)
Encrypt sensitive free-text credit memos so portfolio analysts can aggregate `ead` / `ecl` freely, while only the Chief Credit Officer or Audit holding `$CCO_KEY` can decrypt Stage-3 notes (with no lookup vault file to manage):

```bash
# Credit Risk prepares the quarterly watchlist pack
pytae watchlist.parquet \
  -mask "credit_committee_memo=encrypt, restructuring_terms=encrypt" \
  -key "$CCO_KEY" \
  -o quarterly_watchlist_pack.parquet

# Chief Credit Officer decrypts memos only for high-LGD Stage-3 loans
pytae quarterly_watchlist_pack.parquet \
  -filter "stage == 3 and lgd > 0.45" \
  -unmask "credit_committee_memo, restructuring_terms" -key "$CCO_KEY"
```

| | `loan_id` | `credit_committee_memo` | `lgd` |
|---|---|---|---|
| **Before** | `LN-8841` | `Borrower negotiating asset sale; hold collateral` | `0.52` |
| **After (`-mask`)** | `LN-8841` | `vK9pQ2x...mR8wL1t==` *(random IV per row)* | `0.52` |
| **After (`-unmask -key`)** | `LN-8841` | `Borrower negotiating asset sale; hold collateral` | `0.52` |

---

### 4. Vault Tokenization — Basel IV / External Audit on Corporate Books (`-mask "col=tokenize" -vault`)
Corporate and FI portfolios come from a small, known universe (e.g., S&P 500) where weak hashes could be dictionary-attacked. Tokenize `obligor_id` across linked `facilities` and `collateral` tables using a private vault (`chmod 600`) to preserve joins with zero dictionary-attack risk, then unmask only auditor-flagged outliers:

```bash
# Risk Ops tokenizes linked tables using the same private vault (preserves foreign keys)
pytae facilities.parquet -mask "obligor_id=tokenize" -vault risk_vault.parquet -o audit/facilities.parquet
pytae collateral.parquet -mask "obligor_id=tokenize" -vault risk_vault.parquet -o audit/collateral.parquet

# Later: Risk Ops unmasks the outliers flagged by external auditors
pytae audit_flagged_outliers.parquet -unmask "obligor_id" -vault risk_vault.parquet -o internal_action_list.parquet
```

| | `obligor_id` | `facility_type` | `ead_usd` |
|---|---|---|---|
| **Before** | `Oracle Corp.` | `Revolver` | `250,000,000` |
| **Before** | `Microsoft Corp.` | `Term Loan` | `180,000,000` |
| **After (`-mask`)** | `obligor_id_0001` | `Revolver` | `250,000,000` |
| **After (`-mask`)** | `obligor_id_0002` | `Term Loan` | `180,000,000` |
| **After (`-unmask -vault`)** | `Oracle Corp.` / `Microsoft Corp.` | *(restored)* | *(unchanged)* |

---

### 5. Readable Aliasing — Risk Committee / ALCO Concentration Decks (`-alias`)
Turn `obligor_id_0001` or 64-character salted hashes into clean, deterministic company/banker/city names for Risk Committee slides and MRM docs, and optionally save a local `-vault` to convert flagged names back to exact IDs/hashes for Credit Ops follow-up:

```bash
# Analysts create readable names for ALCO slides & charts (saving a local alias vault)
pytae audit/facilities.parquet \
  -alias "obligor_id=company, relationship_mgr=name, branch_city=city" -seed 42 \
  -vault alco_alias_vault.parquet \
  -o alco_readable.parquet

# Top-10 single-name exposures for the Risk Committee chart (readable names!)
pytae alco_readable.parquet \
  -by obligor_id -agg "total_ead = sum(ead_usd)" \
  -arrange "total_ead desc" -head 10 -bar "obligor_id:total_ead"

# Convert committee-flagged names back to exact obligor tokens/hashes for Credit Ops
pytae alco_followup.parquet -unmask "obligor_id" -vault alco_alias_vault.parquet -o credit_ops_handoff.parquet
```

| | `obligor_id` | `relationship_mgr` | `branch_city` | `ead_usd` |
|---|---|---|---|---|
| **Before (tokens/hashes)** | `obligor_id_0001` *(or `9f4c2a8b...`)* | `emp_4421` | `New York` | `250,000,000` |
| **Before** | `obligor_id_0002` *(or `3a7d91e0...`)* | `emp_8812` | `Chicago` | `180,000,000` |
| **After (`-alias -seed 42`)** | `Good Weather Corp` | `Jordan Brooks` | `Northbrook` | `250,000,000` |
| **After (`-alias -seed 42`)** | `Silver Cedar LLC` | `Maya Lin` | `Clearwater` | `180,000,000` |
| **After (`-unmask -vault`)** | `obligor_id_0001` / `obligor_id_0002` | *(restored if in vault)* | *(restored)* | `250,000,000` |

> **Security Takeaways:**
> - **Never share `-salt`** with receivers — without the salt, dictionary attacks fail even on known universes like S&P 500.
> - **Prefer `tokenize` + `-vault`** for external parties whenever the entity universe is small or guessable.
> - **Use `-alias` strictly for readability/convenience** (`-seed` + optional `-vault`), never as a standalone security control.

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
