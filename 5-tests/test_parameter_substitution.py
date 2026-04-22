#!/usr/bin/env python3
"""
Unit tests for paramify.parameter_substitution.

Covers the {{token}} engine that the pusher uses to inject customer-specific
values into validator definitions at push time. No network calls.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from paramify.parameter_substitution import (  # noqa: E402
    MissingParameterError,
    find_tokens,
    missing_parameters,
    substitute,
)


class FindTokensTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(find_tokens(""), set())
        self.assertEqual(find_tokens({}), set())
        self.assertEqual(find_tokens([]), set())
        self.assertEqual(find_tokens(None), set())

    def test_no_tokens(self):
        self.assertEqual(find_tokens("just a plain string"), set())

    def test_single_token(self):
        self.assertEqual(find_tokens("hello {{name}}"), {"name"})

    def test_multiple_tokens(self):
        self.assertEqual(
            find_tokens("{{a}} and {{b}} and {{a}}"),
            {"a", "b"},
        )

    def test_nested_dict(self):
        validator = {
            "name": "Test",
            "regex": "sg-(?!{{sg_list}})[^\"]+",
            "validationRules": [
                {"value": {"type": "CUSTOM_TEXT", "customText": "{{acct_id}}"}}
            ],
        }
        self.assertEqual(find_tokens(validator), {"sg_list", "acct_id"})

    def test_whitespace_tolerated(self):
        self.assertEqual(find_tokens("{{ spaced }}"), {"spaced"})

    def test_invalid_identifier_not_matched(self):
        # `{{123abc}}` starts with a digit — not a valid identifier
        self.assertEqual(find_tokens("{{123abc}}"), set())


class SubstituteTests(unittest.TestCase):
    def test_simple_string(self):
        self.assertEqual(substitute("{{name}}", {"name": "Alice"}), "Alice")

    def test_preserves_surrounding_text(self):
        self.assertEqual(
            substitute("prefix-{{x}}-suffix", {"x": "VAL"}),
            "prefix-VAL-suffix",
        )

    def test_nested_structure(self):
        before = {
            "a": "{{x}}",
            "b": [{"c": "{{y}}"}, "static"],
        }
        after = substitute(before, {"x": "X!", "y": "Y!"})
        self.assertEqual(after, {"a": "X!", "b": [{"c": "Y!"}, "static"]})

    def test_original_is_not_mutated(self):
        before = {"a": "{{x}}"}
        substitute(before, {"x": "X!"})
        self.assertEqual(before, {"a": "{{x}}"})

    def test_missing_token_raises(self):
        with self.assertRaises(MissingParameterError):
            substitute("{{missing}}", {"other": "value"})

    def test_non_string_values_pass_through(self):
        self.assertEqual(substitute(42, {}), 42)
        self.assertEqual(substitute(True, {}), True)
        self.assertEqual(substitute(None, {}), None)

    def test_int_param_value_coerced_to_str(self):
        self.assertEqual(substitute("id-{{n}}", {"n": 123}), "id-123")


class MissingParametersTests(unittest.TestCase):
    def test_all_supplied(self):
        validator = {"regex": "{{a}}-{{b}}"}
        self.assertEqual(missing_parameters(validator, {"a": "1", "b": "2"}), [])

    def test_none_supplied(self):
        self.assertEqual(
            missing_parameters("{{a}} {{b}}", {}),
            ["a", "b"],
        )

    def test_partial(self):
        self.assertEqual(
            missing_parameters("{{a}} {{b}}", {"a": "1"}),
            ["b"],
        )

    def test_extra_params_ok(self):
        self.assertEqual(
            missing_parameters("{{a}}", {"a": "1", "unused": "x"}),
            [],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
