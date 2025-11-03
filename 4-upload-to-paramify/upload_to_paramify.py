#!/usr/bin/env python3
"""
Upload Evidence to Paramify

This script finds the latest evidence directory and uploads evidence files to Paramify.
It can be run independently or as part of the main workflow.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Add the paramify pusher to the path
sys.path.append(str(Path(__file__).parent.parent / "2-create-evidence-sets"))
from paramify_pusher import ParamifyPusher


def print_header():
    """Print the upload header."""
    print("=" * 60)
    print("UPLOAD EVIDENCE TO PARAMIFY")
    print("=" * 60)
    print()


def find_latest_evidence_directory() -> Optional[Path]:
    """Find the latest evidence directory based on timestamp."""
    evidence_base = Path("evidence")
    if not evidence_base.exists():
        print("✗ Evidence directory not found")
        return None
    
    # Get all evidence directories
    evidence_dirs = []
    for item in evidence_base.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Try to parse timestamp from directory name
            try:
                timestamp = None
                timestamp_str = item.name
                
                # Handle different timestamp formats
                # New format: YYYY_MM_DD_HHMMSS (e.g., 2025_11_03_160232)
                if timestamp_str.count('_') == 3:
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y_%m_%d_%H%M%S")
                    except ValueError:
                        pass
                
                # Old format: YYYYMMDD_HHMMSS (e.g., 20251103_160232)
                if timestamp is None and timestamp_str.count('_') == 1:
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    except ValueError:
                        pass
                
                # Very old format: YYYYMMDDHHMMSS (e.g., 20251103160232)
                if timestamp is None and len(timestamp_str) == 14 and timestamp_str.isdigit():
                    try:
                        timestamp_str_with_underscore = f"{timestamp_str[:8]}_{timestamp_str[8:]}"
                        timestamp = datetime.strptime(timestamp_str_with_underscore, "%Y%m%d_%H%M%S")
                    except ValueError:
                        pass
                
                if timestamp:
                    evidence_dirs.append((timestamp, item))
            except ValueError:
                # Skip directories that don't match timestamp format
                continue
    
    if not evidence_dirs:
        print("✗ No evidence directories found with valid timestamps")
        return None
    
    # Sort by timestamp (newest first)
    evidence_dirs.sort(key=lambda x: x[0], reverse=True)
    latest_dir = evidence_dirs[0][1]
    
    print(f"✓ Found latest evidence directory: {latest_dir.name}")
    return latest_dir


def check_evidence_directory(evidence_dir: Path) -> bool:
    """Check if the evidence directory has the required files."""
    if not evidence_dir.exists():
        print(f"✗ Evidence directory not found: {evidence_dir}")
        return False
    
    # Check for summary file (flexible)
    summary_files = ["summary.json", "execution_summary.json", "evidence_summary.json"]
    summary_found = False
    
    for summary_file in summary_files:
        if (evidence_dir / summary_file).exists():
            print(f"✓ Found summary file: {summary_file}")
            summary_found = True
            break
    
    if not summary_found:
        print("✗ No summary file found in evidence directory")
        return False
    
    # Check for evidence files
    evidence_files = list(evidence_dir.glob("*.json"))
    evidence_files = [f for f in evidence_files if f.name not in summary_files + ["upload_log.json"]]
    
    if not evidence_files:
        print("✗ No evidence files found in evidence directory")
        return False
    
    print(f"✓ Found {len(evidence_files)} evidence files")
    return True


def upload_evidence_to_paramify(evidence_dir: Path) -> bool:
    """Upload evidence files to Paramify."""
    print("\nUploading evidence to Paramify...")
    
    # Initialize the pusher
    api_token = os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
    base_url = os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0")
    
    if not api_token:
        print("✗ PARAMIFY_UPLOAD_API_TOKEN environment variable not set")
        return False
    
    pusher = ParamifyPusher(api_token, base_url)
    
    # Upload evidence files
    success = pusher.upload_evidence_directory(str(evidence_dir))
    
    if success:
        print("✓ Evidence uploaded to Paramify successfully")
    else:
        print("✗ Some evidence files failed to upload")
    
    return success


def main():
    """Main upload function."""
    print_header()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Find latest evidence directory
    print("Finding latest evidence directory...")
    evidence_dir = find_latest_evidence_directory()
    if not evidence_dir:
        print("\nPlease run evidence fetchers first to generate evidence.")
        return
    
    # Check if directory has required files
    print(f"\nChecking evidence directory: {evidence_dir}")
    if not check_evidence_directory(evidence_dir):
        print("\nEvidence directory is missing required files.")
        return
    
    # Show evidence summary
    print(f"\nEvidence Summary:")
    print(f"  Directory: {evidence_dir}")
    print(f"  Timestamp: {evidence_dir.name}")
    
    # Count evidence files
    evidence_files = list(evidence_dir.glob("*.json"))
    summary_files = ["summary.json", "execution_summary.json", "evidence_summary.json", "upload_log.json"]
    evidence_files = [f for f in evidence_files if f.name not in summary_files]
    print(f"  Evidence files: {len(evidence_files)}")
    
    # Ask for confirmation
    print(f"\nThis will upload evidence from {evidence_dir.name} to Paramify.")
    confirm = input("Do you want to proceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Upload cancelled.")
        return
    
    # Upload to Paramify
    success = upload_evidence_to_paramify(evidence_dir)
    
    if success:
        print(f"\n{'='*60}")
        print("UPLOAD COMPLETE")
        print(f"{'='*60}")
        print(f"Evidence uploaded from: {evidence_dir}")
    else:
        print(f"\n{'='*60}")
        print("UPLOAD FAILED")
        print(f"{'='*60}")
        print("Evidence upload failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
