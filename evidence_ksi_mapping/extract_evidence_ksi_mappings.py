#!/usr/bin/env python3
"""
Script to extract evidence-KSI associations from the Paramify machine readable YAML file
and update the evidence_sets.json with the corresponding KSI requirements.

Usage:
    python extract_evidence_ksi_mappings.py [yaml_file] [evidence_sets_file] [output_file]
    
Arguments:
    yaml_file: Path to the machine readable YAML file (default: ../8_29_25_paramify_coalfire_20x_machine_readable.yaml)
    evidence_sets_file: Path to the evidence_sets.json file (default: ../evidence_sets.json)
    output_file: Path for the output file (default: evidence_sets_with_requirements.json)

Examples:
    python extract_evidence_ksi_mappings.py
    python extract_evidence_ksi_mappings.py my_assessment.yaml
    python extract_evidence_ksi_mappings.py my_assessment.yaml my_evidence_sets.json my_output.json
"""

import yaml
import json
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple

def load_yaml_file(file_path: str) -> dict:
    """Load and parse the YAML file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def load_evidence_sets(file_path: str) -> dict:
    """Load the current evidence_sets.json file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def extract_script_name_from_reference(reference: str) -> str:
    """Extract script name from artifact reference."""
    if not reference:
        return ""
    
    # Look for .sh files in the reference
    match = re.search(r'([^/]+\.sh)', reference)
    if match:
        return match.group(1)
    
    # Look for script names in GitHub URLs
    if 'github.com' in reference:
        match = re.search(r'/([^/]+\.sh)', reference)
        if match:
            return match.group(1)
    
    return ""

def extract_evidence_ksi_mappings(yaml_data: dict) -> Dict[str, Set[str]]:
    """
    Extract evidence to KSI mappings from the YAML data.
    Returns a dictionary mapping evidence names to sets of KSI short names.
    """
    evidence_ksi_mappings = {}
    
    # Navigate through the YAML structure
    assessments = yaml_data.get('Package', {}).get('Assessments', [])
    
    for assessment in assessments:
        assessment_data = assessment.get('Assessment', {})
        ksis = assessment_data.get('KSIs', [])
        
        for ksi in ksis:
            ksi_data = ksi.get('KSI', {})
            ksi_name = ksi_data.get('name', '')
            ksi_short_name = ksi_data.get('shortName', '')
            
            validations = ksi_data.get('Validations', [])
            
            for validation in validations:
                validation_data = validation.get('validation', {})
                validation_short_name = validation_data.get('shortName', '')
                
                # Get evidences for this validation
                evidences = validation_data.get('Evidences', [])
                
                for evidence in evidences:
                    evidence_data = evidence.get('evidence', {})
                    evidence_name = evidence_data.get('name', '').strip()
                    
                    if not evidence_name:
                        continue
                    
                    # Extract script names from artifacts
                    artifacts = evidence_data.get('Artifacts', [])
                    script_names = set()
                    
                    for artifact in artifacts:
                        artifact_data = artifact.get('artifact', {})
                        reference = artifact_data.get('reference', '')
                        script_name = extract_script_name_from_reference(reference)
                        if script_name:
                            script_names.add(script_name)
                    
                    # Create mapping key - use evidence name as primary key
                    if evidence_name not in evidence_ksi_mappings:
                        evidence_ksi_mappings[evidence_name] = set()
                    
                    # Add the validation short name (KSI ID)
                    if validation_short_name:
                        evidence_ksi_mappings[evidence_name].add(validation_short_name)
                    
                    # Also map by script names if available
                    for script_name in script_names:
                        script_key = f"script:{script_name}"
                        if script_key not in evidence_ksi_mappings:
                            evidence_ksi_mappings[script_key] = set()
                        if validation_short_name:
                            evidence_ksi_mappings[script_key].add(validation_short_name)
    
    return evidence_ksi_mappings

def map_evidence_sets_to_ksis(evidence_sets: dict, evidence_ksi_mappings: Dict[str, Set[str]]) -> dict:
    """
    Map evidence sets to their corresponding KSI requirements.
    """
    updated_evidence_sets = evidence_sets.copy()
    
    for evidence_key, evidence_data in evidence_sets.get('evidence_sets', {}).items():
        evidence_name = evidence_data.get('name', '')
        instructions = evidence_data.get('instructions', '')
        
        # Extract script name from instructions
        script_match = re.search(r'Script:\s*([^.\s]+\.sh)', instructions)
        script_name = script_match.group(1) if script_match else ""
        
        # Find matching KSIs
        matching_ksis = set()
        
        # Try to match by evidence name (exact match)
        if evidence_name in evidence_ksi_mappings:
            matching_ksis.update(evidence_ksi_mappings[evidence_name])
        
        # Try to match by evidence name with common variations
        # Remove common suffixes/prefixes that might differ between YAML and evidence sets
        base_name = evidence_name
        for suffix in [' validation', ' script', ' (kubectl)', ' Status', ' Rules']:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break
        
        # Try matching the base name
        if base_name != evidence_name and base_name in evidence_ksi_mappings:
            matching_ksis.update(evidence_ksi_mappings[base_name])
        
        # Also try adding common variations to see if they match
        for variation in [' validation', ' script', ' (kubectl)', ' Status', ' Rules']:
            variation_name = evidence_name + variation
            if variation_name in evidence_ksi_mappings:
                matching_ksis.update(evidence_ksi_mappings[variation_name])
        
        # Try to match by script name
        if script_name:
            script_key = f"script:{script_name}"
            if script_key in evidence_ksi_mappings:
                matching_ksis.update(evidence_ksi_mappings[script_key])
        
        # Note: Removed overly aggressive partial matching that was causing false positives
        # Only use exact evidence name matches and script-based matches for accuracy
        
        # Add requirements field to evidence data
        if matching_ksis:
            evidence_data['requirements'] = sorted(list(matching_ksis))
        else:
            evidence_data['requirements'] = []
    
    return updated_evidence_sets

def save_updated_evidence_sets(evidence_sets: dict, output_path: str):
    """Save the updated evidence sets to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(evidence_sets, file, indent=2, ensure_ascii=False)

def print_mapping_summary(evidence_ksi_mappings: Dict[str, Set[str]], evidence_sets: dict):
    """Print a summary of the mappings found."""
    print("=== Evidence-KSI Mapping Summary ===")
    print(f"Total evidence mappings found: {len(evidence_ksi_mappings)}")
    
    print("\n=== Evidence Mappings ===")
    for evidence_name, ksis in evidence_ksi_mappings.items():
        print(f"{evidence_name}: {sorted(ksis)}")
    
    print("\n=== Evidence Sets with Requirements ===")
    for evidence_key, evidence_data in evidence_sets.get('evidence_sets', {}).items():
        requirements = evidence_data.get('requirements', [])
        if requirements:
            print(f"{evidence_key}: {requirements}")
        else:
            print(f"{evidence_key}: No requirements mapped")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract evidence-KSI associations from Paramify machine readable YAML file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s my_assessment.yaml
  %(prog)s my_assessment.yaml my_evidence_sets.json my_output.json
        """
    )
    
    parser.add_argument(
        'yaml_file',
        nargs='?',
        default='../8_29_25_paramify_coalfire_20x_machine_readable.yaml',
        help='Path to the machine readable YAML file (default: %(default)s)'
    )
    
    parser.add_argument(
        'evidence_sets_file',
        nargs='?',
        default='../evidence_sets.json',
        help='Path to the evidence_sets.json file (default: %(default)s)'
    )
    
    parser.add_argument(
        'output_file',
        nargs='?',
        default='evidence_sets_with_requirements.json',
        help='Path for the output file (default: %(default)s)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()

def validate_files(yaml_file: str, evidence_sets_file: str):
    """Validate that input files exist."""
    if not Path(yaml_file).exists():
        print(f"Error: YAML file '{yaml_file}' not found.")
        sys.exit(1)
    
    if not Path(evidence_sets_file).exists():
        print(f"Error: Evidence sets file '{evidence_sets_file}' not found.")
        sys.exit(1)

def main():
    """Main function to extract mappings and update evidence sets."""
    args = parse_arguments()
    
    # Validate input files
    validate_files(args.yaml_file, args.evidence_sets_file)
    
    if args.verbose:
        print(f"YAML file: {args.yaml_file}")
        print(f"Evidence sets file: {args.evidence_sets_file}")
        print(f"Output file: {args.output_file}")
        print()
    
    print("Loading YAML file...")
    yaml_data = load_yaml_file(args.yaml_file)
    
    print("Extracting evidence-KSI mappings...")
    evidence_ksi_mappings = extract_evidence_ksi_mappings(yaml_data)
    
    print("Loading current evidence sets...")
    evidence_sets = load_evidence_sets(args.evidence_sets_file)
    
    print("Mapping evidence sets to KSIs...")
    updated_evidence_sets = map_evidence_sets_to_ksis(evidence_sets, evidence_ksi_mappings)
    
    print("Saving updated evidence sets...")
    save_updated_evidence_sets(updated_evidence_sets, args.output_file)
    
    print("Printing mapping summary...")
    print_mapping_summary(evidence_ksi_mappings, updated_evidence_sets)
    
    print(f"\nUpdated evidence sets saved to: {args.output_file}")

if __name__ == "__main__":
    main()
