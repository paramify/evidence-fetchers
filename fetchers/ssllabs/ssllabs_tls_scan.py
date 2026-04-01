#!/usr/bin/env python3
"""
SSL Labs TLS/SSL Certificate Analysis

Purpose: Run Qualys SSL Labs API v4 scans against configured hosts and collect
TLS/SSL grade, certificate validity, and vulnerability evidence.

SSL Labs API:
    https://api.ssllabs.com/api/v4/analyze

Expected Outcome:
    All scanned hosts should receive a grade of A or A+ with no critical
    vulnerabilities, valid non-expired certificates, and no insecure protocols
    (TLS 1.0, TLS 1.1, SSL 3.0, SSL 2.0).

Configuration:
    All configuration is loaded from environment variables (via .env file).
    See .env.example for available settings.

    Required:
        SSLLABS_EMAIL  - Registered Qualys SSL Labs API v4 email
        SSLLABS_HOSTS  - Comma-separated list of hostnames to scan

    Can be run standalone (zero args) or with optional overrides:
        python ssllabs_tls_scan.py
        python ssllabs_tls_scan.py --output-dir /tmp/evidence
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.env_loader import parse_fetcher_args

API_V4_URL = "https://api.ssllabs.com/api/v4/analyze"
POLL_INTERVAL_SECS = 30
MAX_POLL_ATTEMPTS = 40  # ~20 minutes max per host
# Retries when SSL Labs returns 429 / 529 / 503 on the initial analyze request (public API capacity).
INITIAL_REQUEST_CAPACITY_RETRIES = 3
INITIAL_REQUEST_BACKOFF_SECS = (45, 90, 180)

FORWARD_SECRECY_LABELS = {
    1: "With some browsers (WEAK)",
    2: "With modern browsers",
    4: "Yes (with most browsers) ROBUST",
}


def current_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _api_error_messages_from_json(data: Any) -> Optional[str]:
    """Join Qualys API `errors[].message` strings when present."""
    if not isinstance(data, dict):
        return None
    errs = data.get("errors")
    if not isinstance(errs, list):
        return None
    parts: List[str] = []
    for item in errs:
        if isinstance(item, dict) and item.get("message"):
            parts.append(str(item["message"]))
    return " ".join(parts) if parts else None


def describe_ssl_labs_http_error(status_code: int, response: requests.Response) -> str:
    """Human-readable explanation for orchestrator logs and evidence JSON."""
    api_msg = None
    try:
        api_msg = _api_error_messages_from_json(response.json())
    except (json.JSONDecodeError, ValueError):
        pass
    snippet = (response.text or "").strip()[:400]

    if status_code == 529:
        core = (
            "Qualys SSL Labs returned HTTP 529 (service at capacity). Their public scan API is temporarily overloaded; "
            "this is not caused by your certificates or credentials."
        )
        return f"{core} {api_msg}".strip() if api_msg else core
    if status_code == 429:
        core = (
            "HTTP 429 from SSL Labs (too many requests). Wait several minutes, reduce how many hosts you scan at once, "
            "or run again later."
        )
        return f"{core} Details: {api_msg}" if api_msg else core
    if status_code == 503:
        core = "HTTP 503 from SSL Labs (service unavailable). Try again later."
        return f"{core} {api_msg}".strip() if api_msg else core

    if api_msg:
        return f"HTTP {status_code}: {api_msg}"
    if snippet:
        return f"HTTP {status_code}: {snippet}"
    return f"HTTP {status_code} (no response body)"


def _print_capacity_guidance(host: str, status_code: int, message: str) -> None:
    """Use stderr so run_fetchers shows this when a run fails (it surfaces stderr)."""
    print(f"\n  [{host}] SSL Labs API: HTTP {status_code}", file=sys.stderr)
    print(f"    {message}", file=sys.stderr)
    print(
        "    Tip: Retry after a few minutes, or scan fewer hosts per run.",
        file=sys.stderr,
    )


def analyze_host(host: str, email: str) -> Dict[str, Any]:
    """Start and poll an SSL Labs scan for a single host until complete."""
    headers = {"email": email}

    # Kick off a fresh scan
    params = {
        "host": host,
        "publish": "off",
        "startNew": "on",
        "all": "done",
        "ignoreMismatch": "on",
    }
    print(f"  Starting scan for {host}...")

    response: Optional[requests.Response] = None
    for attempt in range(INITIAL_REQUEST_CAPACITY_RETRIES + 1):
        try:
            response = requests.get(API_V4_URL, params=params, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            return {"status": "error", "host": host, "message": str(e)}

        if response.status_code in (200, 400):
            break

        if response.status_code in (429, 529, 503) and attempt < INITIAL_REQUEST_CAPACITY_RETRIES:
            wait = INITIAL_REQUEST_BACKOFF_SECS[
                min(attempt, len(INITIAL_REQUEST_BACKOFF_SECS) - 1)
            ]
            print(
                f"  {host}: temporary API limit (HTTP {response.status_code}); "
                f"waiting {wait}s before retry {attempt + 1}/{INITIAL_REQUEST_CAPACITY_RETRIES}...",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue

        msg = describe_ssl_labs_http_error(response.status_code, response)
        _print_capacity_guidance(host, response.status_code, msg)
        return {
            "status": "error",
            "host": host,
            "message": msg,
            "http_status": response.status_code,
        }

    assert response is not None
    data = response.json()
    if "errors" in data:
        api_msg = _api_error_messages_from_json(data) or str(data["errors"])
        if response.status_code == 400:
            _print_capacity_guidance(host, response.status_code, api_msg)
        return {
            "status": "error",
            "host": host,
            "message": api_msg,
            "http_status": response.status_code,
        }

    # Poll (drop startNew so we don't restart on each check)
    params.pop("startNew")
    attempts = 0

    while data.get("status") not in ("READY", "ERROR") and attempts < MAX_POLL_ATTEMPTS:
        print(f"  {host}: status={data.get('status', 'UNKNOWN')}, waiting {POLL_INTERVAL_SECS}s...")
        time.sleep(POLL_INTERVAL_SECS)
        attempts += 1

        try:
            response = requests.get(API_V4_URL, params=params, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            return {"status": "error", "host": host, "message": str(e)}

        if response.status_code in (429, 529, 503):
            brief = describe_ssl_labs_http_error(response.status_code, response)
            if len(brief) > 160:
                brief = brief[:157] + "..."
            print(
                f"  {host}: poll hit HTTP {response.status_code}; "
                f"waiting {POLL_INTERVAL_SECS}s — {brief}",
                file=sys.stderr,
            )
            time.sleep(POLL_INTERVAL_SECS)
            continue

        if response.status_code != 200:
            msg = describe_ssl_labs_http_error(response.status_code, response)
            _print_capacity_guidance(host, response.status_code, msg)
            return {
                "status": "error",
                "host": host,
                "message": msg,
                "http_status": response.status_code,
            }

        data = response.json()
        if "errors" in data:
            api_msg = _api_error_messages_from_json(data) or str(data["errors"])
            return {
                "status": "error",
                "host": host,
                "message": api_msg,
                "http_status": response.status_code,
            }

    if data.get("status") != "READY":
        return {"status": "timeout", "host": host, "message": "Scan did not complete in time"}

    return data


def summarize_endpoint(ep: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key security fields from an endpoint result."""
    details = ep.get("details", {})
    supported_protocols = {
        f"{p['name']} {p['version']}" for p in details.get("protocols", [])
    }
    fs_val = details.get("forwardSecrecy", 0)

    return {
        "ip": ep.get("ipAddress"),
        "grade": ep.get("grade"),
        "has_warnings": ep.get("hasWarnings", False),
        "forward_secrecy": FORWARD_SECRECY_LABELS.get(fs_val, str(fs_val)),
        "vulnerabilities": {
            "heartbleed": details.get("heartbleed", False),
            "poodle_ssl": details.get("poodle", False),
            "poodle_tls": details.get("poodleTls", 1) != 1,
            "beast": details.get("vulnBeast", False),
            "freak": details.get("freak", False),
            "drown": details.get("drownVulnerable", False),
            "open_ssl_ccs": details.get("openSslCcs", 1) != 1,
            "lucky_minus20": details.get("openSSLLuckyMinus20", 1) != 1,
        },
        "rc4": {
            "supports_rc4": details.get("supportsRc4", False),
            "rc4_with_modern": details.get("rc4WithModern", False),
            "rc4_only": details.get("rc4Only", False),
        },
        "protocols": {
            "tls_1_3": "TLS 1.3" in supported_protocols,
            "tls_1_2": "TLS 1.2" in supported_protocols,
            "tls_1_1_insecure": "TLS 1.1" in supported_protocols,
            "tls_1_0_insecure": "TLS 1.0" in supported_protocols,
            "ssl_3_0_insecure": "SSL 3.0" in supported_protocols,
            "ssl_2_0_insecure": "SSL 2.0" in supported_protocols,
        },
    }


def cert_expiry_date(data: Dict[str, Any]) -> Optional[str]:
    """Extract certificate expiry from scan result."""
    certs = data.get("certs", [])
    if not certs:
        return None
    not_after = certs[0].get("notAfter")
    if not not_after:
        return None
    # SSL Labs returns 13-digit epoch (milliseconds)
    return datetime.fromtimestamp(float(str(not_after)[:10]), timezone.utc).strftime("%Y-%m-%d")


def endpoint_passes(ep_summary: Dict[str, Any]) -> bool:
    """Return True if an endpoint meets minimum security requirements."""
    if ep_summary.get("grade", "?") not in ("A", "A+", "A-"):
        return False
    vulns = ep_summary.get("vulnerabilities", {})
    if any(vulns.values()):
        return False
    protocols = ep_summary.get("protocols", {})
    if protocols.get("tls_1_0_insecure") or protocols.get("ssl_3_0_insecure") or protocols.get("ssl_2_0_insecure"):
        return False
    return True


def run_scan(hosts: List[str], email: str, output_dir: str) -> Dict[str, Any]:
    """Scan all hosts and return combined structured results."""
    host_results = []
    all_pass = True

    for host in hosts:
        raw = analyze_host(host, email)

        if raw.get("status") in ("error", "timeout"):
            print(f"  {host}: FAILED - {raw.get('message')}")
            host_results.append({"host": host, "status": raw["status"], "message": raw.get("message")})
            all_pass = False
            continue

        expiry = cert_expiry_date(raw)
        endpoints = [summarize_endpoint(ep) for ep in raw.get("endpoints", [])]
        grades = [ep["grade"] for ep in endpoints if ep.get("grade")]
        overall_grade = sorted(grades)[0] if grades else "?"
        host_pass = all(endpoint_passes(ep) for ep in endpoints)

        if not host_pass:
            all_pass = False

        print(f"  {host}: grade={overall_grade}, cert_expiry={expiry}, pass={host_pass}")

        # Save per-host raw JSON
        host_file = Path(output_dir) / f"ssllabs_{host}.json"
        with open(host_file, "w") as f:
            json.dump(raw, f, indent=2)

        host_results.append({
            "host": host,
            "status": "success",
            "pass": host_pass,
            "overall_grade": overall_grade,
            "cert_expiry": expiry,
            "endpoints": endpoints,
        })

    return {
        "status": "success" if all_pass else "issues_found",
        "hosts_scanned": len(hosts),
        "results": host_results,
        "analysis": {
            "all_hosts_pass": all_pass,
            "grades": {r["host"]: r.get("overall_grade") for r in host_results},
            "cert_expiries": {r["host"]: r.get("cert_expiry") for r in host_results},
            "failing_hosts": [r["host"] for r in host_results if not r.get("pass", False)],
        },
        "retrieved_at": current_timestamp(),
    }


def main() -> int:
    output_dir, _profile, _region = parse_fetcher_args()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        email = get_env("SSLLABS_EMAIL")
        hosts_raw = get_env("SSLLABS_HOSTS")
    except RuntimeError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    hosts = [h.strip() for h in hosts_raw.split(",") if h.strip()]
    if not hosts:
        print("Error: SSLLABS_HOSTS is empty", file=sys.stderr)
        return 1

    print(f"Scanning {len(hosts)} host(s) via SSL Labs API v4...")
    result = run_scan(hosts, email, output_dir)

    output_json = Path(output_dir) / "ssllabs_tls_scan.json"
    with open(output_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\nOverall status: {result['status']}")
    print(f"Results saved to: {output_json}")

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
