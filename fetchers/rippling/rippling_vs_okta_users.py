#!/usr/bin/env python3
"""
# Helper script for Rippling <-> Okta User Cross-Reference
# Evidence for access review: identifies gaps between Rippling HR and Okta

Compares active Rippling employees against Okta users to surface:
  1. Okta users NOT in Rippling HR  -> potential stale/orphaned accounts
                                       (or service accounts that should be
                                        documented separately)
  2. Rippling employees NOT in Okta -> employees who may be missing SSO
                                       access (or are intentionally outside
                                       the SSO scope, e.g. contractors)

Outputs 3 files (Isaac's 3-file pattern):
  - rippling_current_employees.json  (Rippling source of truth - reused if exists)
  - okta_all_users.json              (Okta source of truth)
  - rippling_vs_okta_gap.json        (the diff - what validators run on)

Matching key: email address (lowercased)
  Rippling -> work_email (from supergroups members API)
  Okta     -> profile.login (usually email) with profile.email as fallback,
              or top-level "email" when reading a Paramify evidence artifact.

Rippling source endpoint:
  GET /supergroups/?filter=group_type+eq+'Group'  (find "Everyone" group)
  GET /supergroups/{everyone_id}/members/         (member roster)

Note: This script reads from the supergroups endpoint rather than
/platform/api/employees because the current Rippling API token has
supergroups.read scope but not employees.read.

API references:
  https://developer.rippling.com/documentation/rest-api
  https://developer.okta.com/docs/reference/api/users/

Environment variables required (live API mode):
  RIPPLING_API_TOKEN   Bearer token for Rippling
  OKTA_API_TOKEN       Bearer token for Okta (SSWS token)
  OKTA_ORG_URL         Your Okta org URL, e.g. https://paramify.okta.com

Optional:
  RIPPLING_BASE_URL          Defaults to https://rest.ripplingapis.com
  RIPPLING_EVERYONE_GROUP    Defaults to "Everyone"

Usage:
    # Live API mode (requires both tokens)
    python rippling_vs_okta_users.py [--output-dir <path>]

    # Evidence file mode for Okta (no Okta token needed)
    python rippling_vs_okta_users.py --okta-evidence-file okta_least_privilege.json

Output:
    rippling_current_employees.json  Rippling active employees (from Everyone group)
    okta_all_users.json              All active Okta users
    rippling_vs_okta_gap.json        Gap analysis between the two
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

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
# Rippling helpers (supergroups-based)
# ---------------------------------------------------------------------------

RIPPLING_BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://rest.ripplingapis.com").rstrip("/")
EVERYONE_GROUP_NAME = os.getenv("RIPPLING_EVERYONE_GROUP", "Everyone")

# Allowlisted Rippling hosts (SSRF mitigation; same as KB4 script).
RIPPLING_HOST_ALLOWLIST = (
    "rest.ripplingapis.com",
    "api.rippling.com",
)


def _enforce_rippling_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError(f"Refusing non-HTTPS Rippling URL: {url}")
    host = (parsed.hostname or "").lower()
    if host not in RIPPLING_HOST_ALLOWLIST:
        raise RuntimeError(f"Refusing Rippling URL with disallowed host: {host}")


def get_rippling_token() -> str:
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RIPPLING_API_TOKEN is not set.")
    return token


def rippling_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _enforce_rippling_host(url)
    resp = requests.get(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {get_rippling_token()}"},
        params=params,
        timeout=30,
        allow_redirects=False,
    )
    if resp.status_code in (301, 302, 303, 307, 308):
        raise RuntimeError(
            f"Rippling returned redirect {resp.status_code} to {resp.headers.get('Location')!r}; "
            f"refusing to follow (token would leak)."
        )
    resp.raise_for_status()
    return resp.json()


def rippling_paginate(initial_url: str, initial_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Cursor pagination via next_link, with host allowlist enforced on every URL."""
    results: List[Dict[str, Any]] = []
    next_url: Optional[str] = initial_url
    next_params = initial_params
    while next_url:
        payload = rippling_get(next_url, params=next_params)
        results.extend(payload.get("results", []))
        next_url = payload.get("next_link")
        next_params = None
    return results


def find_everyone_group() -> Dict[str, Any]:
    """Find the Everyone supergroup (server-side filter to real human-managed groups)."""
    print(f"Searching Rippling for '{EVERYONE_GROUP_NAME}' supergroup ...")
    groups = rippling_paginate(
        f"{RIPPLING_BASE_URL}/supergroups/",
        {"filter": "group_type eq 'Group'"},
    )
    for g in groups:
        if (g.get("display_name") or g.get("name") or "") == EVERYONE_GROUP_NAME:
            print(f"  Found '{EVERYONE_GROUP_NAME}' group id={g.get('id')}")
            return g
    raise RuntimeError(
        f"Could not find supergroup '{EVERYONE_GROUP_NAME}'. "
        f"Available (first 10): {[g.get('display_name') or g.get('name') for g in groups[:10]]}"
    )


def fetch_rippling_employees() -> List[Dict]:
    """Fetch active employees by reading the Everyone supergroup's members."""
    everyone = find_everyone_group()
    everyone_id = everyone["id"]
    print(f"Fetching members of {everyone_id} ...")
    members = rippling_paginate(f"{RIPPLING_BASE_URL}/supergroups/{everyone_id}/members/", None)
    print(f"  Got {len(members)} members")
    return members


def rippling_email(emp: Dict) -> Optional[str]:
    """Extract the primary work email from a Rippling member record."""
    email = (
        emp.get("work_email")
        or emp.get("workEmail")
        or emp.get("email")
        or ""
    )
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
    url = f"{org_url}/api/v1/users?filter=status+eq+%22ACTIVE%22&limit=200"
    print(f"Fetching active Okta users from {org_url}...")
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        page = resp.json()
        results.extend([u for u in page if isinstance(u, dict)])
        print(f"  fetched {len(page)} users (total: {len(results)})")
        url = None
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                break
    return results


def okta_email(user: Dict) -> Optional[str]:
    """Email lookup. Handles live API (profile.*) and Paramify evidence (top-level)."""
    if user.get("email"):
        return user["email"].strip().lower() or None
    profile = user.get("profile", {})
    email = profile.get("login") or profile.get("email") or ""
    return email.strip().lower() or None


def load_okta_from_evidence_file(path: str) -> List[Dict]:
    """Read Okta users from a Paramify evidence artifact (no API token needed)."""
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

    in_okta_not_rippling = sorted(okta_emails - rippling_emails)
    in_rippling_not_okta = sorted(rippling_emails - okta_emails)
    matched = sorted(rippling_emails & okta_emails)

    def okta_summary(email: str) -> Dict:
        u = okta_by_email[email]
        p = u.get("profile", {})
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
            "admin_type": u.get("admin_type"),
            "is_super_admin": bool(u.get("is_super_admin")),
            "api_token_name": u.get("api_token_name"),
        }

    def rippling_summary(email: str) -> Dict:
        e = rippling_by_email[email]
        full_name = e.get("full_name") or ""
        first_name = e.get("firstName") or e.get("first_name")
        last_name = e.get("lastName") or e.get("last_name")
        if not (first_name or last_name) and full_name:
            parts = full_name.split(" ", 1)
            first_name = parts[0] if parts else None
            last_name = parts[1] if len(parts) > 1 else None
        return {
            "email": email,
            "rippling_id": e.get("id") or e.get("worker_id"),
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name or None,
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
        "in_okta_not_in_rippling": [okta_summary(e) for e in in_okta_not_rippling],
        "in_rippling_not_in_okta": [rippling_summary(e) for e in in_rippling_not_okta],
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

    # --- File 1: Rippling source of truth (from Everyone supergroup) ---
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
                "endpoint": f"/supergroups/<everyone-id>/members/",
                "mode": "current_active_via_everyone_group",
                "count": len(rippling_employees),
                "results": rippling_employees,
            }, f, indent=2)
        print(f"\u2713 Saved {len(rippling_employees)} Rippling employees -> {rippling_path}")

    # --- File 2: Okta source of truth ---
    okta_evidence_file = extra["okta_evidence_file"] or os.getenv("OKTA_EVIDENCE_FILE", "").strip() or None
    if okta_evidence_file:
        okta_users = load_okta_from_evidence_file(okta_evidence_file)
        mode_label = f"evidence_file:{Path(okta_evidence_file).name}"
    else:
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

    print(f"\n\u2713 Gap analysis completed. See {gap_path}")
    print("\nSummary:")
    for k, v in gap["summary"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
