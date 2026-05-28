# Wiz API Key Setup

## Environment Variables

All Wiz fetchers in this folder require Wiz Service Account credentials plus a Paramify API token. The variables below are loaded from `fetchers/.env`.

| Variable | Required | Description | Example |
|---|---:|---|---|
| `WIZ_CLIENT_ID` | Yes | Wiz Service Account client ID | `mlipebtwsndhxdmnzdw...` |
| `WIZ_CLIENT_SECRET` | Yes | Wiz Service Account client secret | `dGpKwL6r6Hrcby6pMM...` |
| `WIZ_AUTH_URL` | Yes | Wiz OAuth token endpoint (tenant-region dependent) | `https://auth.app.wiz.io/oauth/token` |
| `WIZ_API_ENDPOINT` | Yes | Wiz GraphQL API endpoint (tenant-region dependent) | `https://api.us17.app.wiz.io/graphql` |
| `PARAMIFY_API_ISSUES_TOKEN` | Yes* | Paramify API token with view/write issues permissions (preferred for Wiz) | `eyJhbGciOi...` |
| `PARAMIFY_UPLOAD_API_TOKEN` | Yes* | Paramify API token (fallback if `PARAMIFY_API_ISSUES_TOKEN` not set) | `eyJhbGciOi...` |
| `PARAMIFY_API_ISSUES_BASE_URL` | No | Paramify API base URL (default `https://app.paramify.com/api/v0`) | `https://app.paramify.com/api/v0` |
| `WIZ_PARAMIFY_ASSESSMENT_ID` | For Issues fetcher | Paramify Vulnerability Assessment UUID where Wiz Issues are uploaded | `d0318023-55c2-41ea-...` |
| `WIZ_VULN_PARAMIFY_EVIDENCE_ID` | For Vulnerabilities fetcher | Paramify Evidence record UUID where Wiz Vulnerability Findings are uploaded as artifacts | `f85e252b-2a7f-4012-...` |
| `DELTA_MODE` | No | When `true`, Issues fetcher uploads only changed rows since last successful run (default `false`) | `true` |

\* At least one of `PARAMIFY_API_ISSUES_TOKEN` or `PARAMIFY_UPLOAD_API_TOKEN` must be set. The Wiz fetchers prefer `PARAMIFY_API_ISSUES_TOKEN` because it carries the view/write issues permissions; if it isn't set, they fall back to `PARAMIFY_UPLOAD_API_TOKEN`.

## Fetchers Covered

- `wiz_to_paramify.py`
- `wiz_vulnerabilities_to_paramify.py`

## API Endpoints Used

### Wiz endpoints

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| Both | `${WIZ_AUTH_URL}` (OAuth token request) | POST |
| Both | `${WIZ_API_ENDPOINT}` (GraphQL queries/mutations) | POST |
| `wiz_to_paramify.py` | GraphQL: `CreateReport`, `UpdateReport`, `RerunReport`, `ReportDownloadUrl` | POST |
| `wiz_to_paramify.py` | Wiz-issued presigned S3 URL for report CSV download | GET (stream) |
| `wiz_vulnerabilities_to_paramify.py` | GraphQL: `VulnerabilityFindingsPage` (cursor-paginated) | POST |

### Paramify endpoints

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| `wiz_to_paramify.py` | `${PARAMIFY_API_ISSUES_BASE_URL}/assessment/{assessmentId}/intake` | POST (multipart) |
| `wiz_vulnerabilities_to_paramify.py` | `${PARAMIFY_API_ISSUES_BASE_URL}/evidence/{evidenceId}/artifacts/upload` | POST (multipart) |

## Required Permissions (Least Privilege)

### Wiz Service Account scopes

The Service Account must have the union of scopes needed by both fetchers (or scope-limit per fetcher if you use two separate accounts):

| Scope | Fetcher | Purpose |
|---|---|---|
| `read:issues` | `wiz_to_paramify.py` | Read Wiz Issues data |
| `create:reports` | `wiz_to_paramify.py` | Create Wiz Issues reports |
| `read:reports` | `wiz_to_paramify.py` | Poll report status, get presigned download URL |
| `update:reports` | `wiz_to_paramify.py` | Update report config when changed between runs |
| `read:vulnerabilities` | `wiz_vulnerabilities_to_paramify.py` | Read Wiz Vulnerability Findings |

Project scope: `*` (all projects) or specific project IDs.

### Paramify token

- **Access level**: API token with permission to upload artifacts to Vulnerability Assessments and create artifacts under Evidence records.
- **Scope**: Write access to the specific Assessment / Evidence UUIDs configured for Wiz.

## Wiz Tenant Region

Wiz tenants are deployed across multiple regions and the auth + API endpoints differ. Determine yours from the Wiz console URL.

| Tenant Type | `WIZ_AUTH_URL` | `WIZ_API_ENDPOINT` |
|---|---|---|
| Commercial | `https://auth.app.wiz.io/oauth/token` | `https://api.{region}.app.wiz.io/graphql` |
| Gov (US-Gov) | `https://auth.app.wiz.us/oauth/token` | `https://api.{region}.app.wiz.us/graphql` |

`{region}` examples: `us1`, `us17`, `us2` (Gov), `eu1`. Check your tenant's Settings → Tenant Info page in the Wiz console.

## Creating a New Wiz Service Account

1. Sign in to the Wiz console as an Admin.
2. Navigate to **Settings → Service Accounts**.
3. Click **Add Service Account**.
4. Choose **Custom Integration (GraphQL API)**.
5. Name it (e.g., `paramify-evidence-fetchers`).
6. Project scope: `All Projects` (or specific projects).
7. Add the scopes listed in **Required Permissions** above.
8. Save and copy the **Client ID** and **Client Secret** (the secret is shown only once).
9. Store both values in your secrets manager and set:
   ```bash
   export WIZ_CLIENT_ID="<client-id>"
   export WIZ_CLIENT_SECRET="<client-secret>"
   export WIZ_AUTH_URL="https://auth.app.wiz.io/oauth/token"   # or .wiz.us for Gov
   export WIZ_API_ENDPOINT="https://api.us17.app.wiz.io/graphql"  # match your tenant region
   ```

## Creating Paramify Destinations

### For `wiz_to_paramify.py` (Issues)

1. Sign in to Paramify.
2. Navigate to the program where Wiz Issues should be tracked.
3. Open or create a **Configuration**.
4. Copy the Assessment UUID from the URL or settings.
5. Set `WIZ_PARAMIFY_ASSESSMENT_ID` to that UUID.

### For `wiz_vulnerabilities_to_paramify.py` (Vulnerability Findings)

1. Sign in to Paramify.
2. Navigate to **Resources → Evidence**.
3. Click **Create Evidence** (or equivalent) and name it (e.g., `Wiz Vulnerability Findings`).
4. Copy the Evidence UUID from the URL.
5. Set `WIZ_VULN_PARAMIFY_EVIDENCE_ID` to that UUID.

## Rotating the Wiz Client Secret

1. In the Wiz console, open the Service Account and click **Rotate Secret** (or create a new Service Account in parallel).
2. Update `WIZ_CLIENT_SECRET` in your secrets store / runtime environment.
3. Smoke test:
   ```bash
   curl -s -X POST "$WIZ_AUTH_URL" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=client_credentials" \
     -d "audience=wiz-api" \
     -d "client_id=$WIZ_CLIENT_ID" \
     -d "client_secret=$WIZ_CLIENT_SECRET" \
     | python3 -m json.tool | head -10
   ```
   A successful response includes `"access_token": "..."`.
4. Revoke the old secret once the smoke test succeeds.

## Rotating the Paramify Token

1. Generate a new Paramify API token with view/write issues permissions.
2. Update `PARAMIFY_API_ISSUES_TOKEN` in your secrets store.
3. Smoke test (replace `<assessment-id>` with `$WIZ_PARAMIFY_ASSESSMENT_ID`):
   ```bash
   curl -s -H "Authorization: Bearer $PARAMIFY_API_ISSUES_TOKEN" \
     "${PARAMIFY_API_ISSUES_BASE_URL:-https://app.paramify.com/api/v0}/evidence" \
     | python3 -m json.tool | head -20
   ```
4. Revoke the old token once the smoke test succeeds.

## Notes

- The Vulnerabilities fetcher uses cursor-based GraphQL pagination (`first` + `after` + `pageInfo.endCursor`) at `PAGE_SIZE=100`. Large tenants may produce many pages and take several minutes.
- Both fetchers persist state to disk next to the script (`state.json` for Issues, `vuln_state.json` for Vulnerabilities). State files contain a Wiz report ID / config hash / `last_successful_run` timestamp; treat them like operational data and do not commit them to source control.
- The Vulnerabilities fetcher uses the Wiz `VulnerabilityFindings` GraphQL endpoint, which Wiz documents as intended for **incremental** delta updates. For large initial imports, expect the first full run to be the slowest.
