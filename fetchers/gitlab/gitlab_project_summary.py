#!/usr/bin/env python3
"""
GitLab Project Summary

Purpose: Generate inventory of configuration files (e.g., Terraform)
to support KSI-PIY-01 (information resource inventory)
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


def url_encode(segment: str) -> str:
    from urllib.parse import quote
    return quote(segment, safe="")


def http_get(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> requests.Response:
    return requests.get(url, headers=headers, params=params, timeout=30)


def get_project_file_summary(project_id: str, file_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    # Use environment variables set by orchestration layer
    gitlab_url = get_env("GITLAB_URL")
    api_token = get_env("GITLAB_API_TOKEN")
    api_endpoint = f"{gitlab_url.rstrip('/')}/api/v4"

    headers = {
        "PRIVATE-TOKEN": api_token,
        "Content-Type": "application/json",
    }

    # Default patterns for compliance-relevant files
    if file_patterns is None:
        file_patterns = [
            ".tf",
            ".tfvars",
            ".yml",
            ".yaml",
            ".json",
            "Dockerfile",
            ".sh",
        ]

    encoded_project = url_encode(project_id)
    tree_url = f"{api_endpoint}/projects/{encoded_project}/repository/tree"
    params: Dict[str, Any] = {"recursive": "true", "per_page": 100, "page": 1}

    try:
        all_items: List[Dict[str, Any]] = []
        while True:
            response = http_get(tree_url, headers=headers, params=params)
            if response.status_code != 200:
                raise RuntimeError(f"API Error: {response.status_code} {response.text}")
            page_items = response.json()
            all_items.extend(page_items)
            next_page = response.headers.get("x-next-page") or response.headers.get("X-Next-Page")
            if next_page:
                params["page"] = int(next_page)
            else:
                break

        filtered_files: List[Dict[str, Any]] = []
        file_categories: Dict[str, List[Dict[str, Any]]] = {}

        for item in all_items:
            if item.get("type") != "blob":
                continue

            name = item.get("name", "")
            matched_category: Optional[str] = None
            for pattern in file_patterns:
                if name.endswith(pattern) or pattern in name:
                    matched_category = pattern
                    break
            if matched_category is None:
                continue

            file_info = {
                "name": name,
                "path": item.get("path"),
                "mode": item.get("mode"),
                "id": item.get("id"),
                "category": matched_category,
            }
            filtered_files.append(file_info)
            file_categories.setdefault(matched_category, []).append(file_info)

        total_files = sum(1 for f in all_items if f.get("type") == "blob")
        total_dirs = sum(1 for f in all_items if f.get("type") == "tree")

        summary = {
            "status": "success",
            "project_id": project_id,
            "total_items": len(all_items),
            "total_files": total_files,
            "total_directories": total_dirs,
            "filtered_files_count": len(filtered_files),
            "files_by_category": {
                category: {"count": len(files), "files": files}
                for category, files in file_categories.items()
            },
            "files": filtered_files,
            "analysis": {
                "has_terraform": any(".tf" in f["name"] for f in filtered_files),
                "has_ci_cd": any(f.get("name") == ".gitlab-ci.yml" for f in all_items if isinstance(f, dict)),
                "has_docker": any("Dockerfile" in (f.get("name") or "") for f in all_items if isinstance(f, dict)),
                "terraform_files": [f for f in filtered_files if ".tf" in f["name"]],
                "config_files": [f for f in filtered_files if any(ext in f["name"] for ext in [".yml", ".yaml"])],
            },
            "retrieved_at": current_timestamp(),
        }
        return summary
    except Exception as e:
        return {"status": "error", "message": str(e), "project_id": project_id, "retrieved_at": current_timestamp()}


def main() -> int:
    if len(sys.argv) != 5:
        print("Usage: python gitlab_project_summary.py <profile> <region> <output_dir> <csv_file>")
        return 1

    output_dir = sys.argv[3]
    csv_file = sys.argv[4]
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    project_id = os.environ.get("GITLAB_PROJECT_ID", "group/project")
    patterns_env = os.environ.get("GITLAB_FILE_PATTERNS")
    patterns = [p.strip() for p in patterns_env.split(",")] if patterns_env else None

    component = "gitlab_project_summary"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_project_file_summary(project_id, patterns)

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        f.write(f"{component},{status},{current_timestamp()},file summary for {project_id}\n")

    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())


