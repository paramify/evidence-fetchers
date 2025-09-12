#!/usr/bin/env python3
"""
Evidence Fetcher Catalog Manager

This script helps add new evidence fetcher scripts to the catalog and update
the customer configuration template.

Usage:
    python add_evidence_fetcher.py --interactive
    python add_evidence_fetcher.py --script-file path/to/script.sh --category aws --name "Script Name"
"""

import json
import sys
import os
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import re


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


def save_json_file(file_path: str, data: Dict[str, Any]) -> None:
    """Save data to a JSON file with proper formatting."""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Successfully saved to {file_path}")
    except Exception as e:
        print(f"Error saving file: {e}")
        sys.exit(1)


def extract_script_metadata(script_path: str) -> Dict[str, Any]:
    """Extract metadata from a script file."""
    metadata = {
        "script_file": script_path,
        "name": "",
        "description": "",
        "id": "",
        "instructions": "",
        "validationRules": [],
        "dependencies": [],
        "tags": []
    }
    
    try:
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Extract name from script header comment
        name_match = re.search(r'# Helper script for (.+)', content)
        if name_match:
            metadata["name"] = name_match.group(1)
        
        # Extract description from script header
        desc_match = re.search(r'# Evidence for (.+)', content)
        if desc_match:
            metadata["description"] = f"Evidence for {desc_match.group(1)}"
        
        # Extract commands from comments
        commands = re.findall(r'#\s+(aws|kubectl|curl|python)\s+[^\n]+', content)
        if commands:
            metadata["instructions"] = f"Script: {os.path.basename(script_path)}. Commands executed: {', '.join(set(commands))}"
        
        # Extract validation rules from comments
        validation_rules = re.findall(r'#\s+Validation.*?:\s*(.+)', content, re.DOTALL)
        if validation_rules:
            # Parse validation rules (this is a simple implementation)
            metadata["validationRules"] = []
        
# Expected outcome field removed from schema
        
        # Determine dependencies based on script content
        dependencies = []
        if 'aws ' in content or 'aws-' in content:
            dependencies.append('aws-cli')
        if 'kubectl' in content:
            dependencies.append('kubectl')
        if 'curl' in content:
            dependencies.append('curl')
        if 'jq' in content:
            dependencies.append('jq')
        if script_path.endswith('.py'):
            dependencies.append('python3')
        
        metadata["dependencies"] = list(set(dependencies))
        
        # Generate tags based on content
        tags = []
        if 'encryption' in content.lower():
            tags.append('encryption')
        if 'security' in content.lower():
            tags.append('security')
        if 'high-availability' in content.lower() or 'ha' in content.lower():
            tags.append('high-availability')
        if 'iam' in content.lower():
            tags.append('iam')
        if 's3' in content.lower():
            tags.append('s3')
        if 'rds' in content.lower():
            tags.append('rds')
        if 'eks' in content.lower():
            tags.append('eks')
        if 'kubernetes' in content.lower():
            tags.append('kubernetes')
        
        metadata["tags"] = list(set(tags))
        
    except Exception as e:
        print(f"Warning: Could not extract metadata from script: {e}")
    
    return metadata


def generate_script_id(script_name: str, category: str) -> str:
    """Generate a unique ID for the script."""
    # Convert script name to ID format
    id_parts = []
    for part in script_name.split('_'):
        if part.upper() in ['AWS', 'S3', 'RDS', 'EKS', 'IAM', 'KMS', 'EFS', 'VPC', 'DNS', 'API', 'SSL', 'TLS', 'MFA', 'DoS', 'HA']:
            id_parts.append(part.upper())
        else:
            id_parts.append(part.upper())
    
    return f"EVD-{'-'.join(id_parts)}"


def interactive_mode() -> Dict[str, Any]:
    """Interactive mode for adding a new evidence fetcher."""
    print("Evidence Fetcher Catalog Manager - Interactive Mode")
    print("=" * 50)
    
    # Get script file path
    while True:
        script_path = input("Enter the path to the script file: ").strip()
        if os.path.exists(script_path):
            break
        print("File not found. Please try again.")
    
    # Get category
    categories = ['aws', 'k8s', 'knowbe4', 'okta']
    print(f"\nAvailable categories: {', '.join(categories)}")
    while True:
        category = input("Enter the category: ").strip().lower()
        if category in categories:
            break
        print("Invalid category. Please choose from the available categories.")
    
    # Extract metadata from script
    print(f"\nExtracting metadata from {script_path}...")
    metadata = extract_script_metadata(script_path)
    
    # Allow user to override extracted metadata
    print(f"\nExtracted metadata:")
    print(f"  Name: {metadata['name']}")
    print(f"  Description: {metadata['description']}")
    print(f"  Dependencies: {', '.join(metadata['dependencies'])}")
    print(f"  Tags: {', '.join(metadata['tags'])}")
    
    # Get user input for missing or incorrect metadata
    if not metadata['name']:
        metadata['name'] = input("Enter the script name: ").strip()
    
    if not metadata['description']:
        metadata['description'] = input("Enter the script description: ").strip()
    
# Expected outcome input removed from schema
    
    # Generate ID
    script_name = os.path.basename(script_path).replace('.sh', '').replace('.py', '')
    metadata['id'] = generate_script_id(script_name, category)
    
    # Get additional tags
    additional_tags = input("Enter additional tags (comma-separated, or press Enter to skip): ").strip()
    if additional_tags:
        metadata['tags'].extend([tag.strip() for tag in additional_tags.split(',')])
        metadata['tags'] = list(set(metadata['tags']))  # Remove duplicates
    
    return {
        'script_name': script_name,
        'category': category,
        'metadata': metadata
    }


def add_script_to_catalog(catalog: Dict[str, Any], script_name: str, category: str, metadata: Dict[str, Any]) -> None:
    """Add a script to the catalog."""
    if category not in catalog['evidence_fetchers_catalog']['categories']:
        print(f"Error: Category '{category}' not found in catalog.")
        sys.exit(1)
    
    # Check if script already exists
    if script_name in catalog['evidence_fetchers_catalog']['categories'][category]['scripts']:
        print(f"Warning: Script '{script_name}' already exists in category '{category}'.")
        response = input("Do you want to update it? (y/n): ").strip().lower()
        if response != 'y':
            print("Operation cancelled.")
            return
    
    # Add the script
    catalog['evidence_fetchers_catalog']['categories'][category]['scripts'][script_name] = metadata
    print(f"✓ Added script '{script_name}' to category '{category}'")


def update_customer_template(template: Dict[str, Any], script_name: str, category: str) -> None:
    """Update the customer configuration template to include the new script."""
    if category not in template['customer_configuration']['selected_evidence_fetchers']:
        print(f"Warning: Category '{category}' not found in customer template.")
        return
    
    category_config = template['customer_configuration']['selected_evidence_fetchers'][category]
    
    # Add script to the selected_scripts list if it's not already there
    if script_name not in category_config['selected_scripts']:
        category_config['selected_scripts'].append(script_name)
        print(f"✓ Added '{script_name}' to customer template for category '{category}'")
    else:
        print(f"Script '{script_name}' already exists in customer template for category '{category}'")


def validate_catalog(catalog: Dict[str, Any]) -> bool:
    """Validate the catalog structure and content."""
    print("Validating catalog...")
    
    required_keys = ['evidence_fetchers_catalog']
    if not all(key in catalog for key in required_keys):
        print("Error: Invalid catalog structure.")
        return False
    
    catalog_data = catalog['evidence_fetchers_catalog']
    if 'categories' not in catalog_data:
        print("Error: 'categories' not found in catalog.")
        return False
    
    # Validate each category and script
    for category_name, category_data in catalog_data['categories'].items():
        if 'scripts' not in category_data:
            print(f"Error: 'scripts' not found in category '{category_name}'.")
            return False
        
        for script_name, script_data in category_data['scripts'].items():
            required_script_keys = ['script_file', 'name', 'description', 'id', 'instructions', 'validationRules', 'dependencies', 'tags']
            if not all(key in script_data for key in required_script_keys):
                print(f"Error: Missing required keys in script '{script_name}' in category '{category_name}'.")
                return False
    
    print("✓ Catalog validation passed")
    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Add new evidence fetcher scripts to the catalog')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('--script-file', help='Path to the script file')
    parser.add_argument('--category', choices=['aws', 'k8s', 'knowbe4', 'okta'], help='Category for the script')
    parser.add_argument('--name', help='Name of the script')
    parser.add_argument('--validate-only', action='store_true', help='Only validate the catalog')
    
    args = parser.parse_args()
    
    # Load catalog and template
    catalog_file = 'evidence_fetchers_catalog.json'
    template_file = 'customer_config_template.json'
    
    if not os.path.exists(catalog_file):
        print(f"Error: Catalog file '{catalog_file}' not found.")
        sys.exit(1)
    
    if not os.path.exists(template_file):
        print(f"Error: Template file '{template_file}' not found.")
        sys.exit(1)
    
    catalog = load_json_file(catalog_file)
    template = load_json_file(template_file)
    
    # Validate catalog if requested
    if args.validate_only:
        if validate_catalog(catalog):
            print("✓ Catalog is valid")
            sys.exit(0)
        else:
            print("✗ Catalog validation failed")
            sys.exit(1)
    
    # Get script information
    if args.interactive:
        script_info = interactive_mode()
    elif args.script_file and args.category:
        if not os.path.exists(args.script_file):
            print(f"Error: Script file '{args.script_file}' not found.")
            sys.exit(1)
        
        metadata = extract_script_metadata(args.script_file)
        script_name = args.name or os.path.basename(args.script_file).replace('.sh', '').replace('.py', '')
        metadata['name'] = metadata['name'] or script_name
        metadata['id'] = generate_script_id(script_name, args.category)
        
        script_info = {
            'script_name': script_name,
            'category': args.category,
            'metadata': metadata
        }
    else:
        print("Error: Either --interactive or --script-file with --category must be specified.")
        parser.print_help()
        sys.exit(1)
    
    # Add script to catalog
    add_script_to_catalog(catalog, script_info['script_name'], script_info['category'], script_info['metadata'])
    
    # Update customer template
    update_customer_template(template, script_info['script_name'], script_info['category'])
    
    # Save updated files
    save_json_file(catalog_file, catalog)
    save_json_file(template_file, template)
    
    # Validate the updated catalog
    if validate_catalog(catalog):
        print(f"\n✓ Successfully added '{script_info['script_name']}' to the catalog!")
        print(f"  Category: {script_info['category']}")
        print(f"  ID: {script_info['metadata']['id']}")
        print(f"  Dependencies: {', '.join(script_info['metadata']['dependencies'])}")
        print(f"  Tags: {', '.join(script_info['metadata']['tags'])}")
        print(f"\nNext steps:")
        print(f"  1. Test the new script")
        print(f"  2. Update documentation if needed")
        print(f"  3. Run 'python generate_evidence_sets.py' to test the updated catalog")
    else:
        print("✗ Catalog validation failed after adding the script")
        sys.exit(1)


if __name__ == "__main__":
    main()
