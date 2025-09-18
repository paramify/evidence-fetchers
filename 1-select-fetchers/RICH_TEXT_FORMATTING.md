# Rich Text Formatting for Evidence Sets

This document describes the rich text formatting functionality added to the evidence sets generation process.

## Overview

The evidence sets now support rich text formatting for the `instructions` field, providing consistent layout and enhanced readability. The rich text format uses a structured JSON format that supports:

- **Bold text** for section headers
- `Code formatting` for commands and technical terms
- Bulleted lists for commands and validation rules
- Proper spacing and organization

## Files Added/Modified

### New Files
- `rich_text_formatter.py` - Core rich text formatting functionality
- `update_evidence_sets_rich_text.py` - Script to update existing evidence sets
- `RICH_TEXT_FORMATTING.md` - This documentation

### Modified Files
- `generate_evidence_sets.py` - Updated to use rich text formatting

## Rich Text Format Structure

The rich text format uses a JSON structure with the following elements:

```json
[
  {
    "type": "p",
    "children": [
      {"bold": true, "text": "Script:"},
      {"text": " "},
      {"code": true, "text": "script_name.sh"}
    ]
  },
  {
    "type": "p",
    "children": [{"text": ""}]
  },
  {
    "type": "p",
    "children": [{"bold": true, "text": "Commands: "}]
  },
  {
    "type": "ul",
    "children": [
      {
        "type": "li",
        "children": [
          {
            "type": "lic",
            "children": [{"code": true, "text": "command"}]
          }
        ]
      }
    ]
  }
]
```

### Supported Elements

- **Paragraphs** (`type: "p"`) - For text content
- **Lists** (`type: "ul"`) - For bulleted lists
- **List Items** (`type: "li"`) - For individual list items
- **List Item Content** (`type: "lic"`) - For content within list items

### Text Formatting

- **Bold** (`"bold": true`) - For section headers
- **Code** (`"code": true`) - For commands, scripts, and technical terms
- **Plain text** - For regular content

## Usage

### Generating New Evidence Sets with Rich Text

The `generate_evidence_sets.py` script now automatically converts plain text instructions to rich text format:

```bash
python generate_evidence_sets.py customer_config.json evidence_sets.json
```

### Updating Existing Evidence Sets

To convert existing evidence sets to rich text format:

```bash
python update_evidence_sets_rich_text.py evidence_sets.json evidence_sets_rich_text.json
```

### Testing the Rich Text Formatter

To test the rich text formatter:

```bash
python rich_text_formatter.py
```

## Example Output

### Before (Plain Text)
```
Script: aws_component_ssl_enforcement_status.sh. Commands executed: aws s3api list-buckets, aws s3api get-bucket-policy, aws rds describe-db-instances, aws rds describe-db-parameters
```

### After (Rich Text)
```json
[
  {
    "type": "p",
    "children": [
      {"bold": true, "text": "Script:"},
      {"text": " "},
      {"code": true, "text": "aws_component_ssl_enforcement_status.sh"}
    ]
  },
  {
    "type": "p",
    "children": [{"text": ""}]
  },
  {
    "type": "p",
    "children": [{"bold": true, "text": "Commands: "}]
  },
  {
    "type": "ul",
    "children": [
      {
        "type": "li",
        "children": [
          {
            "type": "lic",
            "children": [{"code": true, "text": "aws s3api list-buckets"}]
          }
        ]
      },
      {
        "type": "li",
        "children": [
          {
            "type": "lic",
            "children": [{"code": true, "text": "aws s3api get-bucket-policy"}]
          }
        ]
      },
      {
        "type": "li",
        "children": [
          {
            "type": "lic",
            "children": [{"code": true, "text": "aws rds describe-db-instances"}]
          }
        ]
      },
      {
        "type": "li",
        "children": [
          {
            "type": "lic",
            "children": [{"code": true, "text": "aws rds describe-db-parameters"}]
          }
        ]
      }
    ]
  }
]
```

## Benefits

1. **Consistent Layout** - All evidence sets now have a uniform, professional appearance
2. **Enhanced Readability** - Bold headers and code formatting improve comprehension
3. **Structured Content** - Commands are clearly organized in bulleted lists
4. **Validation Rules Integration** - Validation rules are properly formatted with regex and logic sections
5. **Future-Proof** - Rich text format supports additional formatting options as needed

## Backward Compatibility

The system automatically detects whether instructions are already in rich text format and skips conversion for those entries. This ensures that:

- Existing rich text formatted evidence sets are not modified
- The system can handle both plain text and rich text formats
- No data loss occurs during updates

## Integration with Paramify

The rich text format is designed to be compatible with Paramify's evidence set requirements. When uploading evidence sets to Paramify, the rich text instructions will be properly rendered in the user interface.
