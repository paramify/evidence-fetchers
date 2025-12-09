#!/usr/bin/env python3
"""
FedRAMP to Paramify - Unified Workflow

End-to-end script that parses FedRAMP JSON files and uploads evidence sets to Paramify.

Usage:
    python fedramp_to_paramify.py --url <github_url> [--upload]
    python fedramp_to_paramify.py --file <local_file> [--upload]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Import our parser and uploader
from fedramp_json_parser import download_json, load_json_file, parse_fedramp_requirements
from json_to_paramify import load_env_file, upload_evidence_sets
import os


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Parse FedRAMP JSON and upload evidence sets to Paramify",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse from GitHub URL and upload
  python fedramp_to_paramify.py \\
    --url https://raw.githubusercontent.com/FedRAMP/docs/main/data/FRMR.ADS.authorization-data-sharing.json \\
    --upload
  
  # Parse local file and save JSON only
  python fedramp_to_paramify.py \\
    --file FRMR.MAS.minimum-assessment-scope.json \\
    --json output.json
  
  # Dry run (preview without uploading)
  python fedramp_to_paramify.py \\
    --url <github_url> \\
    --upload \\
    --dry-run
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
        '--json',
        help='Path to output JSON file (default: temporary file if uploading)'
    )
    
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Upload evidence sets to Paramify after parsing'
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
    
    # Validate input
    if not args.file and not args.url:
        print("Error: Must provide either --file or --url")
        sys.exit(1)
    
    if args.file and args.url:
        print("Error: Cannot provide both --file and --url")
        sys.exit(1)
    
    # Load environment variables
    load_env_file()
    
    try:
        # Step 1: Load FedRAMP JSON
        print("=" * 60)
        print("STEP 1: Loading FedRAMP JSON")
        print("=" * 60)
        
        if args.url:
            fedramp_data = download_json(args.url)
        else:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File not found: {file_path}")
                sys.exit(1)
            print(f"Loading from: {file_path}")
            fedramp_data = load_json_file(str(file_path))
        
        # Step 2: Parse and convert
        print("\n" + "=" * 60)
        print("STEP 2: Parsing FedRAMP Requirements")
        print("=" * 60)
        evidence_sets = parse_fedramp_requirements(fedramp_data)
        
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
            if args.file:
                json_path = Path(args.file).stem + "_evidence_sets.json"
            else:
                json_path = "fedramp_evidence_sets.json"
        
        # Save JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(evidence_sets, f, indent=2, ensure_ascii=False)
        
        evidence_count = len(evidence_sets.get("evidence_sets", {}))
        print(f"\n✓ JSON file saved: {json_path}")
        print(f"  Evidence sets: {evidence_count}")
        
        # Step 3: Upload to Paramify (if requested)
        if args.upload:
            print("\n" + "=" * 60)
            print("STEP 3: Uploading to Paramify")
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
            print(f"Total:        {evidence_count}")
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
        print(f"✓ FedRAMP JSON parsed: {json_path}")
        if args.upload:
            print(f"✓ Evidence sets uploaded to Paramify")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


