# Rippling API Token Setup

Rippling uses the same naming pattern as Okta in this repo: **`RIPPLING_API_TOKEN`** (Bearer authorization).

## Environment Variables

| Variable | Required | Description | Example |
|---|---:|---|---|
| `RIPPLING_API_TOKEN` | Yes | Rippling API token (sent in `Authorization: Bearer ...`) | `rpl_...` |
| `RIPPLING_BASE_URL` | No | API base URL (default `https://api.rippling.com`) | `https://api.rippling.com` |
| `RIPPLING_PAGE_SIZE` | No | Pagination page size used by fetchers (default `100`) | `100` |

### Related cross-reference modes (optional)

Some Rippling cross-reference fetchers can run in “evidence file mode” to avoid calling other vendor APIs directly:

| Variable | Required | Description |
|---|---:|---|
| `OKTA_EVIDENCE_FILE` | No | Path to an Okta evidence JSON file (used by `rippling_vs_okta_users.py`) |
| `KB4_EVIDENCE_FILE` | No | Path to a KnowBe4 evidence JSON file (used by `rippling_vs_knowbe4_training.py`) |

## Fetchers Covered

- `rippling_current_employees.py`
- `rippling_all_employees.py`
- `rippling_devices.py`
- `rippling_vs_okta_users.py` (requires Okta API vars unless using `OKTA_EVIDENCE_FILE`)
- `rippling_vs_knowbe4_training.py` (requires KnowBe4 API vars unless using `KB4_EVIDENCE_FILE`)
- `test_connection.py`

## API Endpoints Used

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| `test_connection.py` | `/platform/api/companies/current` | GET |
| `rippling_current_employees.py` | `/platform/api/employees` | GET |
| `rippling_all_employees.py` | `/platform/api/employees/include_terminated` | GET |
| `rippling_devices.py` | `/platform/api/devices` (fallback `/v2/devices`) | GET |
| `rippling_vs_okta_users.py` | `/platform/api/employees` | GET |
| `rippling_vs_knowbe4_training.py` | `/platform/api/employees` | GET |

## Required Permissions (Least Privilege)

- **Credential**: Rippling API token from your Rippling developer/admin console.
- **Scopes**: Minimum required to read:
  - Employees (active and optionally terminated)
  - Devices (only if you run the device inventory fetcher; may require the Rippling MDM add-on)

## Creating a New API Token

1. Log in to Rippling as an admin.
2. Navigate to the developer/API area for generating an API token (varies by tenant).
3. Create a token named `paramify-evidence-fetchers`.
4. Grant read-only access for the endpoints used above (employees; optionally devices).
5. Store the value as `RIPPLING_API_TOKEN` in your secrets manager.

## Rotating the API Token

1. Create a new token first (don’t revoke the old one yet).
2. Update `RIPPLING_API_TOKEN` in your secrets store/runtime environment.
3. Smoke test with the built-in connectivity script:

```bash
python fetchers/rippling/test_connection.py
```

4. Revoke the old token once the smoke test succeeds.

## Notes

- `rippling_devices.py` tries multiple endpoints because Rippling’s device endpoint location can vary. If devices return 404, confirm the **Rippling MDM add-on** is enabled for your account.
