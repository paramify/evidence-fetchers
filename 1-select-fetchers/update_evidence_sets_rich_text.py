#!/usr/bin/env python3
"""
Update Evidence Sets with Rich Text Formatting

This script updates existing evidence_sets.json files to convert plain text instructions
to rich text format with consistent layout and formatting.

Usage:
    python update_evidence_sets_rich_text.py [input_file.json] [output_file.json]

If no arguments are provided, it will use:
    - evidence_sets.json (default input file)
    - evidence_sets_rich_text.json (default output file)
"""

import json
import sys
import os
from typing import Dict, List, Any
from rich_text_formatter import convert_instructions_to_rich_text


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{file_path}': {e}")
        sys.exit(1)


def is_rich_text_format(instructions: Any) -> bool:
    """
    Check if instructions are already in rich text format.
    
    Args:
        instructions: The instructions field to check
        
    Returns:
        bool: True if already in rich text format, False otherwise
    """
    if isinstance(instructions, list):
        # Check if it's a list of rich text objects
        if len(instructions) > 0 and isinstance(instructions[0], dict):
            # Check if it has the expected rich text structure
            first_item = instructions[0]
            if 'type' in first_item and 'children' in first_item:
                return True
    return False


def update_evidence_sets_with_rich_text(evidence_sets: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update evidence sets to use rich text formatting for instructions.
    
    Args:
        evidence_sets: The evidence sets dictionary
        
    Returns:
        Updated evidence sets with rich text instructions
    """
    updated_sets = evidence_sets.copy()
    updated_count = 0
    skipped_count = 0
    
    if 'evidence_sets' not in updated_sets:
        print("Error: Invalid evidence sets structure - missing 'evidence_sets' key")
        return updated_sets
    
    for script_name, script_info in updated_sets['evidence_sets'].items():
        if 'instructions' not in script_info:
            print(f"  Warning: No instructions field found for {script_name}")
            continue
        
        instructions = script_info['instructions']
        
        # Check if already in rich text format
        if is_rich_text_format(instructions):
            print(f"  Skipping {script_name} - already in rich text format")
            skipped_count += 1
            continue
        
        # Convert to rich text format
        try:
            validation_rules = script_info.get('validationRules', [])
            rich_text_instructions = convert_instructions_to_rich_text(
                instructions, 
                validation_rules
            )
            
            # Update the instructions
            updated_sets['evidence_sets'][script_name]['instructions'] = rich_text_instructions
            print(f"  Updated {script_name} with rich text formatting")
            updated_count += 1
            
        except Exception as e:
            print(f"  Error updating {script_name}: {e}")
            continue
    
    print(f"\nSummary:")
    print(f"  Updated: {updated_count} evidence sets")
    print(f"  Skipped: {skipped_count} evidence sets (already rich text)")
    
    return updated_sets


def main():
    """Main function."""
    # Default file paths
    default_input_file = "evidence_sets.json"
    default_output_file = "evidence_sets_rich_text.json"
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = default_input_file
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = default_output_file
    
    print(f"Evidence Sets Rich Text Updater")
    print(f"{'='*40}")
    print(f"Input File: {input_file}")
    print(f"Output File: {output_file}")
    print()
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    
    # Load evidence sets
    print("Loading evidence sets...")
    evidence_sets = load_json_file(input_file)
    
    # Update with rich text formatting
    print("Updating instructions with rich text formatting...")
    updated_evidence_sets = update_evidence_sets_with_rich_text(evidence_sets)
    
    # Save output
    print(f"Saving to {output_file}...")
    try:
        with open(output_file, 'w') as f:
            json.dump(updated_evidence_sets, f, indent=2)
        print(f"Successfully saved updated evidence sets to {output_file}")
    except Exception as e:
        print(f"Error saving file: {e}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"SUCCESS: Evidence sets updated with rich text formatting!")
    print(f"Review the updated file: {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
