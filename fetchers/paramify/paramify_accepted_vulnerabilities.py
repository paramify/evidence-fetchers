#!/usr/bin/env python3
"""
Paramify Accepted Vulnerability Info (FedRAMP 20x VER-RPT-AVI)

Purpose: Produce the FedRAMP 20x Accepted Vulnerability Info JSON from Paramify
issues that carry an accepted Excuse (deviation). An accepted vulnerability is
one the provider does not intend to fully remediate; in Paramify that is an
issue with an accepted deviation of type OPERATIONAL_REQUIREMENT,
VENDOR_DEPENDENCY, or RISK_ADJUSTMENT. FALSE_POSITIVE is excluded on purpose:
a false positive is not a real vulnerability, so it is reported under
VER-RPT-VDT (finalDisposition), not here.

Paramify API:
    GET /issues?projectId=..&deviationType=..&statusDateStart=..&statusDateEnd=..
    Auth: Authorization: Bearer <PARAMIFY_API_TOKEN>

Output:
    paramify_accepted_vulnerabilities.json, validated against
    fedramp-accepted-vulnerability-info-schema-2026-06-24.json before writing.

Configuration (from .env / environment; see .env.example):
    PARAMIFY_API_TOKEN            (required) Paramify API token, read scope
    PARAMIFY_PROJECT_ID           (required) project UUID to scope the report
    PARAMIFY_CERT_PACKAGE_URI     (required) certification package overview URI
    PARAMIFY_REPORT_FROM          (required) ISO start of report period
    PARAMIFY_REPORT_TO            (optional) ISO end; defaults to run time
    PARAMIFY_API_BASE_URL         (optional) defaults to https://app.paramify.com/api/v0

    Standalone:  python paramify_accepted_vulnerabilities.py
    Override:    python paramify_accepted_vulnerabilities.py --output-dir /tmp/evidence
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# --- env_loader setup (official repo convention) ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.env_loader import parse_fetcher_args  # noqa: E402

# --- self-contained FedRAMP schema validation (lives under fetchers/paramify/_fedramp) ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fedramp.schema_validator import validate  # noqa: E402

AVI_SCHEMA_FILE = "fedramp-accepted-vulnerability-info-schema-2026-06-24.json"
OUTPUT_FILENAME = "paramify_accepted_vulnerabilities.json"

ACCEPTED_DEVIATION_TYPES = (
    "OPERATIONAL_REQUIREMENT",
    "VENDOR_DEPENDENCY",
    "RISK_ADJUSTMENT",
)
ACCEPTED_STATUS = "ACCEPTED"

# VER-TFR-MAV: providers MUST categorize any vulnerability not (or not going to be)
# fully mitigated or remediated within 192 days of evaluation as an accepted
# vulnerability. So an issue that is still open 192+ days after its evaluationDate
# is an accepted vulnerability even without an explicit accepted deviation.
ACCEPTANCE_DAYS = 192
# Issue status that indicates the vulnerability is still open (not resolved).
# Confirmed value from the Paramify issues API: "OPEN". If other open-like
# statuses exist in the enum, add them here.
OPEN_ISSUE_STATUSES = ("OPEN",)

# Potential Agency Impact N-rating (VER-EVA-EPA / item 6 of VER-RPT-AVI).
# INTERIM provider-assigned mapping (confirmed by the FedRAMP package owner):
# Paramify severity is mapped by position to N1-N5. API tokens are CHILL and
# MODERATE (UI shows "Informational" and "Medium"); the bridge is positional.
# NOT_SET => no rating emitted.
LEVEL_TO_NRATING = {
    "CHILL": 1,
    "LOW": 2,
    "MODERATE": 3,
    "HIGH": 4,
    "CRITICAL": 5,
}


def current_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


# HTTP timeout (seconds) for Paramify API calls; override with PARAMIFY_HTTP_TIMEOUT.
# Large projects make the /issues and per-issue milestone calls slow; 30s caused
# read timeouts on stage, so the default is 90.
HTTP_TIMEOUT = int(os.environ.get("PARAMIFY_HTTP_TIMEOUT", "300"))


def paramify_get(base_url: str, token: str, path: str, params: Dict[str, Any]) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.get(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        params=params,
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_candidate_issues(
    base_url: str,
    token: str,
    project_id: str,
    status_start: str,
    status_end: str,
    api_failures: List[Dict[str, Any]],
) -> List[Dict]:
    """Query issues once per accepted deviation type, de-dupe by id."""
    by_id: Dict[str, Dict] = {}
    for dtype in ACCEPTED_DEVIATION_TYPES:
        params = {
            "deviationType": dtype,
            "statusDateStart": status_start,
            "statusDateEnd": status_end,
            "projectId": project_id,
        }
        try:
            payload = paramify_get(base_url, token, "/issues", params)
        except requests.exceptions.RequestException as e:
            api_failures.append({"deviationType": dtype, "type": type(e).__name__, "message": str(e)})
            print(f"WARNING: fetch failed for deviationType={dtype}: {e}", file=sys.stderr)
            continue
        for issue in payload.get("issues", []) if isinstance(payload, dict) else []:
            by_id[issue["id"]] = issue

    # VER-TFR-MAV: also fetch issues evaluated 192+ days ago, regardless of
    # deviation, since a long-open issue is an accepted vulnerability on its own.
    # The API filters by evaluation date (evaluationDateEnd = now - 192 days);
    # the open-status check is applied later in _is_192_day_accepted.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ACCEPTANCE_DAYS)).date().isoformat()
    aged_params = {
        "projectId": project_id,
        "evaluationDateEnd": cutoff,
    }
    try:
        payload = paramify_get(base_url, token, "/issues", aged_params)
        for issue in payload.get("issues", []) if isinstance(payload, dict) else []:
            by_id[issue["id"]] = issue
    except requests.exceptions.RequestException as e:
        api_failures.append({"query": "aged_192day", "type": type(e).__name__, "message": str(e)})
        print(f"WARNING: fetch failed for 192-day aged query: {e}", file=sys.stderr)

    return list(by_id.values())


def _accepted_deviation(issue: Dict) -> Optional[Dict]:
    qualifying = [
        d
        for d in issue.get("deviations", [])
        if d.get("type") in ACCEPTED_DEVIATION_TYPES
        and (d.get("deviationMetadata") or {}).get("status") == ACCEPTED_STATUS
    ]
    if not qualifying:
        return None
    qualifying.sort(
        key=lambda d: (d.get("deviationMetadata") or {}).get("acceptanceStatusDate") or "",
        reverse=True,
    )
    return qualifying[0]


def _parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (handling a trailing Z) to an aware datetime.
    Naive values (no timezone) are assumed UTC so comparisons never crash."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# Paramify records some issues with a Unix-epoch evaluationDate
# ("1970-01-01T00:00:00.000Z"). An epoch (or otherwise implausibly ancient)
# timestamp is a missing-data sentinel, not a real evaluation event. Per
# VER-TFR-MAV the 192-day clock runs from *evaluation*, so an issue that was
# never actually evaluated must not be time-accepted; and per VER-RPT-AVI a
# sentinel must not be reported as "Time of completed evaluation". Any date
# before this floor is treated as "no evaluation recorded".
MIN_PLAUSIBLE_EVALUATION = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _effective_evaluation_date(issue: Dict) -> Optional[datetime]:
    """The issue's real completed-evaluation date, or None when the field is
    missing, unparseable, or a pre-2000 sentinel (e.g. Unix epoch)."""
    evaluated = _parse_iso(issue.get("evaluationDate"))
    if evaluated is None or evaluated < MIN_PLAUSIBLE_EVALUATION:
        return None
    return evaluated


def _is_192_day_accepted(issue: Dict, now: Optional[datetime] = None) -> bool:
    """
    VER-TFR-MAV time-based acceptance: True when the issue is still open AND its
    evaluation completed 192 or more days ago, even with no deviation.
    Missing or sentinel (pre-2000/epoch) evaluation dates mean the evaluation
    never happened, so the 192-day clock has not started and the issue is NOT
    time-accepted.
    """
    if issue.get("status") not in OPEN_ISSUE_STATUSES:
        return False
    evaluated = _effective_evaluation_date(issue)
    if evaluated is None:
        return False
    now = now or datetime.now(timezone.utc)
    return (now - evaluated).days >= ACCEPTANCE_DAYS


def is_accepted(issue: Dict) -> bool:
    """A vulnerability is accepted if it has an accepted deviation (Excuse) OR it
    meets the VER-TFR-MAV 192-day-open threshold."""
    return _accepted_deviation(issue) is not None or _is_192_day_accepted(issue)


def map_issue(issue: Dict) -> Dict:
    deviation = _accepted_deviation(issue)
    origin = issue.get("origin") or {}

    detail: Dict[str, Any] = {
        "providerTrackingId": issue.get("poamId") or issue["id"],
        "detection": {
            "detectedAt": issue.get("createdAt"),
            "detectionSource": origin.get("name") or "Unspecified",
        },
        "vulnerabilityDescription": issue.get("description") or issue.get("title") or "",
    }
    if issue.get("internetReachableVulnerability") is not None:
        detail["isInternetReachable"] = issue["internetReachableVulnerability"]
    if issue.get("likelyExploitableVulnerability") is not None:
        detail["isLikelyExploitable"] = issue["likelyExploitableVulnerability"]
    # Only report a completed-evaluation time when it is a real evaluation
    # event; epoch/pre-2000 sentinels would be false data in a required report.
    if _effective_evaluation_date(issue) is not None:
        detail["evaluationCompletedAt"] = issue["evaluationDate"]

    rating = LEVEL_TO_NRATING.get(issue.get("level"))
    if rating is not None:
        detail["currentRating"] = rating

    rationale = (deviation or {}).get("description") or ""
    if not rationale and deviation is None and _is_192_day_accepted(issue):
        # Time-based acceptance with no explicit Excuse: record why it qualifies,
        # rather than emitting an empty rationale.
        rationale = (
            "Categorized as an accepted vulnerability under VER-TFR-MAV: open and "
            "not fully mitigated or remediated within 192 days of evaluation."
        )

    return {
        "vulnerabilityDetail": detail,
        "acceptanceRationale": rationale,
    }


def build_report(
    issues: List[Dict],
    cert_package_uri: str,
    report_from: str,
    report_to: str,
) -> Dict:
    accepted = [map_issue(i) for i in issues if is_accepted(i)]
    return {
        "certificationPackageOverviewUri": cert_package_uri,
        "reportPeriod": {"from": report_from, "to": report_to},
        "acceptedVulnerabilities": accepted,
    }


def _build_summary(report):
    acc = report["acceptedVulnerabilities"]
    with_eval = sum(1 for a in acc if a["vulnerabilityDetail"].get("evaluationCompletedAt"))
    rp = report.get("reportPeriod", {})
    return {
        "report": "VER-RPT-AVI",
        "reportPeriod": {"from": rp.get("from"), "to": rp.get("to")},
        "acceptedVulnerabilities": len(acc),
        "withCompletedEvaluation": with_eval,
        "withoutCompletedEvaluation": len(acc) - with_eval,
    }


def _print_summary(report):
    s = report["_summary"]
    lines = [
        "=== AVI Summary (VER-RPT-AVI) ===",
        f"Accepted vulnerabilities: {s['acceptedVulnerabilities']}",
        f"  With completed-evaluation date: {s['withCompletedEvaluation']} | without: {s['withoutCompletedEvaluation']}",
    ]
    print("\n".join(lines), file=sys.stderr)


def run(evidence_dir: str) -> Tuple[str, str]:
    """
    Collect accepted vulnerabilities and write the FedRAMP AVI JSON.

    Returns (status, evidence_file_path); status is PASS, FAIL, or ERROR.
    PASS  = ran, output valid against the FedRAMP schema.
    FAIL  = ran, but output failed schema validation (file still written).
    ERROR = could not run (missing config or API failure).
    """
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    output_path = Path(evidence_dir) / OUTPUT_FILENAME

    try:
        # Prefer the read-scoped token (repo convention); fall back to the
        # upload token so the fetcher runs when only that is configured.
        token = os.environ.get("PARAMIFY_API_TOKEN") or os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
        if not token:
            raise RuntimeError("Missing required env var: PARAMIFY_API_TOKEN (or PARAMIFY_UPLOAD_API_TOKEN)")
        cert_package_uri = get_env("PARAMIFY_CERT_PACKAGE_URI")
        report_from = get_env("PARAMIFY_REPORT_FROM")
        project_id = get_env("PARAMIFY_PROJECT_ID")
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return "ERROR", ""

    base_url = os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0").rstrip("/")
    report_to = os.environ.get("PARAMIFY_REPORT_TO") or current_timestamp()
    status_start = report_from[:10]
    status_end = report_to[:10]

    api_failures: List[Dict[str, Any]] = []
    issues = fetch_candidate_issues(base_url, token, project_id, status_start, status_end, api_failures)

    # Visibility (VER-TFR-EVU): open issues with no real completed evaluation
    # (missing or epoch-sentinel evaluationDate) are NOT eligible for
    # VER-TFR-MAV time-based acceptance -- the 192-day clock never started.
    # They are excluded here rather than silently mis-accepted; surfaced so the
    # unevaluated backlog is visible (Class C SHOULD evaluate within 5 days).
    unevaluated_open = [
        i for i in issues
        if i.get("status") in OPEN_ISSUE_STATUSES
        and _effective_evaluation_date(i) is None
        and _accepted_deviation(i) is None
    ]
    if unevaluated_open:
        print(
            f"WARNING: {len(unevaluated_open)} open issue(s) have no real completed-"
            "evaluation date (missing or epoch sentinel); excluded from VER-TFR-MAV "
            "time-based acceptance. Per VER-TFR-EVU these should be evaluated "
            "within 5 days of detection.",
            file=sys.stderr,
        )

    report = build_report(issues, cert_package_uri, report_from, report_to)
    report["_summary"] = _build_summary(report)

    missing_rationale = [
        v["vulnerabilityDetail"]["providerTrackingId"]
        for v in report["acceptedVulnerabilities"]
        if not v.get("acceptanceRationale", "").strip()
    ]
    if missing_rationale:
        print(
            f"WARNING: {len(missing_rationale)} accepted vulnerability(ies) have an empty "
            f"acceptance rationale: {', '.join(missing_rationale)}",
            file=sys.stderr,
        )

    schema_errors = validate(report, AVI_SCHEMA_FILE)
    for err in schema_errors:
        print(f"ERROR: schema validation: {err}", file=sys.stderr)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    if not schema_errors:
        _print_summary(report)
    print(f"Evidence saved to {output_path} ({len(report['acceptedVulnerabilities'])} accepted vulnerabilities)")

    if api_failures:
        return "ERROR", str(output_path)
    if schema_errors:
        return "FAIL", str(output_path)
    return "PASS", str(output_path)


if __name__ == "__main__":
    output_dir, _profile, _region = parse_fetcher_args()
    status, evidence_file = run(output_dir)
    print(f"Final result: {status}")
    if evidence_file:
        print(f"Evidence file: {evidence_file}")
    sys.exit(0 if status == "PASS" else 1)
