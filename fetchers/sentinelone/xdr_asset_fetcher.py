#!/usr/bin/env python3
"""
SentinelOne XDR Asset Configuration Retrieval

Purpose: Pull SentinelOne XDR asset records to demonstrate automated inventory
and summary reporting.
"""

import json
import os
import sys
from collections import Counter
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


def count_healthy_infection(records: List[Dict[str, Any]]) -> int:
    return sum(1 for r in records if r.get("infectionStatus") == "Healthy")


def count_active_assets(records: List[Dict[str, Any]]) -> int:
    return sum(1 for r in records if r.get("assetStatus") == "Active")


def extract_field_list(records: List[Dict[str, Any]], field_key: str) -> List[Any]:
    return [r.get(field_key) for r in records if field_key in r]


def fetch_all_pages(base_url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Handles cursor-based pagination to retrieve all XDR asset records.
    """
    all_records: List[Dict[str, Any]] = []
    cursor = None
    endpoint = f"{base_url}/web/api/v2.1/xdr/assets"

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
            print(f"Warning: Pagination interrupted: {e}", file=sys.stderr)
            break

    return all_records


def get_xdr_assets() -> Dict[str, Any]:
    # Use environment variables set by orchestration layer
    api_url = get_env("SENTINELONE_API_URL")
    api_token = get_env("SENTINELONE_API_TOKEN")

    api_url = api_url.rstrip("/")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"ApiToken {api_token}",
    }

    try:
        records = fetch_all_pages(api_url, headers)

        if not records:
            return {
                "status": "partial_or_empty",
                "message": "No records found or API returned empty list",
                "retrieved_at": current_timestamp(),
            }

        region_list = [r.get("region") for r in records if "region" in r]
        name_list = [r.get("name") for r in records if "name" in r]

        result = {
            "status": "success",
            "api_endpoint": f"{api_url}/web/api/v2.1/xdr/assets",
            "record_count": len(records),
            "data": records,
            "analysis": {
                "total_asset_count": len(records),
                "healthy_infection_status_count": count_healthy_infection(records),
                "active_asset_status_count": count_active_assets(records),
                "region_count": dict(Counter(region_list)),
                "name_count": dict(Counter(name_list)),
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
        print("Usage: python xdrassetfetcher.py <profile> <region> <output_dir> <csv_file>")
        return 1

    _profile = sys.argv[1]
    _region = sys.argv[2]
    output_dir = sys.argv[3]
    csv_file = sys.argv[4]

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    component = "xdr_asset_config"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_xdr_assets()

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        msg = f"Asset config retrieved. Records: {result.get('record_count', 0)}"
        f.write(f"{component},{status},{current_timestamp()},{msg}\n")

    return 0 if result.get("status") in {"success", "partial_or_empty"} else 1


if __name__ == "__main__":
    sys.exit(main())
