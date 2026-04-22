#!/usr/bin/env python3
"""
Validator Parameter Configuration Helper

Scans the catalog for every `{{var}}` token referenced by a validator, diffs
against the customer's `config/validator_parameters.json`, and reports:

- tokens required by the catalog
- tokens missing from the config (a push would fail on these)
- tokens in the config that nothing references (safe to remove)

Also verifies that every token produces a valid regex after substitution, to
catch typos early.

Usage:
    python scripts/configure_parameters.py \
        [--catalog 1-select-fetchers/evidence_fetchers_catalog.json] \
        [--config config/validator_parameters.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from paramify.parameter_substitution import (  # noqa: E402
    find_tokens,
    substitute,
    MissingParameterError,
)


def collect_validator_tokens(catalog: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Return {token -> set of 'fetcher_id / validator_name' refs that use it}."""
    refs: Dict[str, Set[str]] = {}
    categories = catalog.get("evidence_fetchers_catalog", {}).get("categories", {})
    for cat in categories.values():
        for sinfo in cat.get("scripts", {}).values():
            fid = sinfo.get("id", "<unknown>")
            for v in sinfo.get("validators") or []:
                vname = v.get("name", "<unnamed>")
                for tok in find_tokens(v):
                    refs.setdefault(tok, set()).add(f"{fid} / {vname}")
    return refs


def validate_regex_after_substitution(
    catalog: Dict[str, Any], params: Dict[str, str]
) -> Tuple[int, int]:
    """Sub every validator, compile each regex. Returns (ok_count, bad_count)."""
    ok = bad = 0
    categories = catalog.get("evidence_fetchers_catalog", {}).get("categories", {})
    for cat in categories.values():
        for sinfo in cat.get("scripts", {}).values():
            for v in sinfo.get("validators") or []:
                if v.get("type") != "AUTOMATED":
                    continue
                try:
                    subbed = substitute(v, params)
                except MissingParameterError:
                    bad += 1
                    continue
                regex_str = subbed.get("regex", "")
                try:
                    re.compile(regex_str)
                    ok += 1
                except re.error as e:
                    bad += 1
                    print(
                        f"  ✗ Regex failed to compile after substitution: "
                        f"{sinfo.get('id')} / {v.get('name')}: {e}"
                    )
    return ok, bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        default=str(REPO_ROOT / "1-select-fetchers" / "evidence_fetchers_catalog.json"),
    )
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "validator_parameters.json"),
    )
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    config_path = Path(args.config)

    if not catalog_path.exists():
        print(f"Catalog not found: {catalog_path}", file=sys.stderr)
        return 2

    with catalog_path.open() as f:
        catalog = json.load(f)

    if config_path.exists():
        with config_path.open() as f:
            params = json.load(f)
        # Drop any comment keys (convention: starts with "_").
        params = {k: v for k, v in params.items() if not k.startswith("_")}
    else:
        params = {}
        print(f"(no config at {config_path} — treating as empty)\n")

    refs = collect_validator_tokens(catalog)
    required = set(refs.keys())
    supplied = set(params.keys())

    missing = sorted(required - supplied)
    unused = sorted(supplied - required)

    print(f"=== Validator parameters ===")
    print(f"  Referenced by catalog: {len(required)}")
    print(f"  Supplied in config:    {len(supplied)}")
    print(f"  Missing:               {len(missing)}")
    print(f"  Unused in config:      {len(unused)}")

    if required:
        print("\n--- Required parameters and which validators use them ---")
        for tok in sorted(required):
            users = sorted(refs[tok])
            first = users[0]
            rest = f"  (+ {len(users)-1} more)" if len(users) > 1 else ""
            present = "✓" if tok in supplied else "✗"
            print(f"  [{present}] {tok:<45}  {first}{rest}")

    if missing:
        print("\n✗ Missing parameters — push would fail. Add these to the config:")
        for tok in missing:
            print(f"  - {tok}")

    if unused:
        print("\n⚠ Unused parameters (in config, no validator references them):")
        for tok in unused:
            print(f"  - {tok}")

    if not missing:
        print("\n=== Post-substitution regex check ===")
        ok, bad = validate_regex_after_substitution(catalog, params)
        print(f"  Regexes compiled OK: {ok}")
        print(f"  Regexes failed:      {bad}")
        if bad:
            return 1

    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
