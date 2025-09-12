# Regex Escape Utilities for Evidence Sets

This directory contains utilities to help you properly escape regex patterns for JSON storage in your evidence sets.

## Files

- `escape_regex_for_json.py` - Main utility for escaping/unescaping regex patterns
- `regex_examples.py` - Examples showing how to use the escape utility
- `update_evidence_sets_regex.py` - Script to update evidence_sets.json with properly escaped patterns
- `REGEX_ESCAPE_README.md` - This documentation

## Quick Start

### 1. Escape a single regex pattern

```bash
python3 escape_regex_for_json.py '"total_storage":\s*(\d+),\s*"encrypted_storage":\s*(\d+)'
```

Output:
```
"\"total_storage\":\\s*(\\d+),\\s*\"encrypted_storage\":\\s*(\\d+)"
```

### 2. Create a complete validation rule

```bash
python3 escape_regex_for_json.py --create-rule '"total_storage":\s*(\d+),\s*"encrypted_storage":\s*(\d+)'
```

Output:
```json
{
  "id": 1,
  "regex": "\"\\\"total_storage\\\":\\\\s*(\\\\d+),\\\\s*\\\"encrypted_storage\\\":\\\\s*(\\\\d+)\"",
  "logic": "IF match.group(1) == expected_value THEN PASS"
}
```

### 3. Interactive mode

```bash
python3 escape_regex_for_json.py --interactive
```

This will give you a menu to:
- Escape regex patterns
- Unescape patterns from JSON
- Create validation rules
- Exit

### 4. Update all evidence sets

```bash
python3 update_evidence_sets_regex.py
```

This will update your `evidence_sets.json` file with properly escaped regex patterns for all evidence sets that have validation rules.

## Examples

### Your specific regex pattern

**Raw regex:**
```regex
"total_storage":\s*(\d+),\s*"encrypted_storage":\s*(\d+)
```

**Escaped for JSON:**
```json
"\"total_storage\":\\s*(\\d+),\\s*\"encrypted_storage\":\\s*(\\d+)"
```

**Complete validation rule:**
```json
{
  "id": 1,
  "regex": "\"\\\"total_storage\\\":\\\\s*(\\\\d+),\\\\s*\\\"encrypted_storage\\\":\\\\s*(\\\\d+)\"",
  "logic": "IF int(match.group(1)) == int(match.group(2)) THEN PASS ELSE FAIL"
}
```

### How it works in your evidence sets

```json
{
  "block_storage_encryption_status": {
    "id": "EVD-BLOCK-ENC",
    "name": "Block Storage Encryption",
    "description": "Evidence for EBS volume encryption status and configurations",
    "service": "AWS",
    "instructions": "Script: block_storage_encryption_status.sh...",
    "validationRules": [
      {
        "id": 1,
        "regex": "\"\\\"total_storage\\\":\\\\s*(\\\\d+),\\\\s*\\\"encrypted_storage\\\":\\\\s*(\\\\d+)\"",
        "logic": "IF int(match.group(1)) == int(match.group(2)) THEN PASS ELSE FAIL"
      }
    ]
  }
}
```

## Why This Matters

JSON requires special characters to be escaped:
- `"` becomes `\"`
- `\` becomes `\\`
- Newlines become `\n`
- etc.

When you store regex patterns in JSON, you need to escape them properly, otherwise:
1. Your JSON will be invalid
2. Your regex patterns won't work as expected
3. You'll get parsing errors

## Testing

Run the examples to see how it works:

```bash
python3 regex_examples.py
```

This will show you:
1. How to escape your regex pattern
2. How to create validation rules
3. How to test the escaped regex against sample data
4. How it looks in the final JSON structure

## Safety

- The `update_evidence_sets_regex.py` script creates a backup before making changes
- You can always restore from `evidence_sets.json.backup` if something goes wrong
- The script will ask for confirmation before making changes
