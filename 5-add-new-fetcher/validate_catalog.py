#!/usr/bin/env python3
"""
Catalog Validation Script

This script validates the integrity of the evidence fetchers catalog and
ensures all scripts referenced in the catalog actually exist.

Usage:
    python validate_catalog.py
    python validate_catalog.py --fix-missing
"""

import json
import sys
import os
import argparse
from pathlib import Path
from typing import Dict, List, Any, Set


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


def validate_catalog_structure(catalog: Dict[str, Any]) -> bool:
    """Validate the basic structure of the catalog."""
    print("Validating catalog structure...")
    
    # Check top-level structure
    if 'evidence_fetchers_catalog' not in catalog:
        print("✗ Error: 'evidence_fetchers_catalog' not found at root level")
        return False
    
    catalog_data = catalog['evidence_fetchers_catalog']
    
    # Check required metadata
    required_metadata = ['version', 'description', 'last_updated']
    for field in required_metadata:
        if field not in catalog_data:
            print(f"✗ Error: Missing metadata field '{field}'")
            return False
    
    # Check categories structure
    if 'categories' not in catalog_data:
        print("✗ Error: 'categories' not found in catalog")
        return False
    
    print("✓ Catalog structure is valid")
    return True


def validate_categories(catalog: Dict[str, Any]) -> bool:
    """Validate all categories and their scripts."""
    print("Validating categories and scripts...")
    
    categories = catalog['evidence_fetchers_catalog']['categories']
    valid_categories = ['aws', 'k8s', 'knowbe4', 'okta']
    
    for category_name, category_data in categories.items():
        if category_name not in valid_categories:
            print(f"✗ Error: Unknown category '{category_name}'")
            return False
        
        # Check category structure
        required_category_fields = ['name', 'description', 'scripts']
        for field in required_category_fields:
            if field not in category_data:
                print(f"✗ Error: Missing field '{field}' in category '{category_name}'")
                return False
        
        # Validate each script in the category
        for script_name, script_data in category_data['scripts'].items():
            if not validate_script_metadata(script_name, script_data, category_name):
                return False
    
    print("✓ All categories and scripts are valid")
    return True


def validate_script_metadata(script_name: str, script_data: Dict[str, Any], category: str) -> bool:
    """Validate individual script metadata."""
    required_fields = [
        'script_file', 'name', 'description', 'id', 'instructions',
        'validationRules', 'dependencies', 'tags'
    ]
    
    for field in required_fields:
        if field not in script_data:
            print(f"✗ Error: Missing field '{field}' in script '{script_name}' (category: {category})")
            return False
    
    # Validate ID format
    if not script_data['id'].startswith('EVD-'):
        print(f"✗ Error: Invalid ID format '{script_data['id']}' in script '{script_name}' (should start with 'EVD-')")
        return False
    
    # Validate dependencies are in expected list
    valid_dependencies = ['aws-cli', 'kubectl', 'curl', 'jq', 'python3']
    for dep in script_data['dependencies']:
        if dep not in valid_dependencies:
            print(f"⚠ Warning: Unknown dependency '{dep}' in script '{script_name}'")
    
    # Validate tags are not empty
    if not script_data['tags']:
        print(f"⚠ Warning: No tags specified for script '{script_name}'")
    
    return True


def validate_script_files_exist(catalog: Dict[str, Any]) -> List[str]:
    """Check if all script files referenced in the catalog actually exist."""
    print("Validating script files exist...")
    
    missing_files = []
    categories = catalog['evidence_fetchers_catalog']['categories']
    
    for category_name, category_data in categories.items():
        for script_name, script_data in category_data['scripts'].items():
            script_file = script_data['script_file']
            
            if not os.path.exists(script_file):
                missing_files.append(f"{script_name} ({category_name}): {script_file}")
                print(f"✗ Missing file: {script_file} (script: {script_name}, category: {category_name})")
            else:
                print(f"✓ Found: {script_file}")
    
    if missing_files:
        print(f"\n✗ Found {len(missing_files)} missing script files")
        return missing_files
    else:
        print("✓ All script files exist")
        return []


def validate_script_files_not_in_catalog() -> List[str]:
    """Find script files that exist but are not in the catalog."""
    print("Checking for script files not in catalog...")
    
    # Find all script files in the fetchers directory
    fetchers_dir = Path('fetchers')
    if not fetchers_dir.exists():
        print("⚠ Warning: 'fetchers' directory not found")
        return []
    
    script_files = []
    for script_file in fetchers_dir.rglob('*.sh'):
        script_files.append(str(script_file))
    for script_file in fetchers_dir.rglob('*.py'):
        script_files.append(str(script_file))
    
    # Get all script files referenced in catalog
    catalog = load_json_file('evidence_fetchers_catalog.json')
    catalog_files = set()
    
    for category_data in catalog['evidence_fetchers_catalog']['categories'].values():
        for script_data in category_data['scripts'].values():
            catalog_files.add(script_data['script_file'])
    
    # Find files not in catalog
    uncatalogued_files = []
    for script_file in script_files:
        if script_file not in catalog_files:
            uncatalogued_files.append(script_file)
            print(f"⚠ Found uncatalogued script: {script_file}")
    
    if uncatalogued_files:
        print(f"\n⚠ Found {len(uncatalogued_files)} script files not in catalog")
        return uncatalogued_files
    else:
        print("✓ All script files are catalogued")
        return []


def validate_customer_template(catalog: Dict[str, Any]) -> bool:
    """Validate that the customer template includes all catalogued scripts."""
    print("Validating customer template...")
    
    try:
        template = load_json_file('customer_config_template.json')
    except:
        print("⚠ Warning: Could not load customer_config_template.json")
        return True
    
    template_scripts = set()
    for category_data in template['customer_configuration']['selected_evidence_fetchers'].values():
        template_scripts.update(category_data.get('selected_scripts', []))
    
    catalog_scripts = set()
    for category_data in catalog['evidence_fetchers_catalog']['categories'].values():
        catalog_scripts.update(category_data['scripts'].keys())
    
    missing_in_template = catalog_scripts - template_scripts
    extra_in_template = template_scripts - catalog_scripts
    
    if missing_in_template:
        print(f"✗ Scripts in catalog but not in template: {missing_in_template}")
        return False
    
    if extra_in_template:
        print(f"✗ Scripts in template but not in catalog: {extra_in_template}")
        return False
    
    print("✓ Customer template is in sync with catalog")
    return True


def validate_id_uniqueness(catalog: Dict[str, Any]) -> bool:
    """Validate that all script IDs are unique."""
    print("Validating ID uniqueness...")
    
    all_ids = []
    for category_data in catalog['evidence_fetchers_catalog']['categories'].values():
        for script_data in category_data['scripts'].values():
            all_ids.append(script_data['id'])
    
    if len(all_ids) != len(set(all_ids)):
        duplicates = [id for id in all_ids if all_ids.count(id) > 1]
        print(f"✗ Duplicate IDs found: {set(duplicates)}")
        return False
    
    print("✓ All IDs are unique")
    return True


def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate the evidence fetchers catalog')
    parser.add_argument('--fix-missing', action='store_true', help='Attempt to fix missing files')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    print("Evidence Fetchers Catalog Validation")
    print("=" * 40)
    
    # Load catalog
    catalog = load_json_file('evidence_fetchers_catalog.json')
    
    # Run all validations
    validations = [
        ("Structure", lambda: validate_catalog_structure(catalog)),
        ("Categories", lambda: validate_categories(catalog)),
        ("ID Uniqueness", lambda: validate_id_uniqueness(catalog)),
        ("Customer Template", lambda: validate_customer_template(catalog))
    ]
    
    all_passed = True
    for validation_name, validation_func in validations:
        print(f"\n{validation_name} Validation:")
        if not validation_func():
            all_passed = False
    
    # Check for missing files
    print(f"\nFile Existence Validation:")
    missing_files = validate_script_files_exist(catalog)
    
    # Check for uncatalogued files
    print(f"\nUncatalogued Files Check:")
    uncatalogued_files = validate_script_files_not_in_catalog()
    
    # Summary
    print(f"\n{'='*40}")
    print("VALIDATION SUMMARY")
    print(f"{'='*40}")
    
    if all_passed and not missing_files:
        print("✓ All validations passed!")
        if uncatalogued_files:
            print(f"⚠ Note: {len(uncatalogued_files)} script files are not in the catalog")
            print("  Consider adding them using: python add_evidence_fetcher.py --interactive")
        return 0
    else:
        print("✗ Some validations failed!")
        if missing_files:
            print(f"  - {len(missing_files)} missing script files")
        return 1


if __name__ == "__main__":
    sys.exit(main())
