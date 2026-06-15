# DataDog API Key Setup

## Environment Variables

All fetchers in this folder require two environment variables:

```bash
export DATADOG_API_KEY="your_api_key_here"
export DATADOG_APP_KEY="your_app_key_here"
export DATADOG_BASE_URL="https://api.ddog-gov.com"   # GovCloud default; omit for commercial
```

`DATADOG_BASE_URL` defaults to `https://api.ddog-gov.com` if not set. Override to `https://api.datadoghq.com` for commercial DataDog tenants.

### Optional Per-Fetcher Variables

```bash
export DATADOG_SIGNALS_LOOKBACK_DAYS=30     # days of SIEM signals to retrieve (default: 30)
export DATADOG_INCIDENTS_LOOKBACK_DAYS=90   # days of incidents to retrieve (default: 90)
```

---

## API Endpoints Used

| Fetcher | Endpoint(s) | Method |
|---|---|---|
| `datadog_siem_detection_rules.py` | `/api/v2/security_monitoring/rules` | GET |
| `datadog_siem_signals.py` | `/api/v2/security_monitoring/signals/search` | POST |
| `datadog_siem_configuration.py` | `/api/v2/security_monitoring/configuration/suppression_rules`, `/api/v1/integration/webhook/configuration/webhooks` | GET |
| `datadog_log_pipelines.py` | `/api/v1/logs/config/pipelines` | GET |
| `datadog_log_indexes.py` | `/api/v1/logs/config/indexes` | GET |
| `datadog_log_archives.py` | `/api/v2/logs/config/archives` | GET |
| `datadog_monitors_list.py` | `/api/v1/monitor` | GET |
| `datadog_agent_hosts.py` | `/api/v1/hosts` | GET |
| `datadog_apm_services.py` | `/api/v2/services/definitions` | GET |
| `datadog_incidents_list.py` | `/api/v2/incidents` | GET |
| `datadog_incident_timelines.py` | `/api/v2/incidents`, `/api/v2/incidents/{id}/relationships/timeline_cells` | GET |

---

## Creating API Credentials

DataDog requires two separate credentials: an **API Key** (identifies the organization) and an **Application Key** (identifies the user/service account making the request).

### 1. Create a Service Account

1. Log in to the DataDog console.
2. Navigate to **Organization Settings → Service Accounts**.
3. Click **New Service Account**.
4. Name it `paramify-evidence-fetchers`.
5. Assign the **DataDog Read Only** role (all fetchers are read-only).
6. Click **Create**.

### 2. Generate an Application Key

1. On the service account page, click **New Key**.
2. Name it `paramify-evidence-fetchers-appkey`.
3. Copy the Application Key value immediately — it is only shown once.
4. Store it in your secrets manager (AWS Secrets Manager, `.env`, etc.).

### 3. Generate an API Key

1. Navigate to **Organization Settings → API Keys**.
2. Click **New Key**.
3. Name it `paramify-evidence-fetchers-apikey`.
4. Copy the API Key value.
5. Store it alongside the Application Key.

### Required Permissions

The service account's role must include read access to:

| DataDog Product | Required Permission |
|---|---|
| Cloud SIEM | `security_monitoring_rules_read`, `security_monitoring_signals_read` |
| Log Management | `logs_read_data`, `logs_read_index_data`, `logs_read_archives` |
| Infrastructure | `metrics_read`, `hosts_read` |
| APM | `apm_read` |
| Monitors | `monitors_read` |
| Incidents | `incident_read` *(only if using DD Incident Management)* |

In DataDog, these are typically all included in the built-in **DataDog Read Only** role. Verify in **Organization Settings → Roles** that the role has these scopes before running fetchers.

---

## Rotating Credentials

### Application Key Rotation

1. Navigate to **Organization Settings → Service Accounts → paramify-evidence-fetchers**.
2. Click the existing key → **Revoke**.
3. Click **New Key** → name it with today's date for traceability.
4. Copy the new value and update `DATADOG_APP_KEY` in your secrets manager.
5. Verify with a smoke test (see below).

### API Key Rotation

1. Navigate to **Organization Settings → API Keys**.
2. Locate `paramify-evidence-fetchers-apikey` → click **Revoke**.
3. Click **New Key** → name it with today's date.
4. Copy and update `DATADOG_API_KEY` in your secrets manager.

---

## Smoke Test

```bash
curl -s \
  -H "DD-API-KEY: $DATADOG_API_KEY" \
  -H "DD-APPLICATION-KEY: $DATADOG_APP_KEY" \
  "$DATADOG_BASE_URL/api/v1/validate" | python3 -m json.tool
```

Expected response:
```json
{"valid": true}
```

If `valid` is `false` or you get a 403, the credentials are invalid or the role is missing permissions.

---

## Notes

- Application Keys are scoped to the creating user/service account. If the service account is deleted, the Application Key is invalidated. Always use a dedicated service account, not a personal account.
- DataDog GovCloud (`ddog-gov.com`) uses the same API structure as commercial but is a separate tenant. Credentials are not shared between commercial and GovCloud environments.
- The fetchers default to GovCloud. If running against a commercial DataDog instance, set `DATADOG_BASE_URL=https://api.datadoghq.com` in your `.env`.
