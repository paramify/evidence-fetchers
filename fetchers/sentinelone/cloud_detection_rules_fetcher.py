#!/usr/bin/env python3
"""
SentinelOne Cloud Detection Rules Retrieval

Purpose: Pull custom cloud detection rules and provide a summary analysis.
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


def fetch_all_pages(base_url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    all_records: List[Dict[str, Any]] = []
    cursor = None
    endpoint = f"{base_url}/web/api/v2.1/cloud-detection/rules"

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


def get_cloud_detection_rules() -> Dict[str, Any]:
    api_url = get_env("SENTINELONE_API_URL")
    api_token = get_env("SENTINELONE_API_TOKEN")
    api_url = api_url.rstrip("/")

    headers = {"Content-Type": "application/json", "Authorization": f"ApiToken {api_token}"}

    try:
        records = fetch_all_pages(api_url, headers)
        if not records:
            return {"status": "partial_or_empty", "message": "No records found", "retrieved_at": current_timestamp()}

        last_alert_time = [r.get("lastAlertTime") for r in records if "lastAlertTime" in r]
        last_updated_at = [r.get("updatedAt") for r in records if "updatedAt" in r]

        last_activity_list = [
            max(t for t in [r.get("lastAlertTime"), r.get("updatedAt")] if t)
            for r in records
            if r.get("lastAlertTime") or r.get("updatedAt")
        ]

        result = {
            "status": "success",
            "api_endpoint": f"{api_url}/web/api/v2.1/cloud-detection/rules",
            "record_count": len(records),
            "data": records,
            "analysis": {
                "total_custom_detection_rules": len(records),
                "rules_never_triggered_count": sum(1 for t in last_alert_time if t is None),
                "last_alert_times": last_alert_time,
                "last_updated_at": last_updated_at,
                "last_activity_time": last_activity_list,
            },
            "retrieved_at": current_timestamp(),
        }

        return result

    except Exception as e:
        return {"status": "error", "message": str(e), "retrieved_at": current_timestamp()}


def main() -> int:
    if len(sys.argv) != 5:
        print("Usage: python clouddetectionrules.py <profile> <region> <output_dir> <csv_file>")
        return 1

    _profile = sys.argv[1]
    _region = sys.argv[2]
    output_dir = sys.argv[3]
    csv_file = sys.argv[4]

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    component = "cloud_detection_rules"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_cloud_detection_rules()

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        msg = f"Cloud detection rules retrieved. Records: {result.get('record_count', 0)}"
        f.write(f"{component},{status},{current_timestamp()},{msg}\n")

    return 0 if result.get("status") in {"success", "partial_or_empty"} else 1


if __name__ == "__main__":
    sys.exit(main())
