#!/usr/bin/env python3
"""
Rich Text Formatter for Evidence Sets Instructions

This module provides functionality to convert plain text instructions
into rich text format with consistent layout and formatting.
"""

import re
import json
from typing import List, Dict, Any, Optional


def create_rich_text_instructions(script_name: str, commands: List[str], 
                                steps: List[str] = None, output_desc: str = None,
                                validation_rules: List[Dict] = None) -> List[Dict[str, Any]]:
    """
    Create rich text formatted instructions for evidence sets.
    
    Args:
        script_name: Name of the script file
        commands: List of commands executed by the script
        steps: Optional list of detailed steps
        output_desc: Optional description of the output
        validation_rules: Optional list of validation rules
    
    Returns:
        List of rich text format objects
    """
    rich_text = []
    
    # Script section
    rich_text.append({
        "type": "p",
        "children": [
            {"bold": True, "text": "Script:"},
            {"text": " "},
            {"code": True, "text": script_name}
        ]
    })
    
    # Empty line
    rich_text.append({"type": "p", "children": [{"text": ""}]})
    
    # Commands section
    rich_text.append({
        "type": "p",
        "children": [{"bold": True, "text": "Commands: "}]
    })
    
    # Commands list
    commands_list = []
    for command in commands:
        commands_list.append({
            "type": "li",
            "children": [
                {
                    "type": "lic",
                    "children": [{"code": True, "text": command}]
                }
            ]
        })
    
    rich_text.append({
        "type": "ul",
        "children": commands_list
    })
    
    # Empty line
    rich_text.append({"type": "p", "children": [{"text": ""}]})
    
    # Steps section (if provided)
    if steps:
        rich_text.append({
            "type": "p",
            "children": [{"bold": True, "text": "Steps:"}]
        })
        
        for i, step in enumerate(steps, 1):
            # Step description
            rich_text.append({
                "type": "p",
                "children": [{"text": f"{i}. {step}"}]
            })
            
            # Empty line
            rich_text.append({"type": "p", "children": [{"text": ""}]})
    
    # Output section (if provided)
    if output_desc:
        rich_text.append({
            "type": "p",
            "children": [
                {"bold": True, "text": "Output: "},
                {"text": output_desc}
            ]
        })
        
        # Empty line
        rich_text.append({"type": "p", "children": [{"text": ""}]})
    
    # Validation section (if provided)
    if validation_rules:
        rich_text.append({
            "type": "p",
            "children": [{"bold": True, "text": "Validation:"}]
        })
        
        for rule in validation_rules:
            rule_id = rule.get('id', 'N/A')
            rule_regex = rule.get('regex', '')
            rule_logic = rule.get('logic', '')
            
            # Rule header
            rich_text.append({
                "type": "p",
                "children": [{"text": f"Rule {rule_id}"}]
            })
            
            # Rule details
            rule_details = []
            if rule_regex:
                rule_details.append({
                    "type": "li",
                    "children": [
                        {
                            "type": "lic",
                            "children": [
                                {"text": "Regex: "},
                                {"code": True, "text": rule_regex}
                            ]
                        }
                    ]
                })
            
            if rule_logic:
                rule_details.append({
                    "type": "li",
                    "children": [
                        {
                            "type": "lic",
                            "children": [
                                {"text": "Logic: "},
                                {"code": True, "text": rule_logic}
                            ]
                        }
                    ]
                })
            
            if rule_details:
                rich_text.append({
                    "type": "ul",
                    "children": rule_details
                })
    
    return rich_text


def parse_plain_instructions(instructions: str) -> Dict[str, Any]:
    """
    Parse plain text instructions to extract components.
    
    Args:
        instructions: Plain text instructions string
    
    Returns:
        Dictionary with parsed components
    """
    # Extract script name
    script_match = re.search(r'Script:\s*([^\s.]+)', instructions)
    script_name = script_match.group(1) if script_match else "unknown_script.sh"
    
    # Extract commands
    commands_match = re.search(r'Commands executed:\s*(.+)', instructions)
    if commands_match:
        commands_text = commands_match.group(1)
        # Split by comma and clean up
        commands = [cmd.strip() for cmd in commands_text.split(',')]
    else:
        commands = []
    
    return {
        "script_name": script_name,
        "commands": commands
    }


def convert_instructions_to_rich_text(instructions: str, validation_rules: List[Dict] = None) -> List[Dict[str, Any]]:
    """
    Convert plain text instructions to rich text format.
    
    Args:
        instructions: Plain text instructions
        validation_rules: Optional validation rules
    
    Returns:
        Rich text formatted instructions
    """
    parsed = parse_plain_instructions(instructions)
    
    # Create rich text with basic components
    rich_text = create_rich_text_instructions(
        script_name=parsed["script_name"],
        commands=parsed["commands"],
        validation_rules=validation_rules
    )
    
    return rich_text


def create_ssl_enforcement_rich_text() -> List[Dict[str, Any]]:
    """
    Create the specific rich text format for SSL enforcement as shown in the example.
    
    Returns:
        Rich text formatted instructions for SSL enforcement
    """
    return [
        {"type": "p", "children": [{"bold": True, "text": "Script:"}, {"text": " "}, {"code": True, "text": "aws_component_ssl_enforcement_status.sh"}]},
        {"type": "p", "children": [{"text": ""}]},
        {"type": "p", "children": [{"bold": True, "text": "Commands: "}]},
        {"type": "ul", "children": [
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws s3api list-buckets"}]}]},
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws s3api get-bucket-policy"}]}]},
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws rds describe-db-instances"}]}]},
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws rds describe-db-parameters"}]}]}
        ]},
        {"type": "p", "children": [{"text": ""}]},
        {"type": "p", "children": [{"bold": True, "text": "Steps:"}]},
        {"type": "p", "children": [{"text": "1. Check S3 bucket policies for enforced HTTPS (aws:SecureTransport)"}]},
        {"type": "ul", "children": [
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws s3api list-buckets"}]}]},
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws s3api get-bucket-policy --bucket <bucket-name>"}]}]}
        ]},
        {"type": "p", "children": [{"text": ""}]},
        {"type": "p", "children": [{"text": "2. Check RDS parameter groups for rds.force_ssl = 1"}]},
        {"type": "ul", "children": [
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws rds describe-db-instances"}]}]},
            {"type": "li", "children": [{"type": "lic", "children": [{"code": True, "text": "aws rds describe-db-parameters --db-parameter-group-name <pg-name>"}]}]}
        ]},
        {"type": "p", "children": [{"text": ""}]},
        {"type": "p", "children": [{"bold": True, "text": "Output: "}, {"text": "Creates JSON report with SSL enforcement status. "}]},
        {"type": "p", "children": [{"text": ""}]},
        {"type": "p", "children": [{"bold": True, "text": "Validation:"}]},
        {"type": "p", "children": [{"text": "Rule 1 – S3 SSL Enforcement"}]},
        {"type": "ul", "children": [
            {"type": "li", "children": [{"type": "lic", "children": [{"text": "Regex: "}, {"code": True, "text": "\"s3_total\":\\s*(?P<s3_total>\\d+)[\\s\\S]*?\"s3_ssl_enforced\":\\s*(?P<s3_ssl_enforced>\\d+)"}]}]},
            {"type": "li", "children": [{"type": "lic", "children": [{"text": "Logic: "}, {"code": True, "text": "IF s3_total == s3_ssl_enforced THEN PASS"}]}]}
        ]},
        {"type": "p", "children": [{"text": "Rule 2 – RDS SSL Enforcement"}]},
        {"type": "ul", "children": [
            {"type": "li", "children": [{"type": "lic", "children": [{"text": "Regex: "}, {"code": True, "text": "\"rds_total\":\\s*(?P<rds_total>\\d+)[\\s\\S]*?\"rds_ssl_enforced\":\\s*(?P<rds_ssl_enforced>\\d+)"}]}]},
            {"type": "li", "children": [{"type": "lic", "children": [{"text": "Logic: "}, {"code": True, "text": "IF rds_total == rds_ssl_enforced THEN PASS"}]}]}
        ]}
    ]


def rich_text_to_string(rich_text: List[Dict[str, Any]]) -> str:
    """
    Convert rich text format back to a readable string format.
    
    Args:
        rich_text: List of rich text objects
        
    Returns:
        str: Readable string representation of the rich text
    """
    if not rich_text:
        return ""
    
    result = []
    
    for item in rich_text:
        if item.get("type") == "p":
            # Handle paragraph
            children = item.get("children", [])
            paragraph_text = ""
            
            for child in children:
                if child.get("bold"):
                    paragraph_text += f"**{child.get('text', '')}**"
                elif child.get("code"):
                    paragraph_text += f"`{child.get('text', '')}`"
                else:
                    paragraph_text += child.get("text", "")
            
            if paragraph_text.strip():
                result.append(paragraph_text)
        
        elif item.get("type") == "ul":
            # Handle unordered list
            children = item.get("children", [])
            for child in children:
                if child.get("type") == "li":
                    lic_children = child.get("children", [])
                    for lic in lic_children:
                        if lic.get("type") == "lic":
                            lic_children_text = lic.get("children", [])
                            list_item_text = ""
                            
                            for lic_child in lic_children_text:
                                if lic_child.get("bold"):
                                    list_item_text += f"**{lic_child.get('text', '')}**"
                                elif lic_child.get("code"):
                                    list_item_text += f"`{lic_child.get('text', '')}`"
                                else:
                                    list_item_text += lic_child.get("text", "")
                            
                            if list_item_text.strip():
                                result.append(f"• {list_item_text}")
    
    return "\n".join(result)


def convert_instructions_to_string(instructions: Any) -> str:
    """
    Convert instructions to string format, handling both rich text and plain text.
    
    Args:
        instructions: Either rich text format (list) or plain text (string)
        
    Returns:
        str: String representation of instructions
    """
    if isinstance(instructions, list):
        # Rich text format - convert to string
        return rich_text_to_string(instructions)
    elif isinstance(instructions, str):
        # Already a string
        return instructions
    else:
        # Fallback
        return str(instructions)


def main():
    """Test the rich text formatter."""
    # Test with SSL enforcement example
    ssl_rich_text = create_ssl_enforcement_rich_text()
    print("SSL Enforcement Rich Text:")
    print(json.dumps(ssl_rich_text, indent=2))
    
    # Test conversion back to string
    ssl_string = rich_text_to_string(ssl_rich_text)
    print("\nSSL Enforcement as String:")
    print(ssl_string)
    
    # Test with generic conversion
    plain_instructions = "Script: aws_config_monitoring.sh. Commands executed: aws configservice describe-configuration-recorders, aws configservice describe-configuration-recorder-status, aws configservice describe-delivery-channels"
    rich_text = convert_instructions_to_rich_text(plain_instructions)
    print("\nGeneric Conversion to Rich Text:")
    print(json.dumps(rich_text, indent=2))
    
    # Test conversion back to string
    generic_string = rich_text_to_string(rich_text)
    print("\nGeneric Conversion as String:")
    print(generic_string)


if __name__ == "__main__":
    main()
