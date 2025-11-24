#!/usr/bin/env python3
"""
Evidence Requirement Mapping

This script reads existing evidence <-> requirement mappings from Paramify
machine readable YAML file and adds the requirement mappings to the evidence set JSON.
"""

import json
import os
import sys
import yaml
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


def load_yaml_file(file_path: str) -> dict:
    """Load and parse a YAML file."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in '{file_path}': {e}")
        sys.exit(1)


def print_header():
    """Print the evidence requirement mapping header."""
    print("=" * 60)
    print("EVIDENCE REQUIREMENT MAPPING")
    print("=" * 60)
    print()


def find_yaml_files():
    """Find Paramify YAML files in the repository."""
    yaml_files = []
    
    # Look for YAML files in the root directory
    for file_path in Path(".").glob("*.yaml"):
        yaml_files.append(str(file_path))
    
    # Look for YAML files in the current directory
    for file_path in Path(".").glob("*.yml"):
        yaml_files.append(str(file_path))
    
    return yaml_files


def extract_evidence_mappings(yaml_data: dict) -> dict:
    """Extract evidence mappings from YAML data."""
    mappings = {}
    
    # This is a simplified extraction - you may need to adjust based on your YAML structure
    if 'evidence' in yaml_data:
        for evidence_item in yaml_data['evidence']:
            if 'id' in evidence_item and 'requirements' in evidence_item:
                mappings[evidence_item['id']] = evidence_item['requirements']
    
    return mappings


def add_requirements_to_evidence_sets(evidence_sets: dict, mappings: dict) -> dict:
    """Add requirement mappings to evidence sets."""
    updated_evidence_sets = evidence_sets.copy()
    
    for script_name, script_data in updated_evidence_sets['evidence_sets'].items():
        script_id = script_data.get('id')
        
        if script_id in mappings:
            script_data['requirements'] = mappings[script_id]
            print(f"  ✓ Added requirements to {script_name}")
        else:
            print(f"  ⚠ No requirements found for {script_name} (ID: {script_id})")
    
    return updated_evidence_sets


def main():
    """Main evidence requirement mapping function."""
    print_header()
    
    print("This script will map evidence to requirements from Paramify YAML files")
    print("and add the requirement mappings to the evidence set JSON.")
    print()
    
    print("Available mapping options:")
    print("1) Basic mapping (simple)")
    print("2) Advanced KSI mapping (recommended)")
    print("3) Analyze existing mappings")
    print()
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == '1':
        print("\nRunning basic mapping...")
        # Use the simple mapping logic from the original script
        run_basic_mapping()
    elif choice == '2':
        print("\nRunning advanced KSI mapping...")
        # Use the advanced script
        import subprocess
        import sys
        try:
            subprocess.run([sys.executable, "extract_evidence_ksi_mappings.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running advanced mapping: {e}")
    elif choice == '3':
        print("\nAnalyzing existing mappings...")
        # Use the analysis script
        import subprocess
        import sys
        try:
            subprocess.run([sys.executable, "mapping_summary.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running analysis: {e}")
    else:
        print("Invalid choice. Please enter 1-3.")


def run_basic_mapping():
    """Run the basic mapping functionality."""
    # Check for evidence_sets.json
    if not os.path.exists("../evidence_sets.json"):
        print("✗ evidence_sets.json not found")
        print("Please run 'Select Fetchers' (option 1) first to generate evidence sets.")
        return
    
    # Find YAML files
    yaml_files = find_yaml_files()
    
    if not yaml_files:
        print("✗ No YAML files found")
        print("Please ensure you have a Paramify machine readable YAML file in the repository.")
        return
    
    print(f"Found {len(yaml_files)} YAML file(s):")
    for yaml_file in yaml_files:
        print(f"  • {yaml_file}")
    print()
    
    # Let user select YAML file
    if len(yaml_files) == 1:
        selected_yaml = yaml_files[0]
        print(f"Using {selected_yaml}")
    else:
        print("Select a YAML file to use:")
        for i, yaml_file in enumerate(yaml_files, 1):
            print(f"  {i}) {yaml_file}")
        
        try:
            choice = int(input("Enter your choice: ")) - 1
            if 0 <= choice < len(yaml_files):
                selected_yaml = yaml_files[choice]
            else:
                print("Invalid choice.")
                return
        except ValueError:
            print("Invalid input.")
            return
    
    # Load YAML file
    print(f"\nLoading {selected_yaml}...")
    yaml_data = load_yaml_file(selected_yaml)
    
    # Extract evidence mappings
    print("Extracting evidence mappings...")
    mappings = extract_evidence_mappings(yaml_data)
    
    if not mappings:
        print("✗ No evidence mappings found in YAML file")
        print("Please check the YAML file structure.")
        return
    
    print(f"✓ Found {len(mappings)} evidence mappings")
    
    # Load evidence sets
    print("\nLoading evidence sets...")
    evidence_sets = load_json_file("../evidence_sets.json")
    
    # Add requirements to evidence sets
    print("\nAdding requirements to evidence sets...")
    updated_evidence_sets = add_requirements_to_evidence_sets(evidence_sets, mappings)
    
    # Save updated evidence sets
    output_file = "evidence_sets_with_requirements.json"
    with open(output_file, 'w') as f:
        json.dump(updated_evidence_sets, f, indent=2)
    
    print(f"\n✓ Updated evidence sets saved to {output_file}")
    
    # Show summary
    print(f"\n{'='*60}")
    print("MAPPING SUMMARY")
    print(f"{'='*60}")
    print(f"YAML file: {selected_yaml}")
    print(f"Evidence mappings found: {len(mappings)}")
    print(f"Evidence sets updated: {len(updated_evidence_sets['evidence_sets'])}")
    print(f"Output file: {output_file}")
    print()
    print("You can now use the updated evidence sets file for Paramify upload.")


if __name__ == "__main__":
    main()
