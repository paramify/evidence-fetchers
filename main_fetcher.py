#!/usr/bin/env python3
"""
Main Fetcher - Simple Evidence Collection System

Runs all scripts for a specified provider and saves results to timestamped evidence folders.
"""

import argparse
import json
import os
import subprocess
import sys
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


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


def create_timestamped_evidence_dir() -> str:
    """Create a timestamped evidence directory with underscore format for readability"""
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    evidence_dir = Path("evidence") / timestamp
    evidence_dir.mkdir(parents=True, exist_ok=True)
    return str(evidence_dir)


def get_provider_scripts(provider: str) -> List[str]:
    """Get all scripts from fetchers/{provider}/ directory"""
    scripts = []
    provider_dir = Path("fetchers") / provider
    
    if provider_dir.exists():
        for script_file in provider_dir.glob("*.sh"):
            # Skip the main runner script for AWS
            if provider == "aws" and script_file.name == "run_evidence_validations.sh":
                continue
            scripts.append(script_file.stem)
    
    return sorted(scripts)


def get_available_providers() -> List[str]:
    """Get list of available providers"""
    providers = []
    fetchers_dir = Path("fetchers")
    
    if fetchers_dir.exists():
        for provider_dir in fetchers_dir.iterdir():
            if provider_dir.is_dir():
                providers.append(provider_dir.name)
    
    return sorted(providers)


def run_provider_script(script_name: str, provider: str, profile: str = None, region: str = None, evidence_dir: str = None, timeout: int = None) -> Tuple[str, str]:
    """Run a script for a specific provider and return status and evidence file path"""
    script_path = Path("fetchers") / provider / f"{script_name}.sh"
    
    if not script_path.exists():
        return "ERROR", f"Script not found: {script_path}"
    
    # Make script executable
    script_path.chmod(0o755)
    
    try:
        # Build command based on provider
        if provider == "aws":
            # AWS scripts expect: profile, region, output_dir, csv_file
            # Pass /dev/null to disable CSV output
            cmd = [str(script_path), profile, region, evidence_dir, "/dev/null"]
        elif provider == "knowbe4":
            # KnowBe4 scripts expect: output_dir only
            cmd = [str(script_path), evidence_dir]
        else:
            # Other providers might have different parameter expectations
            # For now, pass profile and evidence_dir as common parameters
            cmd = [str(script_path)]
            if profile:
                cmd.extend(["--profile", profile])
            if region:
                cmd.extend(["--region", region])
            cmd.extend(["--output-dir", evidence_dir])
        
        # Run script with timeout if specified
        if timeout:
            print(f"  Timeout: {timeout} seconds")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Check if JSON output was created
        json_file = Path(evidence_dir) / f"{script_name}.json"
        if json_file.exists():
            return "PASS", str(json_file)
        else:
            return "FAIL", ""
            
    except subprocess.TimeoutExpired as e:
        print(f"Timeout: {script_name} exceeded {timeout} seconds")
        return "TIMEOUT", ""
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return "ERROR", ""
    except OSError as e:
        print(f"OS Error running {script_name}: {e}")
        return "ERROR", ""


def generate_summary(results: List[Dict], evidence_dir: str, provider: str) -> Dict:
    """Generate summary.json with all results"""
    timestamp = datetime.now().isoformat() + "Z"
    
    summary = {
        "timestamp": timestamp,
        "provider": provider,
        "evidence_directory": evidence_dir,
        "results": results
    }
    
    return summary


def show_help():
    """Show help information"""
    print("Main Fetcher - Simple Evidence Collection System")
    print("=" * 50)
    print()
    print("This script runs all scripts for a specified provider and saves")
    print("the results to timestamped evidence folders.")
    print()
    print("Usage:")
    print("  python main_fetcher.py --provider <provider> [--profile <profile>] [--region <region>] [--timeout <seconds>]")
    print()
    print("Arguments:")
    print("  --provider   Provider to run scripts for (required)")
    print("  --profile    Profile/credentials to use (if needed)")
    print("  --region     Region to use (if needed)")
    print("  --timeout    Timeout in seconds for each script (default: no timeout)")
    print("  --help       Show this help message")
    print()
    print("Environment Variables (from .env file):")
    print("  AWS_PROFILE         Default AWS profile")
    print("  AWS_REGION          Default AWS region")
    print("  KNOWBE4_PROFILE     Default KnowBe4 profile")
    print("  OKTA_PROFILE        Default Okta profile")
    print("  K8S_PROFILE         Default K8s profile")
    print("  DEFAULT_PROVIDER    Default provider to run")
    print()
    print("Examples:")
    print("  python main_fetcher.py --provider aws --profile gov_readonly --region us-gov-west-1")
    print("  python main_fetcher.py --provider knowbe4 --profile my_knowbe4_profile")
    print("  python main_fetcher.py --provider aws --timeout 300  # 5 minute timeout")
    print("  python main_fetcher.py --provider aws  # Uses AWS_PROFILE and AWS_REGION from .env")
    print("  python main_fetcher.py                 # Uses DEFAULT_PROVIDER from .env")
    print()
    print("Available providers:")
    providers = get_available_providers()
    for provider in providers:
        scripts = get_provider_scripts(provider)
        print(f"  - {provider} ({len(scripts)} scripts)")
        for script in scripts:
            print(f"    * {script}")


def main():
    # Load environment variables from .env file
    load_env_file()
    
    parser = argparse.ArgumentParser(description="Main Evidence Fetcher", add_help=False)
    parser.add_argument("--provider", help="Provider to run scripts for")
    parser.add_argument("--profile", help="Profile/credentials to use")
    parser.add_argument("--region", help="Region to use")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds for each script")
    parser.add_argument("--help", action="store_true", help="Show help message")
    
    args = parser.parse_args()
    
    # Show help if requested
    if args.help:
        show_help()
        return 0
    
    # Get provider from args or environment
    provider = args.provider or os.environ.get("DEFAULT_PROVIDER")
    if not provider:
        show_help()
        return 0
    
    # Check if provider exists
    available_providers = get_available_providers()
    if provider not in available_providers:
        print(f"Error: Provider '{provider}' not found.")
        print(f"Available providers: {', '.join(available_providers)}")
        return 1
    
    # Get profile and region from args or environment
    profile = args.profile
    region = args.region
    
    if provider == "aws":
        profile = profile or os.environ.get("AWS_PROFILE")
        region = region or os.environ.get("AWS_REGION", "us-east-1")
    elif provider == "knowbe4":
        profile = profile or os.environ.get("KNOWBE4_PROFILE")
    elif provider == "okta":
        profile = profile or os.environ.get("OKTA_PROFILE")
    elif provider == "k8s":
        profile = profile or os.environ.get("K8S_PROFILE")
    
    # Set AWS profile if provided and provider is AWS
    if provider == "aws" and profile:
        os.environ["AWS_PROFILE"] = profile
        print(f"Using AWS profile: {profile}")
        if region:
            print(f"Using AWS region: {region}")
    
    # Create timestamped evidence directory
    evidence_dir = create_timestamped_evidence_dir()
    print(f"Evidence directory: {evidence_dir}")
    
    # Get all scripts for the provider
    scripts = get_provider_scripts(provider)
    if not scripts:
        print(f"No scripts found for provider '{provider}'")
        return 1
    
    print(f"Running {len(scripts)} {provider} scripts...")
    if args.timeout:
        print(f"Timeout set to {args.timeout} seconds per script")
    
    # Run scripts and collect results
    results = []
    
    for script_name in scripts:
        print(f"\n--- Running {script_name} ({provider}) ---")
        
        status, evidence_file = run_provider_script(
            script_name, provider, profile, region, evidence_dir, args.timeout
        )
        
        result = {
            "script": script_name,
            "provider": provider,
            "status": status,
            "evidence_file": evidence_file
        }
        
        results.append(result)
        
        print(f"Result: {status}")
        if evidence_file:
            print(f"Evidence: {evidence_file}")
    
    # Generate and save summary
    summary = generate_summary(results, evidence_dir, provider)
    summary_path = Path(evidence_dir) / "summary.json"
    
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n--- Summary ---")
    print(f"Summary saved to: {summary_path}")
    
    # Print results summary
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    timeout_count = sum(1 for r in results if r["status"] == "TIMEOUT")
    
    print(f"Results: {pass_count} PASS, {fail_count} FAIL, {error_count} ERROR, {timeout_count} TIMEOUT")
    
    return 0 if error_count == 0 and timeout_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
