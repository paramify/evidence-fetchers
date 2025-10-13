#!/usr/bin/env python3
"""
Simple test to verify validation works correctly
"""

import json
import re


def validate_response(data: dict, validation_rules: list[str]) -> bool:
    json_str = json.dumps(data, sort_keys=True)
    return all(re.search(rule, json_str) for rule in validation_rules)


def test_validation() -> bool:
    """Test the validation function directly"""
    print("Testing validation function...")

    # Test data that should pass
    test_data = {
        "Status": "Enabled",
        "MFADelete": "Enabled",
    }

    validation_rules = [
        r'"MFADelete":\s*"Enabled"',
        r'"Status":\s*"Enabled"',
    ]

    result = validate_response(test_data, validation_rules)
    print(f"Validation result: {result}")

    # Show the JSON string that's being validated
    json_str = json.dumps(test_data, sort_keys=True)
    print(f"JSON string: {json_str}")

    # Test each rule individually
    for i, rule in enumerate(validation_rules):
        match = re.search(rule, json_str)
        print(f"Rule {i+1} ({rule}): {'✓' if match else '✗'}")
        if match:
            print(f"  Matched: {match.group()}")

    return result


if __name__ == "__main__":
    ok = test_validation()
    raise SystemExit(0 if ok else 1)
