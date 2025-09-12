#!/usr/bin/env python3
"""
Utility to escape regex patterns for JSON storage.

This script helps convert raw regex patterns into properly escaped JSON strings
that can be safely stored in JSON files like evidence_sets.json.
"""

import json
import sys
import argparse


def escape_regex_for_json(regex_pattern):
    """
    Escape a regex pattern for safe storage in JSON.
    
    Args:
        regex_pattern (str): The raw regex pattern to escape
        
    Returns:
        str: The escaped regex pattern safe for JSON storage
    """
    return json.dumps(regex_pattern)


def unescape_regex_from_json(escaped_regex):
    """
    Unescape a regex pattern from JSON back to its raw form.
    
    Args:
        escaped_regex (str): The escaped regex pattern from JSON
        
    Returns:
        str: The raw regex pattern
    """
    return json.loads(escaped_regex)


def create_validation_rule(regex_pattern, rule_id=1, logic="IF match.group(1) == expected_value THEN PASS"):
    """
    Create a complete validation rule object with properly escaped regex.
    
    Args:
        regex_pattern (str): The raw regex pattern
        rule_id (int): The rule ID
        logic (str): The validation logic
        
    Returns:
        dict: A validation rule object ready for JSON
    """
    return {
        "id": rule_id,
        "regex": escape_regex_for_json(regex_pattern),
        "logic": logic
    }


def main():
    parser = argparse.ArgumentParser(description="Escape regex patterns for JSON storage")
    parser.add_argument("pattern", nargs="?", help="Regex pattern to escape")
    parser.add_argument("--unescape", action="store_true", help="Unescape a pattern instead")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--create-rule", action="store_true", help="Create a complete validation rule")
    parser.add_argument("--rule-id", type=int, default=1, help="Rule ID for validation rule creation")
    
    args = parser.parse_args()
    
    if args.interactive:
        print("Regex JSON Escape Utility")
        print("=" * 30)
        print("1. Escape regex for JSON")
        print("2. Unescape regex from JSON")
        print("3. Create validation rule")
        print("4. Exit")
        
        while True:
            choice = input("\nEnter choice (1-4): ").strip()
            
            if choice == "1":
                pattern = input("Enter regex pattern: ")
                escaped = escape_regex_for_json(pattern)
                print(f"\nEscaped for JSON:")
                print(escaped)
                print(f"\nYou can copy this directly into your JSON file.")
                
            elif choice == "2":
                escaped = input("Enter escaped regex from JSON: ")
                try:
                    unescaped = unescape_regex_from_json(escaped)
                    print(f"\nRaw regex pattern:")
                    print(unescaped)
                except json.JSONDecodeError as e:
                    print(f"Error: Invalid JSON - {e}")
                    
            elif choice == "3":
                pattern = input("Enter regex pattern: ")
                rule_id = input("Enter rule ID (default 1): ").strip()
                rule_id = int(rule_id) if rule_id else 1
                
                rule = create_validation_rule(pattern, rule_id)
                print(f"\nValidation rule (ready for JSON):")
                print(json.dumps(rule, indent=2))
                
            elif choice == "4":
                break
            else:
                print("Invalid choice. Please enter 1-4.")
                
    elif args.pattern:
        if args.unescape:
            try:
                result = unescape_regex_from_json(args.pattern)
                print(result)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON - {e}", file=sys.stderr)
                sys.exit(1)
        elif args.create_rule:
            rule = create_validation_rule(args.pattern, args.rule_id)
            print(json.dumps(rule, indent=2))
        else:
            escaped = escape_regex_for_json(args.pattern)
            print(escaped)
    else:
        # No pattern provided, show examples
        print("Regex JSON Escape Utility")
        print("=" * 30)
        print("\nExamples:")
        print("\n1. Escape a regex pattern:")
        print("   python escape_regex_for_json.py '\"total_storage\":\\s*(\\d+),\\s*\"encrypted_storage\":\\s*(\\d+)'")
        print("\n2. Create a validation rule:")
        print("   python escape_regex_for_json.py --create-rule '\"total_storage\":\\s*(\\d+),\\s*\"encrypted_storage\":\\s*(\\d+)'")
        print("\n3. Interactive mode:")
        print("   python escape_regex_for_json.py --interactive")
        print("\n4. Unescape a pattern:")
        print("   python escape_regex_for_json.py --unescape '\"total_storage\":\\s*(\\d+),\\s*\"encrypted_storage\":\\s*(\\d+)'")


if __name__ == "__main__":
    main()
