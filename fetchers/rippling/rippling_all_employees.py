#!/usr/bin/env python3
"""
# Helper script for Rippling All Employees
# Evidence for list of all employees including terminated

This script queries the Rippling REST API `/platform/api/employees/include_terminated` endpoint to retrieve all employees including terminated ones.

API reference: https://developer.rippling.com/documentation/rest-api

Environment variables required:
- RIPPLING_API_TOKEN (Bearer token)

Usage:
    python rippling_all_employees.py <evidence-dir>

Output:
    Writes JSON file with all employees under evidence-dir
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests


def rippling_request(path: str, params: Optional[Dict[str, str]] = None) -> List[Dict]:
    base_url = "https://api.rippling.com"
    token = os.getenv("RIPPLING_API_TOKEN")
    if not token:
        raise RuntimeError("RIPPLING_API_TOKEN is required")

    url = f"{base_url.rstrip('/')}{path}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_all_employees() -> List[Dict]:
    results: List[Dict] = []
    limit = 100  # Maximum per Rippling API docs
    offset = 0

    while True:
        params = {"limit": str(limit), "offset": str(offset)}
        
        # Get all employees including terminated
        data = rippling_request("/platform/api/employees/include_terminated", params=params)
        results.extend(data)
        
        # If we got fewer than the limit, we've reached the end
        if len(data) < limit:
            break
            
        offset += limit

    return results


def main() -> None:
    if len(sys.argv) != 5:
        print("Usage: python rippling_all_employees.py <profile> <region> <evidence-dir> <csv-file>")
        sys.exit(1)

    evidence_dir = Path(sys.argv[3])
    evidence_dir.mkdir(parents=True, exist_ok=True)

    employees = fetch_all_employees()

    out_path = evidence_dir / "rippling_all_employees.json"
    with open(out_path, "w") as f:
        json.dump({
            "mode": "all",
            "count": len(employees),
            "results": employees
        }, f, indent=2)

    # Simple CSV summary: count only
    csv_path = evidence_dir / "rippling_employees_summary.csv"
    if not csv_path.exists():
        with open(csv_path, "w") as f:
            f.write("mode,count\n")
    with open(csv_path, "a") as f:
        f.write(f"all,{len(employees)}\n")

    print(f"Saved: {out_path}")
    print(f"Total employees (including terminated): {len(employees)}")


if __name__ == "__main__":
    main()
