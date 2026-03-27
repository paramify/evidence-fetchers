#!/usr/bin/env python3
"""
Quick connectivity and token test for Rippling API.
Run this first to confirm your RIPPLING_API_TOKEN is valid before
running the full fetcher scripts.

Usage:
    python test_connection.py
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from project root (walk up from this file)
for parent in [Path(__file__).parent] + list(Path(__file__).parents):
    env_file = parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)
        print(f"Loaded .env from: {env_file}")
        break

BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://api.rippling.com").rstrip("/")
TOKEN = os.getenv("RIPPLING_API_TOKEN", "").strip()

print(f"\nBase URL : {BASE_URL}")
print(f"Token    : {'SET (' + TOKEN[:8] + '...)' if TOKEN else 'NOT SET \u2717'}\n")

if not TOKEN:
    print("\u2717 RIPPLING_API_TOKEN is not set. Add it to your .env file.")
    sys.exit(1)

headers = {"Accept": "application/json", "Authorization": f"Bearer {TOKEN}"}

checks = [
    ("GET companies/current", f"{BASE_URL}/platform/api/companies/current"),
    ("GET employees (1 record)", f"{BASE_URL}/platform/api/employees"),
    ("GET employees incl. terminated (1 record)", f"{BASE_URL}/platform/api/employees/include_terminated"),
    ("GET devices /platform/api/devices", f"{BASE_URL}/platform/api/devices"),
    ("GET devices /v2/devices", f"{BASE_URL}/v2/devices"),
]

all_ok = True
for label, url in checks:
    try:
        resp = requests.get(url, headers=headers, params={"limit": 1, "offset": 0}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            count = len(data) if isinstance(data, list) else "object"
            print(f"  \u2713 {label}  \u2192  HTTP 200  (records: {count})")
        else:
            print(f"  \u2717 {label}  \u2192  HTTP {resp.status_code}: {resp.text[:120]}")
            all_ok = False
    except Exception as e:
        print(f"  \u2717 {label}  \u2192  Error: {e}")
        all_ok = False

print()
if all_ok:
    print("\u2713 All checks passed \u2014 ready to run fetchers.")
else:
    print("Some checks failed \u2014 see above. Employees/companies failing = token issue or wrong plan tier.")
    print("Devices failing = MDM add-on may not be enabled (that's OK for now).")
