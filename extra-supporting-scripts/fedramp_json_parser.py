#!/usr/bin/env python3
"""
FedRAMP JSON Parser

Parses FedRAMP JSON files from GitHub and converts them to evidence sets format.

FedRAMP JSON files are available at:
https://github.com/FedRAMP/docs/tree/main/data

Usage:
    python fedramp_json_parser.py --file FRMR.ADS.authorization-data-sharing.json --output evidence_sets.json
    python fedramp_json_parser.py --url https://raw.githubusercontent.com/FedRAMP/docs/main/data/FRMR.ADS.authorization-data-sharing.json
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


def download_json(url: str) -> Dict:
    """Download JSON file from URL."""
    print(f"Downloading from: {url}")
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"✓ Downloaded successfully")
            return data
    except Exception as e:
        raise Exception(f"Failed to download JSON: {e}")


def load_json_file(file_path: str) -> Dict:
    """Load JSON file from local path."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_standard_name(fedramp_data: Dict) -> str:
    """Extract standard name from FedRAMP JSON."""
    info = fedramp_data.get("info", {})
    short_name = info.get("short_name", "UNKNOWN")
    return short_name.upper()


def parse_fedramp_requirements(fedramp_data: Dict) -> Dict:
    """Parse FedRAMP JSON and convert to evidence sets format.
    
    FedRAMP JSON structure:
    {
      "FRR": {
        "ADS": {
          "base": {
            "requirements": [...]
          },
          "access_control": {
            "requirements": [...]
          }
        }
      },
      "FRA": {
        "ADS": {
          "requirements": [...]
        }
      }
    }
    """
    evidence_sets = {"evidence_sets": {}}
    
    # Extract standard name
    standard_name = extract_standard_name(fedramp_data)
    print(f"Processing FedRAMP standard: {standard_name}")
    
    # Get FRR (FedRAMP Requirements) section
    frr = fedramp_data.get("FRR", {})
    if not frr:
        print("Warning: No FRR section found in FedRAMP JSON")
        return evidence_sets
    
    # Process each standard in FRR
    for standard_key, standard_data in frr.items():
        if not isinstance(standard_data, dict):
            continue
        
        # Process each requirement group (base, access_control, trust_center, etc.)
        for group_key, group_data in standard_data.items():
            if not isinstance(group_data, dict):
                continue
            
            requirements = group_data.get("requirements", [])
            if not requirements:
                continue
            
            print(f"  Processing {standard_key}.{group_key}: {len(requirements)} requirements")
            
            # Get corresponding FRA (FedRAMP Assistance) requirements
            fra = fedramp_data.get("FRA", {}).get(standard_key, {})
            fra_requirements = {}
            if isinstance(fra, dict) and "requirements" in fra:
                for fra_req in fra["requirements"]:
                    applies_to = fra_req.get("applies_to")
                    if applies_to:
                        fra_requirements[applies_to] = fra_req
            
            # Process each requirement
            for req in requirements:
                req_id = req.get("id", "")
                if not req_id:
                    continue
                
                # Build evidence set entry
                name = req.get("name", req_id)
                statement = req.get("statement", "")
                
                # Get technical assistance if available
                fra_req = fra_requirements.get(req_id, {})
                fra_statement = fra_req.get("statement", "")
                
                # Combine statement and technical assistance for instructions
                instructions_parts = []
                if statement:
                    instructions_parts.append(statement)
                if fra_statement:
                    instructions_parts.append(f"\n\nTechnical Assistance:\n{fra_statement}")
                
                instructions = "\n".join(instructions_parts) if instructions_parts else "No description available."
                
                # Build description
                impact = req.get("impact", {})
                impact_levels = []
                if impact.get("low"):
                    impact_levels.append("Low")
                if impact.get("moderate"):
                    impact_levels.append("Moderate")
                if impact.get("high"):
                    impact_levels.append("High")
                
                impact_str = ", ".join(impact_levels) if impact_levels else "All"
                description = f"FedRAMP {standard_name} > {group_key.replace('_', ' ').title()}.\nImpact Levels: {impact_str}"
                
                # Add standard abbreviation to name
                name_with_prefix = f"{standard_name}: {name}"
                
                # Extract requirements (if any are referenced)
                following_info = req.get("following_information", [])
                requirements_list = []
                
                # Generate evidence key
                evidence_key = f"{standard_key.lower()}_{group_key.lower()}_{req_id.lower().replace('-', '_')}"
                
                # Create evidence set entry
                evidence_sets["evidence_sets"][evidence_key] = {
                    "id": req_id,
                    "name": name_with_prefix,
                    "description": description,
                    "instructions": instructions,
                    "service": "FEDRAMP",
                    "requirements": requirements_list,
                    "impact_levels": impact_levels,
                    "standard": standard_name,
                    "group": group_key
                }
    
    return evidence_sets


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Parse FedRAMP JSON files and convert to evidence sets format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse local file
  python fedramp_json_parser.py \\
    --file FRMR.ADS.authorization-data-sharing.json \\
    --output evidence_sets.json
  
  # Download and parse from GitHub
  python fedramp_json_parser.py \\
    --url https://raw.githubusercontent.com/FedRAMP/docs/main/data/FRMR.ADS.authorization-data-sharing.json \\
    --output evidence_sets.json
  
  # Parse multiple standards
  python fedramp_json_parser.py \\
    --file FRMR.MAS.minimum-assessment-scope.json \\
    --output mas_evidence_sets.json
        """
    )
    
    parser.add_argument(
        '--file',
        help='Path to local FedRAMP JSON file'
    )
    
    parser.add_argument(
        '--url',
        help='URL to FedRAMP JSON file (GitHub raw URL)'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        help='Path to output JSON file'
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not args.file and not args.url:
        print("Error: Must provide either --file or --url")
        sys.exit(1)
    
    if args.file and args.url:
        print("Error: Cannot provide both --file and --url")
        sys.exit(1)
    
    try:
        # Load FedRAMP JSON
        if args.url:
            fedramp_data = download_json(args.url)
        else:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File not found: {file_path}")
                sys.exit(1)
            print(f"Loading from: {file_path}")
            fedramp_data = load_json_file(str(file_path))
        
        # Parse and convert
        print("\nParsing FedRAMP requirements...")
        evidence_sets = parse_fedramp_requirements(fedramp_data)
        
        # Write output
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(evidence_sets, f, indent=2, ensure_ascii=False)
        
        evidence_count = len(evidence_sets.get("evidence_sets", {}))
        print(f"\n✓ Successfully parsed FedRAMP JSON")
        print(f"  Output: {output_path}")
        print(f"  Evidence sets: {evidence_count}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

