#!/usr/bin/env python3
"""
Run Fetchers

This script executes the selected evidence fetcher scripts and stores evidence
in timestamped directories. Optionally uploads evidence files to Paramify.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path


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
    """Print the run fetchers header."""
    print("=" * 60)
    print("RUN EVIDENCE FETCHERS")
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
    
    print("✓ All prerequisites met")
    return True


def load_evidence_sets():
    """Load the evidence sets configuration."""
    evidence_sets = load_json_file("evidence_sets.json")
    print(f"✓ Loaded {len(evidence_sets['evidence_sets'])} evidence sets")
    return evidence_sets


def create_evidence_directory():
    """Create timestamped evidence directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_dir = Path("evidence") / timestamp
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"✓ Created evidence directory: {evidence_dir}")
    return evidence_dir


def run_fetcher_script(script_name: str, script_data: dict, evidence_dir: Path, csv_file: Path) -> bool:
    """Run a single fetcher script."""
    print(f"Running {script_name}...")
    
    # Determine script path
    service = script_data['service'].lower()
    script_path = Path("fetchers") / service / f"{script_name}.sh"
    
    if not script_path.exists():
        script_path = Path("fetchers") / service / f"{script_name}.py"
    
    if not script_path.exists():
        print(f"  ✗ Script not found: {script_path}")
        return False
    
    # Prepare command
    if script_path.suffix == '.py':
        cmd = [sys.executable, str(script_path)]
    else:
        cmd = ["bash", str(script_path)]
    
    # Add common parameters
    cmd.extend([
        "default",  # profile
        "us-west-2",  # region
        str(evidence_dir),  # output directory
        str(csv_file)  # CSV file
    ])
    
    try:
        # Run the script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"  ✓ {script_name} completed successfully")
            return True
        else:
            print(f"  ✗ {script_name} failed with return code {result.returncode}")
            if result.stderr:
                print(f"    Error: {result.stderr}")
            return False
    
    except subprocess.TimeoutExpired:
        print(f"  ✗ {script_name} timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"  ✗ {script_name} failed with error: {e}")
        return False


def upload_evidence_to_paramify(evidence_dir: Path):
    """Upload evidence files to Paramify."""
    print("\nUploading evidence to Paramify...")
    
    # Import the paramify pusher
    sys.path.append(str(Path(__file__).parent))
    from paramify_pusher import ParamifyPusher
    
    # Initialize the pusher
    api_token = os.environ.get("PARAMIFY_API_TOKEN")
    base_url = os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0")
    
    pusher = ParamifyPusher(api_token, base_url)
    
    # Upload evidence files
    success = pusher.upload_evidence_directory(str(evidence_dir))
    
    if success:
        print("✓ Evidence uploaded to Paramify successfully")
    else:
        print("✗ Some evidence files failed to upload")
    
    return success


def create_summary_file(evidence_dir: Path, results: dict):
    """Create a summary file with execution results."""
    summary = {
        "execution_timestamp": datetime.now().isoformat(),
        "evidence_directory": str(evidence_dir),
        "total_scripts": len(results),
        "successful_scripts": sum(1 for success in results.values() if success),
        "failed_scripts": sum(1 for success in results.values() if not success),
        "results": results
    }
    
    summary_file = evidence_dir / "execution_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"✓ Created execution summary: {summary_file}")


def main():
    """Main run fetchers function."""
    print_header()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\nPlease complete the prerequisites and try again.")
        return
    
    # Load evidence sets
    evidence_sets = load_evidence_sets()
    
    # Show summary
    print(f"\nWill execute {len(evidence_sets['evidence_sets'])} evidence fetcher scripts:")
    for script_name, script_data in evidence_sets['evidence_sets'].items():
        print(f"  • {script_data['name']} ({script_name})")
    
    # Ask for confirmation
    confirm = input(f"\nDo you want to proceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Operation cancelled.")
        return
    
    # Create evidence directory
    evidence_dir = create_evidence_directory()
    csv_file = evidence_dir / "evidence_summary.csv"
    
    # Initialize CSV file
    with open(csv_file, 'w') as f:
        f.write("script_name,status,timestamp,notes\n")
    
    # Run fetchers
    print(f"\nExecuting evidence fetchers...")
    print("-" * 40)
    
    results = {}
    for script_name, script_data in evidence_sets['evidence_sets'].items():
        success = run_fetcher_script(script_name, script_data, evidence_dir, csv_file)
        results[script_name] = success
    
    # Create summary
    create_summary_file(evidence_dir, results)
    
    # Show results
    print(f"\nExecution Summary:")
    print(f"  Total scripts: {len(results)}")
    print(f"  Successful: {sum(1 for success in results.values() if success)}")
    print(f"  Failed: {sum(1 for success in results.values() if not success)}")
    
    # Ask about uploading to Paramify
    upload_to_paramify = input(f"\nDo you want to upload evidence files to Paramify? (y/n): ").strip().lower()
    if upload_to_paramify == 'y':
        upload_evidence_to_paramify(evidence_dir)
    
    print(f"\n{'='*60}")
    print("EXECUTION COMPLETE")
    print(f"{'='*60}")
    print(f"Evidence stored in: {evidence_dir}")
    print(f"Summary file: {evidence_dir}/execution_summary.json")
    print(f"CSV summary: {csv_file}")


if __name__ == "__main__":
    main()
