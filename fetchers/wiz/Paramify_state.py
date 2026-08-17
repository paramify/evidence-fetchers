"""
Paramify-backed state store for the Wiz fetchers.
=================================================

Why this exists
---------------
`state.json` / `vuln_state.json` used to live next to the script, and the repo's
own README says "Do not commit state.json - it contains your tenant-specific
report ID". That is the tell: the state is tenant data, not machine data. While
it sits on one laptop the delta watermark belongs to that laptop, and the Wiz
Issues `report_id` - which, if lost, makes the next run create a *second*
orphaned report inside Wiz - belongs to it too. Putting the state in Paramify
puts it where the tenant is.

Layout
------
Each fetcher gets its own evidence set, so reading is "the newest artifact in
*my* set" rather than "the newest artifact in a shared set that happens to have
my filename". That removes any dependence on the server-side
`originalFileName` filter behaving the way we assume, and makes it impossible
for one fetcher's pruning to delete another fetcher's state.

    EVD-WIZ-VULN-STATE    -> wiz_vulnerabilities_state.json
    EVD-WIZ-ISSUES-STATE  -> wiz_issues_state.json

`PATCH /artifacts/{id}` cannot replace a file body, so "update" means "upload a
new one". That suits us: the watermark history ends up append-only.

Reading a file artifact means GETting its `pathname`, which the API documents as
a presigned URL that expires after about 60 minutes. It is therefore fetched
fresh on every read and never cached.

Failure policy
--------------
Every failure path returns None. A missing or unreadable state means "first
run", which means a full fetch: slower, but it cannot lose findings the way a
guessed watermark would.

Environment
-----------
    WIZ_STATE_BACKEND             local | paramify   (default: local)
    WIZ_VULN_STATE_EVIDENCE_ID    evidence set UUID for the vuln fetcher
    WIZ_ISSUES_STATE_EVIDENCE_ID  evidence set UUID for the issues fetcher
    WIZ_STATE_KEEP                artifacts to retain per set (default: 20)
    PARAMIFY_STATE_TIMEOUT        per-request timeout, seconds (default: 60)

    PARAMIFY_API_ISSUES_BASE_URL / PARAMIFY_API_ISSUES_TOKEN are reused unless
    PARAMIFY_STATE_BASE_URL / PARAMIFY_STATE_TOKEN are set.
"""
import json
import logging
import os
from datetime import datetime, timezone

import requests

# Everything below is read lazily, at call time, never at import time.
#
# Fetchers do `from common import paramify_state` in their import block, which
# runs several lines *before* `init_fetcher_env()` loads .env. Module-level
# constants would therefore be frozen from an environment that does not yet
# contain WIZ_STATE_BACKEND, and the backend would silently read as "local"
# with no warning to explain why. Reading on demand keeps this module
# independent of where the caller happens to import it.


def _backend() -> str:
    return os.environ.get('WIZ_STATE_BACKEND', 'local').strip().lower()


def _base() -> str:
    return (os.environ.get('PARAMIFY_STATE_BASE_URL')
            or os.environ.get('PARAMIFY_API_ISSUES_BASE_URL', '')).rstrip('/')


def _token() -> str:
    return (os.environ.get('PARAMIFY_STATE_TOKEN')
            or os.environ.get('PARAMIFY_API_ISSUES_TOKEN', ''))


def _int_env(name: str, default: int) -> int:
    """A malformed number must not take the run down with a ValueError."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        logging.warning('%s=%r is not an integer - using %d',
                        name, raw, default)
        return default


def _keep() -> int:
    return _int_env('WIZ_STATE_KEEP', 20)


def _timeout() -> int:
    return _int_env('PARAMIFY_STATE_TIMEOUT', 60)


def evidence_id(env_name: str) -> str:
    """The evidence set UUID for one fetcher, or '' when unset."""
    return os.environ.get(env_name, '').strip()


def enabled(eid: str) -> bool:
    """True when the Paramify backend is selected AND fully configured.

    A half-configured backend must not silently look like a working one, so
    anything missing is logged by name and we fall back to the local file.
    """
    if _backend() != 'paramify':
        return False
    missing = [n for n, v in (('evidence set id', eid),
                              ('PARAMIFY_API_ISSUES_BASE_URL', _base()),
                              ('PARAMIFY_API_ISSUES_TOKEN', _token())) if not v]
    if missing:
        logging.warning('WIZ_STATE_BACKEND=paramify but %s is not set - using '
                        'the local state file instead', ', '.join(missing))
        return False
    return True


def _headers() -> dict:
    return {'Authorization': f'Bearer {_token()}', 'Accept': 'application/json'}


def _list(eid: str) -> list:
    """Every artifact in the set, newest first.

    The set is dedicated to one fetcher and pruned to KEEP, so listing it
    unfiltered is cheap and avoids relying on the server-side
    `originalFileName` filter, whose matching semantics we have not verified.
    """
    r = requests.get(f'{_base()}/evidence/{eid}/artifacts',
                     headers=_headers(), timeout=_timeout())
    r.raise_for_status()
    arts = r.json().get('artifacts') or []
    # createdAt is ISO 8601, so a lexical sort is chronological.
    return sorted(arts, key=lambda a: a.get('createdAt') or '', reverse=True)


def _mine(arts: list, file_name: str) -> list:
    return [a for a in arts if a.get('originalFileName') == file_name]


def _download(pathname: str) -> dict:
    """GET a presigned artifact URL and parse it as JSON.

    The URL is presigned, so it must not carry our bearer token - an object
    store will reject a request that is authenticated twice. Only if the bare
    GET is refused do we retry with the header, in case a deployment proxies
    downloads through the API instead of redirecting to storage.
    """
    r = requests.get(pathname, timeout=_timeout())
    if r.status_code in (401, 403):
        r = requests.get(pathname, headers=_headers(), timeout=_timeout())
    r.raise_for_status()
    return json.loads(r.text)


def load(eid: str, file_name: str):
    """Return the most recent state dict, or None if there is not one.

    None is not an error. It is the honest answer when no previous run left a
    usable watermark, and the caller should read it as "do a full fetch".
    """
    if not enabled(eid):
        return None
    try:
        arts = _list(eid)
        mine = _mine(arts, file_name)
        if not mine:
            if arts:
                # Something is in the set but not our state file. Reading the
                # newest artifact regardless would risk parsing another
                # fetcher's state, so we decline and take the full fetch.
                logging.warning(
                    'Evidence set %s holds %d artifact(s) but none named %s '
                    '(found: %s) - treating this as a first run',
                    eid, len(arts), file_name,
                    ', '.join(sorted({str(a.get('originalFileName'))
                                      for a in arts})[:5]))
            else:
                logging.info('Evidence set %s is empty - treating this as a '
                             'first run', eid)
            return None

        newest = mine[0]
        pathname = newest.get('pathname')
        if not pathname:
            logging.warning('State artifact %s has no pathname - full fetch',
                            newest.get('id'))
            return None

        state = _download(pathname)
        if not isinstance(state, dict):
            logging.warning('State artifact %s did not contain a JSON object '
                            '- full fetch', newest.get('id'))
            return None

        logging.info('Loaded state from Paramify artifact %s (created %s): %s',
                     newest.get('id'), newest.get('createdAt'),
                     ' '.join(f'{k}={state.get(k)}' for k in
                              ('config_hash', 'report_id',
                               'last_successful_run') if k in state))
        return state
    except Exception as exc:
        # Deliberately broad. A network blip, a 500, a truncated body, a
        # non-JSON payload - none of them justify inventing a watermark.
        logging.warning('Could not read state from Paramify (%s: %s) - '
                        'falling back to a full fetch',
                        type(exc).__name__, exc)
        return None


def save(eid: str, file_name: str, state: dict, label: str = '') -> bool:
    """Upload a new state artifact. Returns True on success."""
    if not enabled(eid):
        return False
    now = datetime.now(timezone.utc)
    title = f'{label or file_name} state {now:%Y-%m-%d %H:%M} UTC'
    note = ('machine state written by the Wiz fetcher (not audit evidence) - '
            + ' '.join(f'{k}={state.get(k)}' for k in
                       ('config_hash', 'report_id', 'last_successful_run')
                       if k in state))
    try:
        r = requests.post(
            f'{_base()}/evidence/{eid}/artifacts/upload',
            headers=_headers(),
            files={'file': (file_name,
                            json.dumps(state, indent=2).encode('utf-8'),
                            'application/json')},
            data={'artifact': json.dumps({'title': title, 'note': note,
                                          'effectiveDate': now.isoformat()})},
            timeout=_timeout(),
        )
        r.raise_for_status()
        logging.info('Saved state to Paramify artifact %s', r.json().get('id'))
        _prune(eid, file_name)
        return True
    except Exception as exc:
        logging.error('Could not write state to Paramify (%s: %s). The next '
                      'run will do a full fetch.', type(exc).__name__, exc)
        return False


def _prune(eid: str, file_name: str) -> None:
    """Delete this fetcher's state artifacts beyond the newest KEEP.

    Only artifacts matching file_name are considered, so a shared set - which
    should not happen, but might - still cannot lose another fetcher's state.
    Pruning failures are logged and swallowed: clutter is not worth failing a
    run that has already succeeded.
    """
    keep = _keep()
    if keep <= 0:
        return
    try:
        mine = _mine(_list(eid), file_name)
        stale = mine[keep:]
        for a in stale:
            requests.delete(f"{_base()}/evidence/{eid}/artifacts/{a['id']}",
                            headers=_headers(), timeout=_timeout())
        if stale:
            logging.info('Pruned %d old state artifact(s), keeping %d',
                         len(stale), keep)
    except Exception as exc:
        logging.warning('Could not prune old state artifacts: %s', exc)
