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
- [Case Study: Bank Credit Portfolio (Team A, Team B & Team C)](#case-study-bank-credit-portfolio-team-a-team-b--team-c)
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

- **Deterministic & Join-Safe**: With the same `-seed`, `"Apple Inc."` (or its hash) maps to the exact same readable alias across every table (`orders`, `customers`, `invoices`).
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

## Case Study: Bank Credit Portfolio (Team A, Team B & Team C)

Suppose **Team A** (Bank Credit Risk) owns `credit_portfolio.parquet` containing corporate loans to S&P 500 borrowers (`borrower`, `loan_officer`, `ssn_guarantor`, `internal_notes`, `exposure_usd`, `pd`, `lgd`).

Team A needs to share this dataset with two very different audiences — and later ingest both teams' analytical findings back into internal reporting:

| Team | Relationship | Risk Profile | What Team A Sends | How Team A Recovers Names |
|---|---|---|---|---|
| **Team B** | External consultant | **High (Strictest)** — knows borrowers are S&P 500 (small guessable universe) | `borrower=tokenize` (`-vault`), `loan_officer=hash` (`-salt`), `ssn_guarantor=redact`, `internal_notes=redact` | `-unmask "borrower" -vault team_a_vault.parquet` |
| **Team C** | Internal bank team (Model Validation) | **Moderate (Internal)** — needs multi-quarter joins & selective note review | `borrower=hash` (`-salt`), `ssn_guarantor=redact`, `internal_notes=encrypt` (`-key`) | Re-hash internal table on the fly with same `-salt` & join (no vault stored) |

---

### Track 1: Team A → Team B (External Consultant — Strictest Protection)

**Why Team A uses `tokenize` instead of `hash` for `borrower`:**
Because borrowers come from a small, known universe (S&P 500), an unsalted hash (or a leaked salt) could be dictionary-attacked in milliseconds. Opaque tokens (`borrower_0001`, `borrower_0002`) have **zero mathematical relationship** to the company name.

```bash
# Step 1 (Team A): Tokenize borrowers into a private vault, salt-hash officers, redact PII/notes
pytae credit_portfolio.parquet \
  -mask "borrower=tokenize, loan_officer=hash, ssn_guarantor=redact, internal_notes=redact" \
  -salt "$BANK_EXT_SALT" \
  -vault team_a_vault.parquet \
  -o for_team_b.parquet

chmod 600 team_a_vault.parquet   # Keep Team A's vault strictly private and out of git
# -> Team A sends ONLY `for_team_b.parquet` to Team B
```

**How Team B works with readable names (`-alias`) instead of `borrower_0001` / hex hashes:**
```bash
# Step 2 (Team B): Create readable, deterministic aliases + save Team B's own alias vault
pytae for_team_b.parquet \
  -alias "borrower=company, loan_officer=name" -seed 42 \
  -vault team_b_alias.parquet \
  -o team_b_working.parquet

# Team B analyzes & presents naturally:
#   "Good Weather Corp accounts for 14% of high-PD exposure, managed by Jordan Brooks."
```

**How Team B hands findings back to Team A:**
```bash
# Step 3 (Team B): Restore Team A's original tokens before sending results back
pytae team_b_top_risks.parquet \
  -unmask "borrower" -vault team_b_alias.parquet \
  -o handoff_from_b.parquet

# Step 4 (Team A): Recover real borrower names using Team A's private vault
pytae handoff_from_b.parquet \
  -unmask "borrower" -vault team_a_vault.parquet \
  -o final_consultant_report.parquet
```

---

### Track 2: Team A → Team C (Internal Bank Team — Stateless & Join-Safe)

**Why Team A uses salted `hash` + `encrypt` for Team C:**
Team C works across quarterly snapshots (`q1_loans.parquet`, `q2_loans.parquet`) inside the bank's network. A strong secret `-salt` gives deterministic, join-safe hashes across quarters without maintaining a growing vault file, while `-key` encryption lets authorized reviewers decrypt `internal_notes` on flagged loans without exposing notes to everyone.

```bash
# Step 1 (Team A): Salted hash for borrowers, redact SSN, encrypt notes for authorized reviewers
pytae credit_portfolio.parquet \
  -mask "borrower=hash, ssn_guarantor=redact, internal_notes=encrypt" \
  -salt "$BANK_AUDIT_SALT" \
  -key "$AUDIT_NOTES_KEY" \
  -o for_team_c.parquet
# -> Team A sends `for_team_c.parquet` to Team C (never shares $BANK_AUDIT_SALT)
```

**How Team C replaces 64-character hashes with readable names (`-alias`):**
```bash
# Step 2 (Team C): Turn 64-char hex hashes into readable company names (same -seed across Q1/Q2)
pytae for_team_c.parquet \
  -alias "borrower=company" -seed 7 \
  -vault team_c_alias.parquet \
  -o team_c_working.parquet

# Team C discusses "Silver Cedar LLC" in model validation reviews instead of `78797397...`
# Authorized reviewer can also decrypt notes on flagged rows if they hold $AUDIT_NOTES_KEY:
pytae team_c_working.parquet -filter "pd > 0.10" -unmask "internal_notes" -key "$AUDIT_NOTES_KEY"
```

**How Team C hands flagged loans back to Team A (no `hash ↔ original` vault needed!):**
```bash
# Step 3 (Team C): Restore original salted hashes before sending flagged loans back
pytae team_c_flags.parquet \
  -unmask "borrower" -vault team_c_alias.parquet \
  -o handoff_from_c.parquet

# Step 4 (Team A): Re-hash internal lookup table on the fly with the same salt & join!
pytae credit_portfolio.parquet \
  -select "borrower, exposure_usd" \
  -mutate "borrower_hash = borrower" \
  -mask "borrower_hash=hash" -salt "$BANK_AUDIT_SALT" \
  -o /tmp/internal_keyed.parquet

pytae k=/tmp/internal_keyed.parquet f=handoff_from_c.parquet \
  -join "left=f, right=k, on=borrower:borrower_hash, how=left" \
  -o final_validation_report.parquet
```

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
