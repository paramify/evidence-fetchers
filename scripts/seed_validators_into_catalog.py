#!/usr/bin/env python3
"""
Dev-side tool. One-time (or repeatable) seed of validator definitions into
`1-select-fetchers/evidence_fetchers_catalog.json` from a Paramify validators
CSV export.

Not on the customer runtime path. Run it to update the committed catalog,
then delete the CSV input.

Usage:
    python scripts/seed_validators_into_catalog.py \
        --csv "/path/to/validators.csv" \
        [--catalog 1-select-fetchers/evidence_fetchers_catalog.json] \
        [--dry-run]

Rules:
- Only seed validators whose `Evidence` column matches a catalog fetcher id.
- Split `Evidence` on "|" to support multi-referenced validators.
- Convert CSV rules JSON (legacy flat shape) to the API's nested shape.
- Dedupe validators per fetcher by validator name; existing entries with the
  same name are replaced.
- Report AUTOMATED validators whose Evidence ref(s) didn't match any fetcher
  so the user can review.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ---------- CSV -> API shape converters -------------------------------------


def _convert_regex_operation(raw_op: Optional[str], group_number: Any) -> Any:
    """Legacy CSV flat shape -> API nested shape for `regexOperation`."""
    if not raw_op:
        return None
    if raw_op == "MATCH_COUNT":
        return {"type": "MATCH_COUNT"}
    if raw_op == "MATCH_GROUP":
        try:
            n = int(group_number)
        except (TypeError, ValueError):
            n = 1
        return {"type": "MATCH_GROUP", "groupNumber": n}
    raise ValueError(f"Unknown regexOperation: {raw_op!r}")


def _convert_value(raw_value: Optional[str], group_number: Any, custom_text: Any) -> Any:
    """Legacy CSV flat shape -> API nested shape for `value`."""
    if not raw_value:
        return None
    if raw_value == "CUSTOM_TEXT":
        return {"type": "CUSTOM_TEXT", "customText": "" if custom_text is None else str(custom_text)}
    if raw_value == "MATCH_COUNT":
        return {"type": "MATCH_COUNT"}
    if raw_value == "MATCH_GROUP":
        try:
            n = int(group_number)
        except (TypeError, ValueError):
            n = 1
        return {"type": "MATCH_GROUP", "groupNumber": n}
    raise ValueError(f"Unknown value type: {raw_value!r}")


def convert_validation_rules(csv_rules_json: str) -> List[Dict[str, Any]]:
    """Convert a CSV `Validation Rules` JSON string to the API's shape."""
    if not csv_rules_json or not csv_rules_json.strip():
        return []
    raw = json.loads(csv_rules_json)
    out: List[Dict[str, Any]] = []
    for rule in raw:
        out.append(
            {
                "regexOperation": _convert_regex_operation(
                    rule.get("regexOperation"), rule.get("regexOperationGroupNumber")
                ),
                "criteria": rule.get("criteria"),
                "value": _convert_value(
                    rule.get("value"),
                    rule.get("valueGroupNumber"),
                    rule.get("valueCustomText"),
                ),
            }
        )
    return out


def _strip_attestation_index(rules: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recursively drop the legacy `index` field on attestation rules."""
    cleaned: List[Dict[str, Any]] = []
    for rule in rules:
        r = {k: v for k, v in rule.items() if k != "index"}
        if isinstance(r.get("nestedRules"), list):
            r["nestedRules"] = _strip_attestation_index(r["nestedRules"])
        else:
            r["nestedRules"] = []
        cleaned.append(r)
    return cleaned


def convert_attestation_rules(csv_questions_json: str) -> List[Dict[str, Any]]:
    if not csv_questions_json or not csv_questions_json.strip():
        return []
    raw = json.loads(csv_questions_json)
    return _strip_attestation_index(raw)


# ---------- Catalog walking -------------------------------------------------


def iter_fetchers(catalog_root: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield each fetcher node in the catalog tree."""
    stack: List[Any] = [catalog_root]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "id" in node and "name" in node and "script_file" in node:
                yield node
                continue
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def build_fetcher_index(catalog_root: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {f["id"]: f for f in iter_fetchers(catalog_root)}


# ---------- Seeding ---------------------------------------------------------


def _parse_evidence_refs(cell: str) -> List[str]:
    """Split a CSV Evidence cell into individual refs.

    Paramify's export uses several separators interchangeably: pipe, newline,
    carriage return, or comma. Treat any of them as a delimiter.
    """
    if not cell:
        return []
    out: List[str] = []
    # Normalize every known separator to a single sentinel before splitting.
    tmp = cell
    for sep in ("|", "\r\n", "\n", "\r", ","):
        tmp = tmp.replace(sep, "\x00")
    for part in tmp.split("\x00"):
        p = part.strip()
        if p:
            out.append(p)
    return out


def build_validator_entry(csv_row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Convert a CSV row to a validator entry in catalog form. Returns None
    if the row is unusable (e.g. unknown Type)."""
    vtype = (csv_row.get("Type") or "").strip()
    name = (csv_row.get("Name") or "").strip()
    statement = (csv_row.get("Statement") or "").strip()
    if not name or not vtype:
        return None

    if vtype == "AUTOMATED":
        return {
            "name": name,
            "statement": statement,
            "type": "AUTOMATED",
            "regex": csv_row.get("Regex") or "",
            "validationRules": convert_validation_rules(csv_row.get("Validation Rules") or ""),
        }
    if vtype == "ATTESTATION":
        return {
            "name": name,
            "statement": statement,
            "type": "ATTESTATION",
            "attestationRules": convert_attestation_rules(csv_row.get("Attestation Questions") or ""),
        }
    # Unknown type — skip.
    return None


def upsert_validator(fetcher: Dict[str, Any], validator: Dict[str, Any]) -> str:
    """Insert or replace a validator on a fetcher by name. Returns 'insert' or 'update'."""
    validators = fetcher.setdefault("validators", [])
    for i, existing in enumerate(validators):
        if existing.get("name") == validator["name"]:
            validators[i] = validator
            return "update"
    validators.append(validator)
    return "insert"


def seed(
    csv_path: Path, catalog_path: Path, dry_run: bool = False
) -> Dict[str, Any]:
    """Seed validators into the catalog.

    Returns a dict with counts and itemized lists:
        inserted, updated,
        unmatched_automated: [(name, refs)],      # Evidence refs set but none match
        no_evidence_automated: [name],            # Evidence column empty
        unmatched_attestation: [(name, refs)],
        no_evidence_attestation: [name],
    """
    with catalog_path.open("r") as f:
        catalog = json.load(f)

    root = catalog["evidence_fetchers_catalog"]
    fetcher_index = build_fetcher_index(root)

    inserted = 0
    updated = 0
    unmatched_automated: List[Tuple[str, str]] = []
    no_evidence_automated: List[str] = []
    unmatched_attestation: List[Tuple[str, str]] = []
    no_evidence_attestation: List[str] = []
    unknown_type: List[Tuple[str, str]] = []

    with csv_path.open("r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vtype = (row.get("Type") or "").strip()
            name = (row.get("Name") or "").strip()
            evidence_cell = row.get("Evidence") or ""
            refs = _parse_evidence_refs(evidence_cell)

            validator = build_validator_entry(row)
            if validator is None:
                if name:
                    unknown_type.append((name, vtype))
                continue

            matched_any = False
            for ref in refs:
                fetcher = fetcher_index.get(ref)
                if fetcher is None:
                    continue
                matched_any = True
                action = upsert_validator(fetcher, validator)
                if action == "insert":
                    inserted += 1
                else:
                    updated += 1

            if not matched_any:
                if not refs:
                    # CSV row doesn't link the validator to any evidence — not
                    # a mismatch with our catalog, just unlinked upstream.
                    if vtype == "AUTOMATED":
                        no_evidence_automated.append(name)
                    else:
                        no_evidence_attestation.append(name)
                else:
                    joined = " | ".join(refs)
                    if vtype == "AUTOMATED":
                        unmatched_automated.append((name, joined))
                    else:
                        unmatched_attestation.append((name, joined))

    if not dry_run:
        with catalog_path.open("w") as f:
            json.dump(catalog, f, indent=2)
            f.write("\n")

    if unknown_type:
        print("\nSkipped CSV rows with unknown Type:")
        for n, t in unknown_type:
            print(f"  {n!r} (Type={t!r})")

    return {
        "inserted": inserted,
        "updated": updated,
        "unmatched_automated": unmatched_automated,
        "no_evidence_automated": no_evidence_automated,
        "unmatched_attestation": unmatched_attestation,
        "no_evidence_attestation": no_evidence_attestation,
    }


# ---------- CLI -------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Paramify validators into evidence_fetchers_catalog.json")
    parser.add_argument("--csv", required=True, help="Path to validators CSV export")
    parser.add_argument(
        "--catalog",
        default="1-select-fetchers/evidence_fetchers_catalog.json",
        help="Path to catalog JSON (default: 1-select-fetchers/evidence_fetchers_catalog.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write the catalog")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    catalog_path = Path(args.catalog)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 2
    if not catalog_path.exists():
        print(f"Catalog not found: {catalog_path}", file=sys.stderr)
        return 2

    result = seed(csv_path, catalog_path, dry_run=args.dry_run)

    print("\n=== Seed summary ===")
    print(f"  Inserted: {result['inserted']}")
    print(f"  Updated:  {result['updated']}")
    print(f"  AUTOMATED — Evidence ref not in catalog:  {len(result['unmatched_automated'])}")
    print(f"  AUTOMATED — CSV had no Evidence ref set:  {len(result['no_evidence_automated'])}")
    print(f"  ATTESTATION — Evidence ref not in catalog:  {len(result['unmatched_attestation'])}")
    print(f"  ATTESTATION — CSV had no Evidence ref set:  {len(result['no_evidence_attestation'])}")
    if args.dry_run:
        print("  (dry-run — catalog was NOT written)")

    if result["unmatched_automated"]:
        print("\n=== Unmatched AUTOMATED validators (Evidence ref does not match any catalog fetcher) ===")
        print("Review these — the CSV references a fetcher id that isn't in our catalog.\n")
        for name, refs in sorted(result["unmatched_automated"]):
            print(f"  - {name}   [Evidence: {refs}]")

    if result["no_evidence_automated"]:
        print("\n=== AUTOMATED validators with no Evidence ref in the CSV ===")
        print("These are unlinked in the source CSV, not a mismatch. No action on our side.\n")
        for name in sorted(result["no_evidence_automated"]):
            print(f"  - {name}")

    # Print per-fetcher validator counts for a quick sanity check.
    with catalog_path.open("r") as f:
        catalog = json.load(f)
    print("\n=== Per-fetcher validator counts ===")
    for fetcher in iter_fetchers(catalog["evidence_fetchers_catalog"]):
        count = len(fetcher.get("validators") or [])
        if count:
            print(f"  {fetcher['id']:<40} {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
