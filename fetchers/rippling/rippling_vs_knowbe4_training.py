#!/usr/bin/env python3
"""
# Helper script for Rippling <-> KnowBe4 Training Cross-Reference
# Evidence for security awareness training compliance

Compares active Rippling employees against KnowBe4 training enrollments to surface:
  1. Rippling employees NOT enrolled in KnowBe4  -> training gap
  2. Rippling employees enrolled but NOT completed -> completion gap
  3. KnowBe4 users NOT in Rippling HR             -> stale training accounts

Outputs 3 files (Isaac's 3-file pattern):
  - rippling_current_employees.json      (Rippling source of truth - reused if exists)
  - knowbe4_training_enrollments.json    (KnowBe4 source of truth)
  - rippling_vs_knowbe4_training.json    (the diff - primary evidence for summary/Paramify)

Matching key: email address
  Rippling -> workEmail
  KnowBe4  -> email field on user records

API reference:
  https://developer.knowbe4.com/rest/reporting

Environment variables required (live API mode):
  RIPPLING_API_TOKEN    API token for Rippling (sent as Bearer)
  KNOWBE4_API_KEY       API key for KnowBe4 Reporting API
  KNOWBE4_BASE_URL      KnowBe4 API base, e.g. https://us.api.knowbe4.com

Optional:
  RIPPLING_BASE_URL              Defaults to https://rest.ripplingapis.com
  RIPPLING_EVERYONE_GROUP        Defaults to "Everyone"
  KNOWBE4_CAMPAIGN_ID   If set, only checks enrollment in this specific campaign ID

Rippling source endpoint (live API mode):
  GET /supergroups/?filter=group_type+eq+'Group'  (find "Everyone" group)
  GET /supergroups/{everyone_id}/members/         (member roster)

Note: Uses the supergroups endpoint rather than /platform/api/employees because
the Rippling API token typically has supergroups.read scope but not employees.read.

Usage:
    # Live API mode (requires Rippling API token + KnowBe4 API key)
    python rippling_vs_knowbe4_training.py [--output-dir <path>]

    # Evidence file mode (no KnowBe4 live credentials needed — use Paramify downloaded JSON)
    python rippling_vs_knowbe4_training.py --kb4-evidence-file security_awareness_training.json [--output-dir <path>]

Output:
    rippling_current_employees.json     Rippling active employees
    knowbe4_training_enrollments.json   KnowBe4 user + enrollment data
    rippling_vs_knowbe4_training.json   Gap analysis (uploaded to Paramify)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover - very old urllib3 fallback
    from requests.packages.urllib3.util.retry import Retry

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
    result: Dict[str, Optional[str]] = {"kb4_evidence_file": None}
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--kb4-evidence-file" and i + 1 < len(args):
            result["kb4_evidence_file"] = args[i + 1]
            i += 2
        else:
            i += 1
    return result


def load_kb4_from_evidence_file(path: str) -> tuple:
    """
    Load KnowBe4 users and enrollments from a Paramify evidence JSON file
    (e.g. security_awareness_training.json).

    Expected format:
      results.users[].email  (+ id, status)
      results.enrollments[].user.email + .status

    Returns (users_list, enrollments_list) in the same format used by the API fetchers.
    """
    with open(path, encoding="utf-8") as f:
        evidence = json.load(f)

    results = evidence.get("results", {})
    users = results.get("users", [])
    enrollments = results.get("enrollments", [])
    summary = results.get("summary", {})

    print(f"Loaded KnowBe4 evidence from {path}")
    print(f"  {len(users)} users, {len(enrollments)} enrollments")
    if summary:
        print(f"  completion_rate: {summary.get('completion_rate')}%  "
              f"(passed: {summary.get('completed_training')}, "
              f"not_started: {summary.get('not_started')}, "
              f"in_progress: {summary.get('in_progress')})")
    return users, enrollments, summary

# ---------------------------------------------------------------------------
# Rippling helpers (same pattern as rippling_vs_okta_users.py)
# ---------------------------------------------------------------------------

RIPPLING_BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://rest.ripplingapis.com").rstrip("/")
EVERYONE_GROUP_NAME = os.getenv("RIPPLING_EVERYONE_GROUP", "Everyone")

RIPPLING_HOST_ALLOWLIST = (
    "rest.ripplingapis.com",
    "api.rippling.com",
)

# Network resilience: configurable read timeout plus automatic retry/backoff so a
# single slow or transient Rippling response no longer fails the whole fetcher run.
RIPPLING_TIMEOUT = float(os.getenv("RIPPLING_TIMEOUT", "60"))
RIPPLING_MAX_RETRIES = int(os.getenv("RIPPLING_MAX_RETRIES", "4"))
RIPPLING_BACKOFF = float(os.getenv("RIPPLING_BACKOFF", "1.5"))


def _build_rippling_session() -> requests.Session:
    """Session with retry/backoff for connect, read, and 429/5xx responses."""
    retry = Retry(
        total=RIPPLING_MAX_RETRIES,
        connect=RIPPLING_MAX_RETRIES,
        read=RIPPLING_MAX_RETRIES,
        status=RIPPLING_MAX_RETRIES,
        backoff_factor=RIPPLING_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
        # Never auto-follow redirects: a leaked bearer token must not be re-sent.
        redirect=False,
        raise_on_redirect=False,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


_RIPPLING_SESSION = _build_rippling_session()


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
    resp = _RIPPLING_SESSION.get(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {get_rippling_token()}"},
        params=params,
        timeout=RIPPLING_TIMEOUT,
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
# KnowBe4 helpers
# ---------------------------------------------------------------------------

def get_knowbe4_config():
    token = os.getenv("KNOWBE4_API_KEY", "").strip()
    base_url = os.getenv("KNOWBE4_BASE_URL", "https://us.api.knowbe4.com").strip().rstrip("/")
    if not token:
        raise RuntimeError("KNOWBE4_API_KEY is not set.")
    return base_url, token


def knowbe4_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    base_url, token = get_knowbe4_config()
    url = f"{base_url}{path}"
    resp = requests.get(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_knowbe4_users() -> List[Dict]:
    """
    Fetch all KnowBe4 users with their training status.
    KnowBe4 uses page-based pagination (page=1,2,3... with per_page up to 500).
    """
    results: List[Dict] = []
    page = 1
    per_page = 500
    print("Fetching KnowBe4 users...")
    while True:
        data = knowbe4_get("/v1/users", params={"page": page, "per_page": per_page, "status": "active"})
        if not isinstance(data, list):
            data = data.get("data") or data.get("users") or []
        results.extend([u for u in data if isinstance(u, dict)])
        print(f"  page={page}: {len(data)} users (total: {len(results)})")
        if len(data) < per_page:
            break
        page += 1
    return results


def fetch_knowbe4_enrollments(campaign_id: Optional[str] = None) -> List[Dict]:
    """
    Fetch training enrollments. If campaign_id is set, filter to that campaign.
    Returns enrollment records with user email + completion status.
    """
    results: List[Dict] = []
    page = 1
    per_page = 500
    path = "/v1/training/enrollments"
    params: Dict[str, Any] = {"page": page, "per_page": per_page}
    if campaign_id:
        params["campaign_id"] = campaign_id

    print(f"Fetching KnowBe4 training enrollments{' for campaign ' + campaign_id if campaign_id else ''}...")
    while True:
        params["page"] = page
        data = knowbe4_get(path, params=params)
        if not isinstance(data, list):
            data = data.get("data") or data.get("enrollments") or []
        results.extend([e for e in data if isinstance(e, dict)])
        print(f"  page={page}: {len(data)} enrollments (total: {len(results)})")
        if len(data) < per_page:
            break
        page += 1
    return results


def knowbe4_email(user: Dict) -> Optional[str]:
    email = user.get("email") or user.get("user", {}).get("email") or ""
    return email.strip().lower() or None


# ---------------------------------------------------------------------------
# Cross-reference / gap analysis
# ---------------------------------------------------------------------------

def build_gap(
    rippling_employees: List[Dict],
    kb4_users: List[Dict],
    kb4_enrollments: List[Dict],
    campaign_id: Optional[str],
) -> Dict:
    """
    Three-way gap analysis: Rippling employees vs KnowBe4 users vs enrollments.
    """
    # Rippling email set
    rippling_by_email: Dict[str, Dict] = {}
    for emp in rippling_employees:
        email = rippling_email(emp)
        if email:
            rippling_by_email[email] = emp

    # KnowBe4 user email set
    kb4_by_email: Dict[str, Dict] = {}
    for user in kb4_users:
        email = knowbe4_email(user)
        if email:
            kb4_by_email[email] = user

    # KnowBe4 enrollment email set - also track completion status
    # Status rank: higher = better. Used to keep the best status if someone
    # has multiple enrollments (e.g. retaken training).
    STATUS_RANK = {"passed": 4, "completed": 4, "complete": 4,
                   "in progress": 3, "not started": 2, "unknown": 1}
    enrolled_emails: Dict[str, str] = {}   # email -> best completion_status
    for enr in kb4_enrollments:
        # Enrollment records have user info nested
        user_info = enr.get("user") or {}
        email = (user_info.get("email") or enr.get("email") or "").strip().lower()
        if email:
            status = enr.get("completion_status") or enr.get("status") or "unknown"
            # Keep the most favourable status if multiple enrollments
            current_rank = STATUS_RANK.get(enrolled_emails.get(email, "unknown").lower(), 1)
            new_rank = STATUS_RANK.get(status.lower(), 1)
            if new_rank > current_rank:
                enrolled_emails[email] = status

    rippling_emails: Set[str] = set(rippling_by_email.keys())
    kb4_emails: Set[str] = set(kb4_by_email.keys())
    enrolled_email_set: Set[str] = set(enrolled_emails.keys())

    # Gaps
    not_in_kb4_at_all = sorted(rippling_emails - kb4_emails)
    in_kb4_not_enrolled = sorted((rippling_emails & kb4_emails) - enrolled_email_set)
    enrolled_not_passed = sorted([
        e for e in rippling_emails & enrolled_email_set
        if enrolled_emails.get(e, "").lower() not in ("passed", "completed", "complete")
    ])
    stale_kb4_accounts = sorted(kb4_emails - rippling_emails)

    def rippling_summary(email: str) -> Dict:
        e = rippling_by_email[email]
        return {
            "email": email,
            "first_name": e.get("firstName") or e.get("first_name"),
            "last_name": e.get("lastName") or e.get("last_name"),
            "department": e.get("department"),
            "start_date": e.get("startDate") or e.get("start_date"),
        }

    def stale_summary(email: str) -> Dict:
        u = kb4_by_email[email]
        return {
            "email": email,
            "kb4_id": u.get("id"),
            "first_name": u.get("first_name"),
            "last_name": u.get("last_name"),
            "status": u.get("status"),
        }

    return {
        "source": "rippling_vs_knowbe4",
        "campaign_id": campaign_id or "all_campaigns",
        "summary": {
            "rippling_active_employees": len(rippling_emails),
            "knowbe4_active_users": len(kb4_emails),
            "training_enrollments_checked": len(kb4_enrollments),
            "not_in_knowbe4_at_all": len(not_in_kb4_at_all),
            "in_knowbe4_not_enrolled": len(in_kb4_not_enrolled),
            "enrolled_but_not_passed": len(enrolled_not_passed),
            "stale_kb4_accounts_not_in_rippling": len(stale_kb4_accounts),
        },
        # Critical: employees who don't even have a KnowBe4 account
        "not_in_knowbe4_at_all": [rippling_summary(e) for e in not_in_kb4_at_all],
        # In KnowBe4 but not enrolled in training
        "in_knowbe4_not_enrolled": [rippling_summary(e) for e in in_kb4_not_enrolled],
        # Enrolled but haven't passed yet
        "enrolled_but_not_passed": [
            {**rippling_summary(e), "enrollment_status": enrolled_emails.get(e)}
            for e in enrolled_not_passed
        ],
        # KnowBe4 accounts with no matching Rippling employee
        "stale_kb4_accounts": [stale_summary(e) for e in stale_kb4_accounts],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    output_dir, _profile, _region = parse_fetcher_args()
    extra = _parse_extra_args()
    evidence_dir = Path(output_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    campaign_id = os.getenv("KNOWBE4_CAMPAIGN_ID", "").strip() or None

    # --- File 1: Rippling source of truth (reuse if already fetched) ---
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
                "mode": "current_active",
                "count": len(rippling_employees),
                "results": rippling_employees,
            }, f, indent=2)
        print(f"\u2713 Saved {len(rippling_employees)} Rippling employees -> {rippling_path}")

    # --- File 2: KnowBe4 source of truth ---
    kb4_evidence_file = extra["kb4_evidence_file"] or os.getenv("KB4_EVIDENCE_FILE", "").strip() or None
    if kb4_evidence_file:
        # Evidence file mode: load from downloaded Paramify JSON (no KnowBe4 live API key needed in env)
        kb4_users, kb4_enrollments, kb4_summary = load_kb4_from_evidence_file(kb4_evidence_file)
        mode_label = f"evidence_file:{Path(kb4_evidence_file).name}"
    else:
        # Live API mode: fetch directly from KnowBe4
        kb4_users = fetch_knowbe4_users()
        kb4_enrollments = fetch_knowbe4_enrollments(campaign_id=campaign_id)
        kb4_summary = {}
        mode_label = "live_api"

    kb4_path = evidence_dir / "knowbe4_training_enrollments.json"
    with kb4_path.open("w", encoding="utf-8") as f:
        json.dump({
            "source": "knowbe4",
            "mode": mode_label,
            "campaign_id": campaign_id or "all_campaigns",
            "user_count": len(kb4_users),
            "enrollment_count": len(kb4_enrollments),
            "summary": kb4_summary,
            "users": kb4_users,
            "enrollments": kb4_enrollments,
        }, f, indent=2)
    print(f"\u2713 Saved {len(kb4_users)} KnowBe4 users + {len(kb4_enrollments)} enrollments -> {kb4_path}")

    # --- File 3: Gap analysis (validators run on this) ---
    gap = build_gap(rippling_employees, kb4_users, kb4_enrollments, campaign_id)
    # Named after this script so create_summary_file / Paramify upload find it
    gap_path = evidence_dir / "rippling_vs_knowbe4_training.json"
    with gap_path.open("w", encoding="utf-8") as f:
        json.dump(gap, f, indent=2)

    print(f"\n\u2713 Gap analysis -> {gap_path}")


if __name__ == "__main__":
    main()
