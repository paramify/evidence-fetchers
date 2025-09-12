#!/usr/bin/env python3
"""
Script to update evidence_sets.json with properly escaped regex patterns.
"""

import json
import sys
from escape_regex_for_json import escape_regex_for_json


def update_evidence_sets_regex():
    """
    Update the evidence_sets.json file with properly escaped regex patterns.
    """
    
    # Read the current evidence_sets.json
    try:
        with open('evidence_sets.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: evidence_sets.json not found")
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in evidence_sets.json - {e}")
        return False
    
    # Define the regex patterns that need to be updated
    regex_updates = {
        "block_storage_encryption_status": [
            {
                "id": 1,
                "raw_regex": r'"total_storage":\s*(\d+),\s*"encrypted_storage":\s*(\d+)',
                "logic": "IF int(match.group(1)) == int(match.group(2)) THEN PASS ELSE FAIL"
            },
            {
                "id": 2,
                "raw_regex": r'"Encrypted":\s*true',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            }
        ],
        "rds_encryption_status": [
            {
                "id": 1,
                "raw_regex": r'"StorageEncrypted":\s*true',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            }
        ],
        "s3_encryption_status": [
            {
                "id": 1,
                "raw_regex": r'"ServerSideEncryptionConfiguration"',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            },
            {
                "id": 2,
                "raw_regex": r'"ApplyServerSideEncryptionByDefault"',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            }
        ],
        "aws_component_ssl_enforcement_status": [
            {
                "id": 1,
                "raw_regex": r'"ssl_enforced":\s*true',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            }
        ],
        "load_balancer_encryption_status": [
            {
                "id": 1,
                "raw_regex": r'"encrypted":\s*true',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            }
        ],
        "s3_mfa_delete": [
            {
                "id": 1,
                "raw_regex": r'"MFADelete":\s*"Enabled"',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            },
            {
                "id": 2,
                "raw_regex": r'"Status":\s*"Enabled"',
                "logic": "IF match.group(1) == expected_value THEN PASS"
            }
        ]
    }
    
    # Update the evidence sets
    updated_count = 0
    for evidence_set_name, rules in regex_updates.items():
        if evidence_set_name in data["evidence_sets"]:
            print(f"Updating {evidence_set_name}...")
            
            # Create new validation rules with properly escaped regex
            new_rules = []
            for rule in rules:
                new_rule = {
                    "id": rule["id"],
                    "regex": escape_regex_for_json(rule["raw_regex"]),
                    "logic": rule["logic"]
                }
                new_rules.append(new_rule)
            
            # Update the evidence set
            data["evidence_sets"][evidence_set_name]["validationRules"] = new_rules
            updated_count += 1
        else:
            print(f"Warning: Evidence set '{evidence_set_name}' not found")
    
    # Write the updated data back to the file
    try:
        with open('evidence_sets.json', 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nSuccessfully updated {updated_count} evidence sets with properly escaped regex patterns.")
        return True
    except Exception as e:
        print(f"Error writing updated file: {e}")
        return False


def main():
    print("Evidence Sets Regex Update Utility")
    print("=" * 40)
    
    # Ask for confirmation
    response = input("This will update evidence_sets.json with properly escaped regex patterns. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return
    
    # Create a backup
    import shutil
    try:
        shutil.copy('evidence_sets.json', 'evidence_sets.json.backup')
        print("Created backup: evidence_sets.json.backup")
    except Exception as e:
        print(f"Warning: Could not create backup - {e}")
    
    # Update the file
    if update_evidence_sets_regex():
        print("\nUpdate completed successfully!")
        print("You can now use the properly escaped regex patterns in your evidence sets.")
    else:
        print("\nUpdate failed. Check the error messages above.")


if __name__ == "__main__":
    main()
