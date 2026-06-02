#!/usr/bin/env python3
"""
# Helper script for Rippling <-> KnowBe4 Training Cross-Reference
# Evidence for verifying that every Rippling Everyone supergroup member has
# the required KnowBe4 security awareness training completed.

Compares Rippling "Everyone" supergroup members against KnowBe4 enrollments.
Match key: work_email (lowercased), with name fallback for unmatched accounts.

Commands (file-based mode is preferred for the published pipeline):
  - Reads RIPPLING_EVIDENCE_FILE (a downloaded Paramify supergroups artifact)
    OR falls back to live Rippling API at RIPPLING_BASE_URL.
  - Reads KB4_EVIDENCE_FILE (a downloaded Paramify KnowBe4 module-based
    summary artifact).
  - Joins by email; falls back to name when there is exactly one unmatched
    candidate by normalized full name.

Environment variables (read from .env via common.env_loader):
  RIPPLING_EVIDENCE_FILE  (optional) Path to local Rippling artifact JSON.
                          When set, the script does not call Rippling's API.
  KB4_EVIDENCE_FILE       (required) Path to local KnowBe4 artifact JSON.
  RIPPLING_API_TOKEN      (required when RIPPLING_EVIDENCE_FILE is unset)
                          Rippling REST API token; sent as Bearer.
  RIPPLING_BASE_URL       (optional) Default https://rest.ripplingapis.com
                          Allowlisted hosts only (SSRF mitigation).
  RIPPLING_EVERYONE_GROUP (optional) Default "Everyone".
  RIPPLING_MEMBER_SLEEP   (optional) Seconds between member calls. Default 0.05.
  EVIDENCE_DIR            (optional) Output directory; overridden by --output-dir
                          or by the orchestrator (timestamped subdirectory).
  PASS_STATUSES           (optional) Comma-separated KB4 status values that
                          count as "passed". Default "Passed,Completed,Complete".
  CRITICAL_STATUSES       (optional) Comma-separated KB4 status values that
                          escalate to "past due". Default "Past Due".
  EVIDENCE_FILE_MAX_BYTES (optional) Max size for evidence files. Default 50MB.

Usage (standalone, reads .env):
  python fetchers/rippling/rippling_vs_knowbe4_training.py
  python fetchers/rippling/rippling_vs_knowbe4_training.py --output-dir /tmp/evidence

Usage (via orchestrator):
  python 3-run-fetchers/run_fetchers.py

Output (single JSON file in the evidence output directory):
  rippling_vs_knowbe4_training.json

# Security
- Evidence file paths are restricted to CWD or ./evidence/ to prevent path
  traversal (e.g. KB4_EVIDENCE_FILE=/etc/passwd).
- Files must be regular .json files under EVIDENCE_FILE_MAX_BYTES (JSON-bomb
  mitigation).
- RIPPLING_BASE_URL must be HTTPS and on an allowlisted hostname (SSRF
  mitigation). The host check is re-applied to every URL we follow,
  including next_link pagination URLs returned by the API.
- HTTP redirects are disabled on Rippling API calls (a 30x with Location
  would otherwise leak the bearer token to the redirect target).
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common.env_loader import parse_fetcher_args
except ModuleNotFoundError:
    from dotenv import load_dotenv

    def parse_fetcher_args():
        """Standalone fallback: load .env and parse the documented named args."""
        for p in [Path(__file__).parent] + list(Path(__file__).parents):
            if (p / ".env").exists():
                load_dotenv(p / ".env", override=False)
                break
        args = sys.argv[1:]
        output_dir = os.getenv("EVIDENCE_DIR", "./evidence")
        profile = os.getenv("AWS_PROFILE", "")
        region = os.getenv("AWS_DEFAULT_REGION", "")
        i = 0
        while i < len(args):
            if args[i] == "--output-dir" and i + 1 < len(args):
                output_dir = args[i + 1]; i += 2
            elif args[i] == "--profile" and i + 1 < len(args):
                profile = args[i + 1]; i += 2
            elif args[i] == "--region" and i + 1 < len(args):
                region = args[i + 1]; i += 2
            else:
                i += 1
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return output_dir, profile, region


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RIPPLING_BASE_URL_RAW = os.getenv("RIPPLING_BASE_URL", "https://rest.ripplingapis.com")
RIPPLING_MEMBER_SLEEP = float(os.getenv("RIPPLING_MEMBER_SLEEP", "0.05"))
EVERYONE_GROUP_NAME = os.getenv("RIPPLING_EVERYONE_GROUP", "Everyone")
PASS_STATUSES = {s.strip().lower() for s in os.getenv("PASS_STATUSES", "Passed,Completed,Complete").split(",")}
CRITICAL_STATUSES = {s.strip().lower() for s in os.getenv("CRITICAL_STATUSES", "Past Due").split(",")}
EVIDENCE_FILE_MAX_BYTES = int(os.getenv("EVIDENCE_FILE_MAX_BYTES", str(50 * 1024 * 1024)))
HTTP_TIMEOUT = int(os.getenv("RIPPLING_HTTP_TIMEOUT", "30"))

RIPPLING_HOST_ALLOWLIST = (
    "rest.ripplingapis.com",
    "api.rippling.com",
)


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _evidence_path_roots() -> List[Path]:
    cwd = Path.cwd().resolve()
    return [cwd, (cwd / "evidence").resolve()]


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_evidence_path(user_path: str, role: str) -> Path:
    if not user_path:
        raise RuntimeError(f"{role} evidence path is empty")
    candidate = Path(user_path).expanduser().resolve()
    roots = _evidence_path_roots()
    if not any(_is_within(candidate, root) for root in roots):
        raise RuntimeError(
            f"Refused to open {role} evidence file outside allowed directories.\n"
            f"  Requested: {candidate}\n"
            f"  Allowed roots: {[str(r) for r in roots]}\n"
            f"  Hint: keep evidence files in the working directory or ./evidence/"
        )
    if not candidate.exists():
        raise RuntimeError(f"{role} evidence file not found: {candidate}")
    if not candidate.is_file():
        raise RuntimeError(f"{role} evidence path is not a regular file: {candidate}")
    if candidate.suffix.lower() != ".json":
        raise RuntimeError(
            f"{role} evidence file must have .json extension (got {candidate.suffix!r})"
        )
    size = candidate.stat().st_size
    if size > EVIDENCE_FILE_MAX_BYTES:
        raise RuntimeError(
            f"{role} evidence file too large: {size:,} bytes "
            f"(limit {EVIDENCE_FILE_MAX_BYTES:,})."
        )
    if size == 0:
        raise RuntimeError(f"{role} evidence file is empty: {candidate}")
    return candidate


def validate_rippling_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError(
            f"RIPPLING_BASE_URL must use HTTPS (got {parsed.scheme!r})."
        )
    host = (parsed.hostname or "").lower()
    if host not in RIPPLING_HOST_ALLOWLIST:
        raise RuntimeError(
            f"RIPPLING_BASE_URL host {host!r} is not in the allowlist "
            f"{RIPPLING_HOST_ALLOWLIST}."
        )
    return url.rstrip("/")


def _enforce_rippling_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError(f"Refusing non-HTTPS Rippling URL: {url}")
    host = (parsed.hostname or "").lower()
    if host not in RIPPLING_HOST_ALLOWLIST:
        raise RuntimeError(f"Refusing Rippling URL with disallowed host: {host}")


# ---------------------------------------------------------------------------
# Rippling client (live mode)
# ---------------------------------------------------------------------------

def get_rippling_token() -> str:
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RIPPLING_API_TOKEN is not set.")
    return token


def rippling_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {get_rippling_token()}"}
    resp = requests.get(url, headers=headers, params=params, timeout=HTTP_TIMEOUT, allow_redirects=False)
    if resp.status_code in (301, 302, 303, 307, 308):
        raise RuntimeError(
            f"Rippling returned redirect {resp.status_code} to {resp.headers.get('Location')!r}; "
            f"refusing to follow (token would leak)."
        )
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        wait = int(retry_after) if (retry_after and retry_after.isdigit()) else 15
        print(f"  Rate limited (429). Sleeping {wait}s then retrying...")
        time.sleep(wait)
        resp = requests.get(url, headers=headers, params=params, timeout=HTTP_TIMEOUT, allow_redirects=False)
    if resp.status_code >= 400:
        body = resp.text[:500] if resp.text else "(empty body)"
        raise RuntimeError(f"Rippling HTTP {resp.status_code} for {resp.url}\n  Body: {body}")
    return resp.json()


def rippling_paginate(initial_url: str, initial_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    next_url: Optional[str] = initial_url
    next_params = initial_params
    while next_url:
        _enforce_rippling_host(next_url)
        payload = rippling_get(next_url, params=next_params)
        results.extend(payload.get("results", []))
        next_url = payload.get("next_link")
        next_params = None
    return results


def find_everyone_group(base_url: str) -> Optional[Dict[str, Any]]:
    print(f"Searching Rippling for '{EVERYONE_GROUP_NAME}' supergroup ...")
    groups = rippling_paginate(
        f"{base_url}/supergroups/",
        {"filter": "group_type eq 'Group'"},
    )
    for g in groups:
        if (g.get("display_name") or g.get("name") or "") == EVERYONE_GROUP_NAME:
            print(f"  Found group id={g.get('id')}")
            return g
    print(f"  Group '{EVERYONE_GROUP_NAME}' not found.")
    return None


def fetch_everyone_members(base_url: str, group_id: str) -> List[Dict[str, Any]]:
    print(f"Fetching members of {group_id} ...")
    members = rippling_paginate(f"{base_url}/supergroups/{group_id}/members/", None)
    print(f"  Got {len(members)} members")
    if RIPPLING_MEMBER_SLEEP > 0:
        time.sleep(RIPPLING_MEMBER_SLEEP)
    return members


def rippling_email(member: Dict[str, Any]) -> Optional[str]:
    email = (member.get("work_email") or member.get("workEmail") or member.get("email") or "").strip().lower()
    return email or None


# ---------------------------------------------------------------------------
# File-mode loaders
# ---------------------------------------------------------------------------

def load_rippling_from_paramify_file(path_str: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    safe_path = safe_evidence_path(path_str, role="Rippling")
    with safe_path.open(encoding="utf-8") as f:
        artifact = json.load(f)
    if not isinstance(artifact, dict):
        raise RuntimeError(f"Rippling evidence file is not a JSON object: {safe_path}")
    results = artifact.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError(f"Rippling evidence 'results' is not a list: {safe_path}")
    for g in results:
        name = (g.get("display_name") or g.get("name") or "").strip()
        if name.lower() == EVERYONE_GROUP_NAME.lower():
            members = g.get("members", [])
            if not isinstance(members, list):
                raise RuntimeError(f"'{name}' group's members is not a list")
            print(f"Loaded Rippling from file: {safe_path}")
            print(f"  Found '{name}' group (id={g.get('id')}) with {len(members)} members")
            return g, members
    available = [g.get("display_name") or g.get("name") for g in results]
    raise RuntimeError(
        f"'{EVERYONE_GROUP_NAME}' group not found in {safe_path}. "
        f"Available groups (first 10): {available[:10]}"
    )


def load_kb4_evidence(path: str):
    safe_path = safe_evidence_path(path, role="KnowBe4")
    with safe_path.open(encoding="utf-8") as f:
        evidence = json.load(f)
    if not isinstance(evidence, dict):
        raise RuntimeError(f"KnowBe4 evidence file is not a JSON object: {safe_path}")
    results = evidence.get("results", {})
    enrollments = results.get("enrollments", []) if isinstance(results, dict) else []
    summary = results.get("summary", {}) if isinstance(results, dict) else {}
    if not isinstance(enrollments, list):
        raise RuntimeError(f"KnowBe4 evidence 'enrollments' is not a list: {safe_path}")
    print(f"Loaded KnowBe4 evidence from {safe_path}")
    print(f"  {len(enrollments)} enrollment records")
    return enrollments, summary


def kb4_user_email(enrollment: Dict[str, Any]) -> Optional[str]:
    user = enrollment.get("user") or {}
    email = (user.get("email") or "").strip().lower()
    return email or None


def kb4_user_full_name(enrollment: Dict[str, Any]) -> str:
    user = enrollment.get("user") or {}
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    return (first + " " + last).strip()


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def build_per_person_report(rippling_by_email, enrollments_by_email):
    all_emails = set(rippling_by_email.keys()) | set(enrollments_by_email.keys())
    report = []
    for email in sorted(all_emails):
        rippling_member = rippling_by_email.get(email)
        kb4_enrollments = enrollments_by_email.get(email, [])
        rippling_name = rippling_member.get("full_name") if rippling_member else None
        kb4_name = kb4_user_full_name(kb4_enrollments[0]) if kb4_enrollments else None
        kb4_user_id = (kb4_enrollments[0].get("user") or {}).get("id") if kb4_enrollments else None
        campaigns: Dict[str, Dict[str, Any]] = {}
        has_past_due = False
        for enr in kb4_enrollments:
            cname = enr.get("campaign_name") or "(no campaign)"
            status_raw = (enr.get("status") or "").strip()
            status_lc = status_raw.lower()
            if cname not in campaigns:
                campaigns[cname] = {
                    "campaign_id": enr.get("campaign_id"),
                    "assigned": 0, "passed": 0, "in_progress": 0,
                    "not_started": 0, "past_due": 0, "other": 0,
                    "modules": [],
                }
            c = campaigns[cname]
            c["assigned"] += 1
            c["modules"].append({
                "module_name": enr.get("module_name"),
                "status": status_raw,
                "completion_date": enr.get("completion_date"),
                "time_spent_seconds": enr.get("time_spent"),
            })
            if status_lc in PASS_STATUSES:
                c["passed"] += 1
            elif status_lc == "in progress":
                c["in_progress"] += 1
            elif status_lc == "not started":
                c["not_started"] += 1
            elif status_lc == "past due":
                c["past_due"] += 1
                has_past_due = True
            else:
                c["other"] += 1
            if status_lc in CRITICAL_STATUSES:
                has_past_due = True
        for cname, c in campaigns.items():
            c["completion_pct"] = round(100 * c["passed"] / c["assigned"]) if c["assigned"] else 0
            if c["completion_pct"] == 100:
                c["campaign_status"] = "complete"
            elif c["completion_pct"] >= 1:
                c["campaign_status"] = "in_progress"
            else:
                c["campaign_status"] = "not_started"
        total_assigned = sum(c["assigned"] for c in campaigns.values())
        total_passed = sum(c["passed"] for c in campaigns.values())
        overall_pct = round(100 * total_passed / total_assigned) if total_assigned else None
        flags: List[str] = []
        if rippling_member and not kb4_enrollments:
            flags.append("not_in_knowbe4")
        if kb4_enrollments and not rippling_member:
            flags.append("stale_kb4_account")
        if rippling_name and kb4_name and rippling_name.strip().lower() != kb4_name.strip().lower():
            flags.append("name_mismatch")
        if has_past_due:
            flags.append("past_due")
        incomplete = [n for n, c in campaigns.items() if c["completion_pct"] < 100]
        if rippling_member and incomplete:
            flags.append("incomplete_training")
        report.append({
            "email": email,
            "rippling_name": rippling_name,
            "rippling_worker_id": (rippling_member or {}).get("worker_id") or (rippling_member or {}).get("id"),
            "in_rippling_everyone": rippling_member is not None,
            "kb4_user_id": kb4_user_id,
            "kb4_name": kb4_name,
            "in_knowbe4": bool(kb4_enrollments),
            "campaigns_assigned": len(campaigns),
            "modules_assigned": total_assigned,
            "modules_passed": total_passed,
            "overall_completion_pct": overall_pct,
            "has_past_due": has_past_due,
            "campaigns": campaigns,
            "flags": flags,
        })
    return report


def build_gap_summary(per_person):
    not_in_kb4 = [p for p in per_person if "not_in_knowbe4" in p["flags"]]
    stale = [p for p in per_person if "stale_kb4_account" in p["flags"]]
    name_mismatches = [p for p in per_person if "name_mismatch" in p["flags"]]
    past_due = [p for p in per_person if "past_due" in p["flags"]]
    incomplete = [p for p in per_person if "incomplete_training" in p["flags"]]
    fully_compliant = [p for p in per_person
                       if p["in_rippling_everyone"] and p["in_knowbe4"] and not p["flags"]]
    return {
        "totals": {
            "rippling_everyone_members": sum(1 for p in per_person if p["in_rippling_everyone"]),
            "knowbe4_users": sum(1 for p in per_person if p["in_knowbe4"]),
            "fully_compliant": len(fully_compliant),
            "not_in_knowbe4": len(not_in_kb4),
            "stale_kb4_accounts": len(stale),
            "name_mismatches": len(name_mismatches),
            "past_due": len(past_due),
            "incomplete_training": len(incomplete),
        },
        "not_in_knowbe4": [{"email": p["email"], "name": p["rippling_name"], "worker_id": p["rippling_worker_id"]} for p in not_in_kb4],
        "stale_kb4_accounts": [{"email": p["email"], "name": p["kb4_name"], "kb4_user_id": p["kb4_user_id"]} for p in stale],
        "name_mismatches": [{"email": p["email"], "rippling_name": p["rippling_name"], "kb4_name": p["kb4_name"]} for p in name_mismatches],
        "past_due": [{"email": p["email"], "name": p["rippling_name"] or p["kb4_name"]} for p in past_due],
        "incomplete_training": [
            {"email": p["email"], "name": p["rippling_name"] or p["kb4_name"],
             "overall_completion_pct": p["overall_completion_pct"],
             "incomplete_campaigns": [n for n, c in p["campaigns"].items() if c["completion_pct"] < 100]}
            for p in incomplete
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    output_dir, _profile, _region = parse_fetcher_args()
    evidence_dir = Path(output_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    print("Rippling vs KnowBe4 training cross-reference")
    print(f"  Output: {evidence_dir}")

    try:
        # 1. Load Rippling Everyone members (from file OR live API).
        rippling_file = os.getenv("RIPPLING_EVIDENCE_FILE", "").strip()
        if rippling_file:
            print(f"\nStep 1: Load Rippling from file (RIPPLING_EVIDENCE_FILE={rippling_file}) ...")
            everyone_group, members = load_rippling_from_paramify_file(rippling_file)
            rippling_source = {
                "mode": "file",
                "file": rippling_file,
                "group_display_name": everyone_group.get("display_name"),
                "group_id": everyone_group.get("id"),
            }
        else:
            print("\nStep 1: Fetch Rippling Everyone group from live API ...")
            base_url = validate_rippling_base_url(RIPPLING_BASE_URL_RAW)
            everyone_group = find_everyone_group(base_url)
            if not everyone_group:
                raise RuntimeError(f"Could not find supergroup '{EVERYONE_GROUP_NAME}'.")
            members = fetch_everyone_members(base_url, everyone_group["id"])
            rippling_source = {
                "mode": "live_api",
                "base_url": base_url,
                "endpoint": f"/supergroups/{everyone_group['id']}/members/",
                "group_display_name": everyone_group.get("display_name"),
                "group_id": everyone_group["id"],
            }

        # 2. Load KnowBe4 enrollments (file-only).
        print("\nStep 2: Load KnowBe4 evidence ...")
        kb4_file = os.getenv("KB4_EVIDENCE_FILE", "").strip()
        if not kb4_file:
            raise RuntimeError(
                "KB4_EVIDENCE_FILE is not set. Set it to the path of a downloaded "
                "Paramify KnowBe4 module-based summary artifact (e.g. "
                "evidence/knowbe4_from_paramify.json)."
            )
        enrollments, kb4_summary = load_kb4_evidence(kb4_file)

        # 3. Cross-reference (email primary, name fallback).
        print("\nStep 3: Build cross-reference (email primary, name fallback) ...")
        rippling_by_email: Dict[str, Dict] = {}
        rippling_no_email: List[Dict] = []
        for m in members:
            email = rippling_email(m)
            if email:
                rippling_by_email[email] = m
            else:
                rippling_no_email.append(m)
        enrollments_by_email: Dict[str, List[Dict]] = {}
        enrollments_no_email: List[Dict] = []
        for enr in enrollments:
            email = kb4_user_email(enr)
            if email:
                enrollments_by_email.setdefault(email, []).append(enr)
            else:
                enrollments_no_email.append(enr)

        def norm_name(s: Optional[str]) -> str:
            return " ".join((s or "").lower().split())

        matched = set(enrollments_by_email.keys()) & set(rippling_by_email.keys())
        unmatched_kb4 = set(enrollments_by_email.keys()) - matched
        unmatched_rippling = set(rippling_by_email.keys()) - matched

        name_fallback_matches: List[Dict] = []
        if unmatched_rippling and unmatched_kb4:
            kb4_by_name: Dict[str, List[str]] = {}
            for kb4_email in unmatched_kb4:
                kb4_name = norm_name(kb4_user_full_name(enrollments_by_email[kb4_email][0]))
                if kb4_name:
                    kb4_by_name.setdefault(kb4_name, []).append(kb4_email)
            for r_email in list(unmatched_rippling):
                r_name = norm_name(rippling_by_email[r_email].get("full_name"))
                candidates = kb4_by_name.get(r_name, []) if r_name else []
                if len(candidates) == 1:
                    kb4_email = candidates[0]
                    merged = list(enrollments_by_email.pop(kb4_email))
                    enrollments_by_email.setdefault(r_email, []).extend(merged)
                    name_fallback_matches.append({
                        "rippling_email": r_email,
                        "rippling_name": rippling_by_email[r_email].get("full_name"),
                        "kb4_email": kb4_email,
                        "kb4_name": kb4_user_full_name(merged[0]),
                    })

        if name_fallback_matches:
            print(f"  Name-fallback matched {len(name_fallback_matches)} people:")
            for m in name_fallback_matches:
                print(f"    {m['rippling_name']}: Rippling<{m['rippling_email']}> <-> KB4<{m['kb4_email']}>")

        per_person = build_per_person_report(rippling_by_email, enrollments_by_email)
        summary = build_gap_summary(per_person)

        # 4. Write the single consolidated output file with metadata envelope.
        output_path = evidence_dir / "rippling_vs_knowbe4_training.json"
        evidence = {
            "metadata": {
                "datetime": utc_now_iso(),
                "source": "rippling_vs_knowbe4",
                "match_key": "email_primary_name_fallback",
                "pass_statuses": sorted(PASS_STATUSES),
                "critical_statuses": sorted(CRITICAL_STATUSES),
                "rippling_source": rippling_source,
                "kb4_source": {
                    "mode": "file",
                    "file": kb4_file,
                },
            },
            "results": {
                "rippling_everyone_members": {
                    "count": len(members),
                    "results": members,
                },
                "knowbe4_module_enrollments": {
                    "count": len(enrollments),
                    "summary": kb4_summary,
                    "enrollments": enrollments,
                },
                "rippling_vs_knowbe4_gap": {
                    "summary": summary,
                    "name_fallback_matches": name_fallback_matches,
                    "per_person": per_person,
                },
            },
            "summary": summary["totals"],
        }
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2, default=str)
        print(f"\n  Saved -> {output_path}")

        print("\nSummary:")
        for k, v in summary["totals"].items():
            print(f"  {k}: {v}")

        print(
            "\nNote: This script does not upload to Paramify. Run "
            "`python 4-upload-to-paramify/upload_to_paramify.py` to push, "
            "or use the orchestrator at `3-run-fetchers/run_fetchers.py`."
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
