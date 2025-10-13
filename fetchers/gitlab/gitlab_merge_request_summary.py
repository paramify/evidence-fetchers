#!/usr/bin/env python3
"""
GitLab Merge Request Summary

Purpose: Pull recent merge requests to demonstrate change management
and review process (KSI-CMT-04)
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def current_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def url_encode(segment: str) -> str:
    from urllib.parse import quote
    return quote(segment, safe="")


def http_get(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> requests.Response:
    return requests.get(url, headers=headers, params=params, timeout=30)


def parse_datetime(s: str) -> datetime:
    if not s:
        return None  # type: ignore
    # Normalize Zulu suffix
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def calculate_average(values: List[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def calculate_percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100.0


def calculate_time_to_merge(mr: Dict[str, Any]) -> Optional[float]:
    if not mr.get("merged_at"):
        return None
    created = parse_datetime(mr.get("created_at"))
    merged = parse_datetime(mr.get("merged_at"))
    if not created or not merged:
        return None
    delta = merged - created
    return delta.total_seconds() / 3600.0


def check_approval_before_merge(mr: Dict[str, Any], approvals_data: Dict[str, Any]) -> Optional[bool]:
    if not mr.get("merged_at"):
        return None
    approved_by = approvals_data.get("approved_by", []) or []
    if not approved_by:
        return False
    merge_time = parse_datetime(mr.get("merged_at"))
    times: List[datetime] = []
    for entry in approved_by:
        created_at = entry.get("user", {}).get("created_at") or entry.get("created_at")
        if created_at:
            times.append(parse_datetime(created_at))
    if not times:
        # If no timestamps available, we cannot confirm ordering
        return None
    return all(t < merge_time for t in times)


def get_merge_requests_summary(project_id: str, state: str = "merged", days_back: int = 30, max_results: int = 50) -> Dict[str, Any]:
    # Use environment variables set by orchestration layer
    gitlab_url = get_env("GITLAB_URL")
    api_token = get_env("GITLAB_API_TOKEN")
    api_endpoint = f"{gitlab_url.rstrip('/')}/api/v4"

    headers = {
        "PRIVATE-TOKEN": api_token,
        "Content-Type": "application/json",
    }

    encoded_project = url_encode(project_id)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)

    mr_url = f"{api_endpoint}/projects/{encoded_project}/merge_requests"
    params: Dict[str, Any] = {
        "state": state,
        "order_by": "updated_at",
        "sort": "desc",
        "per_page": 100,
        "page": 1,
        "updated_after": start_date.isoformat() + "Z",
    }

    try:
        all_mrs: List[Dict[str, Any]] = []
        while len(all_mrs) < max_results:
            response = http_get(mr_url, headers=headers, params=params)
            if response.status_code != 200:
                raise RuntimeError(f"API Error: {response.status_code} {response.text}")
            page_mrs = response.json()
            all_mrs.extend(page_mrs)
            if len(page_mrs) < 100 or len(all_mrs) >= max_results:
                break
            next_page = response.headers.get("x-next-page") or response.headers.get("X-Next-Page")
            if next_page:
                params["page"] = int(next_page)
            else:
                break

        all_mrs = all_mrs[:max_results]

        enriched_mrs: List[Dict[str, Any]] = []
        for mr in all_mrs:
            iid = mr.get("iid")
            approvals_url = f"{api_endpoint}/projects/{encoded_project}/merge_requests/{iid}/approvals"
            discussions_url = f"{api_endpoint}/projects/{encoded_project}/merge_requests/{iid}/discussions"
            changes_url = f"{api_endpoint}/projects/{encoded_project}/merge_requests/{iid}/changes"

            approvals_resp = http_get(approvals_url, headers=headers)
            approvals_data = approvals_resp.json() if approvals_resp.status_code == 200 else {}

            discussions_resp = http_get(discussions_url, headers=headers)
            discussions = discussions_resp.json() if discussions_resp.status_code == 200 else []

            changes_resp = http_get(changes_url, headers=headers)
            changes_data = changes_resp.json() if changes_resp.status_code == 200 else {}

            enriched = {
                "iid": iid,
                "title": mr.get("title"),
                "state": mr.get("state"),
                "author": (mr.get("author") or {}).get("name"),
                "author_username": (mr.get("author") or {}).get("username"),
                "created_at": mr.get("created_at"),
                "updated_at": mr.get("updated_at"),
                "merged_at": mr.get("merged_at"),
                "merged_by": (mr.get("merged_by") or {}).get("name") if mr.get("merged_by") else None,
                "source_branch": mr.get("source_branch"),
                "target_branch": mr.get("target_branch"),
                "web_url": mr.get("web_url"),
                "approvals": {
                    "required": approvals_data.get("approvals_required", 0),
                    "received": len(approvals_data.get("approved_by", []) or []),
                    "approvers": [a.get("user", {}).get("name") for a in (approvals_data.get("approved_by", []) or [])],
                    "approved": approvals_data.get("approved", False),
                },
                "discussions": {
                    "count": len(discussions),
                    "resolved": sum(1 for d in discussions if any(n.get("resolved") for n in d.get("notes", []))),
                },
                "changes": {
                    "files_changed": len(changes_data.get("changes", []) or []),
                    "additions": sum(c.get("additions", 0) for c in (changes_data.get("changes", []) or [])),
                    "deletions": sum(c.get("deletions", 0) for c in (changes_data.get("changes", []) or [])),
                },
                "compliance_checks": {
                    "has_approvals": len(approvals_data.get("approved_by", []) or []) > 0,
                    "has_discussion": len(discussions) > 0,
                    "approved_before_merge": check_approval_before_merge(mr, approvals_data),
                    "time_to_merge_hours": calculate_time_to_merge(mr) if mr.get("merged_at") else None,
                },
            }
            enriched_mrs.append(enriched)

        merged_mrs = [mr for mr in enriched_mrs if mr.get("state") == "merged"]
        metrics = {
            "total_mrs": len(enriched_mrs),
            "merged_count": len(merged_mrs),
            "average_approvals": calculate_average([mr["approvals"]["received"] for mr in enriched_mrs]),
            "average_time_to_merge_hours": calculate_average([mr["compliance_checks"]["time_to_merge_hours"] for mr in merged_mrs if mr["compliance_checks"]["time_to_merge_hours"] is not None]),
            "mrs_with_approvals": sum(1 for mr in enriched_mrs if mr["compliance_checks"]["has_approvals"]),
            "mrs_with_discussion": sum(1 for mr in enriched_mrs if mr["compliance_checks"]["has_discussion"]),
            "approval_rate": calculate_percentage(sum(1 for mr in enriched_mrs if mr["compliance_checks"]["has_approvals"]), len(enriched_mrs)),
            "compliance_rate": calculate_percentage(sum(1 for mr in merged_mrs if mr["compliance_checks"]["approved_before_merge"] is True), len(merged_mrs)),
        }

        def generate_compliance_findings(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
            findings: List[Dict[str, Any]] = []
            if metrics.get("approval_rate", 0) < 80:
                findings.append({
                    "severity": "warning",
                    "message": f"Only {metrics.get('approval_rate', 0):.1f}% of MRs have approvals",
                    "recommendation": "Ensure all merge requests receive proper review and approval",
                })
            if metrics.get("compliance_rate", 0) < 100 and metrics.get("merged_count", 0) > 0:
                findings.append({
                    "severity": "info",
                    "message": f"{metrics.get('compliance_rate', 0):.1f}% of merged MRs had approvals before merge",
                    "recommendation": "Enforce approval requirements before merging",
                })
            avg_time = metrics.get("average_time_to_merge_hours")
            if avg_time is not None and avg_time < 1:
                findings.append({
                    "severity": "warning",
                    "message": "Average time to merge is very short (< 1 hour)",
                    "recommendation": "Ensure adequate review time for changes",
                })
            return findings

        result = {
            "status": "success",
            "project_id": project_id,
            "date_range": {
                "start": start_date.isoformat() + "Z",
                "end": end_date.isoformat() + "Z",
                "days": days_back,
            },
            "state_filter": state,
            "metrics": metrics,
            "merge_requests": enriched_mrs,
            "compliance_summary": {
                "change_management_active": len(merged_mrs) > 0,
                "approval_process_enabled": metrics["approval_rate"] > 0,
                "review_process_active": metrics["mrs_with_discussion"] > 0,
                "meets_minimum_review": metrics["approval_rate"] >= 80,
                "findings": generate_compliance_findings(metrics),
            },
            "retrieved_at": current_timestamp(),
        }
        return result
    except Exception as e:
        return {"status": "error", "message": str(e), "project_id": project_id, "retrieved_at": current_timestamp()}


def main() -> int:
    if len(sys.argv) != 5:
        print("Usage: python gitlab_merge_request_summary.py <profile> <region> <output_dir> <csv_file>")
        return 1

    output_dir = sys.argv[3]
    csv_file = sys.argv[4]
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    project_id = os.environ.get("GITLAB_PROJECT_ID", "group/project")
    state = os.environ.get("GITLAB_MR_STATE", "merged")
    days_back = int(os.environ.get("GITLAB_MR_DAYS_BACK", "30"))
    max_results = int(os.environ.get("GITLAB_MR_MAX_RESULTS", "50"))

    component = "gitlab_merge_request_summary"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_merge_requests_summary(project_id, state=state, days_back=days_back, max_results=max_results)

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        f.write(f"{component},{status},{current_timestamp()},MR summary for {project_id}\n")

    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())


