#!/usr/bin/env python3
"""
# Helper script for Rippling <-> Okta User Cross-Reference
# Evidence for access review: identifies gaps between Rippling HR and Okta

Compares active Rippling employees against Okta users to surface:
  1. Okta users NOT in Rippling HR  -> potential stale/orphaned accounts
  2. Rippling employees NOT in Okta -> employees who may be missing SSO access

Outputs 3 files (as Isaac's 3-file pattern):
  - rippling_current_employees.json  (Rippling source of truth - reused if exists)
  - okta_all_users.json              (Okta source of truth)
  - rippling_vs_okta_gap.json        (the diff - what validators run on)

Matching key: email address
  Rippling -> workEmail field
  Okta     -> profile.login (usually email) with profile.email as fallback

API references:
  https://developer.rippling.com/documentation/rest-api
  https://developer.okta.com/docs/reference/api/users/

Environment variables required (live API mode):
  RIPPLING_API_TOKEN   API token for Rippling (sent as Bearer; same idea as OKTA_API_TOKEN)
  OKTA_API_TOKEN       Bearer token for Okta (SSWS token)
  OKTA_ORG_URL         Your Okta org URL, e.g. https://paramify.okta.com

Optional:
  RIPPLING_BASE_URL    Defaults to https://api.rippling.com
  RIPPLING_PAGE_SIZE   Defaults to 100

Usage:
    # Live API mode (requires Rippling + Okta API tokens)
    python rippling_vs_okta_users.py [--output-dir <path>]

    # Evidence file mode (no Okta live API token needed — use Paramify downloaded JSON)
    python rippling_vs_okta_users.py --okta-evidence-file okta_least_privilege.json [--output-dir <path>]

Output:
    rippling_current_employees.json  Rippling active employees
    okta_all_users.json              All active Okta users
    rippling_vs_okta_gap.json        Gap analysis between the two
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common.env_loader import parse_fetcher_args
except ModuleNotFoundError:
    from dotenv import load_dotenv
    def parse_fetcher_args():
        for p in [Path(__file__).parent] + list(Path(__file__).parents):
            if (p / ".env").exists():
                load_dotenv(p / ".env", override=False)
                break
        args = sys.argv[1:]
        output_dir = "./evidence"
        i = 0
        while i < len(args):
            if args[i] == "--output-dir" and i + 1 < len(args):
                output_dir = args[i + 1]
            i += 1
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return output_dir, "", ""


def _parse_extra_args() -> Dict[str, Optional[str]]:
    """Parse extra CLI flags not handled by parse_fetcher_args."""
    result: Dict[str, Optional[str]] = {"okta_evidence_file": None}
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--okta-evidence-file" and i + 1 < len(args):
            result["okta_evidence_file"] = args[i + 1]
            i += 2
        else:
            i += 1
    return result

# ---------------------------------------------------------------------------
# Rippling helpers
# ---------------------------------------------------------------------------

RIPPLING_BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://api.rippling.com").rstrip("/")
PAGE_SIZE = int(os.getenv("RIPPLING_PAGE_SIZE", "100"))


def get_rippling_token() -> str:
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RIPPLING_API_TOKEN is not set.")
    return token


def rippling_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{RIPPLING_BASE_URL}{path}"
    resp = requests.get(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {get_rippling_token()}"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_records(payload: Any, extra_keys: tuple = ()) -> List[Dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "employees", "items") + extra_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def fetch_rippling_employees() -> List[Dict]:
    results: List[Dict] = []
    offset = 0
    print(f"Fetching active Rippling employees...")
    while True:
        payload = rippling_get("/platform/api/employees", params={"limit": PAGE_SIZE, "offset": offset})
        page = extract_records(payload)
        results.extend(page)
        print(f"  offset={offset}: {len(page)} records (total: {len(results)})")
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return results


def rippling_email(emp: Dict) -> Optional[str]:
    """Extract the primary work email from a Rippling employee record."""
    email = emp.get("workEmail") or emp.get("work_email") or emp.get("email") or ""
    return email.strip().lower() or None


# ---------------------------------------------------------------------------
# Okta helpers
# ---------------------------------------------------------------------------

def get_okta_config():
    token = os.getenv("OKTA_API_TOKEN", "").strip()
    org_url = os.getenv("OKTA_ORG_URL", "").strip().rstrip("/")
    if not token:
        raise RuntimeError("OKTA_API_TOKEN is not set.")
    if not org_url:
        raise RuntimeError("OKTA_ORG_URL is not set (e.g. https://paramify.okta.com).")
    return org_url, token


def fetch_okta_users() -> List[Dict]:
    org_url, token = get_okta_config()
    headers = {
        "Accept": "application/json",
        "Authorization": f"SSWS {token}",
    }
    results: List[Dict] = []
    # Only fetch ACTIVE users - deprovisioned/suspended are separate concern
    url = f"{org_url}/api/v1/users?filter=status+eq+%22ACTIVE%22&limit=200"
    print(f"Fetching active Okta users from {org_url}...")
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        page = resp.json()
        results.extend([u for u in page if isinstance(u, dict)])
        print(f"  fetched {len(page)} users (total: {len(results)})")
        # Okta uses Link header for pagination
        url = None
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                break
    return results


def okta_email(user: Dict) -> Optional[str]:
    """Extract email from an Okta user record.

    Handles two formats:
      - Live Okta API: email is nested under profile.login / profile.email
      - Paramify evidence JSON: email is a top-level field
    """
    # Top-level email (Paramify evidence format: admin_users / regular_users)
    if user.get("email"):
        return user["email"].strip().lower() or None
    # Nested profile (live Okta API format)
    profile = user.get("profile", {})
    email = profile.get("login") or profile.get("email") or ""
    return email.strip().lower() or None


def load_okta_from_evidence_file(path: str) -> List[Dict]:
    """
    Load Okta users from a Paramify evidence JSON file (e.g. okta_least_privilege.json).

    Expected format:
      data.admin_users[].email  (+ login, name, admin_type, ...)
      data.regular_users[].email  (+ name, status, ...)

    Returns a flat list of user dicts, each with at least an 'email' field.
    """
    with open(path, encoding="utf-8") as f:
        evidence = json.load(f)

    data = evidence.get("data", {})
    admin_users = data.get("admin_users", [])
    regular_users = data.get("regular_users", [])
    all_users = admin_users + regular_users

    print(f"Loaded Okta evidence from {path}")
    print(f"  {len(admin_users)} admin users, {len(regular_users)} regular users = {len(all_users)} total")
    return all_users


# ---------------------------------------------------------------------------
# Cross-reference / gap analysis
# ---------------------------------------------------------------------------

def build_gap(rippling_employees: List[Dict], okta_users: List[Dict]) -> Dict:
    """
    Compare the two lists by email and return a structured gap report.
    """
    # Build lookup sets (lowercased email as key)
    rippling_by_email: Dict[str, Dict] = {}
    for emp in rippling_employees:
        email = rippling_email(emp)
        if email:
            rippling_by_email[email] = emp

    okta_by_email: Dict[str, Dict] = {}
    for user in okta_users:
        email = okta_email(user)
        if email:
            okta_by_email[email] = user

    rippling_emails: Set[str] = set(rippling_by_email.keys())
    okta_emails: Set[str] = set(okta_by_email.keys())

    # Gap 1: Okta users NOT in Rippling (potential stale/orphaned accounts)
    in_okta_not_rippling = sorted(okta_emails - rippling_emails)
    # Gap 2: Rippling employees NOT in Okta (missing SSO access)
    in_rippling_not_okta = sorted(rippling_emails - okta_emails)
    # Matched: in both systems
    matched = sorted(rippling_emails & okta_emails)

    def okta_summary(email: str) -> Dict:
        u = okta_by_email[email]
        p = u.get("profile", {})
        # Live API format: profile.firstName / profile.lastName
        # Evidence file format: top-level "name" field (e.g. "Isaac Teuscher")
        first_name = p.get("firstName")
        last_name = p.get("lastName")
        if not first_name and not last_name:
            full_name = u.get("name", "")
            parts = full_name.split(" ", 1)
            first_name = parts[0] if parts else None
            last_name = parts[1] if len(parts) > 1 else None
        return {
            "email": email,
            "okta_id": u.get("id"),
            "first_name": first_name,
            "last_name": last_name,
            "status": u.get("status"),
            "created": u.get("created"),
            "last_login": u.get("lastLogin"),
        }

    def rippling_summary(email: str) -> Dict:
        e = rippling_by_email[email]
        return {
            "email": email,
            "rippling_id": e.get("id"),
            "first_name": e.get("firstName") or e.get("first_name"),
            "last_name": e.get("lastName") or e.get("last_name"),
            "role": e.get("roleState") or e.get("title") or e.get("jobTitle"),
            "department": e.get("department"),
            "start_date": e.get("startDate") or e.get("start_date"),
        }

    return {
        "source": "rippling_vs_okta",
        "summary": {
            "rippling_active_employees": len(rippling_emails),
            "okta_active_users": len(okta_emails),
            "matched_both_systems": len(matched),
            "in_okta_not_in_rippling": len(in_okta_not_rippling),
            "in_rippling_not_in_okta": len(in_rippling_not_okta),
        },
        # High-priority: these are active Okta accounts with no Rippling HR record
        # Could be ex-employees, service accounts, or contractor accounts
        "in_okta_not_in_rippling": [okta_summary(e) for e in in_okta_not_rippling],
        # Lower-priority: Rippling employees without Okta (may intentionally not need SSO)
        "in_rippling_not_in_okta": [rippling_summary(e) for e in in_rippling_not_okta],
        # For reference: employees confirmed in both systems
        "matched_count": len(matched),
        "matched_emails": matched,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    output_dir, _profile, _region = parse_fetcher_args()
    extra = _parse_extra_args()
    evidence_dir = Path(output_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # --- File 1: Rippling source of truth ---
    rippling_path = evidence_dir / "rippling_current_employees.json"
    if rippling_path.exists():
        print(f"Reusing existing {rippling_path}")
        with rippling_path.open(encoding="utf-8") as f:
            existing = json.load(f)
        rippling_employees = existing.get("results", [])
    else:
        rippling_employees = fetch_rippling_employees()
        with rippling_path.open("w", encoding="utf-8") as f:
            json.dump({
                "source": "rippling",
                "endpoint": "/platform/api/employees",
                "mode": "current_active",
                "count": len(rippling_employees),
                "results": rippling_employees,
            }, f, indent=2)
        print(f"\u2713 Saved {len(rippling_employees)} Rippling employees -> {rippling_path}")

    # --- File 2: Okta source of truth ---
    okta_evidence_file = extra["okta_evidence_file"] or os.getenv("OKTA_EVIDENCE_FILE", "").strip() or None
    if okta_evidence_file:
        # Evidence file mode: load from downloaded Paramify JSON (no Okta live API token needed)
        okta_users = load_okta_from_evidence_file(okta_evidence_file)
        mode_label = f"evidence_file:{Path(okta_evidence_file).name}"
    else:
        # Live API mode: fetch directly from Okta
        okta_users = fetch_okta_users()
        mode_label = "live_api"

    okta_path = evidence_dir / "okta_all_users.json"
    with okta_path.open("w", encoding="utf-8") as f:
        json.dump({
            "source": "okta",
            "mode": mode_label,
            "count": len(okta_users),
            "results": okta_users,
        }, f, indent=2)
    print(f"\u2713 Saved {len(okta_users)} Okta users -> {okta_path}")

    # --- File 3: Gap analysis (this is what validators run on) ---
    gap = build_gap(rippling_employees, okta_users)
    gap_path = evidence_dir / "rippling_vs_okta_gap.json"
    with gap_path.open("w", encoding="utf-8") as f:
        json.dump(gap, f, indent=2)

    # Avoid logging potentially sensitive summary statistics directly; refer to file instead.
    print(f"\n\u2713 Gap analysis completed. See {gap_path}")


if __name__ == "__main__":
    main()
