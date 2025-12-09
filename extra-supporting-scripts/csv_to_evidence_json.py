#!/usr/bin/env python3
"""
CSV to Evidence Sets JSON Converter

Converts CSV files (like Coalfire Evidence Request Lists) to JSON format
compatible with Paramify evidence sets.

Usage:
    python csv_to_evidence_json.py --csv input.csv --output output.json --prefix PREFIX

Example:
    python csv_to_evidence_json.py \
      --csv "Coalfire FedRAMP 20x Evidence Request List.csv" \
      --output evidence_sets.json \
      --prefix "COALFIRE"
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


def parse_requirements(requirements_str: str) -> List[str]:
    """Parse comma-separated requirements string into list."""
    if not requirements_str or not requirements_str.strip():
        return []
    
    # Split by comma and clean up
    requirements = [req.strip() for req in requirements_str.split(',')]
    # Remove empty strings
    requirements = [req for req in requirements if req]
    return requirements


def generate_reference_id(evidence_id: str, prefix: str) -> str:
    """Generate reference ID from evidence ID and prefix."""
    # Clean evidence ID (remove any non-alphanumeric except dash)
    clean_id = re.sub(r'[^A-Za-z0-9-]', '', str(evidence_id))
    return f"EVD-{clean_id}-{prefix.upper()}"


def clean_text(text: str) -> str:
    """Clean and normalize text from CSV."""
    if not text:
        return ""
    # Remove extra whitespace, normalize newlines
    text = re.sub(r'\s+', ' ', text.strip())
    # Preserve intentional newlines in instructions
    return text


def build_description(domain: str, category: str, requirements: List[str]) -> str:
    """Build description string from domain, category, and requirements."""
    parts = []
    
    if domain and category:
        parts.append(f"{domain} > {category}")
    
    if requirements:
        req_str = ", ".join(requirements)
        parts.append(f"Requirement: {req_str}")
    
    return ". ".join(parts) if parts else ""


def csv_to_evidence_json(csv_path: str, output_path: str, prefix: str = "CUSTOM") -> Dict:
    """Convert CSV file to evidence sets JSON format.
    
    Args:
        csv_path: Path to input CSV file
        output_path: Path to output JSON file
        prefix: Prefix for reference IDs (e.g., "COALFIRE", "FEDRAMP")
    
    Returns:
        Dictionary with evidence_sets structure
    """
    evidence_sets = {"evidence_sets": {}}
    
    # Expected CSV columns (case-insensitive matching)
    required_columns = {
        'evidence_id': ['evidence id', 'id', 'evidence_id'],
        'evidence_title': ['evidence title', 'title', 'evidence_title'],
        'evidence_description': ['evidence description', 'description', 'evidence_description'],
        'evidence_domain': ['evidence domain', 'domain', 'evidence_domain'],
        'evidence_category': ['evidence category', 'category', 'evidence_category'],
        'requirements': ['requirements', 'requirement', 'req']
    }
    
    print(f"Reading CSV file: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
        # Use csv.Sniffer to detect dialect
        sample = f.read(1024)
        f.seek(0)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        
        reader = csv.DictReader(f, dialect=dialect)
        
        # Clean fieldnames (remove BOM and whitespace) and create mapping
        original_to_cleaned = {}
        cleaned_fieldnames = []
        for orig_name in reader.fieldnames:
            cleaned = orig_name.strip().replace('\ufeff', '')
            original_to_cleaned[orig_name] = cleaned
            cleaned_fieldnames.append(cleaned)
        
        # Map column names (case-insensitive) - use cleaned names for matching
        column_map = {}
        for key, aliases in required_columns.items():
            for i, col_name in enumerate(cleaned_fieldnames):
                if col_name.lower() in aliases:
                    # Store original fieldname for accessing row data
                    column_map[key] = reader.fieldnames[i]
                    break
        
        # Check for required columns
        missing = [key for key in required_columns.keys() if key not in column_map]
        if missing:
            raise ValueError(f"Missing required columns: {missing}. Found columns: {cleaned_fieldnames}")
        
        # Process each row
        row_count = 0
        for row in reader:
            row_count += 1
            
            # Extract values using original fieldnames
            evidence_id = row[column_map['evidence_id']].strip() if column_map['evidence_id'] in row else ""
            if not evidence_id:
                print(f"  Warning: Row {row_count} has empty Evidence ID, skipping")
                continue
            
            title = clean_text(row.get(column_map['evidence_title'], ""))
            description = clean_text(row.get(column_map['evidence_description'], ""))
            domain = clean_text(row.get(column_map['evidence_domain'], ""))
            category = clean_text(row.get(column_map['evidence_category'], ""))
            requirements_str = row.get(column_map['requirements'], "")
            
            # Parse requirements
            requirements = parse_requirements(requirements_str)
            
            # Generate reference ID
            reference_id = generate_reference_id(evidence_id, prefix)
            
            # Build description
            desc_text = build_description(domain, category, requirements)
            
            # Create evidence set entry
            evidence_key = f"evidence_{evidence_id}_{prefix.lower()}"
            evidence_sets["evidence_sets"][evidence_key] = {
                "id": reference_id,
                "name": title,
                "description": desc_text,
                "instructions": description,
                "service": "FEDRAMP",  # Default service
                "requirements": requirements
            }
        
        print(f"  Processed {row_count} rows")
        print(f"  Created {len(evidence_sets['evidence_sets'])} evidence sets")
    
    return evidence_sets


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Convert CSV file to evidence sets JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert Coalfire CSV
  python csv_to_evidence_json.py \\
    --csv "Coalfire FedRAMP 20x Evidence Request List.csv" \\
    --output evidence_sets.json \\
    --prefix "COALFIRE"
  
  # Convert custom CSV
  python csv_to_evidence_json.py \\
    --csv input.csv \\
    --output output.json \\
    --prefix "CUSTOM"
        """
    )
    
    parser.add_argument(
        '--csv',
        required=True,
        help='Path to input CSV file'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        help='Path to output JSON file'
    )
    
    parser.add_argument(
        '--prefix',
        default='CUSTOM',
        help='Prefix for reference IDs (default: CUSTOM)'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    try:
        # Convert CSV to JSON
        evidence_sets = csv_to_evidence_json(
            str(csv_path),
            args.output,
            args.prefix
        )
        
        # Write output file
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(evidence_sets, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Successfully converted CSV to JSON")
        print(f"  Input:  {csv_path}")
        print(f"  Output: {output_path}")
        print(f"  Evidence sets: {len(evidence_sets['evidence_sets'])}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

