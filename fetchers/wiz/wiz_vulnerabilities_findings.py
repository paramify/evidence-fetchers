#!/usr/bin/env python3
"""
Wiz Vulnerability Findings to Paramify Vulnerability Assessment Intake
=====================================================================

Fetches Wiz Vulnerability Findings via GraphQL pagination and uploads
them as a CSV artifact to a Paramify vulnerability ASSESSMENT via the
assessment intake endpoint (POST /assessment/{assessmentId}/intake).

Behavior:
  - Full run: fetches ALL vulnerability findings (no date filter)
  - Delta run (WIZ_VULN_DELTA_MODE=true AND vuln_state.json has
    last_successful_run AND config hash unchanged):
      - Applies a date filter on WIZ_VULN_DELTA_FIELD (default
        lastDetectedAt) to only fetch findings seen since the last run
      - The filter is probed with a 1-row query before the real run. If
        Wiz rejects the field, we log the GraphQL error and fall back to
        a full fetch instead of failing the whole fetcher.
  - Streams paginated results, writes a single CSV
  - Uploads the CSV as an artifact to POST /assessment/{id}/intake
  - Updates last_successful_run only after a successful upload

Outputs:
  - CSV  -> $EVIDENCE_DIR/wiz_vulnerabilities.csv   (the real artifact)
  - CSV  -> <script dir>/wiz_vulnerabilities.csv    (local working copy)
  - JSON -> <script dir>/wiz_vulnerabilities_run.json  (run summary)

The run summary is deliberately NOT written into $EVIDENCE_DIR. Steps 3
and 4 of the orchestrator glob $EVIDENCE_DIR/*.json and push whatever
they find to /evidence/{id}/artifacts/upload. This fetcher uploads its
own CSV to the assessment intake endpoint, so a JSON file in that
directory only results in the wrong artifact type being uploaded twice.

Prerequisites:
  - Paramify vulnerability assessment must already exist (created in UI)
  - Assessment UUID in WIZ_VULN_PARAMIFY_ASSESSMENT_ID
  - Wiz Service Account must have read:vulnerabilities scope
  - Because a full pull can run for 30+ minutes, set a per-fetcher
    subprocess timeout in .env so run_fetchers.py does not kill it:
        WIZ_VULNERABILITIES_FINDINGS_TIMEOUT=7200
"""
import sys
import time
import csv
import logging
import json
import os
import shutil
import hashlib
import random
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
WIZ_VULN_PARAMIFY_ASSESSMENT_ID = os.environ['WIZ_VULN_PARAMIFY_ASSESSMENT_ID']


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean env var. Only 'true'/'1'/'yes' are truthy."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().strip('"').strip("'").lower() in ('true', '1', 'yes')


# Delta mode. WIZ_VULN_DELTA_MODE is checked first so this fetcher can be
# switched independently of the Issues fetcher; DELTA_MODE remains as a
# fallback for existing .env files. Default is False, matching the README.
if os.environ.get('WIZ_VULN_DELTA_MODE') is not None:
    DELTA_MODE = _env_flag('WIZ_VULN_DELTA_MODE', False)
    DELTA_SOURCE = 'WIZ_VULN_DELTA_MODE'
elif os.environ.get('DELTA_MODE') is not None:
    DELTA_MODE = _env_flag('DELTA_MODE', False)
    DELTA_SOURCE = 'DELTA_MODE'
else:
    DELTA_MODE = False
    DELTA_SOURCE = 'default (unset)'

# ============================================================
# File paths
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / 'vuln_state.json'
OUTPUT_CSV = SCRIPT_DIR / 'wiz_vulnerabilities.csv'
EVIDENCE_CSV = Path(output_dir) / 'wiz_vulnerabilities.csv'
RUN_SUMMARY = SCRIPT_DIR / 'wiz_vulnerabilities_run.json'

# ============================================================
# Query configuration
# ============================================================
# Wiz allows a much larger page size on vulnerabilityFindings than the
# 100 this fetcher used to send. At 100/page a 36k-finding tenant needs
# ~370 round trips, which is what pushed the run past the orchestrator's
# 300s subprocess timeout. 500 is a safe default; raise via env if your
# tenant tolerates it.
PAGE_SIZE = int(os.environ.get('WIZ_VULN_PAGE_SIZE', '500'))

# Field used for delta filtering. `updatedAt` is confirmed working against
# the WIN gov tenant (a delta run on 2026-08-12 returned 314 rows and a
# valid artifact id), so it stays the default. If another tenant rejects
# it, the probe below catches that and falls back to a full fetch rather
# than killing the run. Alternatives worth trying: lastDetectedAt,
# detectedAt, firstDetectedAt.
DELTA_FIELD = os.environ.get('WIZ_VULN_DELTA_FIELD', 'updatedAt')

# Empty filter = fetch ALL findings.
FILTER_CONFIG = {'status': ['OPEN', 'RESOLVED']}

# ============================================================
# Internal Configuration
# ============================================================
MAX_RETRIES_FOR_QUERY = 6
RETRY_BASE_SECONDS = 2
# Wiz access tokens are short lived relative to a full pull, so refresh
# proactively rather than waiting for a mid-pagination 401.
TOKEN_REFRESH_AFTER_SECONDS = int(
    os.environ.get('WIZ_TOKEN_REFRESH_SECONDS', '2400')
)

COGNITO_URLS = [
    'https://auth.app.wiz.io/oauth/token',
    'https://auth.gov.wiz.io/oauth/token',
    'https://auth.app.wiz.us/oauth/token'
]

global_token = ''
token_issued_at = 0.0

# ============================================================
# GraphQL query
# ============================================================
VULNERABILITIES_QUERY = """
query VulnerabilityFindingsPage($filterBy: VulnerabilityFindingFilters,
                                  $first: Int, $after: String) {
  vulnerabilityFindings(filterBy: $filterBy, first: $first, after: $after) {
    totalCount
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

# Minimal query used to validate the delta filter before committing to a
# long paginated run.
FILTER_PROBE_QUERY = """
query VulnerabilityFindingsProbe($filterBy: VulnerabilityFindingFilters,
                                   $first: Int) {
  vulnerabilityFindings(filterBy: $filterBy, first: $first) {
    totalCount
    pageInfo { hasNextPage }
  }
}
"""

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


class WizFilterRejected(Exception):
    """Raised when Wiz rejects the filterBy argument (bad field name)."""


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
    global global_token, token_issued_at
    logging.info('>>> RUNNING FILE: %s <<<', __file__)
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
    token_issued_at = time.monotonic()
    logging.info('Got Wiz token')


def _maybe_refresh_token():
    """Re-authenticate if the current token is old enough to be risky."""
    if not global_token:
        get_token()
        return
    if time.monotonic() - token_issued_at > TOKEN_REFRESH_AFTER_SECONDS:
        logging.info('Wiz token is stale - refreshing mid-run')
        get_token()


def _retry_delay(retries: int, response=None) -> float:
    """Exponential backoff with jitter, honouring Retry-After when present."""
    if response is not None:
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                return min(float(retry_after), 120.0)
            except ValueError:
                pass
    return min(RETRY_BASE_SECONDS * (2 ** retries), 60.0) + random.uniform(0, 1)


def query_wiz(graphql_query: str, variables: dict) -> dict:
    """Send a GraphQL query to Wiz with token refresh and backoff."""
    _maybe_refresh_token()
    retries = 0
    reauthed = False
    while True:
        response = requests.post(
            WIZ_API_ENDPOINT,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {global_token}',
                'User-Agent': 'Paramify-WizIntegration-0.2',
            },
            json={'query': graphql_query, 'variables': variables},
            timeout=(10, 120),
        )
        code = response.status_code

        # A 401 partway through a long pull is almost always an expired
        # token, not bad credentials. Re-auth once before giving up.
        if code == 401 and not reauthed:
            logging.warning('Wiz returned 401 - re-authenticating once')
            reauthed = True
            get_token()
            continue
        if code in (401, 403):
            raise Exception(f'Wiz auth error [{code}] - {response.text}')
        if code == 404:
            raise Exception(
                f'Wiz endpoint not found [{code}] - check WIZ_API_ENDPOINT'
            )

        if code == 200:
            payload = response.json()
            errors = payload.get('errors')
            data = payload.get('data')

            # Surface GraphQL errors instead of swallowing them. A bad
            # filter field shows up here, not as an HTTP status.
            if errors:
                messages = '; '.join(
                    str(e.get('message', e)) for e in errors
                )
                if not data or data.get('vulnerabilityFindings') is None:
                    if 'filterBy' in messages or 'Filters' in messages:
                        raise WizFilterRejected(messages)
                    raise Exception(f'Wiz GraphQL error: {messages}')
                logging.warning('Wiz returned partial errors: %s', messages)

            if not data or data.get('vulnerabilityFindings') is None:
                raise Exception(
                    f'Wiz returned no vulnerabilityFindings. '
                    f'errors={errors} data={data}'
                )
            return data

        if retries >= MAX_RETRIES_FOR_QUERY:
            raise Exception(
                f'Max retries exceeded. Last error [{code}] - {response.text}'
            )
        delay = _retry_delay(retries, response)
        logging.info('Wiz query failed [%d], retrying in %.1fs (attempt %d/%d)',
                     code, delay, retries + 1, MAX_RETRIES_FOR_QUERY)
        time.sleep(delay)
        retries += 1


# ============================================================
# Delta filter validation
# ============================================================
def build_delta_filter(last_successful_run: str) -> dict:
    filter_by = dict(FILTER_CONFIG)
    filter_by[DELTA_FIELD] = {'after': last_successful_run}
    return filter_by


def probe_filter(filter_by: dict) -> bool:
    """Return True if Wiz accepts this filter, False if it rejects it."""
    try:
        data = query_wiz(FILTER_PROBE_QUERY,
                         {'filterBy': filter_by, 'first': 1})
    except WizFilterRejected as e:
        logging.warning('Wiz rejected the delta filter field "%s": %s',
                        DELTA_FIELD, e)
        return False
    total = (data.get('vulnerabilityFindings') or {}).get('totalCount')
    logging.info('Delta filter accepted (totalCount=%s)', total)
    return True


# ============================================================
# Vulnerability fetching with pagination
# ============================================================
def fetch_vulnerabilities(last_successful_run: str = None) -> tuple:
    """
    Fetch findings via GraphQL pagination and write them to CSV.
    Returns (row_count, mode_label).
    """
    mode_label = 'full'
    filter_by = dict(FILTER_CONFIG)

    if last_successful_run:
        candidate = build_delta_filter(last_successful_run)
        if probe_filter(candidate):
            filter_by = candidate
            mode_label = 'delta'
            logging.info('Delta mode: %s after %s',
                         DELTA_FIELD, last_successful_run)
        else:
            logging.warning(
                'Falling back to a FULL fetch because the delta filter was '
                'rejected. Set WIZ_VULN_DELTA_FIELD to a field your tenant '
                'supports, or leave delta mode off.'
            )
    else:
        logging.info('Full mode: fetching ALL vulnerability findings')

    after_cursor = None
    page_num = 0
    total_rows = 0
    total_count = None
    started = time.monotonic()

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        while True:
            page_num += 1
            variables = {'filterBy': filter_by, 'first': PAGE_SIZE}
            if after_cursor:
                variables['after'] = after_cursor

            response = query_wiz(VULNERABILITIES_QUERY, variables)
            findings = response['vulnerabilityFindings']

            if total_count is None:
                total_count = findings.get('totalCount')
                logging.info('Wiz reports totalCount=%s at page size %d',
                             total_count, PAGE_SIZE)

            nodes = findings.get('nodes') or []
            page_info = findings.get('pageInfo') or {}

            for node in nodes:
                writer.writerow(flatten_vulnerability(node))
                total_rows += 1

            elapsed = time.monotonic() - started
            logging.info('Page %d: %d rows (total %d%s) [%.0fs elapsed]',
                         page_num, len(nodes), total_rows,
                         f' of {total_count}' if total_count else '',
                         elapsed)

            if not page_info.get('hasNextPage'):
                logging.info('No more pages - pagination complete')
                break
            after_cursor = page_info.get('endCursor')
            if not after_cursor:
                logging.warning('hasNextPage=true but no endCursor - stopping')
                break

    size_mb = OUTPUT_CSV.stat().st_size / 1024 / 1024
    logging.info('Wrote %s (%d rows, %.2f MB) across %d pages in %.0fs',
                 OUTPUT_CSV, total_rows, size_mb, page_num,
                 time.monotonic() - started)

    if total_count is not None and total_rows < total_count:
        logging.warning(
            'Row count (%d) is below Wiz totalCount (%d). Pagination may '
            'have been cut short.', total_rows, total_count
        )

    return total_rows, mode_label


def flatten_vulnerability(node: dict) -> dict:
    """Flatten a vulnerabilityFinding node into a flat CSV row dict."""
    analytics = node.get('relatedIssueAnalytics') or {}
    asset = node.get('vulnerableAsset') or {}
    ip_addresses = asset.get('ipAddresses') or []
    tags = asset.get('tags') or {}

    def num(value):
        return value if value is not None else ''

    return {
        'ID': node.get('id', ''),
        'Name': node.get('name', ''),
        'CVE Description': node.get('CVEDescription') or '',
        'CVSS Severity': node.get('CVSSSeverity') or '',
        'Score': num(node.get('score')),
        'Severity': node.get('severity') or '',
        'NVD Severity': node.get('nvdSeverity') or '',
        'Status': node.get('status') or '',
        'Has Exploit': node.get('hasExploit', ''),
        'Has Fix': node.get('hasFix', ''),
        'Has CISA KEV Exploit': node.get('hasCisaKevExploit', ''),
        'First Detected At': node.get('firstDetectedAt') or '',
        'Last Detected At': node.get('lastDetectedAt') or '',
        'Resolved At': node.get('resolvedAt') or '',
        'Description': node.get('description') or '',
        'Remediation': node.get('remediation') or '',
        'Detailed Name': node.get('detailedName') or '',
        'Version': node.get('version') or '',
        'Fixed Version': node.get('fixedVersion') or '',
        'Detection Method': node.get('detectionMethod') or '',
        'Link': node.get('link') or '',
        'Portal URL': node.get('portalUrl') or '',
        'EPSS Severity': node.get('epssSeverity') or '',
        'EPSS Percentile': num(node.get('epssPercentile')),
        'EPSS Probability': num(node.get('epssProbability')),
        'Related Issue Count': num(analytics.get('issueCount')),
        'Related Critical Issues': num(analytics.get('criticalSeverityCount')),
        'Related High Issues': num(analytics.get('highSeverityCount')),
        'Related Medium Issues': num(analytics.get('mediumSeverityCount')),
        'Related Low Issues': num(analytics.get('lowSeverityCount')),
        'Asset ID': asset.get('id') or '',
        'Asset Type': asset.get('type') or '',
        'Asset Name': asset.get('name') or '',
        'Asset Region': asset.get('region') or '',
        'Asset Provider ID': asset.get('providerUniqueId') or '',
        'Asset Cloud Platform': asset.get('cloudPlatform') or '',
        'Asset Status': asset.get('status') or '',
        'Asset Subscription Name': asset.get('subscriptionName') or '',
        'Asset Subscription External ID': asset.get('subscriptionExternalId') or '',
        'Asset Tags': json.dumps(tags) if tags else '',
        'Asset Has Wide Internet Exposure': asset.get('hasWideInternetExposure', ''),
        'Asset Operating System': asset.get('operatingSystem') or '',
        'Asset IP Addresses': ', '.join(ip_addresses) if ip_addresses else '',
    }


# ============================================================
# Paramify upload
# ============================================================
def upload_to_paramify(csv_path: Path, mode_label: str = 'full') -> dict:
    """Upload the CSV as an artifact to a Paramify assessment intake."""
    today = datetime.now(timezone.utc)
    logging.info('Uploading %s to Paramify (%s mode)', csv_path, mode_label)
    logging.info('  API:        %s', PARAMIFY_API_ISSUES_BASE_URL)
    logging.info('  Assessment: %s', WIZ_VULN_PARAMIFY_ASSESSMENT_ID)
    with open(csv_path, 'rb') as f:
        response = requests.post(
            f"{PARAMIFY_API_ISSUES_BASE_URL}/assessment/"
            f"{WIZ_VULN_PARAMIFY_ASSESSMENT_ID}/intake",
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
                    "note": (
                        "Automated upload via wiz-vulnerabilities-fetcher "
                        f"(mode={mode_label})"
                    ),
                    "effectiveDate": today.isoformat(),
                }),
            },
            timeout=900,
        )
    if response.status_code >= 400:
        # The intake endpoint returns a structured error body; log it
        # before raising so failures are diagnosable from the run log.
        logging.error('Paramify intake failed [%d]: %s',
                      response.status_code, response.text[:2000])
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
        stream=sys.stdout,
    )
    logging.info('=' * 60)
    logging.info('Wiz Vulnerabilities to Paramify Fetcher')
    logging.info('  DELTA_MODE:  %s (from %s)', DELTA_MODE, DELTA_SOURCE)
    logging.info('  DELTA_FIELD: %s', DELTA_FIELD)
    logging.info('  PAGE_SIZE:   %d', PAGE_SIZE)
    logging.info('  EVIDENCE_DIR:%s', output_dir)
    logging.info('=' * 60)

    get_token()

    current_hash = compute_config_hash({
        'filter': FILTER_CONFIG,
        'page_size': PAGE_SIZE,
        'delta_field': DELTA_FIELD,
    })
    logging.info('Current config hash: %s', current_hash)

    state = load_state()
    last_successful_run = None
    if DELTA_MODE:
        if not state:
            logging.info('Delta mode on but no state yet - full fetch')
        elif state.get('config_hash') != current_hash:
            logging.info('Config changed (was %s, now %s) - full fetch',
                         state.get('config_hash'), current_hash)
        else:
            last_successful_run = state.get('last_successful_run')
            if not last_successful_run:
                logging.info('No last_successful_run in state - full fetch')
    else:
        logging.info('Delta mode off - forcing full fetch, ignoring state')

    row_count, mode_label = fetch_vulnerabilities(
        last_successful_run=last_successful_run
    )

    new_successful_run = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    if row_count == 0:
        # A zero-change cycle is itself evidence: "we queried Wiz and nothing
        # changed". Skipping the upload leaves an unexplained gap in the
        # continuous-monitoring record, and makes "nothing changed"
        # indistinguishable from "the fetcher silently failed". Upload the
        # header-only CSV so the cycle is on the record either way.
        logging.info('0 rows - uploading header-only CSV as a no-change record')
        mode_label = '%s, no changes' % mode_label

    artifact = upload_to_paramify(OUTPUT_CSV, mode_label)

    # Keep the CSV alongside the run so the artifact that was uploaded is
    # reproducible from the evidence directory.
    try:
        shutil.copy2(OUTPUT_CSV, EVIDENCE_CSV)
        logging.info('Copied CSV to %s', EVIDENCE_CSV)
    except Exception as e:
        logging.warning('Could not copy CSV to evidence dir: %s', e)

    # Only advance the delta watermark when delta mode is actually on.
    # Advancing it during full runs means the first delta run after
    # flipping the flag silently starts from "now" and returns nothing.
    if DELTA_MODE:
        save_state(current_hash, last_successful_run=new_successful_run)
        logging.info('Updated last_successful_run: %s', new_successful_run)
    else:
        save_state(current_hash)
        logging.info('Delta mode off - last_successful_run left unchanged')

    summary = {
        'fetcher': 'wiz_vulnerabilities_findings',
        'mode': mode_label,
        'delta_mode_setting': DELTA_MODE,
        'delta_field': DELTA_FIELD,
        'page_size': PAGE_SIZE,
        'artifact_id': artifact.get('id'),
        'artifact_title': artifact.get('title'),
        'csv_path': str(EVIDENCE_CSV),
        'row_count': row_count,
        'timestamp': new_successful_run,
    }
    with open(RUN_SUMMARY, 'w') as f:
        json.dump(summary, f, indent=2)
    logging.info('Wrote run summary to %s', RUN_SUMMARY)

    logging.info('=' * 60)
    logging.info('All done! %d rows uploaded as %s', row_count, mode_label)
    logging.info('=' * 60)


if __name__ == '__main__':
    main()
