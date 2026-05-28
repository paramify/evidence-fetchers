# Rippling API Key Setup

## Environment Variables

All Rippling fetchers in this folder use the Rippling REST API with Bearer authentication.

| Variable | Required | Description | Example |
|---|---:|---|---|
| `RIPPLING_API_TOKEN` | Yes | Rippling REST API token (used with `Authorization: Bearer ...`) | `rpl_pat_...` |
| `RIPPLING_BASE_URL` | yes | Rippling REST API base URL (default `https://rest.ripplingapis.com`) | `https://rest.ripplingapis.com` |
| `RIPPLING_API_VERSION` | yes | Rippling API version date (default `2024-01-31`) | `2024-01-31` |
| `RIPPLING_PAGE_SIZE` | No | Results per page for paginated endpoints (default `100`) | `100` |
| `RIPPLING_PARAMIFY_EVIDENCE_ID` | Yes  | Paramify evidence record UUID where Rippling artifacts are uploaded by the orchestrator | `04726592-06f5-4ec5-a837-5d91116c14e6` |
| `RIPPLING_MEMBER_SLEEP` | No | Seconds between supergroup-member calls to stay under rate limits (default `0.05`) | `0.05` |
| `RIPPLING_EVERYONE_GROUP` | No | Name of the "all employees" supergroup (default `Everyone`) | `Everyone` |
| `RIPPLING_EVIDENCE_FILE` | No | Path to a downloaded Paramify Rippling artifact; when set, cross-reference scripts skip the live API and read this file instead | `evidence/rippling_from_paramify.json` |

## Fetchers Covered

- `rippling_org_structure.py`
- `rippling_vs_knowbe4_training.py` (live API mode for Rippling side)
- `rippling_vs_okta_users.py` (live API mode for Rippling side)

## API Endpoints Used

All Rippling fetchers use the Rippling REST API (`/...`).

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| `rippling_org_structure.py` | `/supergroups/?filter=group_type+eq+'Group'` (+ `/supergroups/:id/members/`) | GET |
| `rippling_org_structure.py` | `/departments/?expand=parent,department_hierarchy` | GET |
| `rippling_org_structure.py` | `/teams/`, `/companies/`, `/employment-types/` | GET |
| `rippling_vs_knowbe4_training.py` | `/supergroups/?filter=...`, `/supergroups/:id/members/` | GET |
| `rippling_vs_okta_users.py` | `/supergroups/?filter=...`, `/supergroups/:id/members/` | GET |

Pagination is cursor-based via the `next_link` field on the response body.

## Required Permissions (Least Privilege)

- **Access level**: Rippling Developer Hub access with permission to issue REST API tokens.
- **Role**: Rippling admin role that can read supergroup, department, team, company, and employment-type data.
- **Required scopes** (grant only what is needed for the fetchers you run):

| Scope | Needed By |
|---|---|
| `supergroups.read` | `rippling_org_structure.py`, `rippling_vs_knowbe4_training.py`, `rippling_vs_okta_users.py` |
| `departments.read` | `rippling_org_structure.py` |
| `teams.read` | `rippling_org_structure.py` |
| `companies.read` | `rippling_org_structure.py` |
| `employment-types.read` | `rippling_org_structure.py` |

> Verify exact scope names in the Rippling Developer Hub when creating the token. Rippling uses both dot-separated and colon-separated scope formats in different places.

## Creating a New API Token

1. Sign in to the Rippling Developer Hub at `https://developer.rippling.com`.
2. Open your application and navigate to its API token settings.
3. Create a new token named `paramify-evidence-fetchers`.
4. Select the scopes listed above for the fetchers you intend to run.
5. Copy the generated token immediately — Rippling will not show it again.
6. Store the token in your secrets manager and set the variables shown in the **Environment Variables** table above.

## Creating a Paramify Destination (for orchestrator upload)

`RIPPLING_PARAMIFY_EVIDENCE_ID` is the Paramify evidence record where the orchestrator (`4-upload-to-paramify/upload_to_paramify.py`) pushes Rippling fetcher output.

1. Log in to Paramify.
2. Navigate to **Resources → Evidence**.
3. Create or find the evidence record that should receive Rippling artifacts (e.g. "Active Employees - Rippling").
4. Copy the evidence ID from the URL (`https://<host>/resources/evidence/<UUID>`).
5. Set `RIPPLING_PARAMIFY_EVIDENCE_ID` to the UUID.

## Rotating the API Token

1. Create a second token in the Rippling Developer Hub (don't revoke the old one yet).
2. Update `RIPPLING_API_TOKEN` wherever it is stored.
3. Smoke test:

```bash
curl -s -H "Accept: application/json" \
  -H "Authorization: Bearer $RIPPLING_API_TOKEN" \
  "$RIPPLING_BASE_URL/supergroups/?filter=group_type+eq+'Group'" \
  | python3 -m json.tool | head -30
```

4. Revoke the old token once the smoke test succeeds.

## Rate Limits

- Rippling enforces approximately **300 requests per 10 seconds** per token.
- Scripts that fan out per-record (such as `rippling_org_structure.py`, which fetches members for each supergroup) sleep briefly between requests via `RIPPLING_MEMBER_SLEEP` (default `0.05` seconds).
- On `429 Too Many Requests`, fetchers honor the `Retry-After` header when present, falling back to a fixed 15-second wait.

## Notes

- Cross-reference scripts (`rippling_vs_knowbe4_training.py`, `rippling_vs_okta_users.py`) call the Rippling live API by default. They also support an offline file mode: set `RIPPLING_EVIDENCE_FILE` to read a previously downloaded Paramify Rippling artifact instead of calling the live API. Same pattern applies to the Okta and KnowBe4 sides via `OKTA_EVIDENCE_FILE` and `KB4_EVIDENCE_FILE`. File mode is useful for replaying against a fixed snapshot, avoiding rate limits, or running without the token loaded.
- `RIPPLING_BASE_URL` is HTTPS-only and host-allowlisted (`rest.ripplingapis.com`, `api.rippling.com`) to prevent the bearer token from being sent to an attacker-controlled host. Redirects on API calls are refused for the same reason.
- Per Paramify orchestrator convention, fetcher scripts do not upload to Paramify themselves. Run `python 4-upload-to-paramify/upload_to_paramify.py` (or the orchestrator at `3-run-fetchers/run_fetchers.py`) to push artifacts to the evidence record identified by `RIPPLING_PARAMIFY_EVIDENCE_ID`.
