#!/usr/bin/env python3
"""
Select Fetchers

This script allows users to select which evidence fetcher scripts they want to use
and generates a custom evidence_sets.json file.
"""

import json
import sys
import os
from pathlib import Path


def load_json_file(file_path: str) -> dict:
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


def save_json_file(file_path: str, data: dict) -> None:
    """Save data to a JSON file with proper formatting."""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Successfully saved to {file_path}")
    except Exception as e:
        print(f"Error saving file: {e}")
        sys.exit(1)


def print_header():
    """Print the select fetchers header."""
    print("=" * 60)
    print("SELECT EVIDENCE FETCHERS")
    print("=" * 60)
    print()


def show_catalog_summary(catalog: dict):
    """Show a summary of available evidence fetchers."""
    print("Available Evidence Fetchers:")
    print()
    
    categories = catalog['evidence_fetchers_catalog']['categories']
    
    for category_name, category_data in categories.items():
        print(f"{category_name.upper()} ({len(category_data['scripts'])} scripts):")
        for script_name, script_data in category_data['scripts'].items():
            print(f"  - {script_data['name']}")
        print()


def interactive_selection(catalog: dict) -> dict:
    """Interactive selection of evidence fetchers."""
    print("Interactive Selection Mode")
    print("=" * 40)
    print()
    
    # Start with template
    template_path = "1-select-fetchers/customer_config_template.json"
    if os.path.exists(template_path):
        customer_config = load_json_file(template_path)
        print(f"✓ Loaded template from {template_path}")
    else:
        print("✗ Template not found. Creating new configuration...")
        customer_config = {
            "customer_configuration": {
                "metadata": {
                    "customer_name": "Custom Configuration",
                    "configuration_version": "1.0.0",
                    "created_date": "2025-01-15",
                    "description": "Custom evidence fetcher selection"
                },
                "selected_evidence_fetchers": {}
            }
        }
    
    categories = catalog['evidence_fetchers_catalog']['categories']
    
    for category_name, category_data in categories.items():
        print(f"\n{category_name.upper()} Category")
        print("-" * 30)
        print(f"Description: {category_data['description']}")
        print()
        
        # Ask if category should be enabled
        enable = input(f"Enable {category_name.upper()} scripts? (y/n): ").strip().lower()
        
        if enable == 'y':
            print(f"\nAvailable {category_name.upper()} scripts:")
            scripts = category_data['scripts']
            
            selected_scripts = []
            for script_name, script_data in scripts.items():
                print(f"  {script_name}: {script_data['name']}")
                print(f"    Description: {script_data['description']}")
                print(f"    Dependencies: {', '.join(script_data['dependencies'])}")
                print(f"    Tags: {', '.join(script_data['tags'])}")
                
                include = input(f"    Include this script? (y/n): ").strip().lower()
                if include == 'y':
                    selected_scripts.append(script_name)
                print()
            
            customer_config['customer_configuration']['selected_evidence_fetchers'][category_name] = {
                "enabled": True,
                "selected_scripts": selected_scripts
            }
        else:
            customer_config['customer_configuration']['selected_evidence_fetchers'][category_name] = {
                "enabled": False,
                "selected_scripts": []
            }
    
    return customer_config


def generate_evidence_sets(catalog: dict, customer_config: dict) -> dict:
    """Generate evidence sets from catalog and customer configuration."""
    selected_fetchers = customer_config['customer_configuration']['selected_evidence_fetchers']
    catalog_categories = catalog['evidence_fetchers_catalog']['categories']
    
    evidence_sets = {"evidence_sets": {}}
    
    # Process each category
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
            
            # Create evidence set entry
            evidence_set_entry = {
                "id": script_info["id"],
                "name": script_info["name"],
                "description": script_info["description"],
                "service": category_name.upper(),
                "instructions": script_info["instructions"],
                "validationRules": script_info["validation_rules"],
                # "expected_outcome" field removed
            }
            
            evidence_sets["evidence_sets"][script_name] = evidence_set_entry
            print(f"  Added: {script_name}")
    
    return evidence_sets


def print_summary(evidence_sets: dict, customer_config: dict):
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
    """Main select fetchers function."""
    print_header()
    
    # Load catalog
    catalog_path = "1-select-fetchers/evidence_fetchers_catalog.json"
    if not os.path.exists(catalog_path):
        print(f"Error: Catalog file '{catalog_path}' not found.")
        print("Please ensure you're running this from the correct directory.")
        sys.exit(1)
    
    catalog = load_json_file(catalog_path)
    print(f"✓ Loaded catalog with {len(catalog['evidence_fetchers_catalog']['categories'])} categories")
    
    # Show catalog summary
    show_catalog_summary(catalog)
    
    # Get user choice
    print("Selection Options:")
    print("1) Interactive selection (recommended)")
    print("2) Use template configuration")
    print("3) Load existing configuration")
    print()
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == '1':
        customer_config = interactive_selection(catalog)
    elif choice == '2':
        template_path = "1-select-fetchers/customer_config_template.json"
        if os.path.exists(template_path):
            customer_config = load_json_file(template_path)
            print(f"✓ Loaded template configuration")
        else:
            print("✗ Template not found. Using interactive selection instead.")
            customer_config = interactive_selection(catalog)
    elif choice == '3':
        config_path = input("Enter path to configuration file: ").strip()
        if os.path.exists(config_path):
            customer_config = load_json_file(config_path)
            print(f"✓ Loaded configuration from {config_path}")
        else:
            print("✗ Configuration file not found. Using interactive selection instead.")
            customer_config = interactive_selection(catalog)
    else:
        print("Invalid choice. Using interactive selection.")
        customer_config = interactive_selection(catalog)
    
    # Generate evidence sets
    print(f"\nGenerating evidence sets...")
    evidence_sets = generate_evidence_sets(catalog, customer_config)
    
    # Save files
    output_file = "evidence_sets.json"
    save_json_file(output_file, evidence_sets)
    
    # Save customer configuration
    config_file = "customer_config.json"
    save_json_file(config_file, customer_config)
    
    # Print summary
    print_summary(evidence_sets, customer_config)
    
    print(f"\n{'='*60}")
    print(f"SUCCESS: Evidence sets generated successfully!")
    print(f"Files created:")
    print(f"  - {output_file} (for Paramify upload)")
    print(f"  - {config_file} (your configuration)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
