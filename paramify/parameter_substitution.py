"""
`{{var}}` parameter substitution for validator definitions.

Catalog validators (e.g. the Outbound Security Group Allowlist regex) carry
customer-specific values we can't hard-code in a shared catalog. We tokenize
those values with `{{var_name}}` and substitute them at push time from the
customer's `config/validator_parameters.json`.

Scope is intentionally small: walk a validator dict, replace `{{token}}` in
every string field with the param value. Missing tokens raise so we fail
fast rather than silently pushing `{{unknown}}` to the API.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class MissingParameterError(KeyError):
    """Raised when a validator references a parameter the config doesn't supply."""


def find_tokens(value: Any) -> Set[str]:
    """Return every `{{var}}` name referenced anywhere in `value` (recursive)."""
    found: Set[str] = set()
    _collect(value, found)
    return found


def substitute(value: Any, params: Dict[str, str]) -> Any:
    """Return a deep copy of `value` with every `{{var}}` substituted from
    `params`. Raises MissingParameterError on any unknown token."""
    return _transform(value, params)


def missing_parameters(catalog_node: Any, params: Dict[str, str]) -> List[str]:
    """Tokens referenced in `catalog_node` that are not keys in `params`."""
    return sorted(find_tokens(catalog_node) - set(params.keys()))


# ---------- internals -------------------------------------------------------


def _collect(value: Any, found: Set[str]) -> None:
    if isinstance(value, str):
        found.update(TOKEN_RE.findall(value))
    elif isinstance(value, dict):
        for v in value.values():
            _collect(v, found)
    elif isinstance(value, list):
        for v in value:
            _collect(v, found)


def _transform(value: Any, params: Dict[str, str]) -> Any:
    if isinstance(value, str):
        return _sub_string(value, params)
    if isinstance(value, dict):
        return {k: _transform(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_transform(v, params) for v in value]
    return value


def _sub_string(s: str, params: Dict[str, str]) -> str:
    def repl(m: "re.Match[str]") -> str:
        key = m.group(1)
        if key not in params:
            raise MissingParameterError(key)
        return str(params[key])
    return TOKEN_RE.sub(repl, s)
