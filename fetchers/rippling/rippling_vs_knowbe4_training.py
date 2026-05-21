#!/usr/bin/env python3
"""
# Helper script for Rippling <-> KnowBe4 Training Cross-Reference

Compares Rippling "Everyone" supergroup members against KnowBe4 enrollments.
Match key: work_email (lowercased), with name fallback for unmatched accounts.

Outputs three files to the evidence directory:
- rippling_everyone_members.json
- knowbe4_module_enrollments.json
- rippling_vs_knowbe4_gap.json

# Security
- Evidence file paths are restricted to the working directory and evidence/
  subdirectory to prevent path traversal (e.g. --kb4-evidence-file /etc/passwd).
- RIPPLING_BASE_URL must be HTTPS and on an allowlisted hostname pattern to
  prevent SSRF (e.g. pointing the bearer token at an attacker-controlled host).
- Evidence files larger than EVIDENCE_FILE_MAX_BYTES are rejected to mitigate
  memory-exhaustion attacks via crafted JSON.
- HTTP redirects are disabled on API calls (a redirected request would leak
  the bearer token to the redirect target).
"""

import json
import os
import sys
import time
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


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

# Evidence file path constraints (path-traversal mitigation).
# We refuse to open files outside the working directory tree.
def _evidence_path_roots() -> List[Path]:
    """Allowed root directories for --*-evidence-file arguments."""
    cwd = Path.cwd().resolve()
    return [cwd, (cwd / "evidence").resolve()]


# Max bytes for any evidence file we will read (JSON-bomb mitigation).
EVIDENCE_FILE_MAX_BYTES = int(os.getenv("EVIDENCE_FILE_MAX_BYTES", str(50 * 1024 * 1024)))

# Allowlisted Rippling API hosts (SSRF mitigation).
# RIPPLING_BASE_URL must match one of these patterns.
RIPPLING_HOST_ALLOWLIST = (
    "rest.ripplingapis.com",
    "api.rippling.com",
)


def safe_evidence_path(user_path: str, role: str) -> Path:
    """Validate an evidence file path.

    Prevents path traversal: rejects anything outside CWD or ./evidence/.
    Also requires the file to exist, be a regular file, end in .json,
    and be under EVIDENCE_FILE_MAX_BYTES.

    role is just a string used in error messages ('Rippling' / 'KnowBe4').
    """
    if not user_path:
        raise RuntimeError(f"{role} evidence path is empty")

    candidate = Path(user_path).expanduser().resolve()

    # 1. Confine to allowed roots.
    roots = _evidence_path_roots()
    if not any(_is_within(candidate, root) for root in roots):
        raise RuntimeError(
            f"Refused to open {role} evidence file outside allowed directories.\n"
            f"  Requested: {candidate}\n"
            f"  Allowed roots: {[str(r) for r in roots]}\n"
            f"  Hint: keep evidence files in the working directory or ./evidence/"
        )

    # 2. Must exist and be a regular file.
    if not candidate.exists():
        raise RuntimeError(f"{role} evidence file not found: {candidate}")
    if not candidate.is_file():
        raise RuntimeError(f"{role} evidence path is not a regular file: {candidate}")

    # 3. Must look like JSON.
    if candidate.suffix.lower() != ".json":
        raise RuntimeError(
            f"{role} evidence file must have .json extension (got {candidate.suffix!r})"
        )

    # 4. Reject suspiciously large files (JSON bomb mitigation).
    size = candidate.stat().st_size
    if size > EVIDENCE_FILE_MAX_BYTES:
        raise RuntimeError(
            f"{role} evidence file too large: {size:,} bytes "
            f"(limit {EVIDENCE_FILE_MAX_BYTES:,}). "
            f"Override via EVIDENCE_FILE_MAX_BYTES env var if intentional."
        )
    if size == 0:
        raise RuntimeError(f"{role} evidence file is empty: {candidate}")

    return candidate


def _is_within(child: Path, parent: Path) -> bool:
    """Return True if child is inside parent (after resolution)."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_rippling_base_url(url: str) -> str:
    """Validate the Rippling base URL (SSRF mitigation).

    Rejects non-HTTPS or non-allowlisted hosts. We do this because the bearer
    token gets attached to every request; a misconfigured/malicious base URL
    would leak the token to an attacker-controlled host.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError(
            f"RIPPLING_BASE_URL must use HTTPS (got {parsed.scheme!r}). "
            f"Refusing to send bearer token over insecure transport."
        )
    host = (parsed.hostname or "").lower()
    if host not in RIPPLING_HOST_ALLOWLIST:
        raise RuntimeError(
            f"RIPPLING_BASE_URL host {host!r} is not in the allowlist "
            f"{RIPPLING_HOST_ALLOWLIST}. Refusing to send bearer token "
            f"to an unrecognized host."
        )
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_extra_args():
    result = {"kb4_evidence_file": None, "rippling_evidence_file": None}
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--kb4-evidence-file" and i + 1 < len(args):
            result["kb4_evidence_file"] = args[i + 1]
            i += 2
        elif args[i] == "--rippling-evidence-file" and i + 1 < len(args):
            result["rippling_evidence_file"] = args[i + 1]
            i += 2
        else:
            i += 1
    return result


def _strip_custom_args_from_argv():
    custom_flags = {"--kb4-evidence-file", "--rippling-evidence-file"}
    cleaned = [sys.argv[0]]
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] in custom_flags and i + 1 < len(sys.argv):
            i += 2
        else:
            cleaned.append(sys.argv[i])
            i += 1
    sys.argv = cleaned


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# NOTE: we don't validate the base URL until we actually need to call Rippling
# (so file-only runs don't require RIPPLING_BASE_URL to be set/valid).
RIPPLING_BASE_URL_RAW = os.getenv("RIPPLING_BASE_URL", "https://rest.ripplingapis.com")
RIPPLING_MEMBER_SLEEP = float(os.getenv("RIPPLING_MEMBER_SLEEP", "0.05"))
EVERYONE_GROUP_NAME = os.getenv("RIPPLING_EVERYONE_GROUP", "Everyone")
PASS_STATUSES = {s.strip().lower() for s in os.getenv("PASS_STATUSES", "Passed,Completed,Complete").split(",")}
CRITICAL_STATUSES = {s.strip().lower() for s in os.getenv("CRITICAL_STATUSES", "Past Due").split(",")}


def get_rippling_token() -> str:
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RIPPLING_API_TOKEN is not set.")
    return token


def rippling_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {get_rippling_token()}"}
    # allow_redirects=False: a 30x response with a Location header could redirect
    # the request (and its Authorization header) to an attacker-controlled host.
    resp = requests.get(url, headers=headers, params=params, timeout=30, allow_redirects=False)
    if resp.status_code in (301, 302, 303, 307, 308):
        raise RuntimeError(
            f"Rippling returned redirect {resp.status_code} to {resp.headers.get('Location')!r}; "
            f"refusing to follow (token would leak)."
        )
    if resp.status_code == 429:
        print("  Rate limited (429). Sleeping 15s then retrying...")
        time.sleep(15)
        resp = requests.get(url, headers=headers, params=params, timeout=30, allow_redirects=False)
    if resp.status_code >= 400:
        body = resp.text[:500] if resp.text else "(empty body)"
        raise RuntimeError(f"Rippling HTTP {resp.status_code} for {resp.url}\n  Body: {body}")
    return resp.json()


def rippling_paginate(initial_url: str, initial_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    next_url: Optional[str] = initial_url
    next_params = initial_params
    while next_url:
        # Defense in depth: every URL we follow (including next_link from the
        # API response) must pass the host allowlist.
        _enforce_rippling_host(next_url)
        payload = rippling_get(next_url, params=next_params)
        results.extend(payload.get("results", []))
        next_url = payload.get("next_link")
        next_params = None
    return results


def _enforce_rippling_host(url: str) -> None:
    """Re-check the host on every URL we hit (including next_link values)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError(f"Refusing non-HTTPS Rippling URL: {url}")
    host = (parsed.hostname or "").lower()
    if host not in RIPPLING_HOST_ALLOWLIST:
        raise RuntimeError(f"Refusing Rippling URL with disallowed host: {host}")


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
# File-mode loaders (use safe_evidence_path)
# ---------------------------------------------------------------------------

def load_rippling_from_paramify_file(path_str: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Read a downloaded Paramify supergroups artifact and extract Everyone members."""
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
# Report builders (unchanged logic — these only operate on parsed data)
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

def main():
    extra = _parse_extra_args()
    _strip_custom_args_from_argv()
    output_dir, _profile, _region = parse_fetcher_args()
    evidence_dir = Path(output_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    rippling_file = extra.get("rippling_evidence_file") or os.getenv("RIPPLING_EVIDENCE_FILE", "").strip()
    if rippling_file:
        print(f"\nStep 1: Load Rippling from Paramify-downloaded file ({rippling_file}) ...")
        everyone, members = load_rippling_from_paramify_file(rippling_file)
        rippling_path = evidence_dir / "rippling_everyone_members.json"
        with rippling_path.open("w", encoding="utf-8") as f:
            json.dump({
                "source": "rippling_via_paramify",
                "source_file": rippling_file,
                "group_display_name": everyone.get("display_name"),
                "group_id": everyone.get("id"),
                "count": len(members),
                "results": members,
            }, f, indent=2)
        print(f"  Saved {len(members)} members -> {rippling_path}")
    else:
        print("\nStep 1: Fetch Rippling Everyone group from live API ...")
        # Validate base URL only when actually calling Rippling.
        base_url = validate_rippling_base_url(RIPPLING_BASE_URL_RAW)
        everyone = find_everyone_group(base_url)
        if not everyone:
            raise RuntimeError(f"Could not find supergroup '{EVERYONE_GROUP_NAME}'.")
        members = fetch_everyone_members(base_url, everyone["id"])
        rippling_path = evidence_dir / "rippling_everyone_members.json"
        with rippling_path.open("w", encoding="utf-8") as f:
            json.dump({
                "source": "rippling",
                "endpoint": f"/supergroups/{everyone['id']}/members/",
                "group_display_name": everyone.get("display_name"),
                "group_id": everyone["id"],
                "count": len(members),
                "results": members,
            }, f, indent=2)
        print(f"  Saved {len(members)} members -> {rippling_path}")

    print("\nStep 2: Load KnowBe4 evidence ...")
    kb4_evidence_path = extra["kb4_evidence_file"] or os.getenv("KB4_EVIDENCE_FILE", "").strip()
    if not kb4_evidence_path:
        raise RuntimeError("No KnowBe4 evidence file. Use --kb4-evidence-file <path>.")
    enrollments, kb4_summary = load_kb4_evidence(kb4_evidence_path)
    kb4_out_path = evidence_dir / "knowbe4_module_enrollments.json"
    with kb4_out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "source": "knowbe4",
            "mode": f"evidence_file:{Path(kb4_evidence_path).name}",
            "enrollment_count": len(enrollments),
            "summary": kb4_summary,
            "enrollments": enrollments,
        }, f, indent=2)
    print(f"  Saved {len(enrollments)} enrollments -> {kb4_out_path}")

    print("\nStep 3: Build per-person gap report (email primary, name fallback) ...")
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

    # Name-fallback: case-insensitive, whitespace-normalized.
    def norm_name(s: Optional[str]) -> str:
        return " ".join((s or "").lower().split())

    matched_emails_in_kb4 = set(enrollments_by_email.keys()) & set(rippling_by_email.keys())
    unmatched_kb4_emails = set(enrollments_by_email.keys()) - matched_emails_in_kb4
    unmatched_rippling_emails = set(rippling_by_email.keys()) - matched_emails_in_kb4

    name_fallback_matches: List[Dict] = []
    if unmatched_rippling_emails and unmatched_kb4_emails:
        kb4_by_name: Dict[str, List[str]] = {}
        for kb4_email in unmatched_kb4_emails:
            kb4_name = norm_name(kb4_user_full_name(enrollments_by_email[kb4_email][0]))
            if kb4_name:
                kb4_by_name.setdefault(kb4_name, []).append(kb4_email)
        for r_email in list(unmatched_rippling_emails):
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

    gap_path = evidence_dir / "rippling_vs_knowbe4_gap.json"
    with gap_path.open("w", encoding="utf-8") as f:
        json.dump({
            "source": "rippling_vs_knowbe4",
            "match_key": "work_email",
            "pass_statuses": sorted(PASS_STATUSES),
            "critical_statuses": sorted(CRITICAL_STATUSES),
            "summary": summary,
            "per_person": per_person,
        }, f, indent=2)
    print(f"  Saved gap report -> {gap_path}")

    print("\nSummary:")
    for k, v in summary["totals"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
