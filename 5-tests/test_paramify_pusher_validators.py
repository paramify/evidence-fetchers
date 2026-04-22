#!/usr/bin/env python3
"""
Unit tests for the validator + SC association logic in ParamifyPusher.

HTTP is mocked at the ParamifyClient method boundary. No network calls.
Focused on the new Phase 3/5 code paths: normalization, dedup-by-name,
parameter substitution, and association.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "2-create-evidence-sets"))

from paramify_pusher import ParamifyPusher  # noqa: E402


def _pusher_with_mocked_client(param_config_path: Path = None) -> ParamifyPusher:
    p = ParamifyPusher("dummy-token", param_config_path=param_config_path)
    p.client = MagicMock()
    return p


class NameNormalizationTests(unittest.TestCase):
    def test_lowercase_and_trim(self):
        self.assertEqual(ParamifyPusher._normalize_name("  Hello World  "), "hello world")

    def test_collapse_whitespace(self):
        self.assertEqual(ParamifyPusher._normalize_name("a  b\t\tc"), "a b c")

    def test_none_safe(self):
        self.assertEqual(ParamifyPusher._normalize_name(None), "")


class SolutionCapabilityAssociationTests(unittest.TestCase):
    def test_exact_match(self):
        p = _pusher_with_mocked_client()
        p.client.list_solution_capabilities.return_value = [
            {"id": "sc-1", "name": "Change Request"},
            {"id": "sc-2", "name": "Input Validation"},
        ]
        p.client.associate_evidence.return_value = True

        connected, unmatched = p.associate_solution_capabilities(
            "ev-1", ["Change Request", "Input Validation"]
        )
        self.assertEqual(connected, 2)
        self.assertEqual(unmatched, [])
        self.assertEqual(p.client.associate_evidence.call_count, 2)

    def test_name_normalization_matches(self):
        p = _pusher_with_mocked_client()
        p.client.list_solution_capabilities.return_value = [
            {"id": "sc-1", "name": "Change Request"},
        ]
        p.client.associate_evidence.return_value = True

        connected, unmatched = p.associate_solution_capabilities(
            "ev-1", ["  change request  "]
        )
        self.assertEqual(connected, 1)
        self.assertEqual(unmatched, [])

    def test_unmatched_names_reported(self):
        p = _pusher_with_mocked_client()
        p.client.list_solution_capabilities.return_value = [
            {"id": "sc-1", "name": "Change Request"},
        ]
        p.client.associate_evidence.return_value = True

        connected, unmatched = p.associate_solution_capabilities(
            "ev-1", ["Change Request", "Nonexistent SC"]
        )
        self.assertEqual(connected, 1)
        self.assertEqual(unmatched, ["Nonexistent SC"])

    def test_sc_list_cached_across_calls(self):
        p = _pusher_with_mocked_client()
        p.client.list_solution_capabilities.return_value = [
            {"id": "sc-1", "name": "X"},
        ]
        p.client.associate_evidence.return_value = True

        p.associate_solution_capabilities("ev-1", ["X"])
        p.associate_solution_capabilities("ev-2", ["X"])
        self.assertEqual(p.client.list_solution_capabilities.call_count, 1)


class ValidatorAssociationTests(unittest.TestCase):
    def _make_param_file(self, params: dict) -> Path:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        import json
        json.dump(params, f)
        f.close()
        return Path(f.name)

    def test_existing_validator_reused_not_recreated(self):
        p = _pusher_with_mocked_client()
        p.client.list_validators.return_value = [
            {"id": "v-existing", "name": "My Validator"},
        ]
        p.client.associate_evidence.return_value = True

        validators = [{"name": "My Validator", "type": "AUTOMATED", "regex": "x", "validationRules": []}]
        connected, skipped = p.associate_validators("ev-1", validators)

        self.assertEqual(connected, 1)
        self.assertEqual(skipped, 0)
        # Should NOT have hit create_validator
        p.client.create_validator.assert_not_called()
        # Should have associated the existing UUID
        p.client.associate_evidence.assert_called_once_with("ev-1", "VALIDATOR", "v-existing")

    def test_missing_validator_created_then_associated(self):
        p = _pusher_with_mocked_client()
        p.client.list_validators.return_value = []
        p.client.create_validator.return_value = {"id": "v-new", "name": "New Validator"}
        p.client.associate_evidence.return_value = True

        validators = [{"name": "New Validator", "type": "AUTOMATED", "regex": "x", "validationRules": []}]
        connected, skipped = p.associate_validators("ev-1", validators)

        self.assertEqual(connected, 1)
        self.assertEqual(skipped, 0)
        p.client.create_validator.assert_called_once()
        # Payload should have exactly the API-accepted fields
        payload = p.client.create_validator.call_args[0][0]
        self.assertEqual(
            set(payload.keys()),
            {"name", "type", "regex", "validationRules"},
        )

    def test_missing_param_skips_validator(self):
        # No config file path — params default to empty
        p = _pusher_with_mocked_client(param_config_path=Path("/tmp/definitely-does-not-exist.json"))
        p.client.list_validators.return_value = []

        validators = [
            {
                "name": "Tokenized Validator",
                "type": "AUTOMATED",
                "regex": "sg-(?!{{sg_list}})",
                "validationRules": [],
            }
        ]
        connected, skipped = p.associate_validators("ev-1", validators)

        self.assertEqual(connected, 0)
        self.assertEqual(skipped, 1)
        p.client.create_validator.assert_not_called()
        p.client.associate_evidence.assert_not_called()

    def test_tokens_substituted_before_create(self):
        config_path = self._make_param_file({
            "sg_list": "aaa|bbb",
            "_comment_should_be_ignored": "ignore me",
        })
        try:
            p = _pusher_with_mocked_client(param_config_path=config_path)
            p.client.list_validators.return_value = []
            p.client.create_validator.return_value = {"id": "v-1", "name": "T"}
            p.client.associate_evidence.return_value = True

            validators = [{
                "name": "T",
                "type": "AUTOMATED",
                "regex": "sg-(?!{{sg_list}})",
                "validationRules": [],
            }]
            p.associate_validators("ev-1", validators)

            payload = p.client.create_validator.call_args[0][0]
            self.assertEqual(payload["regex"], "sg-(?!aaa|bbb)")
            self.assertNotIn("{{", payload["regex"])
        finally:
            config_path.unlink()

    def test_sanitize_drops_unknown_fields(self):
        p = _pusher_with_mocked_client()
        dirty = {
            "name": "V",
            "type": "AUTOMATED",
            "regex": "x",
            "validationRules": [],
            "catalog_only_field": "should be dropped",
            "statement": "hello",  # allowed
        }
        clean = p._sanitize_validator_for_api(dirty)
        self.assertNotIn("catalog_only_field", clean)
        self.assertIn("statement", clean)

    def test_sanitize_attestation_shape(self):
        p = _pusher_with_mocked_client()
        clean = p._sanitize_validator_for_api({
            "name": "V",
            "type": "ATTESTATION",
            "attestationRules": [],
            "regex": "should be dropped for attestation",
        })
        self.assertNotIn("regex", clean)
        self.assertIn("attestationRules", clean)


if __name__ == "__main__":
    unittest.main(verbosity=2)
