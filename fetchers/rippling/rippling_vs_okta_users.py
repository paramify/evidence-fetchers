#!/usr/bin/env python3
"""
# Helper script for Rippling <-> Okta User Cross-Reference
# Evidence for access review: identifies gaps between Rippling HR and Okta,
# and reports least-privilege metrics (% of employees with Okta access and
# % in each Okta group, e.g. CloudOps for AWS production access).

Compares active Rippling employees against Okta users to surface:
  1. Okta users NOT in Rippling HR  -> potential stale/orphaned accounts
                                       (or service accounts that should be
                                        documented separately)
  2. Rippling employees NOT in Okta -> employees who may be missing SSO
                                       access (or are intentionally outside
                                       the SSO scope, e.g. contractors)
  3. Per-Okta-group breakdown       -> count + % of employees in each Okta
                                       group (CloudOps, Paramify Production,
                                       etc.) sourced from data.group_memberships
                                       in the Paramify Okta artifact.

Least-privilege metrics (display percentages only; numeric _pct fields were
removed since the _display strings are what reviewers actually read):
  okta_access_pct_display        % with any Okta access
  okta_admin_pct_display         % with Okta admin access
  okta_super_admin_pct_display   % with Okta super-admin access
  okta_group_breakdown[].member_count_pct_display
                                  % of employees in each Okta group

Outputs 3 files (Isaac's 3-file pattern):
  - rippling_current_employees.json  (Rippling source of truth)
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

Service account detection:
  An Okta user is treated as a service account (and excluded from admin
  percentages) when either of these is true:
    - The user has an api_token_name set (e.g. Evidence-Fetcher-Okta)
    - The user is not in Rippling Everyone supergroup AND has admin role
  Use OKTA_SERVICE_ACCOUNT_EMAILS env var to explicitly mark additional
  emails as service accounts (comma-separated, lowercased).

Environment variables required (live API mode):
  RIPPLING_API_TOKEN   Bearer token for Rippling
  OKTA_API_TOKEN       Bearer token for Okta (SSWS token)
  OKTA_ORG_URL         Your Okta org URL, e.g. https://paramify.okta.com

Optional:
  RIPPLING_BASE_URL              Defaults to https://rest.ripplingapis.com
  RIPPLING_EVERYONE_GROUP        Defaults to "Everyone"
  OKTA_SERVICE_ACCOUNT_EMAILS    Comma-separated extra service account emails

Usage:
    # Evidence file mode for Okta (preferred)
    OKTA_EVIDENCE_FILE=evidence/okta_from_paramify.json \\
        python rippling_vs_okta_users.py

Output:
    rippling_current_employees.json  Rippling active employees
    okta_all_users.json              All active Okta users
    rippling_vs_okta_gap.json        Gap analysis (summary at bottom)
"""

import json
import os
import sys
from datetime import datetime, timezone
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

RIPPLING_BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://rest.ripplingapis.com").rstrip("/")
EVERYONE_GROUP_NAME = os.getenv("RIPPLING_EVERYONE_GROUP", "Everyone")

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
    everyone = find_everyone_group()
    everyone_id = everyone["id"]
    print(f"Fetching members of {everyone_id} ...")
    members = rippling_paginate(f"{RIPPLING_BASE_URL}/supergroups/{everyone_id}/members/", None)
    print(f"  Got {len(members)} members")
    return members


def rippling_email(emp: Dict) -> Optional[str]:
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
    if user.get("email"):
        return user["email"].strip().lower() or None
    profile = user.get("profile", {})
    email = profile.get("login") or profile.get("email") or ""
    return email.strip().lower() or None


def load_okta_from_evidence_file(path: str):
    """Returns (users, group_memberships) from a Paramify Okta evidence artifact.

    Group memberships are an OPTIONAL field; older artifacts may not include
    them, in which case an empty list is returned.
    """
    with open(path, encoding="utf-8") as f:
        evidence = json.load(f)
    data = evidence.get("data", {})
    admin_users = data.get("admin_users", [])
    regular_users = data.get("regular_users", [])
    tagged_admins = [{**u, "_source_role": "admin"} for u in admin_users if isinstance(u, dict)]
    tagged_regular = [{**u, "_source_role": "regular"} for u in regular_users if isinstance(u, dict)]
    all_users = tagged_admins + tagged_regular
    group_memberships = data.get("group_memberships", []) or []
    if not isinstance(group_memberships, list):
        group_memberships = []
    print(f"Loaded Okta evidence from {path}")
    print(f"  {len(admin_users)} admin users, {len(regular_users)} regular users = {len(all_users)} total")
    if group_memberships:
        print(f"  {len(group_memberships)} Okta groups found in data.group_memberships")
    else:
        print(f"  (No data.group_memberships in this artifact; group breakdown will be empty)")
    return all_users, group_memberships


# ---------------------------------------------------------------------------
# Service account detection
# ---------------------------------------------------------------------------

def is_service_account(user: Dict, rippling_by_email: Dict[str, Dict],
                       explicit_emails: Set[str]) -> bool:
    email = okta_email(user)
    if email and email in explicit_emails:
        return True
    if user.get("api_token_name"):
        return True
    is_admin = (
        user.get("_source_role") == "admin"
        or user.get("admin_type")
        or user.get("is_super_admin")
    )
    if is_admin and email and email not in rippling_by_email:
        return True
    return False


def parse_explicit_service_accounts() -> Set[str]:
    raw = os.getenv("OKTA_SERVICE_ACCOUNT_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


# ---------------------------------------------------------------------------
# Cross-reference / gap analysis
# ---------------------------------------------------------------------------

def pct(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(100 * numerator / denominator, 1)


def pct_display(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value}%"


def build_group_breakdown(group_memberships: List[Dict], rippling_total: int) -> List[str]:
    """Convert raw Okta data.group_memberships into flat display strings.

    Each input entry looks like:
      {"id": "00g...", "name": "CloudOps", "type": "OKTA_GROUP", "member_count": 5}

    Output format (one string per group, sorted by member_count desc):
      "CloudOps (OKTA_GROUP): 6.1%"
    """
    rows: List[tuple] = []
    for g in group_memberships:
        if not isinstance(g, dict):
            continue
        member_count = g.get("member_count")
        try:
            member_count = int(member_count) if member_count is not None else 0
        except (TypeError, ValueError):
            member_count = 0
        name = g.get("name") or "(unnamed)"
        gtype = g.get("type") or "GROUP"
        pct_str = pct_display(pct(member_count, rippling_total))
        rows.append((member_count, name, f"{name} ({gtype}): {pct_str}"))
    # Sort: highest member_count first, then by name
    rows.sort(key=lambda x: (-x[0], x[1]))
    return [r[2] for r in rows]


def build_gap(rippling_employees: List[Dict], okta_users: List[Dict],
              group_memberships: List[Dict]) -> Dict:
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

    # Service accounts
    explicit_service_accounts = parse_explicit_service_accounts()
    service_account_emails: Set[str] = set()
    for email, user in okta_by_email.items():
        if is_service_account(user, rippling_by_email, explicit_service_accounts):
            service_account_emails.add(email)

    # Admin / super-admin counts (humans only)
    okta_humans = [
        u for e, u in okta_by_email.items() if e not in service_account_emails
    ]
    okta_admin_humans = [
        u for u in okta_humans
        if u.get("_source_role") == "admin"
        or u.get("admin_type")
        or u.get("is_super_admin")
    ]
    okta_super_admin_humans = [
        u for u in okta_humans
        if u.get("is_super_admin")
        or (str(u.get("admin_type") or "").upper() == "SUPER_ADMIN")
    ]

    okta_human_employees = [u for u in okta_humans if okta_email(u) in rippling_by_email]
    okta_admin_employees = [u for u in okta_admin_humans if okta_email(u) in rippling_by_email]
    okta_super_admin_employees = [u for u in okta_super_admin_humans if okta_email(u) in rippling_by_email]

    rippling_total = len(rippling_emails)

    access_pct = pct(len(okta_human_employees), rippling_total)
    admin_pct = pct(len(okta_admin_employees), rippling_total)
    super_admin_pct = pct(len(okta_super_admin_employees), rippling_total)

    # ---- Group breakdown (flat string format) ----------------------------
    group_breakdown = build_group_breakdown(group_memberships, rippling_total)

    # Highlight specific groups (CloudOps, Paramify Production) in the narrative
    # when they are present, since these are the AWS-production-access groups
    # Isaac specifically asked about. We pull the data directly from the raw
    # group_memberships input (the breakdown is now flat strings).
    HIGHLIGHTED_GROUP_NAMES = {"CloudOps", "Paramify Production"}
    group_sentence = ""
    highlighted_parts: List[str] = []
    for g in group_memberships:
        if not isinstance(g, dict):
            continue
        if g.get("name") in HIGHLIGHTED_GROUP_NAMES:
            try:
                mc = int(g.get("member_count") or 0)
            except (TypeError, ValueError):
                mc = 0
            highlighted_parts.append(
                f"{g.get('name')}: {mc} of {rippling_total} employees "
                f"({pct_display(pct(mc, rippling_total))})"
            )
    if highlighted_parts:
        group_sentence = " AWS production access groups: " + "; ".join(highlighted_parts) + "."

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
            "is_service_account": email in service_account_emails,
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
        "least_privilege_narrative": (
            f"Of {rippling_total} active Rippling employees, "
            f"{len(okta_human_employees)} ({pct_display(access_pct)}) have Okta access, "
            f"{len(okta_admin_employees)} ({pct_display(admin_pct)}) have Okta admin access, "
            f"and {len(okta_super_admin_employees)} ({pct_display(super_admin_pct)}) "
            f"have super-admin access. "
            f"{len(service_account_emails)} additional Okta account(s) "
            f"were classified as service accounts and excluded from the human "
            f"percentages."
            + group_sentence
        ),
        "service_accounts": [okta_summary(e) for e in sorted(service_account_emails)],
        "in_okta_not_in_rippling": [okta_summary(e) for e in in_okta_not_rippling],
        "in_rippling_not_in_okta": [rippling_summary(e) for e in in_rippling_not_okta],
        "matched_count": len(matched),
        "matched_emails": matched,
        "summary": {
            "rippling_active_employees": rippling_total,
            "okta_active_users": len(okta_emails),
            "matched_both_systems": len(matched),
            "in_okta_not_in_rippling": len(in_okta_not_rippling),
            "in_rippling_not_in_okta": len(in_rippling_not_okta),
            "service_accounts_detected": len(service_account_emails),
            "okta_human_employees": len(okta_human_employees),
            "okta_admin_employees": len(okta_admin_employees),
            "okta_super_admin_employees": len(okta_super_admin_employees),
            # Display forms only (numeric _pct fields dropped per Option A).
            "okta_access_pct_display": pct_display(access_pct),
            "okta_admin_pct_display": pct_display(admin_pct),
            "okta_super_admin_pct_display": pct_display(super_admin_pct),
            "okta_groups_analyzed": len(group_breakdown),
            "okta_group_breakdown": group_breakdown,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
                "endpoint": "/supergroups/<everyone-id>/members/",
                "mode": "current_active_via_everyone_group",
                "datetime": utc_now_iso(),
                "count": len(rippling_employees),
                "results": rippling_employees,
            }, f, indent=2)
        print(f"\u2713 Saved {len(rippling_employees)} Rippling employees -> {rippling_path}")

    # --- File 2: Okta source of truth ---
    okta_evidence_file = extra["okta_evidence_file"] or os.getenv("OKTA_EVIDENCE_FILE", "").strip() or None
    group_memberships: List[Dict] = []
    if okta_evidence_file:
        okta_users, group_memberships = load_okta_from_evidence_file(okta_evidence_file)
        mode_label = f"evidence_file:{Path(okta_evidence_file).name}"
    else:
        okta_users = fetch_okta_users()
        mode_label = "live_api"
        # Live API mode: group_memberships not collected from the live API in
        # this script; use evidence file mode if you need the group breakdown.

    okta_path = evidence_dir / "okta_all_users.json"
    with okta_path.open("w", encoding="utf-8") as f:
        json.dump({
            "source": "okta",
            "mode": mode_label,
            "datetime": utc_now_iso(),
            "count": len(okta_users),
            "group_memberships_count": len(group_memberships),
            "group_memberships": group_memberships,
            "results": okta_users,
        }, f, indent=2)
    print(f"\u2713 Saved {len(okta_users)} Okta users -> {okta_path}")

    # --- File 3: Gap analysis (summary at bottom) ---
    gap = build_gap(rippling_employees, okta_users, group_memberships)
    gap["datetime"] = utc_now_iso()
    summary = gap.pop("summary")
    gap["summary"] = summary

    gap_path = evidence_dir / "rippling_vs_okta_gap.json"
    with gap_path.open("w", encoding="utf-8") as f:
        json.dump(gap, f, indent=2)

    print(f"\n\u2713 Gap analysis completed. See {gap_path}")
    print("\nSummary:")
    for k, v in gap["summary"].items():
        if k == "okta_group_breakdown":
            continue  # Printed separately below
        print(f"  {k}: {v}")
    breakdown = gap["summary"].get("okta_group_breakdown") or []
    if breakdown:
        print("\nOkta group breakdown:")
        for s in breakdown:
            print(f"  {s}")
    print(f"\n{gap['least_privilege_narrative']}")


if __name__ == "__main__":
    main()
