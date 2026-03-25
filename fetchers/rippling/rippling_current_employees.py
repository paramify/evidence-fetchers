#!/usr/bin/env python3
"""
# Helper script for Rippling Current Employees
# Evidence for list of current active employees

Queries the Rippling Platform API to retrieve all currently active employees.
Uses offset-based pagination to handle large employee lists.

API reference: https://developer.rippling.com/documentation/rest-api
Endpoint: GET /platform/api/employees

Environment variables required:
- RIPPLING_API_TOKEN  Bearer token (from Rippling Developer Portal)

Optional:
- RIPPLING_BASE_URL   Defaults to https://api.rippling.com
- RIPPLING_PAGE_SIZE  Records per page, defaults to 100

Usage:
    python rippling_current_employees.py [--output-dir <path>]

Output:
    rippling_current_employees.json  under the evidence output directory
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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

BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://api.rippling.com").rstrip("/")
PAGE_SIZE = int(os.getenv("RIPPLING_PAGE_SIZE", "100"))


def get_token() -> str:
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "RIPPLING_API_TOKEN is not set. "
            "Set it in your .env file or environment before running this script."
        )
    return token


def rippling_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Make a single GET request to the Rippling API."""
    url = f"{BASE_URL}{path}"
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {get_token()}",
        },
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_records(payload: Any) -> List[Dict]:
    """Handle both list responses and wrapped dict responses."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "employees", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def fetch_current_employees() -> List[Dict]:
    """Fetch all active employees using offset-based pagination."""
    results: List[Dict] = []
    offset = 0

    print(f"Fetching active employees from {BASE_URL}/platform/api/employees ...")
    while True:
        payload = rippling_get(
            "/platform/api/employees",
            params={"limit": PAGE_SIZE, "offset": offset},
        )
        page = extract_records(payload)
        results.extend(page)
        print(f"  Page offset={offset}: got {len(page)} records (total so far: {len(results)})")

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return results


def main() -> None:
    output_dir, _profile, _region = parse_fetcher_args()

    evidence_dir = Path(output_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    employees = fetch_current_employees()

    out_path = evidence_dir / "rippling_current_employees.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": "rippling",
                "endpoint": "/platform/api/employees",
                "mode": "current_active",
                "count": len(employees),
                "results": employees,
            },
            f,
            indent=2,
        )

    print(f"\n\u2713 Saved {len(employees)} active employees -> {out_path}")


if __name__ == "__main__":
    main()
