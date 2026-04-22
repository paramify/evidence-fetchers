#!/usr/bin/env python3
"""
Evidence Sets Generator

This script generates a custom evidence_sets.json file based on customer selections
from the customer_config.json file and the master catalog in evidence_fetchers_catalog.json.

The script automatically escapes regex patterns in validation rules for safe JSON storage
and converts plain text instructions to rich text format with consistent layout.

Usage:
    python generate_evidence_sets.py [customer_config.json] [output_file.json]

If no arguments are provided, it will use:
    - customer_config.json (default customer config)
    - evidence_sets.json (default output file)

Features:
    - Generates evidence sets from customer configuration
    - Converts instructions to rich text format with consistent layout
    - Automatically escapes regex patterns for JSON storage
    - Processes validation rules with proper JSON escaping
    - Provides detailed logging of regex processing
"""

import json
import sys
import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Any, Optional
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
            processed_validation_rules = process_validation_rules(script_info.get("validation_rules", []))
            
            # Convert instructions to rich text format
            rich_text_instructions = convert_instructions_to_rich_text(
                script_info["instructions"], 
                processed_validation_rules
            )
            
            # Create evidence set entry
            evidence_set_entry = {
                "id": script_info["id"],
                "name": script_info["name"],
                "description": script_info["description"],
                "service": category_name.upper(),
                "instructions": rich_text_instructions,
                "validationRules": processed_validation_rules,
                # Include script_file from catalog for proper script path resolution
                "script_file": script_info.get("script_file", ""),
                # Carry forward catalog associations so the pusher can wire them
                # up against the Paramify API at runtime.
                "solution_capabilities": script_info.get("solution_capabilities", []),
                "controls": script_info.get("controls", []),
                "validators": script_info.get("validators", []),
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


FREQUENCY_CHOICES = [
    ("NOT_SET", "no schedule"),
    ("DAILY", "every day"),
    ("THREE_DAY", "every 3 days  (FedRAMP 20x Class C / Moderate)"),
    ("WEEKLY", "every 7 days  (FedRAMP 20x Class D / Low)"),
    ("BIWEEKLY", "every 2 weeks"),
    ("MONTHLY", "every month"),
    ("QUARTERLY", "every 3 months"),
    ("BIANNUAL", "every 6 months"),
    ("ANNUAL", "every year"),
]
FREQUENCY_DEFAULT_IDX = 2  # 0-based index of THREE_DAY in FREQUENCY_CHOICES


def _prompt_choice(prompt: str, choices: List[str], default_idx: int) -> int:
    """Ask the user to pick a numbered option. Returns the 1-based index chosen."""
    while True:
        raw = input(f"{prompt} [default {default_idx + 1}]: ").strip()
        if not raw:
            return default_idx + 1
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return int(raw)
        print(f"  Please enter a number 1-{len(choices)}.")


def _select_frequency() -> str:
    """Show the frequency menu and return the chosen enum value."""
    print("\nChoose frequency:")
    for i, (value, hint) in enumerate(FREQUENCY_CHOICES, start=1):
        print(f"  {i}) {value:<10} — {hint}")
    idx = _prompt_choice("Choice", [c[0] for c in FREQUENCY_CHOICES], FREQUENCY_DEFAULT_IDX)
    return FREQUENCY_CHOICES[idx - 1][0]


def _prompt_start_date() -> Optional[str]:
    """Ask the user when collection should start. Returns ISO YYYY-MM-DD or None."""
    today = date.today().isoformat()
    print()
    print("Apply a start date to these evidence sets?")
    print(f"  1) Today ({today}) — start now")
    print("  2) Pick a future date (YYYY-MM-DD)")
    print("  3) Skip — leave start date unset")
    choice = _prompt_choice("Choice", ["today", "future", "skip"], 0)

    if choice == 1:
        return today
    if choice == 3:
        return None

    # choice == 2: accept a YYYY-MM-DD from the user
    while True:
        raw = input("Enter start date (YYYY-MM-DD): ").strip()
        try:
            parsed = date.fromisoformat(raw)
        except ValueError:
            print("  Not a valid YYYY-MM-DD date. Try again.")
            continue
        if parsed < date.today():
            print(f"  {raw} is in the past. Start date must be today or later.")
            continue
        return parsed.isoformat()


def prompt_frequency_config(evidence_sets: Dict[str, Any]) -> None:
    """Optionally set a `frequency` on each evidence set in-place.

    Mutates the `evidence_sets` dict directly. Silently returns if stdin is
    not a TTY (e.g. when called from an orchestrator), leaving frequency unset.
    """
    if not sys.stdin.isatty():
        return
    if not evidence_sets.get("evidence_sets"):
        return

    print()
    print("=" * 60)
    print("EVIDENCE COLLECTION FREQUENCY (OPTIONAL)")
    print("=" * 60)
    print("Set how often each evidence set should be refreshed. This maps to")
    print("the `frequency` field on POST /evidence and drives the collection")
    print("schedule shown in Paramify.")
    print()
    print("FedRAMP 20x reference cadence for automated (machine-based) evidence:")
    print("  • Class C (Moderate):  every 3 days   (THREE_DAY)")
    print("  • Class D (Low):       every 7 days   (WEEKLY)")
    print()
    print("How would you like to set frequency?")
    print("  1) Apply ONE frequency to ALL evidence sets")
    print("  2) Set frequency per-fetcher (individually)")
    print("  3) Skip — leave frequency unset (can be set later in the Paramify UI)")
    mode = _prompt_choice("Choice", ["all", "per-fetcher", "skip"], 2)

    if mode == 3:
        print("Skipping frequency configuration.")
        return

    if mode == 1:
        freq = _select_frequency()
        if freq == "NOT_SET":
            print("Leaving frequency unset (NOT_SET will not be sent to Paramify).")
            return
        for entry in evidence_sets["evidence_sets"].values():
            entry["frequency"] = freq
        print(f"Applied frequency '{freq}' to {len(evidence_sets['evidence_sets'])} evidence sets.")
    else:
        # mode == 2: per-fetcher
        print("\nSetting frequency for each evidence set. Press Enter to accept default.")
        for script_name, entry in evidence_sets["evidence_sets"].items():
            print(f"\n--- {script_name} ({entry.get('id', '')}) ---")
            freq = _select_frequency()
            if freq != "NOT_SET":
                entry["frequency"] = freq

    # Shared start date for every entry that ended up with a frequency.
    scheduled = [e for e in evidence_sets["evidence_sets"].values() if e.get("frequency")]
    if not scheduled:
        return
    start = _prompt_start_date()
    if not start:
        return
    for entry in scheduled:
        entry["startDate"] = start
    print(f"Applied start date '{start}' to {len(scheduled)} evidence set{'s' if len(scheduled) != 1 else ''}.")


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

    # Optional: interactive frequency configuration (skipped in non-TTY runs)
    prompt_frequency_config(evidence_sets)

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
