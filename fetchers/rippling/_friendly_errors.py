"""
Shared error-handling helpers for the Rippling fetcher scripts.

The Rippling, Okta, and KnowBe4 APIs return HTTP 401/403/404 when the API
token is missing required scopes, has been revoked, or when an add-on (e.g.
Rippling MDM) is not enabled on the account. Out of the box `requests` would
raise an HTTPError, leading to a noisy traceback in the orchestrator log.

This module centralizes the "downgrade an HTTP/network error into a clean,
actionable one-line message + exit code" pattern so every rippling script
behaves consistently:

    from _friendly_errors import run_with_friendly_errors

    if __name__ == "__main__":
        run_with_friendly_errors(main, primary_service="Rippling")
"""

from __future__ import annotations

import sys
from typing import Callable, Iterable, NoReturn, Optional
from urllib.parse import urlparse

import requests


PERMISSION_HINTS = {
    "Rippling": (
        "In the Rippling Developer Portal, confirm the API token has the "
        "required scopes (e.g. 'employees:read', 'devices:read') and that "
        "the relevant add-ons (e.g. MDM for /devices) are enabled on the "
        "account. See fetchers/rippling/API_KEY_SETUP.md for details."
    ),
    "Okta": (
        "Confirm OKTA_API_TOKEN is a valid SSWS token and OKTA_ORG_URL is "
        "correct. The token must have permission to list users."
    ),
    "KnowBe4": (
        "Confirm KNOWBE4_API_KEY is valid and KNOWBE4_BASE_URL matches your "
        "region (e.g. https://us.api.knowbe4.com). The Reporting API must "
        "be enabled on your subscription."
    ),
}


class FriendlyApiError(RuntimeError):
    """Wraps an API failure with a clean, single-line message.

    When raised inside main(), `run_with_friendly_errors` catches it and
    prints the message without a traceback before exiting non-zero.
    """


def _host_matches(host: str, domain: str) -> bool:
    """Return True if `host` equals `domain` or is a subdomain of it.

    Compares against the parsed hostname (not a substring of the full URL),
    so an attacker-controlled URL like https://evil.com/?fake=rippling.com
    will not be misclassified as a known service.
    """
    return host == domain or host.endswith(f".{domain}")


def _service_for_url(url: str) -> str:
    if not url:
        return ""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    if not host:
        return ""
    if _host_matches(host, "rippling.com"):
        return "Rippling"
    if _host_matches(host, "knowbe4.com"):
        return "KnowBe4"
    if _host_matches(host, "okta.com") or _host_matches(host, "oktapreview.com"):
        return "Okta"
    return ""


def format_http_error(
    exc: requests.HTTPError, fallback_service: Optional[str] = None
) -> str:
    """Build a single-line, user-actionable message from an HTTPError."""
    resp = exc.response
    status = resp.status_code if resp is not None else None
    url = resp.url if resp is not None else ""
    service = _service_for_url(url) or fallback_service or "API"

    if status == 401:
        reason = (
            f"{service} returned HTTP 401 Unauthorized. The API token is "
            f"missing, invalid, or expired."
        )
    elif status == 403:
        reason = (
            f"{service} returned HTTP 403 Forbidden. The API token does not "
            f"have the scopes/permissions required for this endpoint."
        )
    elif status == 404:
        reason = (
            f"{service} returned HTTP 404 Not Found at {url}. The endpoint "
            f"may not be enabled on this account (e.g. an add-on is required)."
        )
    elif status == 429:
        reason = (
            f"{service} returned HTTP 429 Too Many Requests. Wait a bit and "
            f"re-run, or lower the page size."
        )
    elif status is not None and 500 <= status < 600:
        reason = (
            f"{service} returned HTTP {status} (server error) at {url}. The "
            f"API is temporarily unavailable; re-run later."
        )
    else:
        status_label = status if status is not None else "?"
        reason = f"{service} returned HTTP {status_label} at {url}."

    hint = PERMISSION_HINTS.get(service)
    if hint and status in (401, 403, 404):
        return f"{reason}\n  Hint: {hint}"
    return reason


def format_request_error(
    exc: requests.RequestException, fallback_service: Optional[str] = None
) -> str:
    """Format connection/timeout errors as a single clean line."""
    service = fallback_service or "API"
    if isinstance(exc, requests.ConnectionError):
        return f"Could not reach {service}: connection error ({exc})."
    if isinstance(exc, requests.Timeout):
        return f"Request to {service} timed out ({exc})."
    return f"Request to {service} failed: {exc}."


def run_with_friendly_errors(
    main_fn: Callable[[], None],
    primary_service: str = "Rippling",
    extra_services: Iterable[str] = (),
) -> NoReturn:
    """Run main_fn() and translate known errors into clean exits.

    - On HTTP 4xx/5xx, network errors, or RuntimeError (missing env vars),
      prints a single-line message to stderr and exits 1.
    - On KeyboardInterrupt, prints "Interrupted" and exits 130.
    - On any other exception, falls back to the default traceback so that
      genuinely unexpected bugs remain debuggable.

    `primary_service` is used as the fallback label when the failing URL
    doesn't disambiguate the service.
    """
    try:
        main_fn()
    except FriendlyApiError as e:
        print(f"\n\u2717 {e}", file=sys.stderr)
        sys.exit(1)
    except requests.HTTPError as e:
        msg = format_http_error(e, fallback_service=primary_service)
        print(f"\n\u2717 {msg}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        msg = format_request_error(e, fallback_service=primary_service)
        print(f"\n\u2717 {msg}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n\u2717 {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    sys.exit(0)
