#!/usr/bin/env python3
"""
Wiz Vulnerability Findings to Paramify Vulnerability Assessment Intake
=====================================================================

Fetches Wiz Vulnerability Findings via GraphQL pagination and uploads
them as an artifact to a Paramify vulnerability ASSESSMENT via the
assessment intake endpoint (POST /assessment/{assessmentId}/intake).

Behavior:
  - First run: fetches ALL vulnerabilities (no updatedAt filter)
  - Subsequent runs (if state.json has last_successful_run):
    - Uses updatedAt.after filter to only fetch changed vulnerabilities
    - "Delta updates" pattern recommended by Wiz docs
  - If DELTA_MODE=false: always fetches ALL vulnerabilities (ignores saved state)
  - Streams paginated results, writes to a single CSV locally
  - Uploads CSV as an artifact to a Paramify assessment intake
    via POST /assessment/{assessmentId}/intake
  - Updates last_successful_run after successful upload

Prerequisites:
  - Paramify vulnerability assessment must already exist
    (created in the Paramify UI)
  - Assessment UUID set in WIZ_VULN_PARAMIFY_ASSESSMENT_ID env var
  - Wiz Service Account must have read:vulnerabilities scope

Configuration:
  - Loaded from .env file
  - State (config_hash, last_run, last_successful_run)
    persisted in vuln_state.json
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

import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.env_loader import init_fetcher_env

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
# Paramify vulnerability ASSESSMENT UUID (the assessment intake destination).
WIZ_VULN_PARAMIFY_ASSESSMENT_ID = os.environ['WIZ_VULN_PARAMIFY_ASSESSMENT_ID']

# Delta mode: when False, always fetch ALL vulnerabilities (ignores saved state).
# When True (default), use last_successful_run from state for incremental fetches.
DELTA_MODE = os.environ.get('DELTA_MODE', 'true').lower() == 'true'

# ============================================================
# File paths
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / 'vuln_state.json'
OUTPUT_CSV = SCRIPT_DIR / 'wiz_vulnerabilities.csv'

# ============================================================
# Query configuration
# ============================================================
# Page size for GraphQL pagination (Wiz API max: 1000, default: 1)
# 100 chosen as a balance between throughput and response size.
PAGE_SIZE = 100

# Filter configuration: empty filter = fetch ALL vulnerabilities.
# Add filters here if needed (e.g., severity, status).
FILTER_CONFIG = {}

# ============================================================
# Internal Configuration
# ============================================================
MAX_RETRIES_FOR_QUERY = 5
RETRY_TIME_FOR_QUERY = 2

COGNITO_URLS = [
    'https://auth.app.wiz.io/oauth/token',
    'https://auth.gov.wiz.io/oauth/token',
    'https://auth.app.wiz.us/oauth/token'
]

global_token = ''

# ============================================================
# GraphQL query
# ============================================================
# Fetches a focused subset of vulnerability fields - enough for compliance
# evidence without bloating the CSV. Pagination uses 'first' + 'after'.
VULNERABILITIES_QUERY = """
query VulnerabilityFindingsPage($filterBy: VulnerabilityFindingFilters,
                                  $first: Int, $after: String) {
  vulnerabilityFindings(filterBy: $filterBy, first: $first, after: $after) {
    nodes {
      id
      name
      CVEDescription
      CVSSSeverity
      score
      severity
      nvdSeverity
      status
      hasExploit
      hasFix
      hasCisaKevExploit
      firstDetectedAt
      lastDetectedAt
      resolvedAt
      description
      remediation
      detailedName
      version
      fixedVersion
      detectionMethod
      link
      portalUrl
      epssSeverity
      epssPercentile
      epssProbability
      relatedIssueAnalytics {
        issueCount
        criticalSeverityCount
        highSeverityCount
        mediumSeverityCount
        lowSeverityCount
      }
      vulnerableAsset {
        ... on VulnerableAssetBase {
          id
          type
          name
          region
          providerUniqueId
          cloudPlatform
          status
          subscriptionName
          subscriptionExternalId
          tags
          hasWideInternetExposure
        }
        ... on VulnerableAssetVirtualMachine {
          operatingSystem
          ipAddresses
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# CSV columns - flat list matching the GraphQL fields above. Nested fields
# are flattened (e.g., asset.name -> Asset Name).
CSV_COLUMNS = [
    'ID', 'Name', 'CVE Description', 'CVSS Severity', 'Score',
    'Severity', 'NVD Severity', 'Status',
    'Has Exploit', 'Has Fix', 'Has CISA KEV Exploit',
    'First Detected At', 'Last Detected At', 'Resolved At',
    'Description', 'Remediation',
    'Detailed Name', 'Version', 'Fixed Version',
    'Detection Method', 'Link', 'Portal URL',
    'EPSS Severity', 'EPSS Percentile', 'EPSS Probability',
    'Related Issue Count',
    'Related Critical Issues', 'Related High Issues',
    'Related Medium Issues', 'Related Low Issues',
    'Asset ID', 'Asset Type', 'Asset Name', 'Asset Region',
    'Asset Provider ID', 'Asset Cloud Platform', 'Asset Status',
    'Asset Subscription Name', 'Asset Subscription External ID',
    'Asset Tags', 'Asset Has Wide Internet Exposure',
    'Asset Operating System', 'Asset IP Addresses',
]

# ============================================================
# Config hashing
# ============================================================
def compute_config_hash(config: dict) -> str:
    """Compute a stable hash of the query config to detect changes."""
    serialized = json.dumps(config, sort_keys=True)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:16]

# ============================================================
# State management
# ============================================================
def load_state():
    """Load saved state from vuln_state.json."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
        logging.info(
            'Loaded state: config_hash=%s, last_successful_run=%s',
            state.get('config_hash'),
            state.get('last_successful_run')
        )
        return state
    logging.info('No previous state found - this is the first run')
    return None

def save_state(config_hash: str, last_successful_run: str = None) -> None:
    """Save current state to vuln_state.json."""
    existing = load_state() or {}
    state = {
        'config_hash': config_hash,
        'last_run': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
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
            raise Exception(
                f'Wiz endpoint not found [{code}] - check WIZ_API_ENDPOINT'
            )
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
        logging.info('Wiz query failed [%d], retrying in %ds',
                     code, RETRY_TIME_FOR_QUERY)
        time.sleep(RETRY_TIME_FOR_QUERY)
        retries += 1

# ============================================================
# Vulnerability fetching with pagination
# ============================================================
def fetch_vulnerabilities(last_successful_run: str = None) -> int:
    """
    Fetch all vulnerabilities via GraphQL pagination, write to CSV.
    If last_successful_run is provided, only fetch vulnerabilities
    updated after that timestamp (delta mode).
    Returns total number of rows written.
    """
    filter_by = dict(FILTER_CONFIG)
    if last_successful_run:
        filter_by['updatedAt'] = {'after': last_successful_run}
        logging.info('Delta mode: fetching vulnerabilities updated after %s',
                     last_successful_run)
    else:
        logging.info('Full mode: fetching ALL vulnerabilities')

    after_cursor = None
    page_num = 0
    total_rows = 0

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        while True:
            page_num += 1
            variables = {
                'filterBy': filter_by,
                'first': PAGE_SIZE,
            }
            if after_cursor:
                variables['after'] = after_cursor

            logging.info('Fetching page %d (after=%s)', page_num,
                         after_cursor[:20] + '...' if after_cursor else 'None')
            response = query_wiz(VULNERABILITIES_QUERY, variables)

            findings = response.get('vulnerabilityFindings')
            if not findings:
                raise Exception(
                    'No vulnerabilityFindings in response: %s' % response
                )

            nodes = findings.get('nodes') or []
            page_info = findings.get('pageInfo') or {}

            for node in nodes:
                row = flatten_vulnerability(node)
                writer.writerow(row)
                total_rows += 1

            logging.info('Page %d: %d findings (total so far: %d)',
                         page_num, len(nodes), total_rows)

            if not page_info.get('hasNextPage'):
                logging.info('No more pages - pagination complete')
                break
            after_cursor = page_info.get('endCursor')
            if not after_cursor:
                logging.warning('hasNextPage=true but no endCursor - stopping')
                break

    size_mb = OUTPUT_CSV.stat().st_size / 1024 / 1024
    logging.info('Wrote %s (%d rows, %.2f MB) across %d pages',
                 OUTPUT_CSV, total_rows, size_mb, page_num)
    return total_rows

def flatten_vulnerability(node: dict) -> dict:
    """Flatten a vulnerabilityFinding node into a flat CSV row dict."""
    analytics = node.get('relatedIssueAnalytics') or {}
    asset = node.get('vulnerableAsset') or {}
    ip_addresses = asset.get('ipAddresses') or []
    tags = asset.get('tags') or {}

    return {
        'ID': node.get('id', ''),
        'Name': node.get('name', ''),
        'CVE Description': node.get('CVEDescription', '') or '',
        'CVSS Severity': node.get('CVSSSeverity', '') or '',
        'Score': node.get('score', '') if node.get('score') is not None else '',
        'Severity': node.get('severity', '') or '',
        'NVD Severity': node.get('nvdSeverity', '') or '',
        'Status': node.get('status', '') or '',
        'Has Exploit': node.get('hasExploit', ''),
        'Has Fix': node.get('hasFix', ''),
        'Has CISA KEV Exploit': node.get('hasCisaKevExploit', ''),
        'First Detected At': node.get('firstDetectedAt', '') or '',
        'Last Detected At': node.get('lastDetectedAt', '') or '',
        'Resolved At': node.get('resolvedAt', '') or '',
        'Description': node.get('description', '') or '',
        'Remediation': node.get('remediation', '') or '',
        'Detailed Name': node.get('detailedName', '') or '',
        'Version': node.get('version', '') or '',
        'Fixed Version': node.get('fixedVersion', '') or '',
        'Detection Method': node.get('detectionMethod', '') or '',
        'Link': node.get('link', '') or '',
        'Portal URL': node.get('portalUrl', '') or '',
        'EPSS Severity': node.get('epssSeverity', '') or '',
        'EPSS Percentile': node.get('epssPercentile', '')
                          if node.get('epssPercentile') is not None else '',
        'EPSS Probability': node.get('epssProbability', '')
                            if node.get('epssProbability') is not None else '',
        'Related Issue Count': analytics.get('issueCount', '')
                               if analytics.get('issueCount') is not None else '',
        'Related Critical Issues': analytics.get('criticalSeverityCount', '')
                                   if analytics.get('criticalSeverityCount') is not None else '',
        'Related High Issues': analytics.get('highSeverityCount', '')
                               if analytics.get('highSeverityCount') is not None else '',
        'Related Medium Issues': analytics.get('mediumSeverityCount', '')
                                 if analytics.get('mediumSeverityCount') is not None else '',
        'Related Low Issues': analytics.get('lowSeverityCount', '')
                              if analytics.get('lowSeverityCount') is not None else '',
        'Asset ID': asset.get('id', '') or '',
        'Asset Type': asset.get('type', '') or '',
        'Asset Name': asset.get('name', '') or '',
        'Asset Region': asset.get('region', '') or '',
        'Asset Provider ID': asset.get('providerUniqueId', '') or '',
        'Asset Cloud Platform': asset.get('cloudPlatform', '') or '',
        'Asset Status': asset.get('status', '') or '',
        'Asset Subscription Name': asset.get('subscriptionName', '') or '',
        'Asset Subscription External ID': asset.get('subscriptionExternalId', '') or '',
        'Asset Tags': json.dumps(tags) if tags else '',
        'Asset Has Wide Internet Exposure': asset.get('hasWideInternetExposure', ''),
        'Asset Operating System': asset.get('operatingSystem', '') or '',
        'Asset IP Addresses': ', '.join(ip_addresses) if ip_addresses else '',
    }

# ============================================================
# Paramify upload
# ============================================================
def upload_to_paramify(csv_path: Path, mode_label: str = 'full') -> dict:
    """Upload CSV as an artifact to a Paramify vulnerability assessment intake."""
    today = datetime.now(timezone.utc)
    logging.info('Uploading %s to Paramify (%s mode)', csv_path, mode_label)
    logging.info('  API:        %s', PARAMIFY_API_ISSUES_BASE_URL)
    logging.info('  Assessment: %s', WIZ_VULN_PARAMIFY_ASSESSMENT_ID)
    with open(csv_path, 'rb') as f:
        response = requests.post(
            f"{PARAMIFY_API_ISSUES_BASE_URL}/assessment/{WIZ_VULN_PARAMIFY_ASSESSMENT_ID}/intake",
            headers={
                "Authorization": f"Bearer {PARAMIFY_API_ISSUES_TOKEN}",
                "Accept": "application/json",
            },
            files={
                "file": (csv_path.name, f, "text/csv"),
            },
            data={
                "artifact": json.dumps({
                    "title": f"Wiz Vulnerabilities {today:%Y-%m-%d %H:%M} ({mode_label})",
                    "note": f"Automated upload via wiz-vulnerabilities-fetcher (mode={mode_label})",
                    "effectiveDate": today.isoformat(),
                }),
            },
            timeout=600,
        )
    response.raise_for_status()
    # Assessment intake endpoint returns an array of artifacts.
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
    logging.info('Wiz Vulnerabilities to Paramify Fetcher')
    logging.info('  DELTA_MODE: %s', DELTA_MODE)
    logging.info('=' * 60)

    # Step 1: Authenticate to Wiz
    get_token()

    # Step 2: Compute current config hash
    current_hash = compute_config_hash({
        'filter': FILTER_CONFIG,
        'page_size': PAGE_SIZE,
    })
    logging.info('Current config hash: %s', current_hash)

    # Step 3: Load state to decide full vs delta
    state = load_state()
    last_successful_run = None
    if DELTA_MODE and state:
        saved_hash = state.get('config_hash')
        if saved_hash != current_hash:
            logging.info('Config changed (was %s, now %s) - falling back to full fetch',
                         saved_hash, current_hash)
        else:
            last_successful_run = state.get('last_successful_run')
    elif not DELTA_MODE:
        logging.info('DELTA_MODE=false - forcing full fetch (ignoring saved state)')

    mode_label = 'delta' if last_successful_run else 'full'

    # Step 4: Fetch vulnerabilities (paginated)
    row_count = fetch_vulnerabilities(last_successful_run=last_successful_run)

    if row_count == 0:
        logging.info('No vulnerabilities to upload (0 rows)')
        # Still update last_successful_run so next run picks up new changes
        new_successful_run = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        save_state(current_hash, last_successful_run=new_successful_run)
        logging.info('Updated last_successful_run: %s', new_successful_run)
        logging.info('=' * 60)
        logging.info('All done (nothing to upload)')
        logging.info('=' * 60)
        return

    # Step 5: Upload to Paramify
    artifact = upload_to_paramify(OUTPUT_CSV, mode_label)

    # Step 6: Update last_successful_run after successful upload.
    # UTC ISO 8601 with 'Z' suffix matches Wiz's updatedAt format,
    # so the delta filter in the next run compares correctly.
    new_successful_run = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    save_state(current_hash, last_successful_run=new_successful_run)
    logging.info('Updated last_successful_run: %s', new_successful_run)

    # Step 7: Write summary JSON for TUI review screen
    summary_path = Path(output_dir) / 'wiz_vulnerabilities.json'
    summary = {
        'fetcher': 'wiz_vulnerabilities_findings',
        'mode': mode_label,
        'artifact_id': artifact.get('id'),
        'artifact_title': artifact.get('title'),
        'row_count': row_count,
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
