#!/usr/bin/env python3
"""
SentinelOne User Management Configuration Retrieval
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def current_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def http_get(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> requests.Response:
    return requests.get(url, headers=headers, params=params, timeout=30)


def count_admins(records: List[Dict[str, Any]]) -> int:
    count = 0
    for record in records:
        scope_roles = record.get("scopeRoles", [])
        # Check if 'roles' list exists in any scope role entry and if 'Admin' is present
        if any("Admin" in sr.get("roles", []) for sr in scope_roles if isinstance(sr, dict)):
            count += 1
    return count


def count_2fa_enabled(records: List[Dict[str, Any]]) -> int:
    return sum(1 for r in records if r.get("twoFaEnabled") is True)


def count_2fa_configured(records: List[Dict[str, Any]]) -> int:
    return sum(1 for r in records if r.get("twoFaStatus") == "configured")


def extract_field_list(records: List[Dict[str, Any]], field_key: str) -> List[Any]:
    return [r.get(field_key) for r in records if field_key in r]


def fetch_all_pages(base_url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Handles cursor-based pagination to retrieve all user records.
    """
    all_records = []
    cursor = None
    endpoint = f"{base_url}/web/api/v2.1/users"

    while True:
        params = {"cursor": cursor} if cursor else {}
        
        try:
            response = http_get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            
            payload = response.json()
            data = payload.get("data", [])
            all_records.extend(data)
            
            pagination = payload.get("pagination", {})
            cursor = pagination.get("nextCursor")

            if not cursor:
                break
        except requests.exceptions.RequestException as e:
            # We log the error but allow the calling function to handle the partial data or failure
            print(f"Warning: Pagination interrupted: {e}", file=sys.stderr)
            break
            
    return all_records


def get_sentinelone_users() -> Dict[str, Any]:
    # Use environment variables set by orchestration layer
    api_url = get_env("SENTINELONE_API_URL")
    api_token = get_env("SENTINELONE_API_TOKEN")

    # Clean URL to avoid double slashes if user included trailing slash
    api_url = api_url.rstrip("/")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"ApiToken {api_token}"
    }

    try:
        # Fetch Data
        records = fetch_all_pages(api_url, headers)

        if not records:
            return {
                "status": "partial_or_empty",
                "message": "No records found or API returned empty list",
                "retrieved_at": current_timestamp(),
            }

        # Analyze Data (Mapping original 'summary' logic to 'analysis' block)
        result = {
            "status": "success",
            "api_endpoint": f"{api_url}/web/api/v2.1/users",
            "record_count": len(records),
            "data": records,  # The raw records
            "analysis": {
                "total_user_count": len(records),
                "admin_user_count": count_admins(records),
                "two_factor_authentication_enabled_count": count_2fa_enabled(records),
                "two_factor_authentication_configured_count": count_2fa_configured(records),
                "full_names": extract_field_list(records, "fullName"),
                "last_logins": extract_field_list(records, "lastLogin"),
                "sources": extract_field_list(records, "source"),
            },
            "retrieved_at": current_timestamp(),
        }
        return result

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "retrieved_at": current_timestamp(),
        }


def main() -> int:
    # Args from runner: profile, region, output_dir, csv_file
    if len(sys.argv) != 5:
        print("Usage: python sentinelone_user_config.py <profile> <region> <output_dir> <csv_file>")
        return 1

    _profile = sys.argv[1]
    _region = sys.argv[2]
    output_dir = sys.argv[3]
    csv_file = sys.argv[4]

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    component = "sentinelone_user_config"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_sentinelone_users()

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Append CSV summary
    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        # Generate a brief summary message based on analysis if available
        msg = f"User config retrieved. Records: {result.get('record_count', 0)}"
        f.write(f"{component},{status},{current_timestamp()},{msg}\n")

    return 0 if result.get("status") in {"success", "partial_or_empty"} else 1


if __name__ == "__main__":
    sys.exit(main())