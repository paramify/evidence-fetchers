#!/usr/bin/env python3
"""
# Helper script for Rippling Device Inventory
# Evidence for company-managed device inventory from Rippling MDM

Queries the Rippling API to retrieve the full device inventory managed
through Rippling MDM. Includes laptops, desktops, and mobile devices.

NOTE: Device inventory requires the Rippling MDM add-on to be enabled
for your account. If you get a 404, confirm MDM is active in your
Rippling subscription.

API reference: https://developer.rippling.com/documentation/rest-api
Endpoint: GET /platform/api/devices  (falls back to /v2/devices if needed)

Environment variables required:
- RIPPLING_API_TOKEN   Bearer token (from Rippling Developer Portal)

Optional:
- RIPPLING_BASE_URL    Defaults to https://api.rippling.com
- RIPPLING_PAGE_SIZE   Records per page, defaults to 100

Usage:
    python rippling_devices.py [--output-dir <path>]

Output:
    rippling_devices.json  under the evidence output directory
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common.env_loader import parse_fetcher_args
except ModuleNotFoundError:
    # Standalone fallback - works outside the evidence-fetchers repo
    from dotenv import load_dotenv
    def parse_fetcher_args():
        for p in [Path(__file__).parent] + list(Path(__file__).parents):
            if (p / ".env").exists():
                load_dotenv(p / ".env", override=False)
                break
        args = sys.argv[1:]
        output_dir = "./evidence"
        i = 0
        while i < len(args):
            if args[i] == "--output-dir" and i + 1 < len(args):
                output_dir = args[i + 1]
            i += 1
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return output_dir, "", ""

BASE_URL = os.getenv("RIPPLING_BASE_URL", "https://api.rippling.com").rstrip("/")
PAGE_SIZE = int(os.getenv("RIPPLING_PAGE_SIZE", "100"))

# Try these endpoints in order - Rippling has had the device endpoint in multiple locations
DEVICE_ENDPOINTS = [
    "/platform/api/devices",
    "/v2/devices",
]


def get_token() -> str:
    token = os.getenv("RIPPLING_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "RIPPLING_API_TOKEN is not set. "
            "Set it in your .env file or environment before running this script."
        )
    return token


def rippling_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Make a single GET request to the Rippling API."""
    url = f"{BASE_URL}{path}"
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {get_token()}",
        },
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_records(payload: Any) -> List[Dict]:
    """Handle both list responses and wrapped dict responses."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "devices", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def find_working_endpoint() -> Tuple[str, Any]:
    """Try each known device endpoint and return the first that responds."""
    for endpoint in DEVICE_ENDPOINTS:
        try:
            print(f"Trying endpoint: {BASE_URL}{endpoint} ...")
            payload = rippling_get(endpoint, params={"limit": 1, "offset": 0})
            print(f"  Endpoint works: {endpoint}")
            return endpoint, payload
        except requests.exceptions.HTTPError as e:
            print(f"  {endpoint} -> HTTP {e.response.status_code}: {e.response.text[:100]}")
        except Exception as e:
            print(f"  {endpoint} -> {e}")

    raise RuntimeError(
        "No working device endpoint found. "
        "Confirm that Rippling MDM is enabled for your account and that "
        "RIPPLING_API_TOKEN has the required device scopes."
    )


def fetch_devices() -> Tuple[str, List[Dict]]:
    """Fetch all devices using offset-based pagination."""
    endpoint, first_payload = find_working_endpoint()

    results: List[Dict] = []
    offset = 0

    # Process first page already fetched during endpoint detection
    first_page = extract_records(first_payload)
    if first_page:
        results.extend(first_page)
        print(f"  Page offset=0: got {len(first_page)} records")
        if len(first_page) < PAGE_SIZE:
            return endpoint, results
        offset = PAGE_SIZE

    # Fetch remaining pages
    while True:
        payload = rippling_get(endpoint, params={"limit": PAGE_SIZE, "offset": offset})
        page = extract_records(payload)
        results.extend(page)
        print(f"  Page offset={offset}: got {len(page)} records (total so far: {len(results)})")

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return endpoint, results


def main() -> None:
    output_dir, _profile, _region = parse_fetcher_args()

    evidence_dir = Path(output_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    endpoint, devices = fetch_devices()

    out_path = evidence_dir / "rippling_devices.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": "rippling",
                "endpoint": endpoint,
                "mode": "device_inventory",
                "count": len(devices),
                "results": devices,
            },
            f,
            indent=2,
        )

    print(f"\n\u2713 Saved {len(devices)} devices -> {out_path}")


if __name__ == "__main__":
    main()
