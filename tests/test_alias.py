"""Tests for deterministic human-readable aliasing (`-alias`, `pt.alias`, `df.alias`)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import pytae as pt
from pytae.alias import _disambiguate, alias_polars, parse_alias_spec
from pytae.cli import main as cli_main


def test_parse_alias_spec_presets_and_validation() -> None:
    assert parse_alias_spec("customer=company, rep=name, email=email, loc=city, item, tag=code") == {
        "customer": "company",
        "rep": "name",
        "email": "email",
        "loc": "city",
        "item": "alias",
        "tag": "code",
    }
    assert parse_alias_spec("a=org, b=person, c=short, d=friendly") == {
        "a": "company",
        "b": "name",
        "c": "code",
        "d": "alias",
    }
    with pytest.raises(ValueError, match="unknown alias preset"):
        parse_alias_spec("customer=unknown_preset")


def test_alias_deterministic_across_tables_and_seed_rotation() -> None:
    orders = pt.DataFrame({"customer": ["Apple Inc.", "Google LLC", "Apple Inc.", None], "amt": [10, 20, 30, 40]})
    customers = pt.DataFrame({"customer": ["Google LLC", "Apple Inc."], "tier": ["A", "A"]})

    a1 = orders.alias("customer=company", seed=42)
    a2 = customers.alias("customer=company", seed=42)

    # Null preserved; duplicates get identical alias; cross-table join keys match
    vals_orders = a1._df["customer"].to_list()
    vals_cust = a2._df["customer"].to_list()
    assert vals_orders[3] is None
    assert vals_orders[0] == vals_orders[2]
    assert vals_orders[0] == vals_cust[1]
    assert vals_orders[1] == vals_cust[0]
    assert vals_orders[0] != "Apple Inc."
    assert len(vals_orders[0].split()) == 3  # Adjective Noun Suffix

    # Different seed produces different aliases
    a3 = orders.alias("customer=company", seed=99)
    assert a3._df["customer"].to_list()[0] != vals_orders[0]


def test_alias_all_presets_and_hashed_input() -> None:
    df = pt.DataFrame(
        {
            "cust_hash": ["787973979w7900bffdhkhdsfds880", "a1b2c3d4e5f6g7h8i9j0"],
            "rep": ["u1", "u2"],
            "mail": ["a@b.com", "c@d.com"],
            "city": ["NYC", "SFO"],
            "prod": ["SKU-1", "SKU-2"],
            "acct": ["10001", "10002"],
        }
    )
    res = pt.alias(
        df,
        "cust_hash=company, rep=name, mail=email, city=city, prod=alias, acct=code",
        seed=7,
    )
    assert len(res._df["cust_hash"][0].split()) == 3
    assert len(res._df["rep"][0].split()) == 2
    assert "@" in res._df["mail"][0] and res._df["mail"][0].endswith(".example")
    assert res._df["city"][0][0].isupper()
    assert len(res._df["prod"][0].split()) == 2
    assert re.fullmatch(r"[A-Z]\d[A-Z]-\d{3}", res._df["acct"][0])


def test_alias_auto_disambiguates_collisions(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    alias_mod = sys.modules["pytae.alias"]
    # Force all inputs to hash to the exact same phrase to test auto-disambiguation
    monkeypatch.setattr(alias_mod, "_format_alias", lambda _v, _p, seed: "Good Weather Corp")
    df = pt.DataFrame({"customer": ["Apple Inc.", "Beta Corp", "Gamma LLC", "Apple Inc."]})
    res = df.alias("customer=company", seed=1)
    vals = res._df["customer"].to_list()
    assert vals[0] == vals[3] == "Good Weather Corp"
    assert set(vals) == {"Good Weather Corp", "Good Weather Corp 2", "Good Weather Corp 3"}
    assert _disambiguate("a.b@x.example", "email", 2) == "a.b2@x.example"
    assert _disambiguate("A7K-492", "code", 2) == "A7K-492-2"


def test_alias_vault_roundtrip_with_unmask_and_cli(tmp_path: Path) -> None:
    src = tmp_path / "sales.parquet"
    masked_out = tmp_path / "aliased.parquet"
    restored_out = tmp_path / "restored.parquet"
    vault = tmp_path / "vault.parquet"

    orig = pt.DataFrame({"customer": ["Apple Inc.", "Acme Co", None], "amt": [100, 200, 300]})
    orig.to(src)

    # CLI -alias with -seed and -vault
    rc1 = cli_main([str(src), "-alias", "customer=company", "-seed", "42", "-vault", str(vault), "-o", str(masked_out)])
    assert rc1 == 0
    aliased_df = pt.read(masked_out)
    assert aliased_df._df["customer"][0] != "Apple Inc."
    assert aliased_df._df["customer"][2] is None

    # Existing -unmask -vault reverses the readable alias back to original!
    rc2 = cli_main([str(masked_out), "-unmask", "customer", "-vault", str(vault), "-o", str(restored_out)])
    assert rc2 == 0
    restored_df = pt.read(restored_out)
    assert restored_df._df["customer"].to_list() == ["Apple Inc.", "Acme Co", None]

    # Works with LazyFrame directly
    lf_res = alias_polars(orig._df.lazy(), {"customer": "company"}, seed=42).collect()
    assert lf_res["customer"].to_list() == aliased_df._df["customer"].to_list()
