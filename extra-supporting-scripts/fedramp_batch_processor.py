#!/usr/bin/env python3
"""
FedRAMP Batch Processor

Processes all FedRAMP JSON files from GitHub and creates evidence sets.
Can optionally upload all to Paramify.

Usage:
    python fedramp_batch_processor.py [--upload] [--output-dir output/]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Import our parser
from fedramp_json_parser import download_json, parse_fedramp_requirements


# List of all FedRAMP standards from GitHub
FEDRAMP_STANDARDS = [
    "FRMR.ADS.authorization-data-sharing",
    "FRMR.CCM.collaborative-continuous-monitoring",
    "FRMR.FRD.fedramp-definitions",
    "FRMR.FSI.fedramp-security-inbox",
    "FRMR.ICP.incident-communications-procedures",
    "FRMR.KSI.key-security-indicators",
    "FRMR.MAS.minimum-assessment-scope",
    "FRMR.PVA.persistent-validation-and-assessment",
    "FRMR.RSC.recommended-secure-configuration",
    "FRMR.SCN.significant-change-notifications",
    "FRMR.UCM.using-cryptographic-modules",
    "FRMR.VDR.vulnerability-detection-and-response",
]

GITHUB_BASE_URL = "https://raw.githubusercontent.com/FedRAMP/docs/main/data"


def get_fedramp_url(standard: str) -> str:
    """Get GitHub raw URL for a FedRAMP standard."""
    return f"{GITHUB_BASE_URL}/{standard}.json"


def process_fedramp_standard(
    standard: str,
    output_dir: Path,
    upload: bool = False,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    dry_run: bool = False
) -> Dict:
    """Process a single FedRAMP standard.
    
    Returns:
        Dictionary with processing results
    """
    print(f"\n{'='*60}")
    print(f"Processing: {standard}")
    print(f"{'='*60}")
    
    url = get_fedramp_url(standard)
    output_file = output_dir / f"{standard}_evidence_sets.json"
    
    result = {
        "standard": standard,
        "url": url,
        "output_file": str(output_file),
        "success": False,
        "evidence_count": 0,
        "upload_success": False,
        "upload_successful": 0,
        "upload_failed": 0,
        "error": None
    }
    
    try:
        # Download and parse
        print(f"Downloading from: {url}")
        fedramp_data = download_json(url)
        
        print("Parsing FedRAMP requirements...")
        evidence_sets = parse_fedramp_requirements(fedramp_data)
        
        evidence_count = len(evidence_sets.get("evidence_sets", {}))
        result["evidence_count"] = evidence_count
        
        # Save JSON file
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(evidence_sets, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved {evidence_count} evidence sets to: {output_file}")
        result["success"] = True
        
        # Upload if requested
        if upload and api_token:
            print(f"\nUploading to Paramify...")
            try:
                # Import uploader only when needed
                from json_to_paramify import upload_evidence_sets
                
                successful, failed, skipped = upload_evidence_sets(
                    evidence_sets,
                    api_token,
                    base_url,
                    dry_run=dry_run
                )
                
                result["upload_successful"] = len(successful)
                result["upload_failed"] = len(failed)
                result["upload_success"] = len(failed) == 0
                
                print(f"✓ Uploaded {len(successful)}/{evidence_count} evidence sets")
                if failed:
                    print(f"✗ Failed to upload {len(failed)} evidence sets")
            except ImportError as e:
                print(f"✗ Cannot upload: Missing dependencies ({e})")
                print("  Install required packages: pip install requests")
                result["error"] = f"Upload failed: {e}"
        
    except Exception as e:
        print(f"✗ Error processing {standard}: {e}")
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
    
    return result


def process_all_fedramp_standards(
    standards: List[str],
    output_dir: Path,
    upload: bool = False,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    dry_run: bool = False
) -> List[Dict]:
    """Process all FedRAMP standards.
    
    Returns:
        List of processing results for each standard
    """
    results = []
    
    print(f"Processing {len(standards)} FedRAMP standards...")
    print(f"Output directory: {output_dir}")
    if upload:
        print(f"Upload mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    
    for idx, standard in enumerate(standards, 1):
        print(f"\n[{idx}/{len(standards)}] {standard}")
        
        result = process_fedramp_standard(
            standard,
            output_dir,
            upload=upload,
            api_token=api_token,
            base_url=base_url,
            dry_run=dry_run
        )
        
        results.append(result)
    
    return results


def print_summary(results: List[Dict]):
    """Print summary of processing results."""
    print("\n" + "="*60)
    print("PROCESSING SUMMARY")
    print("="*60)
    
    total_standards = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total_standards - successful
    
    total_evidence = sum(r["evidence_count"] for r in results)
    
    print(f"\nStandards Processed:")
    print(f"  Total:     {total_standards}")
    print(f"  Successful: {successful}")
    print(f"  Failed:    {failed}")
    print(f"  Total Evidence Sets: {total_evidence}")
    
    # Upload summary
    upload_results = [r for r in results if r.get("upload_successful", 0) > 0 or r.get("upload_failed", 0) > 0]
    if upload_results:
        total_uploaded = sum(r["upload_successful"] for r in upload_results)
        total_failed = sum(r["upload_failed"] for r in upload_results)
        print(f"\nUpload Summary:")
        print(f"  Standards Uploaded: {len(upload_results)}")
        print(f"  Evidence Sets Uploaded: {total_uploaded}")
        print(f"  Evidence Sets Failed: {total_failed}")
    
    # Failed standards
    failed_standards = [r for r in results if not r["success"]]
    if failed_standards:
        print(f"\nFailed Standards:")
        for result in failed_standards:
            print(f"  - {result['standard']}: {result.get('error', 'Unknown error')}")
    
    # Success details
    print(f"\nSuccessful Standards:")
    for result in results:
        if result["success"]:
            status = "✓"
            if result.get("upload_success"):
                status += " (uploaded)"
            elif result.get("upload_successful", 0) > 0:
                status += f" (uploaded {result['upload_successful']}/{result['evidence_count']})"
            print(f"  {status} {result['standard']}: {result['evidence_count']} evidence sets")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Process all FedRAMP JSON files from GitHub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all standards and save JSON files
  python fedramp_batch_processor.py --output-dir fedramp_evidence_sets/
  
  # Process and upload all to Paramify
  python fedramp_batch_processor.py --upload --output-dir fedramp_evidence_sets/
  
  # Dry run (preview without uploading)
  python fedramp_batch_processor.py --upload --dry-run
  
  # Process specific standards only
  python fedramp_batch_processor.py \\
    --standards FRMR.ADS.authorization-data-sharing FRMR.MAS.minimum-assessment-scope
        """
    )
    
    parser.add_argument(
        '--standards',
        nargs='+',
        help='Specific standards to process (default: all)'
    )
    
    parser.add_argument(
        '--output-dir',
        default='fedramp_evidence_sets',
        help='Directory to save JSON files (default: fedramp_evidence_sets)'
    )
    
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Upload evidence sets to Paramify after processing'
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
    
    # Load environment variables from .env file
    env_file = Path(".env")
    if env_file.exists():
        print(f"Loading environment variables from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
                    if key == "PARAMIFY_UPLOAD_API_TOKEN":
                        print(f"  Loaded {key}")
    
    # Determine which standards to process
    standards = args.standards if args.standards else FEDRAMP_STANDARDS
    
    # Validate standards
    invalid = [s for s in standards if s not in FEDRAMP_STANDARDS]
    if invalid:
        print(f"Error: Invalid standards: {invalid}")
        print(f"Valid standards: {', '.join(FEDRAMP_STANDARDS)}")
        sys.exit(1)
    
    # Get API credentials if uploading
    api_token = None
    base_url = None
    if args.upload:
        api_token = args.api_token or os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
        if not api_token:
            print("Error: Paramify API token required for upload")
            print("Set PARAMIFY_UPLOAD_API_TOKEN environment variable or use --api-token")
            sys.exit(1)
        
        base_url = args.base_url or os.environ.get(
            "PARAMIFY_API_BASE_URL",
            "https://app.paramify.com/api/v0"
        )
    
    try:
        # Process all standards
        output_dir = Path(args.output_dir)
        results = process_all_fedramp_standards(
            standards,
            output_dir,
            upload=args.upload,
            api_token=api_token,
            base_url=base_url,
            dry_run=args.dry_run
        )
        
        # Print summary
        print_summary(results)
        
        # Save results summary
        summary_file = output_dir / "processing_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                "total_standards": len(results),
                "successful": sum(1 for r in results if r["success"]),
                "failed": sum(1 for r in results if not r["success"]),
                "total_evidence_sets": sum(r["evidence_count"] for r in results),
                "results": results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Processing summary saved to: {summary_file}")
        
        # Exit with error code if any failed
        failed_count = sum(1 for r in results if not r["success"])
        if failed_count > 0:
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

