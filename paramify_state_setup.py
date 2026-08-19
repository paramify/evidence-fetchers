"""
Create (or find) the two Evidence Sets that hold Wiz fetcher state.

One set per fetcher, so that reading state is "the newest artifact in my set"
and pruning one fetcher's history can never touch the other's.

    python3 paramify_state_setup.py            # dry run, shows what it would do
    python3 paramify_state_setup.py --create   # actually create them
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / '.env', override=False)

BASE = os.environ['PARAMIFY_API_ISSUES_BASE_URL'].rstrip('/')
TOKEN = os.environ['PARAMIFY_API_ISSUES_TOKEN']
H = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json'}

_NOTE = ('Machine state for the Wiz evidence fetchers. NOT audit evidence - '
         'kept in its own set so it never appears beside artifacts an '
         'assessor reviews. One artifact per run; the newest is authoritative.')

SETS = [
    {'referenceId': 'EVD-WIZ-VULN-STATE',
     'name': 'Wiz Vulnerability Fetcher State',
     'description': _NOTE + ' Holds wiz_vulnerabilities_state.json '
                            '(delta watermark + config hash).',
     'env': 'WIZ_VULN_STATE_EVIDENCE_ID'},
    {'referenceId': 'EVD-WIZ-ISSUES-STATE',
     'name': 'Wiz Issues Fetcher State',
     'description': _NOTE + ' Holds wiz_issues_state.json (delta watermark, '
                            'config hash, and the Wiz report_id - losing that '
                            'id makes the next run create a second orphaned '
                            'report inside Wiz).',
     'env': 'WIZ_ISSUES_STATE_EVIDENCE_ID'},
]

CREATE = '--create' in sys.argv

print('=' * 70)
print('Wiz fetcher state - Evidence Set setup')
print('=' * 70)
print('API  :', BASE)
print('mode :', 'CREATE' if CREATE else 'dry run (nothing will be written)')
print()

r = requests.get(f'{BASE}/evidence', headers=H, timeout=60)
r.raise_for_status()
existing = r.json().get('evidences', [])
print(f'Existing evidence sets: {len(existing)}')
print()

env_lines = ['WIZ_STATE_BACKEND=paramify']
failed = False

for spec in SETS:
    print('-' * 70)
    print(spec['name'], f"({spec['referenceId']})")
    match = [e for e in existing
             if e.get('referenceId') == spec['referenceId']
             or e.get('name') == spec['name']]
    if match:
        e = match[0]
        print(f"  already exists  id={e.get('id')}  "
              f"artifacts={e.get('artifactCount')}")
        env_lines.append(f"{spec['env']}={e.get('id')}")
        continue

    if not CREATE:
        print('  would create:')
        print('   ', json.dumps({k: spec[k] for k in
                                 ('referenceId', 'name', 'description')},
                                ensure_ascii=False)[:200] + '...')
        env_lines.append(f"{spec['env']}=<created on --create>")
        continue

    rr = requests.post(
        f'{BASE}/evidence',
        headers={**H, 'Content-Type': 'application/json'},
        json={k: spec[k] for k in ('referenceId', 'name', 'description')},
        timeout=60)
    if rr.status_code != 200:
        print(f'  CREATE FAILED HTTP {rr.status_code}')
        print('  ' + rr.text[:400])
        failed = True
        continue
    e = rr.json()
    print(f"  created  id={e.get('id')}")
    env_lines.append(f"{spec['env']}={e.get('id')}")

print('-' * 70)
print()
print('Add these to .env:')
print()
for line in env_lines:
    print('  ' + line)
print('  # WIZ_STATE_KEEP=20   # state artifacts retained per set')
print()
if not CREATE:
    print('Re-run with --create to actually create the sets.')
sys.exit(1 if failed else 0)
