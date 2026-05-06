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
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

csv.field_size_limit(sys.maxsize)

# ============================================================
# Load configuration from .env
# ============================================================
load_dotenv()

WIZ_CLIENT_ID = os.environ['WIZ_CLIENT_ID']
WIZ_CLIENT_SECRET = os.environ['WIZ_CLIENT_SECRET']
WIZ_AUTH_URL = os.environ['WIZ_AUTH_URL']
WIZ_API_ENDPOINT = os.environ['WIZ_API_ENDPOINT']

PARAMIFY_API_BASE_URL = os.environ['PARAMIFY_API_BASE_URL']
PARAMIFY_API_TOKEN = os.environ['PARAMIFY_API_TOKEN']
PARAMIFY_ASSESSMENT_ID = os.environ['PARAMIFY_ASSESSMENT_ID']

# Delta mode: when True, filter CSV to only changed issues
DELTA_MODE = os.environ.get('DELTA_MODE', 'false').lower() == 'true'

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
    "compressionMethod": "GZIP",
    "issueParams": {
        "type": "DETAILED",
        "issueFilters": {
            "status": ["OPEN", "IN_PROGRESS", "RESOLVED"]
        }
    }
}

COLUMNS_TO_DROP = ['Resource original JSON']

# Column used for Delta filtering
DELTA_FILTER_COLUMN = 'Status Changed At'

# ============================================================
# Internal Configuration
# ============================================================
MAX_RETRIES_FOR_QUERY = 5
RETRY_TIME_FOR_QUERY = 2
MAX_RETRIES_FOR_DOWNLOAD = 5
RETRY_TIME_FOR_DOWNLOAD = 60
CHECK_INTERVAL_FOR_DOWNLOAD = 20

COGNITO_URLS = [
    'https://auth.app.wiz.io/oauth/token',
    'https://auth.gov.wiz.io/oauth/token',
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
def load_state():
    """Load saved state from state.json."""
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
               last_successful_run: str = None) -> None:
    """Save current state to state.json."""
    existing = load_state() or {}
    state = {
        'report_id': report_id,
        'config_hash': config_hash,
        'last_run': datetime.now().isoformat(),
        'last_successful_run': (
            last_successful_run
            if last_successful_run is not None
            else existing.get('last_successful_run')
        ),
    }
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
        }
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
            json={'query': graphql_query, 'variables': variables}
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
    """Poll Wiz until report is ready, then return presigned download URL."""
    retries = 0
    while retries < MAX_RETRIES_FOR_DOWNLOAD:
        logging.info('Waiting %ds for report to complete', CHECK_INTERVAL_FOR_DOWNLOAD)
        time.sleep(CHECK_INTERVAL_FOR_DOWNLOAD)
        response = query_wiz(DOWNLOAD_REPORT_QUERY, {'reportId': report_id})
        status = response['report']['lastRun']['status']
        if status == 'COMPLETED':
            url = response['report']['lastRun']['url']
            logging.info('Report ready: %s', url[:80] + '...')
            return url
        if status in ('FAILED', 'EXPIRED'):
            logging.warning('Report status %s - rerunning', status)
            rerun_report(report_id)
            time.sleep(RETRY_TIME_FOR_DOWNLOAD)
            retries += 1
    raise Exception('Report download failed after max retries')

def download_csv(download_url: str) -> Path:
    """Stream Wiz CSV to disk, dropping unwanted columns. Returns path."""
    logging.info('Downloading CSV from Wiz')
    logging.info('Dropping columns: %s', COLUMNS_TO_DROP)
    with closing(requests.get(download_url, stream=True)) as r:
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
    today = datetime.now()
    logging.info('Uploading %s to Paramify (%s mode)', csv_path, mode_label)
    logging.info('  API:        %s', PARAMIFY_API_BASE_URL)
    logging.info('  Assessment: %s', PARAMIFY_ASSESSMENT_ID)
    with open(csv_path, 'rb') as f:
        response = requests.post(
            f"{PARAMIFY_API_BASE_URL}/assessment/{PARAMIFY_ASSESSMENT_ID}/intake",
            headers={
                "Authorization": f"Bearer {PARAMIFY_API_TOKEN}",
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
            }
        )
    response.raise_for_status()
    artifact = response.json()['artifacts'][0]
    logging.info('Uploaded artifact:')
    logging.info('  ID:    %s', artifact['id'])
    logging.info('  Title: %s', artifact['title'])
    logging.info('  File:  %s', artifact['originalFileName'])
    return artifact

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
    logging.info('  DELTA_MODE: %s', DELTA_MODE)
    logging.info('=' * 60)

    # Step 1: Authenticate to Wiz
    get_token()

    # Step 2: Compute current config hash
    current_hash = compute_config_hash(REPORT_CONFIG)
    logging.info('Current config hash: %s', current_hash)

    # Step 3: Decide create / update / rerun
    state = load_state()
    if not state or not state.get('report_id'):
        logging.info('No previous report - creating new')
        report_id = create_report()
    else:
        report_id = state['report_id']
        saved_hash = state.get('config_hash')
        if saved_hash != current_hash:
            logging.info('Config changed (was %s, now %s) - updating',
                         saved_hash, current_hash)
            update_report(report_id)
            rerun_report(report_id)
        else:
            logging.info('Config unchanged - rerunning existing report')
            rerun_report(report_id)

    # Step 4: Save state (without updating last_successful_run yet)
    save_state(report_id, current_hash)

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
    upload_to_paramify(upload_path, mode_label)

    # Step 8: Update last_successful_run after successful upload
    new_successful_run = datetime.now().isoformat()
    save_state(report_id, current_hash, last_successful_run=new_successful_run)
    logging.info('Updated last_successful_run: %s', new_successful_run)

    logging.info('=' * 60)
    logging.info('All done!')
    logging.info('=' * 60)

if __name__ == '__main__':
    main()
