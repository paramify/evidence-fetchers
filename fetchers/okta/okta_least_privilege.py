#!/usr/bin/env python3
"""
KSI-IAM-05: Least Privilege

Thin wrapper around okta_iam_core.py that runs only this KSI and outputs a dedicated JSON file.
"""

import json
import sys
from pathlib import Path

# Ensure we can import sibling module and common package
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))

from common.env_loader import parse_fetcher_args
from okta_iam_core import OktaIAMEvidenceFetcher  # type: ignore


def main():
    skip_check = "--skip-check" in sys.argv

    output_dir_str, _profile, _region = parse_fetcher_args()
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)

    fetcher = OktaIAMEvidenceFetcher(skip_compatibility_check=skip_check)
    evidence = fetcher.collect_ksi_iam_05()

    output_path = output_dir / "okta_least_privilege.json"
    with open(output_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\n✅ Evidence saved to: {output_path}")
    # Avoid logging unvetted summary values (may include PII like admin email lists).
    # Evidence JSON output remains unchanged.
    summary = evidence.get("summary", {}) or {}
    safe_keys = [
        "total_active_users",
        "admin_users_count",
        "regular_users_count",
        "admin_percentage",
        "regular_user_percentage",
        "super_admin_count",
        "read_only_admin_count",
        "other_admin_count",
        "groups_analyzed",
    ]
    # print("\nSummary (safe metrics):")
    # for key in safe_keys:
    #     if key in summary and not isinstance(summary.get(key), (dict, list)):
    #         print(f"  {key}: {summary.get(key)}")


if __name__ == "__main__":
    main()
