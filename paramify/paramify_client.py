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
