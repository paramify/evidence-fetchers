#!/usr/bin/env python3
"""
GitLab CI/CD Pipeline Configuration Retrieval

Purpose: Pull .gitlab-ci.yml file to demonstrate automated testing and
validation (KSI-CMT-03: automated testing before deployment)
"""

import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml


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


def base64_decode(content_b64: str) -> str:
    return base64.b64decode(content_b64).decode("utf-8")


def yaml_parse(content: str) -> Any:
    try:
        return yaml.safe_load(content) or {}
    except yaml.YAMLError:
        return {"parse_error": True, "raw": content}


def extract_stages(ci_config: Any) -> Any:
    return ci_config.get("stages") if isinstance(ci_config, dict) else None


def has_stage(ci_config: Any, stage_name: str) -> bool:
    stages = extract_stages(ci_config)
    if isinstance(stages, list):
        return stage_name in stages
    # Also check jobs for stage usage
    if isinstance(ci_config, dict):
        for job_name, job in ci_config.items():
            if job_name.startswith(".") or not isinstance(job, dict):
                continue
            if job.get("stage") == stage_name:
                return True
    return False


def check_for_security_scanning(ci_config: Any) -> bool:
    if not isinstance(ci_config, dict):
        return False
    content_str = json.dumps(ci_config, sort_keys=True)
    keywords = [
        "sast", "dependency_scanning", "container_scanning", "secret_detection",
        "dast", "license_scanning", "code_quality"
    ]
    return any(k in content_str.lower() for k in keywords)


def count_jobs(ci_config: Any) -> int:
    if not isinstance(ci_config, dict):
        return 0
    count = 0
    for name, body in ci_config.items():
        if name.startswith("."):
            continue
        if isinstance(body, dict) and ("script" in body or "stage" in body):
            count += 1
    return count


def check_for_includes(ci_config: Any) -> bool:
    if not isinstance(ci_config, dict):
        return False
    return "include" in ci_config


def extract_deployment_jobs(ci_config: Any) -> Any:
    if not isinstance(ci_config, dict):
        return []
    deployments = []
    for name, job in ci_config.items():
        if name.startswith(".") or not isinstance(job, dict):
            continue
        if job.get("environment") or job.get("when") in {"manual", "delayed"}:
            deployments.append(name)
    return deployments


def check_artifacts(ci_config: Any) -> bool:
    if not isinstance(ci_config, dict):
        return False
    for name, job in ci_config.items():
        if name.startswith(".") or not isinstance(job, dict):
            continue
        if "artifacts" in job:
            return True
    return False


def get_gitlab_ci_config(project_id: str, branch: str = "main") -> Dict[str, Any]:
    # Use environment variables set by orchestration layer
    gitlab_url = get_env("GITLAB_URL")
    api_token = get_env("GITLAB_API_TOKEN")
    api_endpoint = f"{gitlab_url.rstrip('/')}/api/v4"

    headers = {
        "PRIVATE-TOKEN": api_token,
        "Content-Type": "application/json",
    }

    file_path = ".gitlab-ci.yml"
    encoded_path = url_encode(file_path)
    encoded_project = url_encode(project_id)
    metadata_url = f"{api_endpoint}/projects/{encoded_project}/repository/files/{encoded_path}"
    params = {"ref": branch}

    try:
        response = http_get(metadata_url, headers=headers, params=params)
        if response.status_code == 404:
            return {
                "status": "not_found",
                "message": "No .gitlab-ci.yml file found in project",
                "project_id": project_id,
                "branch": branch,
                "retrieved_at": current_timestamp(),
            }
        if response.status_code != 200:
            raise RuntimeError(f"API Error: {response.status_code} {response.text}")

        file_data = response.json()
        content = base64_decode(file_data.get("content", ""))
        ci_config = yaml_parse(content)

        result = {
            "status": "success",
            "project_id": project_id,
            "branch": branch,
            "file_name": file_data.get("file_name"),
            "file_path": file_data.get("file_path"),
            "last_commit_id": file_data.get("last_commit_id"),
            "content_raw": content,
            "content_parsed": ci_config,
            "analysis": {
                "stages": extract_stages(ci_config),
                "has_test_stage": has_stage(ci_config, "test"),
                "has_security_scan": check_for_security_scanning(ci_config),
                "jobs_count": count_jobs(ci_config),
                "uses_templates": check_for_includes(ci_config),
                "deployment_jobs": extract_deployment_jobs(ci_config),
                "artifacts_configured": check_artifacts(ci_config),
            },
            "retrieved_at": current_timestamp(),
        }
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "project_id": project_id,
            "retrieved_at": current_timestamp(),
        }


def main() -> int:
    # Args from runner: profile, region, output_dir, csv_file
    if len(sys.argv) != 5:
        print("Usage: python gitlab_ci_cd_pipeline_config.py <profile> <region> <output_dir> <csv_file>")
        return 1

    _profile = sys.argv[1]
    _region = sys.argv[2]
    output_dir = sys.argv[3]
    csv_file = sys.argv[4]

    # Inputs via env for consistency with other providers
    project_id = os.environ.get("GITLAB_PROJECT_ID", "group/project")
    branch = os.environ.get("GITLAB_BRANCH", "main")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    component = "gitlab_ci_cd_pipeline_config"
    output_json = Path(output_dir) / f"{component}.json"

    result = get_gitlab_ci_config(project_id, branch)

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Append CSV summary
    with open(csv_file, "a") as f:
        status = result.get("status", "unknown")
        f.write(f"{component},{status},{current_timestamp()},CI config retrieved for {project_id}\n")

    return 0 if result.get("status") in {"success", "not_found"} else 1


if __name__ == "__main__":
    sys.exit(main())


