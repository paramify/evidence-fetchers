#!/usr/bin/env python3
"""
Evidence Sets Generator

This script generates a custom evidence_sets.json file based on customer selections
from the customer_config.json file and the master catalog in evidence_fetchers_catalog.json.

The script automatically escapes regex patterns in validation rules for safe JSON storage.

Usage:
    python generate_evidence_sets.py [customer_config.json] [output_file.json]

If no arguments are provided, it will use:
    - customer_config.json (default customer config)
    - evidence_sets.json (default output file)

Features:
    - Generates evidence sets from customer configuration
    - Automatically escapes regex patterns for JSON storage
    - Processes validation rules with proper JSON escaping
    - Provides detailed logging of regex processing
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any


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


def escape_regex_for_json(regex_pattern: str) -> str:
    """
    Escape a regex pattern for safe storage in JSON.
    
    Args:
        regex_pattern (str): The raw regex pattern to escape
        
    Returns:
        str: The escaped regex pattern safe for JSON storage
    """
    return json.dumps(regex_pattern)


def process_validation_rules(validation_rules: List[Any]) -> List[Dict[str, Any]]:
    """
    Process validation rules and escape regex patterns for JSON storage.
    
    Handles both string format (from catalog) and object format (from existing evidence sets).
    
    Args:
        validation_rules (List[Any]): List of validation rules (strings or objects)
        
    Returns:
        List[Dict[str, Any]]: Processed validation rules with escaped regex patterns
    """
    if not validation_rules:
        return []
    
    processed_rules = []
    for i, rule in enumerate(validation_rules):
        if isinstance(rule, str):
            # Handle string format from catalog - convert to object format
            processed_rule = {
                "id": i + 1,
                "regex": escape_regex_for_json(rule),
                "logic": "IF match.group(1) == expected_value THEN PASS"
            }
        elif isinstance(rule, dict):
            # Handle object format - escape the regex if it exists
            processed_rule = rule.copy()
            if 'regex' in rule and rule['regex']:
                processed_rule['regex'] = escape_regex_for_json(rule['regex'])
        else:
            # Skip invalid rule formats
            print(f"    Warning: Skipping invalid validation rule format: {type(rule)}")
            continue
        
        processed_rules.append(processed_rule)
    
    return processed_rules


def validate_customer_config(config: Dict[str, Any]) -> bool:
    """Validate the customer configuration structure."""
    required_keys = ['customer_configuration']
    if not all(key in config for key in required_keys):
        print("Error: Invalid customer configuration structure.")
        return False
    
    customer_config = config['customer_configuration']
    if 'selected_evidence_fetchers' not in customer_config:
        print("Error: 'selected_evidence_fetchers' not found in customer configuration.")
        return False
    
    return True


def generate_evidence_sets(catalog: Dict[str, Any], customer_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate evidence_sets.json from catalog and customer configuration."""
    
    selected_fetchers = customer_config['customer_configuration']['selected_evidence_fetchers']
    catalog_categories = catalog['evidence_fetchers_catalog']['categories']
    
    evidence_sets = {"evidence_sets": {}}
    
    # Process each category (aws, k8s, knowbe4, okta)
    for category_name, category_config in selected_fetchers.items():
        if not category_config.get('enabled', False):
            print(f"Skipping disabled category: {category_name}")
            continue
        
        if category_name not in catalog_categories:
            print(f"Warning: Category '{category_name}' not found in catalog.")
            continue
        
        category_scripts = catalog_categories[category_name]['scripts']
        selected_scripts = category_config.get('selected_scripts', [])
        
        print(f"Processing category: {category_name}")
        print(f"  Selected scripts: {len(selected_scripts)}")
        
        # Process each selected script
        for script_name in selected_scripts:
            if script_name not in category_scripts:
                print(f"  Warning: Script '{script_name}' not found in catalog for category '{category_name}'")
                continue
            
            script_info = category_scripts[script_name]
            
            # Process validation rules and escape regex patterns
            processed_validation_rules = process_validation_rules(script_info.get("validationRules", []))
            
            # Create evidence set entry
            evidence_set_entry = {
                "id": script_info["id"],
                "name": script_info["name"],
                "description": script_info["description"],
                "service": category_name.upper(),
                "instructions": script_info["instructions"],
                "validationRules": processed_validation_rules,
                # "expected_outcome" field removed
            }
            
            evidence_sets["evidence_sets"][script_name] = evidence_set_entry
            
            # Log validation rules processing
            if processed_validation_rules:
                print(f"  Added: {script_name} (with {len(processed_validation_rules)} validation rules)")
                for rule in processed_validation_rules:
                    if 'regex' in rule:
                        print(f"    - Rule {rule.get('id', 'N/A')}: Regex pattern escaped for JSON")
            else:
                print(f"  Added: {script_name}")
    
    return evidence_sets


def print_summary(evidence_sets: Dict[str, Any], customer_config: Dict[str, Any]) -> None:
    """Print a summary of the generated evidence sets."""
    customer_name = customer_config['customer_configuration'].get('customer_name', 'Unknown')
    total_scripts = len(evidence_sets['evidence_sets'])
    
    print(f"\n{'='*60}")
    print(f"EVIDENCE SETS GENERATION SUMMARY")
    print(f"{'='*60}")
    print(f"Customer: {customer_name}")
    print(f"Total Evidence Sets Generated: {total_scripts}")
    print(f"\nBreakdown by Category:")
    
    # Count by category
    category_counts = {}
    for script_name, script_info in evidence_sets['evidence_sets'].items():
        service = script_info.get('service', 'Unknown')
        category_counts[service] = category_counts.get(service, 0) + 1
    
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count} scripts")
    
    print(f"\nGenerated Evidence Sets:")
    for script_name in sorted(evidence_sets['evidence_sets'].keys()):
        print(f"  - {script_name}")


def main():
    """Main function."""
    # Default file paths
    default_customer_config = "customer_config.json"
    default_output_file = "evidence_sets.json"
    catalog_file = "evidence_fetchers_catalog.json"
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        customer_config_file = sys.argv[1]
    else:
        customer_config_file = default_customer_config
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = default_output_file
    
    print(f"Evidence Sets Generator")
    print(f"{'='*40}")
    print(f"Customer Config: {customer_config_file}")
    print(f"Output File: {output_file}")
    print(f"Catalog File: {catalog_file}")
    print()
    
    # Check if catalog file exists
    if not os.path.exists(catalog_file):
        print(f"Error: Catalog file '{catalog_file}' not found.")
        print("Please ensure the evidence_fetchers_catalog.json file exists.")
        sys.exit(1)
    
    # Load files
    print("Loading catalog...")
    catalog = load_json_file(catalog_file)
    
    print("Loading customer configuration...")
    customer_config = load_json_file(customer_config_file)
    
    # Validate customer configuration
    if not validate_customer_config(customer_config):
        sys.exit(1)
    
    # Generate evidence sets
    print("Generating evidence sets...")
    evidence_sets = generate_evidence_sets(catalog, customer_config)
    
    # Save output
    print(f"Saving to {output_file}...")
    try:
        with open(output_file, 'w') as f:
            json.dump(evidence_sets, f, indent=2)
        print(f"Successfully saved evidence sets to {output_file}")
    except Exception as e:
        print(f"Error saving file: {e}")
        sys.exit(1)
    
    # Print summary
    print_summary(evidence_sets, customer_config)
    
    print(f"\n{'='*60}")
    print(f"SUCCESS: Evidence sets generated successfully!")
    print(f"Upload the generated '{output_file}' file to Paramify.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
