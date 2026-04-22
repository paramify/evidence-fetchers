"""
Shared HTTP client for the Paramify REST API (v0.5.1).

This is the single place where Paramify API calls are made. Higher-level
modules (e.g. `2-create-evidence-sets/paramify_pusher.py`) should use this
client instead of reaching for `requests` directly.

Base URL is chosen in this order:
  1. explicit `base_url` argument
  2. `PARAMIFY_API_BASE_URL` environment variable
  3. default `https://app.paramify.com/api/v0`
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


DEFAULT_BASE_URL = "https://app.paramify.com/api/v0"


class ParamifyClient:
    def __init__(self, api_token: str, base_url: Optional[str] = None):
        self.api_token = api_token
        self.base_url = (
            base_url
            or os.environ.get("PARAMIFY_API_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self._json_headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self._auth_only_headers = {"Authorization": f"Bearer {api_token}"}

    # ----- Low-level HTTP -------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path if path.startswith('/') else '/' + path}"

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        return requests.get(self._url(path), headers=self._json_headers, params=params)

    def post_json(self, path: str, body: Dict[str, Any]) -> requests.Response:
        return requests.post(self._url(path), headers=self._json_headers, json=body)

    def post_multipart(self, path: str, files: Dict[str, Any]) -> requests.Response:
        return requests.post(self._url(path), headers=self._auth_only_headers, files=files)

    # ----- Evidence -------------------------------------------------------

    def list_evidence(self) -> List[Dict[str, Any]]:
        resp = self.get("/evidence")
        resp.raise_for_status()
        return resp.json().get("evidences", [])

    def find_evidence_by_reference_id(self, reference_id: str) -> Optional[Dict[str, Any]]:
        """Return the full evidence record matching `referenceId`, or None."""
        try:
            for evidence in self.list_evidence():
                if evidence.get("referenceId") == reference_id:
                    return evidence
            return None
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve Evidence records: {e}")
            return None

    def create_evidence(
        self,
        reference_id: str,
        name: str,
        description: Optional[str],
        instructions: Optional[str],
        automated: bool = True,
    ) -> Optional[str]:
        """Create a new evidence record. Returns the new internal UUID, or
        None on failure. If the referenceId already exists, looks up the
        existing record and returns its UUID (idempotent behavior).
        """
        body = {
            "referenceId": reference_id,
            "name": name,
            "description": description,
            "instructions": instructions,
            "automated": automated,
        }

        try:
            resp = self.post_json("/evidence", body)
        except requests.exceptions.RequestException as e:
            print(f"Error creating evidence: {e}")
            return None

        if resp.status_code in (200, 201):
            return resp.json().get("id")

        if resp.status_code == 400:
            try:
                err = resp.json()
            except ValueError:
                err = {}
            msg = err.get("message") or err.get("error") or ""
            if "Reference ID already exists" in msg:
                existing = self.find_evidence_by_reference_id(reference_id)
                return existing.get("id") if existing else None
            print(f"Failed to create evidence (HTTP 400): {msg or resp.text}")
            return None

        print(f"Failed to create evidence (HTTP {resp.status_code}): {resp.text}")
        return None

    # ----- Solution Capabilities -----------------------------------------

    def list_solution_capabilities(self) -> List[Dict[str, Any]]:
        """GET /solution-capabilities -> list of {id, name, family, subfamily}."""
        resp = self.get("/solution-capabilities")
        resp.raise_for_status()
        return resp.json().get("solutionCapabilities", [])

    # ----- Validators -----------------------------------------------------

    def list_validators(
        self,
        ids: Optional[List[str]] = None,
        validator_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """GET /validators -> list of Validator records."""
        params: Dict[str, Any] = {}
        if ids:
            params["ids"] = ids
        if validator_type:
            params["type"] = validator_type
        resp = self.get("/validators", params=params)
        resp.raise_for_status()
        return resp.json().get("validators", [])

    def create_validator(self, definition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST /validators. Returns the created record, or None on failure."""
        try:
            resp = self.post_json("/validators", definition)
        except requests.exceptions.RequestException as e:
            print(f"Error creating validator: {e}")
            return None
        if resp.status_code in (200, 201):
            return resp.json()
        print(
            f"Failed to create validator {definition.get('name')!r} "
            f"(HTTP {resp.status_code}): {resp.text}"
        )
        return None

    # ----- Associations ---------------------------------------------------

    VALID_SUBJECT_TYPES = frozenset(
        {"CONTROL_IMPLEMENTATION", "SOLUTION_CAPABILITY", "ELEMENT", "VALIDATOR"}
    )

    def associate_evidence(
        self,
        evidence_id: str,
        subject_type: str,
        subject_id: str,
        connect: bool = True,
    ) -> bool:
        """POST /evidence/{id}/associate. Returns True on 2xx or when the
        association already exists (duplicate 400/409 swallowed)."""
        if subject_type not in self.VALID_SUBJECT_TYPES:
            raise ValueError(
                f"Invalid subject_type {subject_type!r}; "
                f"must be one of {sorted(self.VALID_SUBJECT_TYPES)}"
            )
        body = {
            "associationType": "CONNECT" if connect else "DISCONNECT",
            "subjectType": subject_type,
            "subjectId": subject_id,
        }
        try:
            resp = self.post_json(f"/evidence/{evidence_id}/associate", body)
        except requests.exceptions.RequestException as e:
            print(f"Error associating evidence {evidence_id} -> {subject_type} {subject_id}: {e}")
            return False
        if 200 <= resp.status_code < 300:
            return True
        if resp.status_code in (400, 409):
            # Treat "already associated" as success. The API returns 400 on
            # idempotent reconnects in some cases; inspect the message.
            try:
                msg = (resp.json().get("message") or resp.json().get("error") or "").lower()
            except ValueError:
                msg = resp.text.lower()
            if "already" in msg or "duplicate" in msg or "exists" in msg:
                return True
        print(
            f"Failed to associate evidence {evidence_id} -> {subject_type} {subject_id} "
            f"(HTTP {resp.status_code}): {resp.text}"
        )
        return False

    # ----- Artifacts ------------------------------------------------------

    def list_artifacts(
        self, evidence_id: str, original_file_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if original_file_name:
            params["originalFileName"] = [original_file_name]
        try:
            resp = self.get(f"/evidence/{evidence_id}/artifacts", params=params)
        except requests.exceptions.RequestException:
            return []
        if resp.status_code != 200:
            return []
        data = resp.json()
        # API has returned either a bare list or {"artifacts": [...]}.
        if isinstance(data, list):
            return data
        return data.get("artifacts", [])

    def upload_artifact(
        self,
        evidence_id: str,
        file_path: str,
        artifact_metadata: Dict[str, Any],
    ) -> bool:
        """Upload a file as an artifact on the given evidence record.

        `artifact_metadata` becomes the JSON body of the `artifact` multipart
        part (typically: title, note, effectiveDate).
        """
        file_path_p = Path(file_path)
        if not file_path_p.exists():
            print(f"Artifact file not found: {file_path}")
            return False

        temp_artifact_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as temp_artifact:
                json.dump(artifact_metadata, temp_artifact)
                temp_artifact_path = temp_artifact.name

            with open(file_path_p, "rb") as f, open(temp_artifact_path, "rb") as artifact_f:
                files = {
                    "file": f,
                    "artifact": ("artifact.json", artifact_f, "application/json"),
                }
                resp = self.post_multipart(
                    f"/evidence/{evidence_id}/artifacts/upload", files=files
                )

            if resp.status_code in (200, 201):
                return True
            print(
                f"Failed to upload artifact (HTTP {resp.status_code}): {resp.text}"
            )
            return False
        except requests.exceptions.RequestException as e:
            print(f"Error uploading artifact: {e}")
            return False
        finally:
            if temp_artifact_path:
                try:
                    os.unlink(temp_artifact_path)
                except OSError:
                    pass
