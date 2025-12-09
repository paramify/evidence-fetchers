#!/usr/bin/env python3
"""
JSON to Paramify Evidence Sets Uploader

Uploads evidence sets from JSON file to Paramify using paramify_pusher.

Usage:
    python json_to_paramify.py --json evidence_sets.json [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path to import paramify_pusher
sys.path.append(str(Path(__file__).parent.parent / "2-create-evidence-sets"))
from paramify_pusher import ParamifyPusher


def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = Path(".env")
    if env_file.exists():
        print(f"Loading environment variables from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value


def load_evidence_sets(json_path: str) -> Dict:
    """Load evidence sets from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both formats: {"evidence_sets": {...}} and {"evidenceRequests": {...}}
    if "evidence_sets" in data:
        return data
    elif "evidenceRequests" in data:
        # Convert old format to new format
        evidence_sets = {"evidence_sets": {}}
        for key, value in data["evidenceRequests"].items():
            evidence_sets["evidence_sets"][key] = {
                "id": value.get("referenceId", key),
                "name": value.get("name", ""),
                "description": value.get("description", ""),
                "instructions": value.get("instructions", ""),
                "service": value.get("service", "FEDRAMP"),
                "requirements": value.get("requirements", [])
            }
        return evidence_sets
    else:
        raise ValueError("JSON file must contain 'evidence_sets' or 'evidenceRequests' key")


def upload_evidence_sets(
    evidence_sets: Dict,
    api_token: str,
    base_url: str,
    dry_run: bool = False
) -> tuple[List[Dict], int, int]:
    """Upload evidence sets to Paramify.
    
    Returns:
        tuple: (successful_uploads, failed_uploads, skipped_uploads)
    """
    pusher = ParamifyPusher(api_token, base_url)
    
    evidence_sets_dict = evidence_sets.get("evidence_sets", {})
    total = len(evidence_sets_dict)
    
    print(f"\nProcessing {total} evidence sets...")
    print("=" * 60)
    
    successful = []
    failed = []
    skipped = []
    
    for idx, (key, evidence_set_data) in enumerate(evidence_sets_dict.items(), 1):
        reference_id = evidence_set_data.get("id", key)
        name = evidence_set_data.get("name", "Unknown")
        
        print(f"\n[{idx}/{total}] {reference_id}: {name}")
        
        if dry_run:
            print(f"  [DRY RUN] Would create/update evidence set")
            successful.append({
                "key": key,
                "reference_id": reference_id,
                "name": name,
                "status": "dry_run"
            })
            continue
        
        try:
            # Get or create evidence set
            evidence_id = pusher.get_or_create_evidence_set(evidence_set_data)
            
            if evidence_id:
                print(f"  ✓ Successfully processed")
                successful.append({
                    "key": key,
                    "reference_id": reference_id,
                    "name": name,
                    "evidence_id": evidence_id,
                    "status": "success"
                })
            else:
                print(f"  ✗ Failed to create/update evidence set")
                failed.append({
                    "key": key,
                    "reference_id": reference_id,
                    "name": name,
                    "status": "failed"
                })
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed.append({
                "key": key,
                "reference_id": reference_id,
                "name": name,
                "status": "error",
                "error": str(e)
            })
    
    return successful, failed, skipped


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Upload evidence sets from JSON file to Paramify",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload evidence sets
  python json_to_paramify.py --json evidence_sets.json
  
  # Dry run (preview without uploading)
  python json_to_paramify.py --json evidence_sets.json --dry-run
  
  # Custom API base URL
  python json_to_paramify.py \\
    --json evidence_sets.json \\
    --base-url "https://stage.paramify.com/api/v0"
        """
    )
    
    parser.add_argument(
        '--json',
        required=True,
        help='Path to JSON file with evidence sets'
    )
    
    parser.add_argument(
        '--api-token',
        help='Paramify API token (or set PARAMIFY_UPLOAD_API_TOKEN env var)'
    )
    
    parser.add_argument(
        '--base-url',
        help='Paramify API base URL (or set PARAMIFY_API_BASE_URL env var)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without uploading'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_env_file()
    
    # Get API token
    api_token = args.api_token or os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
    if not api_token:
        print("Error: Paramify API token required")
        print("Set PARAMIFY_UPLOAD_API_TOKEN environment variable or use --api-token")
        sys.exit(1)
    
    # Get base URL
    base_url = args.base_url or os.environ.get(
        "PARAMIFY_API_BASE_URL",
        "https://app.paramify.com/api/v0"
    )
    
    # Validate JSON file
    json_path = Path(args.json)
    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        sys.exit(1)
    
    try:
        # Load evidence sets
        print(f"Loading evidence sets from: {json_path}")
        evidence_sets = load_evidence_sets(str(json_path))
        
        evidence_count = len(evidence_sets.get("evidence_sets", {}))
        print(f"Found {evidence_count} evidence sets")
        
        if args.dry_run:
            print("\n⚠️  DRY RUN MODE - No changes will be made to Paramify")
        
        # Upload evidence sets
        successful, failed, skipped = upload_evidence_sets(
            evidence_sets,
            api_token,
            base_url,
            dry_run=args.dry_run
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("UPLOAD SUMMARY")
        print("=" * 60)
        print(f"Total:        {evidence_count}")
        print(f"Successful:   {len(successful)}")
        print(f"Failed:       {len(failed)}")
        print(f"Skipped:      {len(skipped)}")
        
        if failed:
            print("\nFailed evidence sets:")
            for item in failed:
                print(f"  - {item['reference_id']}: {item['name']}")
                if 'error' in item:
                    print(f"    Error: {item['error']}")
        
        if args.dry_run:
            print("\n⚠️  This was a dry run. Use without --dry-run to actually upload.")
        
        # Exit with error code if any failed
        sys.exit(0 if len(failed) == 0 else 1)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


