# Okta API Token Setup

## Environment Variables

All Okta fetchers in this folder require:

```bash
export OKTA_ORG_URL="https://your-org.okta.com"   # no trailing slash
export OKTA_API_TOKEN="<your-api-token>"         # SSWS token value
```

| Variable | Required | Description | Example |
|---|---:|---|---|
| `OKTA_ORG_URL` | Yes | Okta org base URL | `https://paramify.okta.com` |
| `OKTA_API_TOKEN` | Yes | Okta API token (used with `Authorization: SSWS ...`) | `00abc...` |

## Fetchers Covered

- `okta_iam_core.py` (shared implementation)
- `okta_least_privilege.py`
- `okta_phishing_resistant_mfa.py`
- `okta_passwordless_authentication.py`
- `okta_just_in_time_authorization.py`
- `okta_non_user_accounts_authentication.py`
- `okta_suspicious_activity_management.py`
- `okta_automated_account_management.py`
- `okta_authenticators.sh`

## API Endpoints Used

Most Okta fetchers use the Okta Management API (`/api/v1/...`).

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| `okta_iam_core.py` (via wrappers) | `/api/v1/users` (+ nested: `/users/:id`, `/users/:id/factors`, `/users/:id/roles`, `/users/:id/appLinks`) | GET |
| `okta_iam_core.py` (via wrappers) | `/api/v1/groups`, `/api/v1/groups/:id/users`, `/api/v1/groups/rules` | GET |
| `okta_iam_core.py` (via wrappers) | `/api/v1/apps`, `/api/v1/apps/:id/users`, `/api/v1/apps/:id/groups` | GET |
| `okta_iam_core.py` (via wrappers) | `/api/v1/policies?type=...`, `/api/v1/policies/:id/rules` | GET |
| `okta_iam_core.py` (via wrappers) | `/api/v1/logs` (limited pages) | GET |
| `okta_iam_core.py` (via wrappers) | `/api/v1/authenticators` (+ details/methods) | GET |
| `okta_iam_core.py` (via wrappers) | `/api/v1/authorizationServers` (+ scopes/claims/policies) | GET |
| `okta_iam_core.py` (via wrappers) | `/api/v1/api-tokens` | GET |
| `okta_authenticators.sh` | `/api/v1/apps`, `/api/v1/apps/:id/policies` | GET |
| `okta_authenticators.sh` | `/api/v1/policies?type=AUTHENTICATOR_ENROLLMENT`, `/api/v1/policies/:id/rules` | GET |
| `okta_authenticators.sh` | `/api/v1/policies/simulate` | POST |
| `okta_authenticators.sh` | `/api/v1/authenticators`, `/api/v1/authenticators/:id` | GET |

## Required Permissions (Least Privilege)

- **Role**: Okta admin role that can read users/groups/apps/policies/system logs.
- **Scopes**: Okta API tokens are role-based; grant only what is required for:
  - user + group inventory
  - policy/authenticator configuration
  - system log reads (as applicable)

## Creating a New API Token

1. Log in to Okta Admin.
2. Navigate to **Security → API → Tokens**.
3. Create a token named `paramify-evidence-fetchers`.
4. Assign the minimum admin role needed for read-only access to the endpoints above.
5. Copy the token and store it as `OKTA_API_TOKEN` in your secrets manager.

## Rotating the API Token

1. Create a second token (don’t revoke the old one yet).
2. Update `OKTA_API_TOKEN` wherever it is stored.
3. Smoke test:

```bash
curl -s -H "Authorization: SSWS $OKTA_API_TOKEN" \
  "$OKTA_ORG_URL/api/v1/users?limit=1" | python3 -m json.tool | head -30
```

4. Revoke the old token once the smoke test succeeds.

## Notes

- Some endpoints may require specific Okta SKUs (for example, some authenticator/policy APIs can depend on OIE / API Access Management). If you hit 403/404, verify your tenant features and the token’s admin role.

