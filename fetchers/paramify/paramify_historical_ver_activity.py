#!/usr/bin/env python3
"""
Paramify Historical VER Activity (FedRAMP 20x VER-TFR-MRH)

Purpose: Produce the FedRAMP 20x Historical Vulnerability Evaluation and
Reporting Activity JSON from Paramify issues. Per VER-TFR-MRH (Class C:
SHOULD, updated at least every 14 days) this is a point-in-time snapshot
containing BOTH partitions in one document:
    activeVulnerabilities    -- all non-accepted vulnerabilities (VER-RPT-VDT fields)
    acceptedVulnerabilities  -- all accepted vulnerabilities (VER-RPT-AVI fields)

Design: this fetcher deliberately contains NO acceptance or mapping logic of
its own. It imports the AVI and VDT fetchers and reuses their shared
"accepted" definition and field mappers, then partitions a SINGLE issue fetch.
That guarantees the two arrays are consistent by construction (same issue set,
same instant): every issue appears in exactly one array, and this snapshot can
never disagree with the individually generated AVI/VDT reports' logic.
Data is always fetched fresh from the Paramify API -- never reassembled from
previously generated evidence artifacts.

Paramify API:
    GET /issues?projectId=..&statusDateStart=..&statusDateEnd=..
    GET /issues/{id}/milestones   (per open non-accepted issue, via VDT mapper)
    Auth: Authorization: Bearer <PARAMIFY_API_TOKEN>

Output:
    paramify_historical_ver_activity.json, validated against
    fedramp-historical-ver-activity-schema-2026-06-24.json before the run is
    reported as PASS.

Configuration (from .env / environment; see .env.example):
    PARAMIFY_API_TOKEN            (required) Paramify API token, read scope
                                  (falls back to PARAMIFY_UPLOAD_API_TOKEN)
    PARAMIFY_PROJECT_ID           (required) project UUID to scope the snapshot
    PARAMIFY_CERT_PACKAGE_URI     (required) certification package overview URI
    PARAMIFY_REPORT_FROM          (required) ISO start of the activity window
    PARAMIFY_REPORT_TO            (optional) ISO end; defaults to run time
    PARAMIFY_API_BASE_URL         (optional) defaults to https://app.paramify.com/api/v0
    PARAMIFY_HTTP_TIMEOUT         (optional) per-request timeout seconds (default 90)

    Standalone:  python paramify_historical_ver_activity.py
    Override:    python paramify_historical_ver_activity.py --output-dir /tmp/evidence
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- env_loader setup (official repo convention) ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.env_loader import parse_fetcher_args  # noqa: E402

# --- self-contained FedRAMP schema validation ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fedramp.schema_validator import validate  # noqa: E402

# --- reuse the sibling fetchers' shared logic (no third copy) ---
import paramify_accepted_vulnerabilities as avi  # noqa: E402
import paramify_vulnerability_detail_report as vdt  # noqa: E402

MRH_SCHEMA_FILE = "fedramp-historical-ver-activity-schema-2026-06-24.json"
OUTPUT_FILENAME = "paramify_historical_ver_activity.json"


def build_report(
    issues: List[Dict],
    cert_package_uri: str,
    generated_at: str,
    base_url: str,
    token: str,
) -> Dict:
    """Partition ONE issue fetch into the two MRH arrays using the shared
    accepted definition, mapping each side with its report's own mapper."""
    active: List[Dict] = []
    accepted: List[Dict] = []
    for issue in issues:
        if vdt.is_accepted(issue):
            accepted.append(avi.map_issue(issue))
        else:
            active.append(vdt.map_issue(issue, base_url, token)["vulnerabilityDetail"])
    return {
        "certificationPackageOverviewUri": cert_package_uri,
        "generatedAt": generated_at,
        "activeVulnerabilities": active,
        "acceptedVulnerabilities": accepted,
    }


def run(output_dir: Optional[str] = None) -> "tuple[str, str]":
    base_url = os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0").rstrip("/")
    token = os.environ.get("PARAMIFY_API_TOKEN") or os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
    project_id = os.environ.get("PARAMIFY_PROJECT_ID")
    cert_package_uri = os.environ.get("PARAMIFY_CERT_PACKAGE_URI")
    report_from = os.environ.get("PARAMIFY_REPORT_FROM")
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report_to = os.environ.get("PARAMIFY_REPORT_TO") or generated_at

    missing = [
        name
        for name, val in (
            ("PARAMIFY_API_TOKEN (or PARAMIFY_UPLOAD_API_TOKEN)", token),
            ("PARAMIFY_PROJECT_ID", project_id),
            ("PARAMIFY_CERT_PACKAGE_URI", cert_package_uri),
            ("PARAMIFY_REPORT_FROM", report_from),
        )
        if not val
    ]
    if missing:
        for name in missing:
            print(f"ERROR: required environment variable not set: {name}", file=sys.stderr)
        print("Final result: ERROR")
        return "ERROR", ""

    api_failures: List[Dict[str, Any]] = []
    issues = vdt.fetch_all_issues(
        base_url, token, project_id, report_from[:10], report_to[:10], api_failures
    )

    # Visibility (VER-TFR-EVU): open issues with no real completed evaluation
    # are active (never accepted -- the VER-TFR-MAV clock never started).
    unevaluated_open = [
        i for i in issues
        if i.get("status") in vdt.OPEN_ISSUE_STATUSES
        and vdt._effective_evaluation_date(i) is None
        and vdt._accepted_deviation(i) is None
    ]
    if unevaluated_open:
        print(
            f"WARNING: {len(unevaluated_open)} open issue(s) have no real completed-"
            "evaluation date (missing or epoch sentinel); reported as active without "
            "evaluationCompletedAt. Per VER-TFR-EVU these should be evaluated "
            "within 5 days of detection.",
            file=sys.stderr,
        )

    report = build_report(issues, cert_package_uri, generated_at, base_url, token)

    out_dir = Path(output_dir or os.environ.get("EVIDENCE_DIR", "./evidence"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUTPUT_FILENAME
    out_path.write_text(json.dumps(report, indent=2))

    errors = validate(report, MRH_SCHEMA_FILE)
    n_active = len(report["activeVulnerabilities"])
    n_accepted = len(report["acceptedVulnerabilities"])
    if errors:
        print(f"Evidence saved to {out_path} ({n_active} active, {n_accepted} accepted)")
        for err in errors:
            print(f"  SCHEMA ERROR: {err}", file=sys.stderr)
        print("Final result: ERROR")
        return "ERROR", str(out_path)
    if api_failures:
        print(
            f"Evidence saved to {out_path} ({n_active} active, {n_accepted} accepted), "
            "but some API calls failed"
        )
        print("Final result: ERROR")
        return "ERROR", str(out_path)

    print(f"Evidence saved to {out_path} ({n_active} active, {n_accepted} accepted)")
    print("Final result: PASS")
    print(f"Evidence file: {out_path}")
    return "PASS", str(out_path)


def main() -> None:
    output_dir, _, _ = parse_fetcher_args()
    status, _ = run(output_dir)
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
