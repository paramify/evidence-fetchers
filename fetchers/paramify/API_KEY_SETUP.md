# Paramify API Key Setup

## Environment Variables

The Paramify FedRAMP fetchers in this folder read from a Paramify project (program)
and emit FedRAMP 20x machine-readable report JSON. They require a Paramify API token
with read access, plus the identifiers for the project and reporting period. Upload to
Paramify is handled by the standard pipeline (stage 4), not by these fetchers. The
variables below are loaded from `.env`.

| Variable | Required | Description | Example |
|---|---:|---|---|
| `PARAMIFY_PROJECT_ID` | Yes | UUID of the Paramify project (program) to report on | `00000000-0000-0000-0000-000000000000` |
| `PARAMIFY_CERT_PACKAGE_URI` | Yes | Certification Package Overview URI recorded in each report | `https://example.com/certification-package-overview` |
| `PARAMIFY_REPORT_FROM` | Yes | ISO-8601 start of the report period (covers all activity since the previous report per VER-RPT-PER) | `2026-01-01T00:00:00Z` |
| `PARAMIFY_REPORT_TO` | No | ISO-8601 end of the report period (defaults to the run time) | `2026-07-01T00:00:00Z` |
| `PARAMIFY_HTTP_TIMEOUT` | No | Per-request HTTP timeout in seconds (default 90) | `90` |

The API token is read from `PARAMIFY_API_TOKEN`, falling back to
`PARAMIFY_UPLOAD_API_TOKEN` (the name used at the top of `.env.example`). Either works.

## Fetchers Covered

- `paramify_accepted_vulnerabilities.py` — FedRAMP Accepted Vulnerability Info (VER-RPT-AVI)
- `paramify_vulnerability_detail_report.py` — FedRAMP Vulnerability Detail Report (VER-RPT-VDT)
- `paramify_historical_ver_activity.py` — FedRAMP Historical VER Activity (VER-TFR-MRH)

## API Endpoints Used

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| Both | `${PARAMIFY_API_BASE_URL}/issues?projectId=...` (issues in the project, filtered by date) | GET |
| `paramify_accepted_vulnerabilities.py` | `${PARAMIFY_API_BASE_URL}/issues?deviationType=...` (per accepted deviation type) | GET |
| `paramify_vulnerability_detail_report.py` | `${PARAMIFY_API_BASE_URL}/issues/{issueId}/milestones` (per open non-accepted issue, to detect partial mitigation) | GET |
| `paramify_historical_ver_activity.py` | same endpoints as the VDT fetcher (single issues fetch + per-issue milestones) | GET |

The fetchers themselves make read-only GET calls and write their reports locally.
Upload happens in pipeline stage 4, which resolves each report's Evidence record by
its stable referenceId (`EVD-PARAMIFY-VER-RPT-AVI` / `EVD-PARAMIFY-VER-RPT-VDT`), creating the record
if it does not exist. A report is only uploaded after it passes FedRAMP schema
validation, and no evidence UUIDs are ever configured by hand.

## Required Permissions

- **Fetchers (these scripts)**: API token with read access to the project's issues,
  deviations, and milestones.
- **Pipeline upload (stage 4)**: additionally requires evidence write permission to
  create Evidence records and upload artifacts.
- **Scope**: access to the project identified by `PARAMIFY_PROJECT_ID`.

## Output

Each fetcher writes a single JSON file to the evidence output directory and validates
it against the corresponding vendored FedRAMP schema in `_fedramp/schemas/` before
reporting success:

| Fetcher | Output file | Schema |
|---|---|---|
| `paramify_accepted_vulnerabilities.py` | `paramify_accepted_vulnerabilities.json` | `fedramp-accepted-vulnerability-info-schema-2026-06-24.json` |
| `paramify_vulnerability_detail_report.py` | `paramify_vulnerability_detail_report.json` | `fedramp-vulnerability-detail-report-schema-2026-06-24.json` |
| `paramify_historical_ver_activity.py` | `paramify_historical_ver_activity.json` | `fedramp-historical-ver-activity-schema-2026-06-24.json` |

If validation fails, or if any API call fails, the fetcher reports an error and does
not present the output as valid evidence. Open issues with a missing or epoch-sentinel
evaluation date are reported in the VDT output without `evaluationCompletedAt` and
counted in a run warning (see README, "How Accepted Is Determined").

## Finding the Project UUID

1. Sign in to Paramify.
2. Open the program (project) you want to report on.
3. Copy the UUID from the browser URL: `.../programs/<UUID>/...`.
4. Set `PARAMIFY_PROJECT_ID` to that UUID.

Note: the Paramify UI labels this a "program"; the API parameter is `projectId`. They
refer to the same identifier.

## Rotating the Paramify Token

1. Generate a new Paramify API token with the permissions above.
2. Update `PARAMIFY_API_TOKEN` (or `PARAMIFY_UPLOAD_API_TOKEN`) in your secrets store.
3. Smoke test (read-only):
   ```bash
   curl -s -H "Authorization: Bearer $PARAMIFY_API_TOKEN" \
     "${PARAMIFY_API_BASE_URL:-https://app.paramify.com/api/v0}/issues?projectId=$PARAMIFY_PROJECT_ID" \
     | python3 -m json.tool | head -20
   ```
   A successful response lists issues for the project.
4. Revoke the old token once the smoke test succeeds.
