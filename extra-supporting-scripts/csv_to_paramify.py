#!/usr/bin/env python3
"""
CSV to Paramify - Unified Workflow

End-to-end script that converts CSV to JSON and uploads evidence sets to Paramify.

Usage:
    python csv_to_paramify.py --csv input.csv --prefix PREFIX [--upload]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Import our converter and uploader
from csv_to_evidence_json import csv_to_evidence_json
from json_to_paramify import load_env_file, load_evidence_sets, upload_evidence_sets
import os


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Convert CSV to JSON and upload evidence sets to Paramify",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert CSV to JSON only
  python csv_to_paramify.py \\
    --csv "Coalfire FedRAMP 20x Evidence Request List.csv" \\
    --prefix "COALFIRE" \\
    --json output.json
  
  # Convert and upload to Paramify
  python csv_to_paramify.py \\
    --csv input.csv \\
    --prefix "CUSTOM" \\
    --upload
  
  # Dry run (preview without uploading)
  python csv_to_paramify.py \\
    --csv input.csv \\
    --prefix "CUSTOM" \\
    --upload \\
    --dry-run
        """
    )
    
    parser.add_argument(
        '--csv',
        required=True,
        help='Path to input CSV file'
    )
    
    parser.add_argument(
        '--prefix',
        default='CUSTOM',
        help='Prefix for reference IDs (default: CUSTOM)'
    )
    
    parser.add_argument(
        '--json',
        help='Path to output JSON file (default: temporary file if uploading)'
    )
    
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Upload evidence sets to Paramify after conversion'
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
        help='Preview changes without uploading (requires --upload)'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_env_file()
    
    # Validate CSV file
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    try:
        # Determine output JSON path
        if args.json:
            json_path = args.json
        elif args.upload:
            # Use temporary file if uploading
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json_path = temp_file.name
            temp_file.close()
        else:
            # Default output name
            json_path = csv_path.stem + "_evidence_sets.json"
        
        # Step 1: Convert CSV to JSON
        print("=" * 60)
        print("STEP 1: Converting CSV to JSON")
        print("=" * 60)
        evidence_sets = csv_to_evidence_json(
            str(csv_path),
            json_path,
            args.prefix
        )
        
        # Save JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(evidence_sets, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ JSON file saved: {json_path}")
        print(f"  Evidence sets: {len(evidence_sets['evidence_sets'])}")
        
        # Step 2: Upload to Paramify (if requested)
        if args.upload:
            print("\n" + "=" * 60)
            print("STEP 2: Uploading to Paramify")
            print("=" * 60)
            
            # Get API token
            api_token = args.api_token or os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
            if not api_token:
                print("Error: Paramify API token required for upload")
                print("Set PARAMIFY_UPLOAD_API_TOKEN environment variable or use --api-token")
                sys.exit(1)
            
            # Get base URL
            base_url = args.base_url or os.environ.get(
                "PARAMIFY_API_BASE_URL",
                "https://app.paramify.com/api/v0"
            )
            
            # Upload
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
            print(f"Total:        {len(evidence_sets['evidence_sets'])}")
            print(f"Successful:   {len(successful)}")
            print(f"Failed:       {len(failed)}")
            print(f"Skipped:      {len(skipped)}")
            
            if failed:
                print("\nFailed evidence sets:")
                for item in failed:
                    print(f"  - {item['reference_id']}: {item['name']}")
            
            if args.dry_run:
                print("\n⚠️  This was a dry run. Use without --dry-run to actually upload.")
            
            # Exit with error code if any failed
            if len(failed) > 0:
                sys.exit(1)
        
        print("\n" + "=" * 60)
        print("SUCCESS")
        print("=" * 60)
        print(f"✓ CSV converted to JSON: {json_path}")
        if args.upload:
            print(f"✓ Evidence sets uploaded to Paramify")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


