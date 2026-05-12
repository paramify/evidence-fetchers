# KnowBe4 API Key Setup

## Environment Variables

KnowBe4 fetchers in this repo use the KnowBe4 Reporting API (`/v1/...`) with Bearer authentication.

| Variable | Required | Description | Example |
|---|---:|---|---|
| `KNOWBE4_API_KEY` | Yes | KnowBe4 Reporting API key | `kb4_...` |
| `KNOWBE4_REGION` | Yes | KnowBe4 region (used to form the API hostname for shell fetchers) | `US` |
| `KNOWBE4_BASE_URL` | No | Full API base URL (default `https://us.api.knowbe4.com`; used by `rippling_vs_knowbe4_training.py` when not using region-based hostnames) | `https://us.api.knowbe4.com` |
| `KNOWBE4_CAMPAIGN_ID` | No | If set, only checks enrollment in this campaign (`rippling_vs_knowbe4_training.py`) | `123456` |

Shell scripts under `fetchers/knowbe4/` build the host as `https://{KNOWBE4_REGION}.api.knowbe4.com`. The Rippling cross-reference script uses `KNOWBE4_BASE_URL` (set it to match your region, e.g. `https://us.api.knowbe4.com`).

## Fetchers Covered

- `security_awareness_training.sh`
- `high_risk_training.sh`
- `developer_specific_training.sh`
- `module_based_summary.sh`
- `../rippling/rippling_vs_knowbe4_training.py` (live API mode)

## API Endpoints Used

All KnowBe4 shell fetchers call:

| Endpoint(s) | Method(s) |
|---|---|
| `https://{KNOWBE4_REGION}.api.knowbe4.com/v1/users` | GET |
| `https://{KNOWBE4_REGION}.api.knowbe4.com/v1/training/enrollments` | GET |

Some fetchers additionally call:

| Endpoint(s) | Method(s) |
|---|---|
| `https://{KNOWBE4_REGION}.api.knowbe4.com/v1/training/campaigns` | GET |
| `https://{KNOWBE4_REGION}.api.knowbe4.com/v1/groups` | GET |
| `https://{KNOWBE4_REGION}.api.knowbe4.com/v1/groups/{group_id}/members` | GET |

`rippling_vs_knowbe4_training.py` calls `{KNOWBE4_BASE_URL}/v1/users` and `{KNOWBE4_BASE_URL}/v1/training/enrollments`.

## Required Permissions (Least Privilege)

- **Access level**: KnowBe4 Reporting API access enabled for your account.
- **Role**: Admin access sufficient to generate a reporting API key.
- **Scope**: Read-only access to reporting endpoints (users, enrollments, campaigns, groups).

## Creating a New API Key

1. Sign in to KnowBe4 as an Admin.
2. Navigate to **Account Settings → Account Integrations → API**.
3. Enable **Reporting API Access** (KnowBe4 notes this is typically available only to Platinum/Diamond customers).
4. Copy the **Secure API key**.
5. Determine your `KNOWBE4_REGION`:
   - Log in to KnowBe4 and note the region in the browser URL / tenant hostname.
   - Supported values used by these fetchers: `US`, `EU`, `CA`, `UK`, `DE`.
6. Store the key in your secrets manager and set:

```bash
export KNOWBE4_API_KEY="<your-key>"
export KNOWBE4_REGION="US"
```

For `rippling_vs_knowbe4_training.py`, also set `KNOWBE4_BASE_URL` to the matching regional base (e.g. `https://us.api.knowbe4.com`).

## Rotating the API Key

1. Generate a new key in the KnowBe4 console.
2. Update `KNOWBE4_API_KEY` in your secrets store/runtime environment.
3. Smoke test:

```bash
curl -s -H "Authorization: Bearer $KNOWBE4_API_KEY" \
  "https://${KNOWBE4_REGION}.api.knowbe4.com/v1/users?page=1" \
  | python3 -m json.tool | head -30
```

4. Revoke the old key once the smoke test succeeds.

## Notes

- The KnowBe4 scripts paginate using `page=N` until an empty page is returned.
