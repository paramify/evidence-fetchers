#!/usr/bin/env python3
"""
Shared FedRAMP JSON schema validation for paramify-category fetchers.

The FedRAMP Consolidated Rules 2026 publish 11 machine-readable schemas, all of
which $ref a single fedramp-common-definitions schema. This helper loads a named
schema plus the common definitions and validates a document against it, so every
paramify fetcher that produces a FedRAMP artifact can check its own output
before writing.

Two things worth knowing:
  1. The common-definitions file is shared by all 11 schemas, so it lives here
     in _shared/schemas/ and is loaded alongside whichever top schema is named.
  2. FedRAMP writes cross-file $refs WITHOUT the '#' fragment separator
     (e.g. "...common-definitions-...json/$defs/vulnerabilityDetail"). Standard
     JSON Schema resolvers cannot follow that, so we insert the '#' in memory.
     The vendored files on disk stay byte-for-byte as FedRAMP published them.
"""

import json
import os
from typing import List

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schemas")
COMMON_SCHEMA_FILE = "fedramp-common-definitions-schema-2026-06-24.json"


def _load(filename: str) -> dict:
    with open(os.path.join(SCHEMA_DIR, filename)) as f:
        return json.load(f)


def _normalize_refs(node):
    """Insert the missing '#' in FedRAMP cross-file $refs, in memory only."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and "#" not in ref and ".json/$defs/" in ref:
            node["$ref"] = ref.replace(".json/$defs/", ".json#/$defs/", 1)
        for value in node.values():
            _normalize_refs(value)
    elif isinstance(node, list):
        for item in node:
            _normalize_refs(item)
    return node


def build_validator(schema_filename: str) -> Draft202012Validator:
    """
    Build a validator for one FedRAMP schema file (by filename in schemas/),
    with the common-definitions file registered so external $refs resolve.
    """
    top_schema = _normalize_refs(_load(schema_filename))
    common_schema = _normalize_refs(_load(COMMON_SCHEMA_FILE))
    registry = Registry().with_resources(
        [
            (top_schema["$id"], Resource.from_contents(top_schema)),
            (common_schema["$id"], Resource.from_contents(common_schema)),
        ]
    )
    return Draft202012Validator(
        top_schema, registry=registry, format_checker=FormatChecker()
    )


def validate(document: dict, schema_filename: str) -> List[str]:
    """
    Validate a document against the named FedRAMP schema.

    Returns a list of human-readable error strings (empty list means valid), so
    callers can treat schema failure as a collection failure without raising.
    """
    validator = build_validator(schema_filename)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(document), key=lambda e: e.absolute_path)
    ]
