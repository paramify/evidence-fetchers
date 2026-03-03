#!/usr/bin/env python3
"""
Tests for multi-instance evidence file mapping and artifact title generation.

Verifies the fixes for:
- create_summary_file() correctly mapping evidence files to multi-instance fetchers
- Paramify artifact titles using repo names instead of opaque project_1/project_2 labels
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Add repo root to path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "3-run-fetchers"))
sys.path.insert(0, str(repo_root / "2-create-evidence-sets"))


# ─── run_fetchers.py helpers ───────────────────────────────────────────────

from run_fetchers import (
    _sanitize_project_id,
    _find_evidence_file_for_instance,
    _extract_resource,
)


def test_sanitize_project_id():
    """Test that _sanitize_project_id mirrors shell script sanitization."""
    print("Testing _sanitize_project_id...")

    cases = [
        ("cloudops/change-management", "cloudops_change-management"),
        ("paramify/govcloud-infrastructure-in-terraform", "paramify_govcloud-infrastructure-in-terraform"),
        ("paramify/paramify", "paramify_paramify"),
        ("paramify/admission", "paramify_admission"),
        ("group/sub group/project", "group_sub_group_project"),  # spaces handled by regex
        ("simple-project", "simple-project"),
        ("a/b/c", "a_b_c"),
    ]

    for project_id, expected in cases:
        result = _sanitize_project_id(project_id)
        assert result == expected, f"_sanitize_project_id({project_id!r}) = {result!r}, expected {expected!r}"

    print("  All sanitization cases passed")
    return True


def test_find_evidence_file_for_instance_multi_instance():
    """Test precise file matching for multi-instance fetchers using GITLAB_PROJECT_ID."""
    print("Testing _find_evidence_file_for_instance (multi-instance)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        evidence_dir = Path(tmpdir)

        # Create evidence files matching the naming pattern: {fetcher}_{sanitized_project_id}.json
        files = [
            "checkov_terraform_cloudops_change-management.json",
            "checkov_terraform_paramify_govcloud-infrastructure-in-terraform.json",
            "checkov_kubernetes_cloudops_change-management.json",
            "checkov_kubernetes_paramify_govcloud-infrastructure-in-terraform.json",
            "gitlab_merge_request_summary_cloudops_change-management.json",
            "gitlab_merge_request_summary_paramify_paramify.json",
        ]
        for f in files:
            (evidence_dir / f).write_text("{}")

        json_files = {f.stem: f for f in evidence_dir.glob("*.json")}

        # Instance configs
        test_cases = [
            (
                "checkov_terraform_project_1",
                {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "cloudops/change-management"}},
                "checkov_terraform_cloudops_change-management.json",
            ),
            (
                "checkov_terraform_project_2",
                {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "paramify/govcloud-infrastructure-in-terraform"}},
                "checkov_terraform_paramify_govcloud-infrastructure-in-terraform.json",
            ),
            (
                "checkov_kubernetes_project_1",
                {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "cloudops/change-management"}},
                "checkov_kubernetes_cloudops_change-management.json",
            ),
            (
                "checkov_kubernetes_project_2",
                {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "paramify/govcloud-infrastructure-in-terraform"}},
                "checkov_kubernetes_paramify_govcloud-infrastructure-in-terraform.json",
            ),
            (
                "gitlab_merge_request_summary_project_1",
                {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "cloudops/change-management"}},
                "gitlab_merge_request_summary_cloudops_change-management.json",
            ),
            (
                "gitlab_merge_request_summary_project_3",
                {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "paramify/paramify"}},
                "gitlab_merge_request_summary_paramify_paramify.json",
            ),
        ]

        for instance_name, instance, expected_filename in test_cases:
            result = _find_evidence_file_for_instance(instance_name, instance, json_files)
            assert result is not None, f"No file found for {instance_name}"
            actual_filename = Path(result).name
            assert actual_filename == expected_filename, (
                f"{instance_name}: got {actual_filename}, expected {expected_filename}"
            )

    print("  All multi-instance matching cases passed")
    return True


def test_find_evidence_file_standard_fetcher():
    """Test that standard (non-multi-instance) fetchers still match correctly."""
    print("Testing _find_evidence_file_for_instance (standard fetchers)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        evidence_dir = Path(tmpdir)

        files = [
            "backup_validation.json",
            "iam_policies.json",
            "s3_encryption_status.json",
        ]
        for f in files:
            (evidence_dir / f).write_text("{}")

        json_files = {f.stem: f for f in evidence_dir.glob("*.json")}

        # Standard fetchers have no instance info
        for script_name in ["backup_validation", "iam_policies", "s3_encryption_status"]:
            result = _find_evidence_file_for_instance(script_name, None, json_files)
            assert result is not None, f"No file found for {script_name}"
            assert script_name in Path(result).name, f"Wrong file for {script_name}: {result}"

    print("  All standard fetcher cases passed")
    return True


def test_find_evidence_file_missing():
    """Test graceful handling when the expected evidence file doesn't exist."""
    print("Testing _find_evidence_file_for_instance (missing file)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        evidence_dir = Path(tmpdir)
        # Only create one project's file
        (evidence_dir / "checkov_terraform_cloudops_change-management.json").write_text("{}")
        json_files = {f.stem: f for f in evidence_dir.glob("*.json")}

        # The second project's file doesn't exist — should return None rather
        # than incorrectly returning project 1's file
        instance = {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "paramify/govcloud-infrastructure-in-terraform"}}
        result = _find_evidence_file_for_instance("checkov_terraform_project_2", instance, json_files)

        assert result is None, (
            f"Should return None when expected file is missing, not a different project's file: {result}"
        )

    print("  Missing file handling passed")
    return True


def test_extract_resource():
    """Test resource extraction from instance config."""
    print("Testing _extract_resource...")

    # GitLab instance
    gitlab_instance = {"provider": "gitlab", "config": {"GITLAB_PROJECT_ID": "cloudops/change-management"}}
    assert _extract_resource("checkov_terraform_project_1", gitlab_instance) == "cloudops/change-management"

    # AWS instance
    aws_instance = {"provider": "aws", "config": {"AWS_REGION": "us-east-1"}}
    assert _extract_resource("s3_encryption_status_region_1", aws_instance) == "us-east-1"

    # No instance info - falls back to pattern
    assert _extract_resource("checkov_terraform_project_2", None) == "project_2"
    assert _extract_resource("s3_encryption_status_region_1", None) == "region_1"

    # Standard fetcher
    assert _extract_resource("backup_validation", None) == "unknown"

    print("  All resource extraction cases passed")
    return True


# ─── paramify_pusher.py helpers ────────────────────────────────────────────

from paramify_pusher import ParamifyPusher


def test_build_artifact_title():
    """Test that artifact titles include repo names for multi-instance fetchers."""
    print("Testing _build_artifact_title...")

    pusher = ParamifyPusher.__new__(ParamifyPusher)  # avoid __init__ needing a real token

    # Multi-instance with evidence_set_info
    evidence_set_info = {"name": "Checkov Terraform Security", "id": "EVD-CHECKOV-TERRAFORM"}
    title = pusher._build_artifact_title("checkov_terraform_project_1", "cloudops/change-management", evidence_set_info)
    assert title == "Checkov Terraform Security - cloudops/change-management", f"Got: {title}"

    title = pusher._build_artifact_title("checkov_terraform_project_2", "paramify/govcloud-infrastructure-in-terraform", evidence_set_info)
    assert title == "Checkov Terraform Security - paramify/govcloud-infrastructure-in-terraform", f"Got: {title}"

    # Standard fetcher (no resource)
    title = pusher._build_artifact_title("backup_validation", "unknown", evidence_set_info)
    assert title == "Checkov Terraform Security", f"Standard fetcher title should not include 'unknown': {title}"

    # No evidence_set_info
    title = pusher._build_artifact_title("backup_validation", "unknown", None)
    assert title == "backup_validation", f"Got: {title}"

    # Multi-instance without evidence_set_info (falls back to check_name)
    title = pusher._build_artifact_title("checkov_terraform_project_1", "cloudops/change-management", None)
    assert title == "checkov_terraform_project_1 - cloudops/change-management", f"Got: {title}"

    print("  All artifact title cases passed")
    return True


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    """Run all tests."""
    print("Running evidence file mapping tests...\n")

    tests = [
        test_sanitize_project_id,
        test_find_evidence_file_for_instance_multi_instance,
        test_find_evidence_file_standard_fetcher,
        test_find_evidence_file_missing,
        test_extract_resource,
        test_build_artifact_title,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"  FAILED with exception: {e}")
            print()

    print(f"Test Results: {passed}/{total} tests passed")
    if passed == total:
        print("All evidence file mapping tests passed!")
        return 0
    else:
        print("Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
