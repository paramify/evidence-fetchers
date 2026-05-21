#!/usr/bin/env python3
"""
# Helper script for Rippling <-> KnowBe4 Training Cross-Reference
Compares Rippling "Everyone" supergroup members against KnowBe4 enrollments.
Match key: work_email (lowercased).
Outputs 3 files: rippling_everyone_members.json,
knowbe4_module_enrollments.json, rippling_vs_knowbe4_gap.json.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def load_rippling_from_paramify_file(path_str):
    """Read a downloaded Paramify supergroups artifact and extract Everyone members."""
    with open(path_str, encoding="utf-8") as f:
        artifact = json.load(f)
    results = artifact.get("results", [])
    for g in results:
        name = (g.get("display_name") or g.get("name") or "").strip()
        if name.lower() == EVERYONE_GROUP_NAME.lower():
            members = g.get("members", [])
            print(f"Loaded Rippling from file: {path_str}")
            print(f"  Found '{name}' group (id={g.get('id')}) with {len(members)} members")
            return g, members
    available = [g.get("display_name") or g.get("name") for g in results]
    raise RuntimeError(
        f"'{EVERYONE_GROUP_NAME}' group not found in {path_str}. "
        f"Available groups (first 10): {available[:10]}"
    )


RIPPLING_BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://rest.ripplingapis.com").rstrip("/")
RIPPLING_MEMBER_SLEEP = float(os.getenv("RIPPLING_MEMBER_SLEEP", "0.05"))
EVERYONE_GROUP_NAME = os.getenv("RIPPLING_EVERYONE_GROUP", "Everyone")
PASS_STATUSES = {s.strip().lower() for s in os.getenv("PASS_STATUSES", "Passed,Completed,Complete").split(",")}
CRITICAL_STATUSES = {s.strip().lower() for s in os.getenv("CRITICAL_STATUSES", "Past Due").split(",")}


def get_rippling_token():
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RIPPLING_API_TOKEN is not set.")
    return token


def rippling_get(url, params=None):
    headers = {"Accept": "application/json", "Authorization": f"Bearer {get_rippling_token()}"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code == 429:
        print("  Rate limited (429). Sleeping 15s then retrying...")
        time.sleep(15)
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code >= 400:
        body = resp.text[:500] if resp.text else "(empty body)"
        raise RuntimeError(f"Rippling HTTP {resp.status_code} for {resp.url}\n  Body: {body}")
    return resp.json()


def rippling_paginate(initial_url, initial_params=None):
    results = []
    next_url = initial_url
    next_params = initial_params
    while next_url:
        payload = rippling_get(next_url, params=next_params)
        results.extend(payload.get("results", []))
        next_url = payload.get("next_link")
        next_params = None
    return results


def find_everyone_group():
    print(f"Searching Rippling for '{EVERYONE_GROUP_NAME}' supergroup ...")
    groups = rippling_paginate(
        f"{RIPPLING_BASE_URL}/supergroups/",
        {"filter": "group_type eq 'Group'"},
    )
    for g in groups:
        if (g.get("display_name") or g.get("name") or "") == EVERYONE_GROUP_NAME:
            print(f"  Found group id={g.get('id')}")
            return g
    print(f"  Group '{EVERYONE_GROUP_NAME}' not found.")
    return None


def fetch_everyone_members(group_id):
    print(f"Fetching members of {group_id} ...")
    members = rippling_paginate(f"{RIPPLING_BASE_URL}/supergroups/{group_id}/members/", None)
    print(f"  Got {len(members)} members")
    if RIPPLING_MEMBER_SLEEP > 0:
        time.sleep(RIPPLING_MEMBER_SLEEP)
    return members


def rippling_email(member):
    email = (member.get("work_email") or member.get("workEmail") or member.get("email") or "").strip().lower()
    return email or None


def load_kb4_evidence(path):
    with open(path, encoding="utf-8") as f:
        evidence = json.load(f)
    results = evidence.get("results", {})
    enrollments = results.get("enrollments", []) if isinstance(results, dict) else []
    summary = results.get("summary", {}) if isinstance(results, dict) else {}
    print(f"Loaded KnowBe4 evidence from {path}")
    print(f"  {len(enrollments)} enrollment records")
    return enrollments, summary


def kb4_user_email(enrollment):
    user = enrollment.get("user") or {}
    email = (user.get("email") or "").strip().lower()
    return email or None


def kb4_user_full_name(enrollment):
    user = enrollment.get("user") or {}
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    return (first + " " + last).strip()


def build_per_person_report(rippling_by_email, enrollments_by_email):
    all_emails = set(rippling_by_email.keys()) | set(enrollments_by_email.keys())
    report = []
    for email in sorted(all_emails):
        rippling_member = rippling_by_email.get(email)
        kb4_enrollments = enrollments_by_email.get(email, [])
        rippling_name = rippling_member.get("full_name") if rippling_member else None
        kb4_name = kb4_user_full_name(kb4_enrollments[0]) if kb4_enrollments else None
        kb4_user_id = (kb4_enrollments[0].get("user") or {}).get("id") if kb4_enrollments else None
        campaigns = {}
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
        flags = []
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
        everyone = find_everyone_group()
        if not everyone:
            raise RuntimeError(f"Could not find supergroup '{EVERYONE_GROUP_NAME}'.")
        members = fetch_everyone_members(everyone["id"])
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
    rippling_by_email = {}
    rippling_no_email = []
    for m in members:
        email = rippling_email(m)
        if email:
            rippling_by_email[email] = m
        else:
            rippling_no_email.append(m)
    enrollments_by_email = {}
    enrollments_no_email = []
    for enr in enrollments:
        email = kb4_user_email(enr)
        if email:
            enrollments_by_email.setdefault(email, []).append(enr)
        else:
            enrollments_no_email.append(enr)

    # Name-fallback pass: any Rippling member without an email match, try matching
    # an unmatched KB4 user by full_name (case-insensitive, whitespace-normalized).
    def norm_name(s):
        return " ".join((s or "").lower().split())

    matched_emails_in_kb4 = set(enrollments_by_email.keys()) & set(rippling_by_email.keys())
    unmatched_kb4_emails = set(enrollments_by_email.keys()) - matched_emails_in_kb4
    unmatched_rippling_emails = set(rippling_by_email.keys()) - matched_emails_in_kb4

    name_fallback_matches = []
    if unmatched_rippling_emails and unmatched_kb4_emails:
        kb4_by_name = {}
        for kb4_email in unmatched_kb4_emails:
            kb4_name = norm_name(kb4_user_full_name(enrollments_by_email[kb4_email][0]))
            if kb4_name:
                kb4_by_name.setdefault(kb4_name, []).append(kb4_email)
        for r_email in list(unmatched_rippling_emails):
            r_name = norm_name(rippling_by_email[r_email].get("full_name"))
            candidates = kb4_by_name.get(r_name, []) if r_name else []
            if len(candidates) == 1:
                # Merge KB4 enrollments under the Rippling email key.
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
