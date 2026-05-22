#!/usr/bin/env python3
"""
# Helper script for Rippling Organizational Structure
# Evidence for org-level access groupings: supergroups (with members),
# departments (with hierarchy), teams, companies, and employment types.

Queries the Rippling REST API to retrieve organizational metadata used
for compliance evidence (access reviews, SoD, org structure documentation).

API reference: https://developer.rippling.com/documentation/rest-api
Endpoints:
  GET /supergroups/?filter=group_type+eq+'Group'   (real human-managed groups only)
  GET /supergroups/{id}/members/                   (member roster per group)
  GET /departments/?expand=parent,department_hierarchy
  GET /teams/
  GET /companies/
  GET /employment-types/

Environment variables required:
- RIPPLING_API_TOKEN  REST API token (sent as Bearer)

Required token scopes:
- supergroups.read
- departments.read
- teams.read
- companies.read
- employment-types.read

Optional:
- RIPPLING_BASE_URL          Defaults to https://rest.ripplingapis.com
- RIPPLING_MEMBER_SLEEP      Seconds between member fetches (default 0.05).
                             Helps stay under the 300 req / 10 sec rate limit.

Usage:
    python rippling_org_structure.py [--output-dir <path>]

Output (under the evidence output directory):
    rippling_supergroups.json
    rippling_departments.json
    rippling_teams.json
    rippling_companies.json
    rippling_employment_types.json
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common.env_loader import parse_fetcher_args
except ModuleNotFoundError:
    # Standalone fallback - works outside the evidence-fetchers repo
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


BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://rest.ripplingapis.com").rstrip("/")
SLEEP_BETWEEN_MEMBER_CALLS = float(os.getenv("RIPPLING_MEMBER_SLEEP", "0.05"))


def get_token() -> str:
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "RIPPLING_API_TOKEN is not set. "
            "Set it in your .env file or environment before running this script."
        )
    return token


def rippling_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make a single GET request to the Rippling REST API with 429 retry."""
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {get_token()}",
        },
        params=params,
        timeout=30,
    )
    if resp.status_code == 429:
        print("  Rate limited (429). Sleeping 15s then retrying...")
        time.sleep(15)
        resp = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {get_token()}",
            },
            params=params,
            timeout=30,
        )
    if resp.status_code >= 400:
        body = resp.text[:500] if resp.text else "(empty body)"
        raise RuntimeError(f"Rippling HTTP {resp.status_code} for {resp.url}\n  Body: {body}")
    return resp.json()


def paginate(initial_url: str, initial_params: Optional[Dict[str, Any]] = None,
             on_page: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """Cursor-based pagination via the next_link field returned by Rippling."""
    results: List[Dict[str, Any]] = []
    next_url: Optional[str] = initial_url
    next_params = initial_params
    page_num = 0
    while next_url:
        page_num += 1
        payload = rippling_get(next_url, params=next_params)
        page_results = payload.get("results", [])
        meta = payload.get("__meta") or {}
        redacted = meta.get("redacted_fields") if isinstance(meta, dict) else None
        if on_page:
            on_page(page_num, page_results, redacted)
        results.extend(page_results)
        next_url = payload.get("next_link")
        next_params = None
    return results


def make_progress_printer(label: str):
    total = {"count": 0}
    def _print(page_num, records, redacted):
        total["count"] += len(records)
        note = f" (redacted: {redacted})" if redacted else ""
        print(f"  Page {page_num}: got {len(records)} {label} (total: {total['count']}){note}")
    return _print


def fetch_supergroups() -> List[Dict[str, Any]]:
    """Server-side filter to only return real human-managed groups (group_type=Group)."""
    print(f"\nFetching supergroups (group_type=Group) from {BASE_URL}/supergroups/ ...")
    return paginate(
        f"{BASE_URL}/supergroups/",
        {"filter": "group_type eq 'Group'"},
        on_page=make_progress_printer("supergroups"),
    )


def fetch_supergroup_members(group_id: str) -> List[Dict[str, Any]]:
    # No expand=worker - that requires workers.read scope which is not in this fetcher's required set.
    return paginate(f"{BASE_URL}/supergroups/{group_id}/members/", None)


def fetch_supergroups_with_members() -> List[Dict[str, Any]]:
    supergroups = fetch_supergroups()
    print(f"\nFetching members for each of {len(supergroups)} supergroups ...")
    for idx, group in enumerate(supergroups, start=1):
        gid = group.get("id")
        name = group.get("display_name") or group.get("name") or "(unnamed)"
        if not gid:
            group["members"], group["member_count"] = [], 0
            continue
        try:
            members = fetch_supergroup_members(gid)
            group["members"], group["member_count"] = members, len(members)
            print(f"  [{idx}/{len(supergroups)}] '{name}': {len(members)} members")
        except RuntimeError as exc:
            group["members"], group["member_count"] = [], 0
            group["fetch_error"] = str(exc)
            print(f"  [{idx}/{len(supergroups)}] '{name}': FAILED - {exc}")
        if SLEEP_BETWEEN_MEMBER_CALLS > 0:
            time.sleep(SLEEP_BETWEEN_MEMBER_CALLS)
    return supergroups


def fetch_departments() -> List[Dict[str, Any]]:
    print(f"\nFetching departments from {BASE_URL}/departments/ ...")
    return paginate(
        f"{BASE_URL}/departments/",
        {"expand": "parent,department_hierarchy"},
        on_page=make_progress_printer("departments"),
    )


def fetch_teams() -> List[Dict[str, Any]]:
    print(f"\nFetching teams from {BASE_URL}/teams/ ...")
    return paginate(f"{BASE_URL}/teams/", None, on_page=make_progress_printer("teams"))


def fetch_companies() -> List[Dict[str, Any]]:
    print(f"\nFetching companies from {BASE_URL}/companies/ ...")
    return paginate(f"{BASE_URL}/companies/", None, on_page=make_progress_printer("companies"))


def fetch_employment_types() -> List[Dict[str, Any]]:
    print(f"\nFetching employment types from {BASE_URL}/employment-types/ ...")
    return paginate(f"{BASE_URL}/employment-types/", None, on_page=make_progress_printer("employment-types"))


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved -> {path}")


def main() -> None:
    output_dir, _profile, _region = parse_fetcher_args()
    evidence_dir = Path(output_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    print(f"Rippling org structure fetcher")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Output:   {evidence_dir}")

    # 1. Supergroups (filtered server-side to real groups) + members
    supergroups = fetch_supergroups_with_members()
    provisioning = [g for g in supergroups if str(g.get("display_name", "")).upper() == "PROVISIONING"]
    write_json(evidence_dir / "rippling_supergroups.json", {
        "source": "rippling",
        "endpoint": "/supergroups/?filter=group_type+eq+'Group'",
        "count": len(supergroups),
        "provisioning_group_count": len(provisioning),
        "results": supergroups,
    })

    # 2. Departments with hierarchy
    departments = fetch_departments()
    write_json(evidence_dir / "rippling_departments.json", {
        "source": "rippling",
        "endpoint": "/departments/",
        "count": len(departments),
        "results": departments,
    })

    # 3. Teams
    teams = fetch_teams()
    write_json(evidence_dir / "rippling_teams.json", {
        "source": "rippling",
        "endpoint": "/teams/",
        "count": len(teams),
        "results": teams,
    })

    # 4. Companies
    companies = fetch_companies()
    write_json(evidence_dir / "rippling_companies.json", {
        "source": "rippling",
        "endpoint": "/companies/",
        "count": len(companies),
        "results": companies,
    })

    # 5. Employment types
    employment_types = fetch_employment_types()
    write_json(evidence_dir / "rippling_employment_types.json", {
        "source": "rippling",
        "endpoint": "/employment-types/",
        "count": len(employment_types),
        "results": employment_types,
    })

    print(f"\nDone. 5 evidence files written to {evidence_dir}")


if __name__ == "__main__":
    main()
