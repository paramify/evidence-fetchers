#!/usr/bin/env python3
"""
Create Evidence Sets in Paramify

This script uploads evidence sets to Paramify via API and optionally uploads
fetcher scripts as evidence artifacts.
"""

import json
import os
import sys
from pathlib import Path


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
                    print(f"  Loaded {key}")
        return True
    return False


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


def print_header():
    """Print the create evidence sets header."""
    print("=" * 60)
    print("CREATE EVIDENCE SETS IN PARAMIFY")
    print("=" * 60)
    print()


def check_prerequisites():
    """Check if prerequisites are met."""
    print("Checking prerequisites...")
    print()
    
    # Check for evidence_sets.json
    if not os.path.exists("evidence_sets.json"):
        print("✗ evidence_sets.json not found")
        print("Please run 'Select Fetchers' (option 1) first to generate evidence sets.")
        return False
    
    # Check for .env file
    if not os.path.exists(".env"):
        print("✗ .env file not found")
        print("Please run 'Prerequisites' (option 0) first to set up environment variables.")
        return False
    
    # Check for required environment variables
    required_vars = ["PARAMIFY_UPLOAD_API_TOKEN"]
    missing_vars = []
    
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"✗ Missing environment variables: {', '.join(missing_vars)}")
        print("Please add these to your .env file.")
        return False
    
    # Check for required Python packages
    try:
        import requests
        import boto3
        print("✓ Required Python packages are available")
    except ImportError as e:
        print(f"✗ Missing required Python package: {e}")
        print("Please run 'Prerequisites' (option 0) first to install dependencies.")
        return False
    
    print("✓ All prerequisites met")
    return True


def load_evidence_sets():
    """Load the evidence sets configuration."""
    evidence_sets = load_json_file("evidence_sets.json")
    print(f"✓ Loaded {len(evidence_sets['evidence_sets'])} evidence sets")
    return evidence_sets


def show_evidence_sets_summary(evidence_sets: dict):
    """Show a summary of the evidence sets to be created."""
    print("\nEvidence Sets to be created in Paramify:")
    print("-" * 50)
    
    for script_name, script_data in evidence_sets['evidence_sets'].items():
        print(f"• {script_data['name']}")
        print(f"  ID: {script_data['id']}")
        print(f"  Service: {script_data['service']}")
        print(f"  Description: {script_data['description']}")
        print()


def upload_evidence_sets(evidence_sets: dict, upload_scripts: bool = False):
    """Upload evidence sets to Paramify."""
    print("Uploading evidence sets to Paramify...")
    print()
    
    # Import the paramify pusher
    sys.path.append(str(Path(__file__).parent))
    from paramify_pusher import ParamifyPusher
    
    # Initialize the pusher
    api_token = os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
    base_url = os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0")
    
    pusher = ParamifyPusher(api_token, base_url)
    
    # Upload each evidence set
    success_count = 0
    skipped_count = 0
    total_count = len(evidence_sets['evidence_sets'])
    
    for script_name, script_data in evidence_sets['evidence_sets'].items():
        print(f"Processing {script_name}...")
        
        try:
            # Get or create evidence set in Paramify
            result = pusher.get_or_create_evidence_set(script_data)
            
            if result:
                print(f"  ✓ Processed evidence set: {script_data['name']}")
                success_count += 1
                
                # Optionally upload script as artifact
                if upload_scripts:
                    # Try to find the script file in the fetchers directory
                    script_path = f"../fetchers/{script_data['service'].lower()}/{script_name}.sh"
                    if not os.path.exists(script_path):
                        script_path = f"../fetchers/{script_data['service'].lower()}/{script_name}.py"
                    
                    if os.path.exists(script_path):
                        print(f"  Uploading script artifact: {script_path}")
                        artifact_result = pusher.upload_evidence_file(result, script_path, script_name)
                        if artifact_result:
                            print(f"  ✓ Script artifact uploaded successfully")
                        else:
                            print(f"  ✗ Failed to upload script artifact")
                    else:
                        print(f"  ⚠ Script file not found: {script_path}")
                        print(f"  ⚠ Tried paths: ../fetchers/{script_data['service'].lower()}/{script_name}.sh and ../fetchers/{script_data['service'].lower()}/{script_name}.py")
            else:
                print(f"  ✗ Failed to process evidence set: {script_data['name']}")
        
        except Exception as e:
            print(f"  ✗ Error processing {script_name}: {e}")
    
    print(f"\nUpload Summary:")
    print(f"  Successfully processed: {success_count}/{total_count}")
    print(f"  Failed: {total_count - success_count}/{total_count}")
    
    if success_count < total_count:
        print(f"\nNote: Some evidence sets may have failed to process.")
        print(f"Check the output above for specific error messages.")
    
    return success_count == total_count


def main():
    """Main create evidence sets function."""
    print_header()
    
    # Load environment variables from .env file
    load_env_file()
    print()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\nPlease complete the prerequisites and try again.")
        return
    
    # Load evidence sets
    evidence_sets = load_evidence_sets()
    
    # Show summary
    show_evidence_sets_summary(evidence_sets)
    
    # Ask for confirmation
    print(f"This will create {len(evidence_sets['evidence_sets'])} evidence sets in Paramify.")
    confirm = input("Do you want to proceed? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("Operation cancelled.")
        return
    
    # Ask about uploading scripts
    upload_scripts = input("Do you want to upload fetcher scripts as evidence artifacts? (y/n): ").strip().lower() == 'y'
    
    # Upload evidence sets
    success = upload_evidence_sets(evidence_sets, upload_scripts)
    
    if success:
        print(f"\n{'='*60}")
        print("SUCCESS: All evidence sets created in Paramify!")
        print("You can now proceed to 'Run Fetchers' (option 3)")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("WARNING: Some evidence sets failed to upload.")
        print("Check the upload log for details.")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
