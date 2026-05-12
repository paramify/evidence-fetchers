# <Integration Name> API Key Setup

This document describes how to create, store, and rotate credentials for the fetchers in `fetchers/<integration>/`.

## Environment Variables

All fetchers in this folder require the following environment variables.

| Variable | Required | Description | Example |
|---|---:|---|---|
| `VAR_NAME` | Yes | What it is used for | `https://example.example` |

## Fetchers Covered

- `script_one.py`
- `script_two.py`

## API Endpoints Used

One row per fetcher script. This table is used to scope credentials to least-privilege access.

| Fetcher | Endpoint(s) | Method(s) | Notes |
|---|---|---|---|
| `script_one.py` | `/api/v1/resource` | GET | Pagination via `limit`/`cursor` |

## Required Permissions (Least Privilege)

- **Role**: Viewer / Read-only (or minimum equivalent)
- **Scope**: Account / Organization / Project (minimum required)
- **Notes**: Call out anything that forces broader permissions than desired

## Creating a New API Token / Credential

1. Log in to the vendor console.
2. Navigate to **<Menu → Submenu → ...>**.
3. Create a service user/app (recommended name: `paramify-evidence-fetchers`).
4. Assign the role/scope above.
5. Generate the credential and store it in your secrets manager.

## Rotating the API Token / Credential

1. Navigate to **<Menu → ...>**.
2. Regenerate/revoke and create a new credential (follow vendor guidance).
3. Update the secret wherever it is stored (e.g., AWS Secrets Manager, `.env`).
4. Verify with a quick smoke test:

```bash
# Prefer a single, fast, read-only request.
curl -s -H "Authorization: Bearer <token>" \
  "https://example.example/api/v1/health" | python3 -m json.tool | head -20
```

## Troubleshooting

- **401/403**: likely missing scope/role; confirm permissions for the endpoints listed above
- **Base URL issues**: confirm correct tenant/region and whether a trailing slash is allowed
- **Rate limits**: note recommended backoff / paging strategy if the API is throttling

## Notes

Integration-specific quirks, such as:

- Multiple auth schemes across endpoints (but same underlying token value)
- Token expiration limits (and how to track/rotate before expiry)
- IP allowlisting requirements
- Links to vendor docs

