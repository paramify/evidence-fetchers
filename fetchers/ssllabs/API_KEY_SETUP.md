# Qualys SSL Labs API v4 Setup

These fetchers use the public Qualys SSL Labs API v4 to analyze TLS/SSL posture for one or more hostnames.

## Environment Variables

| Variable | Required | Description | Example |
|---|---:|---|---|
| `SSLLABS_EMAIL` | Yes | Email registered with SSL Labs API v4 | `security@example.com` |
| `SSLLABS_HOSTS` | Yes | Comma-separated list of hostnames to scan | `app.example.com,proxy.example.com` |

## Fetchers Covered

- `ssllabs_tls_scan.py`

## API Endpoints Used

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| `ssllabs_tls_scan.py` | `https://api.ssllabs.com/api/v4/analyze` | GET |

## Required Permissions

- This is a public API and uses **email registration** rather than a traditional token.

## Registering / Activating API Access

1. Register your email for API v4 access:
   - `https://api.ssllabs.com/api/v4/register`
2. Set the environment variables:

```bash
export SSLLABS_EMAIL="you@example.com"
export SSLLABS_HOSTS="app.example.com,proxy.example.com"
```

## Rotation

- No token rotation is required; update `SSLLABS_EMAIL` only if you change the registered email identity.

## Smoke Test

```bash
python fetchers/ssllabs/ssllabs_tls_scan.py --output-dir /tmp/evidence
```

## Notes

- The SSL Labs public API is frequently capacity-limited. The fetcher includes retries and will emit helpful messages for HTTP 429/503/529.
- Each host generates a per-host raw JSON file (`ssllabs_<host>.json`) plus the combined summary (`ssllabs_tls_scan.json`).

