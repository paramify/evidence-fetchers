# Wiz Issues Fetcher

Pulls security Issues from Wiz and uploads them to a Paramify Vulnerability Assessment cycle as CSV.

Designed for monthly automated runs via cron, with optional Delta mode for incremental updates after the first run.

## Prerequisites

- Python 3.9 or higher
- Wiz tenant with API access
- Paramify account with a Vulnerability Assessment configured for Wiz

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/paramify/evidence-fetchers.git
cd evidence-fetchers/fetchers/wiz

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Edit .env with your actual values
chmod 600 .env

# 4. Run
python3 wiz_to_paramify.py
```

## Setup

### Step 1: Create a Wiz Service Account

In your Wiz console:

1. Go to **Settings → Service Accounts**
2. Create a new service account
3. Assign these permissions:
   - `read:issues`
   - `create:reports`
   - `update:reports`
4. Save the **Client ID** and **Client Secret** — you will need them for `.env`

### Step 2: Find Your Wiz API Endpoint

Your Wiz API endpoint follows this pattern:

```
https://api.{TENANT}.app.wiz.io/graphql
```

Replace `{TENANT}` with your tenant identifier (e.g., `us17`, `eu1`).

### Step 3: Configure Paramify

1. Create a Vulnerability Assessment in Paramify
2. Configure it with the Wiz mechanism
3. Generate an API token under **Settings → API Tokens** with these permissions:
   - View Issues
   - Write Issues
   - View Evidences
   - Write Evidences
4. Copy the Assessment ID from the URL when viewing your assessment:

```
https://app.paramify.com/assessment/{ASSESSMENT_ID}
```

### Step 4: Configure Environment

```bash
cp .env.example .env
chmod 600 .env  # Restrict file permissions
```

Edit `.env` with your actual values (see [Configuration](#configuration) below).

### Step 5: First Run

```bash
python3 wiz_to_paramify.py
```

The first run will:
- Create a new Wiz Issues report
- Wait for the report to complete (typically 3-5 minutes)
- Download the CSV
- Upload it to your Paramify Vulnerability Assessment cycle
- Save state to `state.json` for subsequent runs

## Configuration

All configuration is done via the `.env` file:

| Variable | Required | Description |
|---|---|---|
| `WIZ_CLIENT_ID` | Yes | Wiz service account ID |
| `WIZ_CLIENT_SECRET` | Yes | Wiz service account secret |
| `WIZ_AUTH_URL` | Yes | Wiz OAuth URL (default: `https://auth.app.wiz.io/oauth/token`) |
| `WIZ_API_ENDPOINT` | Yes | Your tenant's GraphQL endpoint |
| `PARAMIFY_API_BASE_URL` | Yes | Paramify API base URL |
| `PARAMIFY_API_TOKEN` | Yes | Paramify API token |
| `PARAMIFY_ASSESSMENT_ID` | Yes | Target Vulnerability Assessment UUID |
| `DELTA_MODE` | No | `true` for Delta filtering, `false` for full upload (default: `false`) |

## Field Mapping

The Wiz CSV columns are mapped to Paramify fields automatically by the mechanism.

### Field Names

| Wiz CSV Column | → | Paramify Field |
|---|---|---|
| Issue ID | → | Unique Record ID |
| Title | → | Weakness Name |
| Description | → | Weakness Description |
| Created At | → | Effective Date |
| Resolved Time | → | Date Closed |
| Remediation Recommendation | → | Recommendation |
| Resource external ID | → | Asset Identifier |
| Severity | → | Original Risk Level |

### Severity Mapping

Wiz uses 5 severity levels; Paramify uses 4:

| Wiz Severity | → | Paramify Level |
|---|---|---|
| CRITICAL | → | Critical |
| HIGH | → | High |
| MEDIUM | → | Moderate |
| LOW | → | Low |
| INFORMATIONAL | → | (not imported) |

⚠️ **Note**: Wiz `INFORMATIONAL` issues are not imported into Paramify, as they typically don't require POA&M tracking.

## Customer Workflow

### Each Fetcher Run

After `python3 wiz_to_paramify.py` completes successfully:

1. Open your Vulnerability Assessment cycle in Paramify
2. Click **Run Intake Workflow**
3. Click **Next** through the 5 wizard steps
4. Click **Process Intake Configurations**
5. Click **Save to Cycle**
6. When ready, click **Close Cycle** to convert observations into Issues

⚠️ Steps 1-6 are manual UI actions in Phase 1. They will be automated in Phase 2.

### Monthly Cron Setup

After your first successful run, enable Delta mode for faster monthly updates:

```bash
# Edit .env
DELTA_MODE=true
```

Then add a cron job:

```bash
crontab -e
```

```
# Run on the 1st of each month at 6 AM
0 6 1 * * cd /path/to/evidence-fetchers/fetchers/wiz && /usr/bin/python3 wiz_to_paramify.py >> wiz_fetcher.log 2>&1
```

## Delta Mode

Delta mode filters the CSV to only include Issues whose `Status Changed At` is after the last successful run.

| Mode | First Run | Subsequent Runs |
|---|---|---|
| `DELTA_MODE=false` | Full CSV upload | Full CSV upload |
| `DELTA_MODE=true` | Full CSV upload (no `last_successful_run` yet) | Delta only |

Typical reduction: **99%+** payload size after first run.

## How It Works

1. Authenticates with Wiz using OAuth client credentials
2. Creates a Wiz Issues Report on first run, or reruns the existing one (saved in `state.json`)
3. If the report configuration changes, calls `UpdateReport` before rerun
4. Polls for report completion
5. Downloads the CSV via the presigned URL
6. (Optional) Filters CSV by `Status Changed At > last_successful_run` for Delta mode
7. Uploads the CSV to Paramify Vulnerability Assessment Intake API
8. Updates `state.json` with the new `last_successful_run` timestamp

## State Management

`state.json` is created automatically and contains:

```json
{
  "report_id": "...",
  "config_hash": "...",
  "last_run": "...",
  "last_successful_run": "..."
}
```

**Do not commit `state.json` to version control** — it contains your tenant-specific report ID. It is excluded by `.gitignore`.

## Troubleshooting

### `Wiz auth failed [401]`

- Verify `WIZ_CLIENT_ID` and `WIZ_CLIENT_SECRET` in `.env`
- Confirm the service account has the required permissions

### `Wiz endpoint not found [404]`

- Check `WIZ_API_ENDPOINT` matches your tenant
- Format: `https://api.{TENANT}.app.wiz.io/graphql`

### `Paramify upload failed [403]`

- Verify `PARAMIFY_API_TOKEN` has `Write Evidences` permission
- Confirm `PARAMIFY_ASSESSMENT_ID` is correct

### Report stays in `RUNNING` forever

- Try deleting `state.json` and rerun
- Check the Wiz console to confirm reports are being created

### Delta mode uploads 0 rows

- This is normal if no Issues changed since the last run
- The script still uploads an empty CSV to maintain the audit trail

## Phase 1 Limitations

Current Phase 1 implementation:

- ❌ Cycle close requires manual UI click (Paramify Cycle API not yet available)
- ❌ Intake Workflow requires manual UI click (will be automated when API ships)
- ❌ No bidirectional sync between Wiz and Paramify Issue status
- ❌ Real-time updates not supported (monthly batch only)

### Coming in Phase 2

- ✅ Automated Cycle Close
- ✅ Automated Intake Workflow
- ✅ Webhook integration for real-time sync
- ✅ Bidirectional Issue status updates

## Support

For issues or feature requests, see the [Paramify Community Feature Requests](https://support.paramify.com/hc/en-us/community/topics/31851789568275-Feature-Requests).
