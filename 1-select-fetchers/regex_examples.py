#!/usr/bin/env python3
"""
Examples of how to use the regex escape utility for evidence sets.
"""

import json
from escape_regex_for_json import escape_regex_for_json, create_validation_rule


def main():
    print("Regex Escape Examples for Evidence Sets")
    print("=" * 50)
    
    # Your specific regex pattern
    raw_regex = r'"total_storage":\s*(\d+),\s*"encrypted_storage":\s*(\d+)'
    
    print(f"\n1. Raw regex pattern:")
    print(f"   {raw_regex}")
    
    print(f"\n2. Escaped for JSON:")
    escaped_regex = escape_regex_for_json(raw_regex)
    print(f"   {escaped_regex}")
    
    print(f"\n3. Complete validation rule:")
    validation_rule = create_validation_rule(raw_regex, rule_id=1)
    print(json.dumps(validation_rule, indent=2))
    
    print(f"\n4. How it would look in evidence_sets.json:")
    example_evidence_set = {
        "block_storage_encryption_status": {
            "id": "EVD-BLOCK-ENC",
            "name": "Block Storage Encryption",
            "description": "Evidence for EBS volume encryption status and configurations",
            "service": "AWS",
            "instructions": "Script: block_storage_encryption_status.sh. Commands executed: aws ec2 get-ebs-encryption-by-default, aws ec2 get-ebs-default-kms-key-id, aws ec2 describe-volumes, aws efs describe-file-systems",
            "validationRules": [
                validation_rule,
                {
                    "id": 2,
                    "regex": escape_regex_for_json(r'"Encrypted":\s*true'),
                    "logic": "IF match.group(1) == expected_value THEN PASS"
                }
            ]
        }
    }
    print(json.dumps(example_evidence_set, indent=2))
    
    print(f"\n5. Testing the escaped regex:")
    test_text = '      "total_storage": 17,\n      "encrypted_storage": 17,'
    import re
    
    # Unescape the regex for actual use
    unescaped_regex = json.loads(escaped_regex)
    match = re.search(unescaped_regex, test_text)
    
    if match:
        total_storage = int(match.group(1))
        encrypted_storage = int(match.group(2))
        print(f"   Match found!")
        print(f"   Total storage: {total_storage}")
        print(f"   Encrypted storage: {encrypted_storage}")
        print(f"   All encrypted: {total_storage == encrypted_storage}")
    else:
        print("   No match found")


if __name__ == "__main__":
    main()
