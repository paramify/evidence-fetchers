#!/usr/bin/env python3
"""
SentinelOne Activities Retrieval

Purpose: Pull SentinelOne activities for selected activity types and provide summary analysis.
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


def fetch_all_pages(base_url: str, headers: Dict[str, str], activity_type_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    all_records: List[Dict[str, Any]] = []
    cursor = None
    endpoint = f"{base_url}/web/api/v2.1/activities"

    # If activity types provided, join into comma-separated string
    activity_type_str = ",".join(map(str, activity_type_ids)) if activity_type_ids else None

    while True:
        params = {"cursor": cursor}
        if activity_type_str:
            params["activityTypes"] = activity_type_str
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


def get_activities() -> Dict[str, Any]:
    api_url = get_env("SENTINELONE_API_URL")
    api_token = get_env("SENTINELONE_API_TOKEN")
    api_url = api_url.rstrip("/")

    headers = {"Content-Type": "application/json", "Authorization": f"ApiToken {api_token}"}

    # Default fedramp activity type ids (from original activity_fetcher)
    fedramp_ids = [5125, 5232, 4112, 7803, 104, 111, 5040, 5041, 5042, 7700, 7800, 7853, 7881, 70, 77, 5044, 3750, 3752, 5228, 65, 153, 1025, 5027, 7834, 7854, 13029]

    try:
        records = fetch_all_pages(api_url, headers, activity_type_ids=fedramp_ids)
        if not records:
            return {"status": "partial_or_empty", "message": "No records found", "retrieved_at": current_timestamp()}

        activity_type = [r.get("activityType") for r in records if "activityType" in r]
        created_at = [r.get("createdAt") for r in records if "createdAt" in r]
        primary_description = [r.get("primaryDescription") for r in records if "primaryDescription" in r]

        result = {
            "status": "success",
            "api_endpoint": f"{api_url}/web/api/v2.1/activities",
            "record_count": len(records),
            "data": records,
            "analysis": {
                "total_activities_collected": len(records),
                "activity_type": dict(Counter(activity_type)) if activity_type else {},
                "created_at": created_at,
                "primary_description": primary_description,
            },
            "retrieved_at": current_timestamp(),
        }

        return result

    except Exception as e:
        return {"status": "error", "message": str(e), "retrieved_at": current_timestamp()}


def main() -> int:
    if len(sys.argv) != 5:
        print("Usage: python activityfetcher.py <profile> <region> <output_dir> <csv_file>")
        return 1

    _profile = sys.argv[1]
    _region = sys.argv[2]
    output_dir = sys.argv[3]
    csv_file = sys.argv[4]

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    component = "sentinelone_activities"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_activities()

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        msg = f"Activities retrieved. Records: {result.get('record_count', 0)}"
        f.write(f"{component},{status},{current_timestamp()},{msg}\n")

    return 0 if result.get("status") in {"success", "partial_or_empty"} else 1


if __name__ == "__main__":
    from collections import Counter
    sys.exit(main())
