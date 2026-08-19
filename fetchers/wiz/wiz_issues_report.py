#!/usr/bin/env python3
"""
Wiz Issues to Paramify Vulnerability Assessment Intake
======================================================

Fetches Wiz Issues report and uploads it to Paramify.

Behavior:
  - First run: creates a new Wiz report
  - Subsequent runs:
    - If config unchanged: reruns existing report
    - If config changed:   updates report and reruns
  - If DELTA_MODE=true and last_successful_run exists:
    - Filter CSV to only include issues with Status Changed At
      after last_successful_run
    - Upload filtered CSV (smaller payload)
  - Otherwise:
    - Upload full CSV
  - Updates last_successful_run after successful upload

Configuration:
  - Loaded from .env file
  - State (report_id, config_hash, last_run, last_successful_run)
    persisted in state.json
"""
import sys
import time
import csv
import codecs
import logging
import json
import os
import hashlib
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

# Add fetchers/ to path so we can import common utilities

import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.env_loader import init_fetcher_env
from common import paramify_state

csv.field_size_limit(sys.maxsize)

# ============================================================
# Load configuration from .env
# ============================================================
output_dir, _, _ = init_fetcher_env()

WIZ_CLIENT_ID = os.environ['WIZ_CLIENT_ID']
WIZ_CLIENT_SECRET = os.environ['WIZ_CLIENT_SECRET']
WIZ_AUTH_URL = os.environ['WIZ_AUTH_URL']
WIZ_API_ENDPOINT = os.environ['WIZ_API_ENDPOINT']


PARAMIFY_API_ISSUES_BASE_URL = os.environ['PARAMIFY_API_ISSUES_BASE_URL']
PARAMIFY_API_ISSUES_TOKEN = os.environ['PARAMIFY_API_ISSUES_TOKEN']
WIZ_ISSUES_PARAMIFY_ASSESSMENT_ID = os.environ['WIZ_ISSUES_PARAMIFY_ASSESSMENT_ID']

def _env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean env var. Only 'true'/'1'/'yes' are truthy."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().strip('"').strip("'").lower() in ('true', '1', 'yes')


# Delta mode: when True, filter the CSV to only changed issues.
# WIZ_ISSUES_DELTA_MODE is checked first so this fetcher can be switched
# independently of the vulnerability fetcher; DELTA_MODE remains as a fallback
# for existing .env files. Default is False, matching the README.
if os.environ.get('WIZ_ISSUES_DELTA_MODE') is not None:
    DELTA_MODE = _env_flag('WIZ_ISSUES_DELTA_MODE', False)
    DELTA_SOURCE = 'WIZ_ISSUES_DELTA_MODE'
elif os.environ.get('DELTA_MODE') is not None:
    DELTA_MODE = _env_flag('DELTA_MODE', False)
    DELTA_SOURCE = 'DELTA_MODE'
else:
    DELTA_MODE = False
    DELTA_SOURCE = 'default (unset)'

# ============================================================
# Report and file paths
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / 'state.json'
OUTPUT_CSV = SCRIPT_DIR / 'wiz_issues.csv'
DELTA_CSV = SCRIPT_DIR / 'wiz_issues_delta.csv'

# Report configuration
REPORT_CONFIG = {
    "name": "Paramify-Wiz-Fetcher",
    "type": "ISSUES",
    "projectId": "*",
    "issueParams": {
        "type": "DETAILED",
        "issueFilters": {
            "status": ["OPEN", "IN_PROGRESS", "RESOLVED"]
        }
    }
}

COLUMNS_TO_DROP = ['Resource original JSON']

# Column used for Delta filtering.
#
# 'Status Changed At' only moves when an Issue transitions between OPEN /
# IN_PROGRESS / RESOLVED. An Issue whose note, ticket link, assignee or
# severity changed without a status transition keeps its old timestamp and is
# therefore dropped from every delta, permanently. 'Updated At' moves on any
# change, which is what "give me what changed" is supposed to mean.
# Override with WIZ_ISSUES_DELTA_COLUMN if a tenant's export differs.
DELTA_FILTER_COLUMN = os.environ.get('WIZ_ISSUES_DELTA_COLUMN', 'Updated At')

# ============================================================
# Internal Configuration
# ============================================================
MAX_RETRIES_FOR_QUERY = 5
RETRY_TIME_FOR_QUERY = 2
MAX_RETRIES_FOR_DOWNLOAD = 5
RETRY_TIME_FOR_DOWNLOAD = 60
CHECK_INTERVAL_FOR_DOWNLOAD = 20
# Hard ceiling on report generation. Keep this comfortably below the
# orchestrator's WIZ_ISSUES_REPORT_TIMEOUT so we fail with our own
# message rather than being killed mid-poll.
MAX_WAIT_FOR_DOWNLOAD_SECONDS = int(
    os.environ.get('WIZ_ISSUES_REPORT_WAIT_SECONDS', '1200')
)

COGNITO_URLS = [
    'https://auth.app.wiz.io/oauth/token',
    'https://auth.gov.wiz.io/oauth/token',
    'https://auth.app.wiz.us/oauth/token'
]

global_token = ''

# ============================================================
# GraphQL queries
# ============================================================
CREATE_REPORT_MUTATION = """
    mutation CreateReport($input: CreateReportInput!) {
      createReport(input: $input) {
        report {
          id
        }
      }
    }
"""

UPDATE_REPORT_MUTATION = """
    mutation UpdateReport($input: UpdateReportInput!) {
        updateReport(input: $input) {
            report {
                id
            }
        }
    }
"""

DOWNLOAD_REPORT_QUERY = """
    query ReportDownloadUrl($reportId: ID!) {
        report(id: $reportId) {
            lastRun {
                url
                status
            }
        }
    }
"""

RERUN_REPORT_MUTATION = """
    mutation RerunReport($reportId: ID!) {
        rerunReport(input: { id: $reportId }) {
            report {
                id
            }
        }
    }
"""

# ============================================================
# Config hashing
# ============================================================
def compute_config_hash(config: dict) -> str:
    """Compute a stable hash of the report config to detect changes."""
    serialized = json.dumps(config, sort_keys=True)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:16]

# ============================================================
# State management
# ============================================================
STATE_ARTIFACT_NAME = 'wiz_issues_state.json'
STATE_EVIDENCE_ID = paramify_state.evidence_id('WIZ_ISSUES_STATE_EVIDENCE_ID')


def load_state():
    """Return the previous run's state, or None if there is not one.

    With WIZ_STATE_BACKEND=paramify the state lives in a Paramify evidence set
    instead of on this machine. That matters more here than for the
    vulnerability fetcher: this state carries `report_id`, and losing it does
    not merely cost a full fetch - it makes the next run create a *second*
    report inside Wiz and leave the first one orphaned.

    Any failure to read returns None, which the caller treats as "no previous
    report".
    """
    if paramify_state.enabled(STATE_EVIDENCE_ID):
        return paramify_state.load(STATE_EVIDENCE_ID, STATE_ARTIFACT_NAME)

    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
        logging.info('Loaded state: report_id=%s, config_hash=%s, last_successful_run=%s',
                     state.get('report_id'),
                     state.get('config_hash'),
                     state.get('last_successful_run'))
        return state
    logging.info('No previous state found')
    return None


def save_state(report_id: str, config_hash: str,
               last_successful_run: str = None,
               previous: dict = None) -> None:
    """Persist state to whichever backend is configured.

    `previous` is the state the caller already loaded. It is passed in rather
    than re-read here because main() saves twice per run (once before the
    report is polled so a crash cannot orphan the report_id, once after a
    successful upload), and with a remote backend each implicit re-read would
    be another HTTP round trip.
    """
    existing = previous if previous is not None else (load_state() or {})
    state = {
        'report_id': report_id,
        'config_hash': config_hash,
        'last_run': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'last_successful_run': (
            last_successful_run
            if last_successful_run is not None
            else (existing or {}).get('last_successful_run')
        ),
    }

    if paramify_state.enabled(STATE_EVIDENCE_ID):
        ok = paramify_state.save(STATE_EVIDENCE_ID, STATE_ARTIFACT_NAME, state,
                                 label='Wiz Issues')
        # The local file is still written, but only as a breadcrumb. It is
        # never read back while the Paramify backend is on, so the two cannot
        # drift into disagreeing about the watermark or the report id.
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({**state, '_authoritative': False,
                           '_backend': 'paramify'}, f, indent=2)
        except OSError as exc:
            logging.warning('Could not write the local state breadcrumb: %s', exc)
        if not ok:
            logging.warning('State was not persisted to Paramify. The next run '
                            'will create a new Wiz report instead of reusing '
                            'report_id %s.', report_id)
        return

    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    logging.info('Saved state to %s', STATE_FILE)

# ============================================================
# Wiz authentication and queries
# ============================================================
def get_token():
    global global_token
    logging.info('Getting Wiz token')
    if WIZ_AUTH_URL not in COGNITO_URLS:
        raise Exception('Invalid Wiz auth URL')
    response = requests.post(
        WIZ_AUTH_URL,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'grant_type': 'client_credentials',
            'audience': 'wiz-api',
            'client_id': WIZ_CLIENT_ID,
            'client_secret': WIZ_CLIENT_SECRET,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise Exception(
            f'Wiz auth failed [{response.status_code}] - {response.text}'
        )
    token = response.json().get('access_token')
    if not token:
        raise Exception('No access_token in Wiz auth response')
    global_token = token
    logging.info('Got Wiz token')

def query_wiz(graphql_query: str, variables: dict) -> dict:
    """Send GraphQL query to Wiz with retries."""
    if not global_token:
        raise Exception('Wiz token not initialized')
    retries = 0
    while True:
        response = requests.post(
            WIZ_API_ENDPOINT,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {global_token}',
                'User-Agent': 'Paramify-WizIntegration-0.1',
            },
            json={'query': graphql_query, 'variables': variables},
            timeout=30,
        )
        code = response.status_code
        if code in (401, 403):
            raise Exception(f'Wiz auth error [{code}] - {response.text}')
        if code == 404:
            raise Exception(f'Wiz endpoint not found [{code}] - check WIZ_API_ENDPOINT')
        if code == 200:
            data = response.json().get('data')
            if not data:
                errors = response.json().get('errors')
                raise Exception(f'Wiz returned no data: {errors}')
            return data
        if retries >= MAX_RETRIES_FOR_QUERY:
            raise Exception(
                f'Max retries exceeded. Last error [{code}] - {response.text}'
            )
        logging.info('Wiz query failed [%d], retrying in %ds', code, RETRY_TIME_FOR_QUERY)
        time.sleep(RETRY_TIME_FOR_QUERY)
        retries += 1

def create_report() -> str:
    """Create a new Wiz Issues report. Returns report_id."""
    logging.info('Creating new Wiz report')
    response = query_wiz(CREATE_REPORT_MUTATION, {"input": REPORT_CONFIG})
    report_id = response['createReport']['report']['id']
    logging.info('Created report. ID: %s', report_id)
    return report_id

def update_report(report_id: str) -> str:
    """Update existing Wiz report's parameters. Returns same report_id."""
    logging.info('Updating Wiz report config: %s', report_id)
    override = {
        "name": REPORT_CONFIG["name"],
        "issueParams": REPORT_CONFIG["issueParams"],
    }
    variables = {
        "input": {
            "id": report_id,
            "override": override,
        }
    }
    response = query_wiz(UPDATE_REPORT_MUTATION, variables)
    same_id = response['updateReport']['report']['id']
    logging.info('Update successful. ID: %s', same_id)
    return same_id

def rerun_report(report_id: str) -> str:
    """Rerun an existing Wiz report. Returns same report_id."""
    logging.info('Rerunning report: %s', report_id)
    response = query_wiz(RERUN_REPORT_MUTATION, {'reportId': report_id})
    same_id = response['rerunReport']['report']['id']
    logging.info('Rerun successful. ID: %s', same_id)
    return same_id

def get_report_download_url(report_id: str) -> str:
    """Poll Wiz until the report is ready, then return its presigned URL.

    The loop is bounded by wall clock as well as by failure count. Counting
    only FAILED/EXPIRED reruns meant a report stuck in RUNNING polled forever,
    with the orchestrator's subprocess timeout as the only way out - which
    kills the run without a usable error. MAX_WAIT_FOR_DOWNLOAD_SECONDS gives
    us a diagnosable failure instead.
    """
    reruns = 0
    started = time.monotonic()
    last_status = None
    while True:
        waited = time.monotonic() - started
        if waited > MAX_WAIT_FOR_DOWNLOAD_SECONDS:
            raise Exception(
                f'Report {report_id} was still "{last_status}" after '
                f'{waited:.0f}s (limit {MAX_WAIT_FOR_DOWNLOAD_SECONDS}s). '
                f'Raise WIZ_ISSUES_REPORT_WAIT_SECONDS if this tenant is '
                f'simply slow, or check the Wiz console for a stuck report.'
            )
        logging.info('Waiting %ds for report to complete (%.0fs elapsed)',
                     CHECK_INTERVAL_FOR_DOWNLOAD, waited)
        time.sleep(CHECK_INTERVAL_FOR_DOWNLOAD)
        response = query_wiz(DOWNLOAD_REPORT_QUERY, {'reportId': report_id})
        last_run = response['report']['lastRun'] or {}
        last_status = last_run.get('status')
        if last_status == 'COMPLETED':
            url = last_run.get('url')
            if not url:
                raise Exception('Report reported COMPLETED but returned no '
                                'download URL')
            logging.info('Report ready after %.0fs', time.monotonic() - started)
            return url
        if last_status in ('FAILED', 'EXPIRED'):
            reruns += 1
            if reruns > MAX_RETRIES_FOR_DOWNLOAD:
                raise Exception(f'Report {report_id} failed {reruns} times '
                                f'({last_status}) - giving up')
            logging.warning('Report status %s - rerunning (%d/%d)',
                            last_status, reruns, MAX_RETRIES_FOR_DOWNLOAD)
            rerun_report(report_id)
            time.sleep(RETRY_TIME_FOR_DOWNLOAD)

def download_csv(download_url: str) -> Path:
    """Stream Wiz CSV to disk, dropping unwanted columns. Returns path."""
    logging.info('Downloading CSV from Wiz')
    logging.info('Dropping columns: %s', COLUMNS_TO_DROP)
    # timeout=(connect_timeout, read_timeout) for streaming downloads.
    # Large CSVs can take many minutes to fully stream, but each chunk
    # should arrive within 60s — keeps us from hanging on dead connections.
    with closing(requests.get(download_url, stream=True, timeout=(10, 60))) as r:
        reader = csv.reader(codecs.iterdecode(r.iter_lines(), 'utf-8'))
        header = next(reader)
        drop_indices = {
            i for i, col in enumerate(header) if col in COLUMNS_TO_DROP
        }
        kept_header = [c for i, c in enumerate(header) if i not in drop_indices]
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(kept_header)
            row_count = 0
            for row in reader:
                kept_row = [v for i, v in enumerate(row) if i not in drop_indices]
                writer.writerow(kept_row)
                row_count += 1
    size_mb = OUTPUT_CSV.stat().st_size / 1024 / 1024
    logging.info('Saved %s (%d rows, %.2f MB)', OUTPUT_CSV, row_count, size_mb)
    return OUTPUT_CSV

# ============================================================
# Delta filtering
# ============================================================
def filter_csv_by_delta(csv_path: Path, last_successful_run: str) -> Path:
    """
    Filter CSV to only include rows where DELTA_FILTER_COLUMN > last_successful_run.
    Returns path to the filtered CSV (smaller file).
    """
    logging.info('Filtering CSV for Delta updates')
    logging.info('  Filter column:        %s', DELTA_FILTER_COLUMN)
    logging.info('  last_successful_run:  %s', last_successful_run)
    total_rows = 0
    kept_rows = 0
    with open(csv_path, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = reader.fieldnames
        if DELTA_FILTER_COLUMN not in fieldnames:
            raise Exception(
                f'Delta filter column "{DELTA_FILTER_COLUMN}" '
                f'not found in CSV. Available: {fieldnames}'
            )
        with open(DELTA_CSV, 'w', newline='', encoding='utf-8') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                total_rows += 1
                changed_at = row.get(DELTA_FILTER_COLUMN, '').strip()
                if changed_at and changed_at > last_successful_run:
                    writer.writerow(row)
                    kept_rows += 1
    size_mb = DELTA_CSV.stat().st_size / 1024 / 1024
    logging.info('Delta filter result:')
    logging.info('  Total rows:    %d', total_rows)
    logging.info('  Kept rows:     %d (%.1f%%)', kept_rows,
                 (kept_rows / total_rows * 100) if total_rows else 0)
    logging.info('  Output:        %s (%.2f MB)', DELTA_CSV, size_mb)
    return DELTA_CSV

# ============================================================
# Paramify upload
# ============================================================
def upload_to_paramify(csv_path: Path, mode_label: str = 'full') -> dict:
    """Upload CSV to Paramify Vulnerability Assessment Intake API."""
    today = datetime.now(timezone.utc)
    logging.info('Uploading %s to Paramify (%s mode)', csv_path, mode_label)
    logging.info('  API:        %s', PARAMIFY_API_ISSUES_BASE_URL)
    logging.info('  Assessment: %s', WIZ_ISSUES_PARAMIFY_ASSESSMENT_ID)
    with open(csv_path, 'rb') as f:
        response = requests.post(
            f"{PARAMIFY_API_ISSUES_BASE_URL}/assessment/{WIZ_ISSUES_PARAMIFY_ASSESSMENT_ID}/intake",
            headers={
                "Authorization": f"Bearer {PARAMIFY_API_ISSUES_TOKEN}",
                "Accept": "application/json",
            },
            files={
                "file": (csv_path.name, f, "text/csv"),
            },
            data={
                "artifact": json.dumps({
                    "title": f"Wiz Issues {today:%Y-%m-%d %H:%M} ({mode_label})",
                    "note": f"Automated upload via wiz-fetcher (mode={mode_label})",
                    "effectiveDate": today.isoformat(),
                }),
            },
            timeout=120,
        )
    response.raise_for_status()
    artifact = response.json()['artifacts'][0]
    logging.info('Uploaded artifact:')
    logging.info('  ID:    %s', artifact['id'])
    logging.info('  Title: %s', artifact['title'])
    logging.info('  File:  %s', artifact['originalFileName'])
    return artifact

# ============================================================
# Report lifecycle
# ============================================================
def _reuse_or_create_report(state: dict, current_hash: str) -> str:
    """Reuse the saved Wiz report if it still exists, otherwise make a new one.

    Wiz retains reports for 7 days and then deletes them permanently ("Reports
    are automatically expired after 7 days" in the Saved Reports UI). Any run
    cadence looser than weekly - and this fetcher is documented for monthly
    cron - therefore finds its saved report_id already gone. That is normal
    ageing, not an error, so a failed rerun must not take the run down with it:
    we log it and create a replacement.

    Without this, a stale report_id crashed the fetcher at Step 3 before it
    could record anything, which is how ten orphaned "Paramify-Wiz-Fetcher"
    reports accumulated in the tenant.
    """
    if not state or not state.get('report_id'):
        logging.info('No previous report - creating new')
        return create_report()

    report_id = state['report_id']
    saved_hash = state.get('config_hash')
    try:
        if saved_hash != current_hash:
            logging.info('Config changed (was %s, now %s) - updating',
                         saved_hash, current_hash)
            update_report(report_id)
        else:
            logging.info('Config unchanged - rerunning existing report')
        rerun_report(report_id)
        return report_id
    except Exception as exc:
        logging.warning('Saved report %s could not be reused (%s: %s). Wiz '
                        'expires reports after 7 days, so this is expected '
                        'when runs are further apart than that - creating a '
                        'replacement.', report_id, type(exc).__name__, exc)
        return create_report()


# ============================================================
# Main
# ============================================================
def main():
    logging.basicConfig(
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        level=logging.INFO,
    )
    logging.info('=' * 60)
    logging.info('Wiz to Paramify Fetcher (Delta Updates support)')
    logging.info('  DELTA_MODE: %s (from %s)', DELTA_MODE, DELTA_SOURCE)
    logging.info('=' * 60)

    # Step 1: Authenticate to Wiz
    get_token()

    # Step 2: Compute current config hash
    current_hash = compute_config_hash(REPORT_CONFIG)
    logging.info('Current config hash: %s', current_hash)

    # Step 3: Decide create / update / rerun
    state = load_state()
    report_id = _reuse_or_create_report(state, current_hash)

    # Step 4: Save state now, before the long poll. If the process dies while
    # the report is generating, report_id is already recorded and the next run
    # reuses it instead of leaving an orphan behind in Wiz.
    # last_successful_run is deliberately not touched yet - nothing has been
    # uploaded, so the watermark has not moved.
    save_state(report_id, current_hash, previous=state)

    # Step 5: Wait for report and download CSV
    download_url = get_report_download_url(report_id)
    csv_path = download_csv(download_url)

    # Step 6: Decide full vs delta upload
    last_successful_run = state.get('last_successful_run') if state else None
    if DELTA_MODE and last_successful_run:
        logging.info('Delta mode: filtering CSV')
        upload_path = filter_csv_by_delta(csv_path, last_successful_run)
        mode_label = 'delta'
    else:
        if DELTA_MODE and not last_successful_run:
            logging.info('Delta mode requested but no last_successful_run found')
            logging.info('First run - uploading full CSV (delta starts next run)')
        else:
            logging.info('Full mode - uploading complete CSV')
        upload_path = csv_path
        mode_label = 'full'

    # Step 7: Upload to Paramify
    artifact = upload_to_paramify(upload_path, mode_label)

    # Step 8: Update last_successful_run after successful upload
    # UTC ISO 8601 with 'Z' suffix matches Wiz's "Status Changed At" format,
    # so string comparison in filter_csv_by_delta() works correctly.
    new_successful_run = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    save_state(report_id, current_hash,
               last_successful_run=new_successful_run, previous=state)
    logging.info('Updated last_successful_run: %s', new_successful_run)

    # Step 9: Write summary JSON for TUI review screen
    summary_path = Path(output_dir) / 'wiz_issues.json'
    summary = {
        'fetcher': 'wiz_issues_report',
        'mode': mode_label,
        'artifact_id': artifact.get('id'),
        'artifact_title': artifact.get('title'),
        'timestamp': new_successful_run,
    }
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    logging.info('Wrote summary to %s', summary_path)

    logging.info('=' * 60)
    logging.info('All done!')
    logging.info('=' * 60)

if __name__ == '__main__':
    main()
