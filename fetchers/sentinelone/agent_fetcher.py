#!/usr/bin/env python3
"""
SentinelOne Agents Configuration Retrieval

Purpose: Pull SentinelOne agent records and provide a summary analysis.
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


def fetch_all_pages(base_url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    all_records: List[Dict[str, Any]] = []
    cursor = None
    endpoint = f"{base_url}/web/api/v2.1/agents"

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


def fetch_agents_count(base_url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Optional[int]:
    endpoint = f"{base_url}/web/api/v2.1/agents/count"
    try:
        response = http_get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        # payload expected to contain data.total
        return int(payload.get("data", {}).get("total", 0))
    except requests.exceptions.RequestException:
        return None


def extract_field_list(records: List[Dict[str, Any]], field_key: str) -> List[Any]:
    return [r.get(field_key) for r in records if field_key in r]


def last_successful_scan_percentage(records: List[Dict[str, Any]]) -> float:
    """Return the fraction (0..1) of records with a non-null lastSuccessfulScanDate."""
    if not records:
        return 0.0
    total = len(records)
    non_null = sum(1 for r in records if r.get("lastSuccessfulScanDate") not in (None, "", []))
    try:
        return float(non_null) / float(total)
    except Exception:
        return 0.0


def get_agents() -> Dict[str, Any]:
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
            return {"status": "partial_or_empty", "message": "No records found", "retrieved_at": current_timestamp()}

        reported_count = fetch_agents_count(api_url, headers)

        cluster_names = [
            r.get("cloudProviders", {}).get("Kubernetes", {}).get("clusterName")
            for r in records
            if r.get("cloudProviders", {}).get("Kubernetes", {}).get("clusterName")
        ]

        containers_count = [
            r.get("containerizedWorkloadCounts", {}).get("containersCount")
            for r in records
            if r.get("containerizedWorkloadCounts")
        ]

        pods_count = [
            r.get("containerizedWorkloadCounts", {}).get("podsCount")
            for r in records
            if r.get("containerizedWorkloadCounts")
        ]

        tasks_count = [
            r.get("containerizedWorkloadCounts", {}).get("tasksCount")
            for r in records
            if r.get("containerizedWorkloadCounts")
        ]

        subnet_ids = [
            r.get("cloudProviders", {}).get("AWS", {}).get("awsSubnetIds")
            for r in records
            if r.get("cloudProviders", {}).get("AWS", {}).get("awsSubnetIds")
        ]

        result = {
            "status": "success",
            "api_endpoint": f"{api_url}/web/api/v2.1/agents",
            "record_count": len(records),
            "data": records,
            "analysis": {
                "total_agents": len(records),
                "reported_agent_count": reported_count,
                "cluster_names": dict(Counter([c for c in cluster_names if c])),
                "containers_count": containers_count,
                "pods_count": pods_count,
                "tasks_count": tasks_count,
                "subnet_ids": subnet_ids,
                "last_successful_scan_percentage": last_successful_scan_percentage(records),
            },
            "retrieved_at": current_timestamp(),
        }

        return result

    except Exception as e:
        return {"status": "error", "message": str(e), "retrieved_at": current_timestamp()}


def main() -> int:
    if len(sys.argv) != 5:
        print("Usage: python agentfetcher.py <profile> <region> <output_dir> <csv_file>")
        return 1

    _profile = sys.argv[1]
    _region = sys.argv[2]
    output_dir = sys.argv[3]
    csv_file = sys.argv[4]

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    component = "agents_config"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_agents()

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        msg = f"Agents config retrieved. Records: {result.get('record_count', 0)}"
        f.write(f"{component},{status},{current_timestamp()},{msg}\n")

    return 0 if result.get("status") in {"success", "partial_or_empty"} else 1


if __name__ == "__main__":
    sys.exit(main())
