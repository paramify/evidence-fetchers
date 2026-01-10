#!/usr/bin/env python3
"""
KSI-IAM-02: Passwordless Authentication

Thin wrapper around okta_iam_core.py that runs only this KSI and outputs a dedicated JSON file.
"""

import json
import sys
from pathlib import Path

# Ensure we can import sibling module when running as a script
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from okta_iam_core import OktaIAMEvidenceFetcher  # type: ignore


def main():
    skip_check = "--skip-check" in sys.argv
    filtered_argv = [arg for arg in sys.argv if arg != "--skip-check"]

    if len(filtered_argv) < 4:
        print("Usage: python okta_passwordless_authentication.py <profile> <region> <output_dir> [--skip-check]")
        sys.exit(1)

    output_dir = Path(filtered_argv[3])
    output_dir.mkdir(parents=True, exist_ok=True)

    fetcher = OktaIAMEvidenceFetcher(skip_compatibility_check=skip_check)
    evidence = fetcher.collect_ksi_iam_02()

    output_path = output_dir / "okta_passwordless_authentication.json"
    with open(output_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\n✅ Evidence saved to: {output_path}")
    # Avoid logging unvetted summary values (may include sensitive/PII or large policy structures).
    # Evidence JSON output remains unchanged.
    summary = evidence.get("summary", {}) or {}
    safe_keys = [
        "password_policies_count",
        "mfa_enrollment_policies_count",
        "passwordless_authenticators_count",
        "total_active_users_checked",
        "users_with_security_key_enrolled",
        "security_key_enrollment_percentage",
        "security_key_enforced_for_application_sign_on",
    ]

    print("\nSummary (safe metrics):")
    for key in safe_keys:
        if key in summary and not isinstance(summary.get(key), (dict, list)):
            print(f"  {key}: {summary.get(key)}")

    # For complex fields, print only sizes (no raw contents).
    if "password_policy_requirements" in summary:
        ppr = summary.get("password_policy_requirements") or []
        try:
            count = len(ppr)
        except TypeError:
            count = 1
        print(f"  password_policy_requirements (items): {count}")

    if "enforced_authentication_method_for_sign_on" in summary:
        enforced = summary.get("enforced_authentication_method_for_sign_on") or []
        try:
            count = len(enforced)
        except TypeError:
            count = 1
        print(f"  enforced_authentication_method_for_sign_on (items): {count}")

    print("  (Full details are written to the JSON evidence file.)")


if __name__ == "__main__":
    main()
