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
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv


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


def get_aws_region_from_cli(profile: str = None) -> str:
    """Get AWS region from AWS CLI configuration if environment variable is not set."""
    try:
        cmd = ["aws", "configure", "get", "region"]
        if profile:
            cmd.extend(["--profile", profile])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    return ""


def create_evidence_directory():
    """Create timestamped evidence directory."""
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    evidence_dir = Path("evidence") / timestamp
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"✓ Created evidence directory: {evidence_dir}")
    return evidence_dir


def parse_multi_instance_config() -> Dict[str, List[Dict[str, Any]]]:
    """Parse environment variables for multi-instance configurations."""
    config = {
        "gitlab_projects": [],
        "aws_regions": []
    }
    
    # Parse GitLab projects
    gitlab_pattern = re.compile(r'^GITLAB_PROJECT_(\d+)_(.+)$')
    gitlab_projects = {}
    
    for key, value in os.environ.items():
        match = gitlab_pattern.match(key)
        if match:
            project_num = match.group(1)
            config_key = match.group(2).lower()
            
            if project_num not in gitlab_projects:
                gitlab_projects[project_num] = {}
            
            gitlab_projects[project_num][config_key] = value
    
    # Convert to list and filter valid projects
    for project_num, project_config in gitlab_projects.items():
        if all(key in project_config for key in ['url', 'api_access_token', 'id', 'fetchers']):
            fetchers = [f.strip() for f in project_config['fetchers'].split(',')]
            config["gitlab_projects"].append({
                'name': f"project_{project_num}",
                'url': project_config['url'],
                'token': project_config['api_access_token'],
                'project_id': project_config['id'],
                'fetchers': fetchers,
                'config': {k: v for k, v in project_config.items() 
                          if k not in ['url', 'api_access_token', 'id', 'fetchers']}
            })
    
    # Parse AWS regions
    aws_pattern = re.compile(r'^AWS_REGION_(\d+)_(.+)$')
    aws_regions = {}
    
    for key, value in os.environ.items():
        match = aws_pattern.match(key)
        if match:
            region_num = match.group(1)
            config_key = match.group(2).lower()
            
            if region_num not in aws_regions:
                aws_regions[region_num] = {}
            
            aws_regions[region_num][config_key] = value
    
    # Convert to list and filter valid regions
    for region_num, region_config in aws_regions.items():
        if all(key in region_config for key in ['fetchers']):
            fetchers = [f.strip() for f in region_config['fetchers'].split(',')]
            config["aws_regions"].append({
                'name': f"region_{region_num}",
                'region': region_config.get('region', region_num),
                'profile': region_config.get('profile', os.environ.get('AWS_PROFILE', '')),
                'fetchers': fetchers,
                'config': {k: v for k, v in region_config.items() 
                          if k not in ['region', 'profile', 'fetchers']}
            })
    
    return config


def create_fetcher_instances(evidence_sets: Dict[str, Any], multi_config: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Create multiple instances of fetchers based on multi-instance configuration."""
    instances = []
    
    # Handle GitLab projects
    for project in multi_config["gitlab_projects"]:
        for fetcher_name in project["fetchers"]:
            if fetcher_name in evidence_sets["evidence_sets"]:
                instance = {
                    "script_name": fetcher_name,
                    "script_data": evidence_sets["evidence_sets"][fetcher_name].copy(),
                    "instance_name": f"{fetcher_name}_{project['name']}",
                    "provider": "gitlab",
                    "config": {
                        "GITLAB_URL": project["url"],
                        "GITLAB_API_TOKEN": project["token"],
                        "GITLAB_PROJECT_ID": project["project_id"]
                    }
                }
                
                # Add project-specific overrides
                for key, value in project["config"].items():
                    instance["config"][f"GITLAB_{key.upper()}"] = value
                
                instances.append(instance)
    
    # Handle AWS regions
    for region in multi_config["aws_regions"]:
        for fetcher_name in region["fetchers"]:
            if fetcher_name in evidence_sets["evidence_sets"]:
                instance = {
                    "script_name": fetcher_name,
                    "script_data": evidence_sets["evidence_sets"][fetcher_name].copy(),
                    "instance_name": f"{fetcher_name}_{region['name']}",
                    "provider": "aws",
                    "config": {
                        "AWS_PROFILE": region["profile"],
                        "AWS_REGION": region["region"]
                    }
                }
                
                # Add region-specific overrides
                for key, value in region["config"].items():
                    instance["config"][f"AWS_{key.upper()}"] = value
                
                instances.append(instance)
    
    return instances


def run_fetcher_instance(instance: Dict[str, Any], evidence_dir: Path, timeout: int) -> bool:
    """Run a single fetcher instance with its specific configuration."""
    script_name = instance["script_name"]
    script_data = instance["script_data"]
    instance_name = instance["instance_name"]
    provider = instance["provider"]
    config = instance["config"]
    
    print(f"Running {instance_name}...")
    
    # Determine script path - use script_file from catalog if available
    script_path = None
    
    if "script_file" in script_data:
        script_path = Path(script_data["script_file"])
    else:
        # Try to load from catalog
        catalog_path = Path("1-select-fetchers/evidence_fetchers_catalog.json")
        if catalog_path.exists():
            try:
                catalog = load_json_file(str(catalog_path))
                if "evidence_fetchers" in catalog and script_name in catalog["evidence_fetchers"]:
                    if "script_file" in catalog["evidence_fetchers"][script_name]:
                        script_path = Path(catalog["evidence_fetchers"][script_name]["script_file"])
            except:
                pass
        
        # Fallback to constructing from script name
        if script_path is None or not script_path.exists():
            # Try service-based path from script_data first (for Checkov, service is "CHECKOV")
            if "service" in script_data:
                service = script_data["service"].lower()
                script_path = Path("fetchers") / service / f"{script_name}.sh"
                if not script_path.exists():
                    script_path = Path("fetchers") / service / f"{script_name}.py"
            
            # If still not found, try provider-based path
            if script_path is None or not script_path.exists():
                script_path = Path("fetchers") / provider / f"{script_name}.sh"
                if not script_path.exists():
                    script_path = Path("fetchers") / provider / f"{script_name}.py"
    
    if not script_path.exists():
        print(f"  ✗ Script not found: {script_path}")
        return False
    
    # Prepare command
    if script_path.suffix == '.py':
        cmd = [sys.executable, str(script_path)]
    else:
        cmd = ["bash", str(script_path)]
    
    # Add common parameters - CSV disabled in favor of JSON
    cmd.extend([
        config.get("AWS_PROFILE", os.environ.get("AWS_PROFILE", "")),  # profile
        config.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "")),  # region
        str(evidence_dir),  # output directory
        "/dev/null"  # CSV file disabled - JSON output preferred
    ])
    
    try:
        # Set instance-specific environment variables
        env = os.environ.copy()
        for key, value in config.items():
            env[key] = value
        
        # Run the script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        
        if result.returncode == 0:
            print(f"  ✓ {instance_name} completed successfully")
            return True
        else:
            print(f"  ✗ {instance_name} failed with return code {result.returncode}")
            if result.stderr:
                print(f"    Error: {result.stderr}")
            return False
    
    except subprocess.TimeoutExpired:
        print(f"  ✗ {instance_name} timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"  ✗ {instance_name} failed with error: {e}")
        return False


def run_fetcher_script(script_name: str, script_data: dict, evidence_dir: Path, 
                      aws_profile: str = None, aws_region: str = None, timeout: int = 300, 
                      additional_flags: list = None) -> bool:
    """Run a single fetcher script."""
    print(f"Running {script_name}...")
    
    # Determine script path - use script_file from catalog if available
    if "script_file" in script_data:
        script_path = Path(script_data["script_file"])
    else:
        # Fallback to constructing from script name
        service = script_data.get('service', 'aws').lower()
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
    
    # Get AWS profile and region from environment or use defaults
    profile = aws_profile or os.environ.get("AWS_PROFILE", "")
    region = aws_region or os.environ.get("AWS_DEFAULT_REGION", "")
    
    # If region is not set, try to get it from AWS CLI
    if not region:
        region = get_aws_region_from_cli(profile)
    
    # Add common parameters - CSV disabled in favor of JSON
    cmd.extend([
        profile,  # AWS profile
        region,   # AWS region
        str(evidence_dir),  # output directory
        "/dev/null"  # CSV file disabled - JSON output preferred
    ])
    
    # Add additional flags if provided
    if additional_flags:
        cmd.extend(additional_flags)
    
    try:
        # Run the script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if result.returncode == 0:
            print(f"  ✓ {script_name} completed successfully")
            return True
        else:
            print(f"  ✗ {script_name} failed with return code {result.returncode}")
            if result.stderr:
                print(f"    Error: {result.stderr}")
            return False
    
    except subprocess.TimeoutExpired:
        print(f"  ✗ {script_name} timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"  ✗ {script_name} failed with error: {e}")
        return False


def create_summary_file(evidence_dir: Path, results: dict, instance_info: dict = None):
    """Create a summary file with execution results.
    
    Args:
        evidence_dir: Directory containing evidence files
        results: Dict mapping script_name/instance_name to success bool
        instance_info: Optional dict mapping instance_name to instance config (for resource extraction)
    """
    timestamp = datetime.now().isoformat() + "Z"
    
    # Get all JSON files in evidence directory (excluding summary.json)
    json_files = {f.stem: f for f in evidence_dir.glob("*.json") if f.name != "summary.json"}
    
    # Convert results to the format expected by paramify pusher
    summary_results = []
    for script_name, success in results.items():
        # Determine status based on success
        status = "PASS" if success else "FAIL"
        
        # Try to find the evidence file
        evidence_file = None
        
        # First, try exact match with script_name
        if script_name in json_files:
            evidence_file = str(json_files[script_name])
        else:
            # Extract base script name by removing instance suffixes like _project_1, _region_1, etc.
            # Pattern: script_name_project_X or script_name_region_X
            base_name = re.sub(r'_(project|region)_\d+$', '', script_name)
            
            # Try to match with base name
            if base_name in json_files:
                evidence_file = str(json_files[base_name])
            else:
                # Try to find any file that starts with the base name
                for file_stem, file_path in json_files.items():
                    if file_stem.startswith(base_name) or base_name.startswith(file_stem):
                        evidence_file = str(file_path)
                        break
        
        # Extract resource information from instance_name or instance_info
        resource = "unknown"
        if instance_info:
            # Try to get instance info for this script_name
            instance = instance_info.get(script_name)
            if instance:
                if instance.get("provider") == "gitlab" and "GITLAB_PROJECT_ID" in instance.get("config", {}):
                    resource = instance["config"]["GITLAB_PROJECT_ID"]
                elif instance.get("provider") == "aws" and "AWS_REGION" in instance.get("config", {}):
                    resource = instance["config"]["AWS_REGION"]
                elif instance.get("provider") == "aws" and "AWS_PROFILE" in instance.get("config", {}):
                    resource = instance["config"]["AWS_PROFILE"]
        else:
            # Fallback: try to extract from instance_name pattern
            # For project patterns: script_name_project_X -> use project_X
            project_match = re.search(r'_(project_\d+)$', script_name)
            if project_match:
                resource = project_match.group(1)
            # For region patterns: script_name_region_X -> use region_X
            region_match = re.search(r'_(region_\d+)$', script_name)
            if region_match:
                resource = region_match.group(1)
        
        result_entry = {
            "check": script_name,
            "resource": resource,
            "status": status,
            "evidence_file": evidence_file
        }
        summary_results.append(result_entry)
    
    summary = {
        "timestamp": timestamp,
        "evidence_directory": str(evidence_dir),
        "total_scripts": len(results),
        "successful_scripts": sum(1 for success in results.values() if success),
        "failed_scripts": sum(1 for success in results.values() if not success),
        "results": summary_results
    }
    
    # Create the summary.json file
    summary_file = evidence_dir / "summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"✓ Created summary: {summary_file}")


def main():
    """Main run fetchers function."""
    print_header()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\nPlease complete the prerequisites and try again.")
        return
    
    # Load evidence sets
    evidence_sets = load_evidence_sets()
    
    # Parse multi-instance configuration
    multi_config = parse_multi_instance_config()
    
    # Create fetcher instances
    instances = create_fetcher_instances(evidence_sets, multi_config)
    
    # Track which fetchers are covered by multi-instance config
    covered_fetchers = set()
    if instances:
        for instance in instances:
            covered_fetchers.add(instance['script_name'])
    
    # Find fetchers not covered by multi-instance config
    all_fetchers = set(evidence_sets['evidence_sets'].keys())
    uncovered_fetchers = all_fetchers - covered_fetchers
    
    # Show summary
    total_to_run = len(instances) + len(uncovered_fetchers)
    print(f"\nWill execute {total_to_run} evidence fetcher scripts:")
    
    if instances:
        print(f"  Multi-instance fetchers ({len(instances)} instances):")
        for instance in instances:
            print(f"    • {instance['script_data']['name']} ({instance['instance_name']})")
    
    if uncovered_fetchers:
        print(f"  Standard fetchers ({len(uncovered_fetchers)} scripts):")
        for script_name in sorted(uncovered_fetchers):
            script_data = evidence_sets['evidence_sets'][script_name]
            print(f"    • {script_data['name']} ({script_name})")
    
    # Ask for confirmation
    confirm = input(f"\nDo you want to proceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Operation cancelled.")
        return
    
    # Create evidence directory
    evidence_dir = create_evidence_directory()
    
    # Run fetchers
    print(f"\nExecuting evidence fetchers...")
    print("-" * 40)
    
    # Get configuration from environment or use defaults
    timeout = int(os.environ.get("FETCHER_TIMEOUT", "300"))  # 5 minutes default
    
    print(f"Configuration:")
    print(f"  Timeout: {timeout} seconds")
    print()
    
    results = {}
    instance_info_map = {}  # Map instance_name to instance config
    
    # Get AWS profile and region for standard fetchers
    aws_profile = os.environ.get("AWS_PROFILE", "")
    aws_region = os.environ.get("AWS_DEFAULT_REGION", "")
    
    # If region is not set in environment, try to get it from AWS CLI
    if not aws_region:
        aws_region = get_aws_region_from_cli(aws_profile)
    
    # Run multi-instance fetchers first
    if instances:
        print("Running multi-instance fetchers...")
        for instance in instances:
            success = run_fetcher_instance(instance, evidence_dir, timeout)
            instance_name = instance['instance_name']
            results[instance_name] = success
            # Store instance info for resource extraction
            instance_info_map[instance_name] = instance
        print()
    
    # Run standard fetchers that aren't covered by multi-instance config
    if uncovered_fetchers:
        if instances:
            print("Running standard fetchers...")
        print(f"  AWS Profile: {aws_profile}")
        print(f"  AWS Region: {aws_region}")
        print()
        
        for script_name in sorted(uncovered_fetchers):
            script_data = evidence_sets['evidence_sets'][script_name]
            
            # Get additional flags for this specific fetcher
            additional_flags = []
            
            # Check for fetcher-specific flags in environment variables (new naming convention)
            fetcher_flags_env = os.environ.get(f"{script_name.upper()}_FETCHER", "")
            if fetcher_flags_env:
                additional_flags.extend(fetcher_flags_env.split())
            
            # Check for legacy fetcher-specific flags in environment variables (backward compatibility)
            legacy_fetcher_flags_env = os.environ.get(f"FETCHER_FLAGS_{script_name.upper()}", "")
            if legacy_fetcher_flags_env:
                additional_flags.extend(legacy_fetcher_flags_env.split())
            
            # Check for flags in script data
            if "flags" in script_data:
                additional_flags.extend(script_data["flags"])
            
            # Show additional flags if any
            if additional_flags:
                print(f"  Using additional flags: {' '.join(additional_flags)}")
            
            success = run_fetcher_script(script_name, script_data, evidence_dir, 
                                       aws_profile, aws_region, timeout, additional_flags)
            results[script_name] = success
    
    # Create summary
    create_summary_file(evidence_dir, results, instance_info_map if instance_info_map else None)
    
    # Show results
    print(f"\nExecution Summary:")
    print(f"  Total scripts: {len(results)}")
    print(f"  Successful: {sum(1 for success in results.values() if success)}")
    print(f"  Failed: {sum(1 for success in results.values() if not success)}")
    
    # Note: Paramify upload is now available as a separate step (option 4)
    print(f"\nNote: To upload evidence to Paramify, use option 4 from the main menu.")
    
    print(f"\n{'='*60}")
    print("EXECUTION COMPLETE")
    print(f"{'='*60}")
    print(f"Evidence stored in: {evidence_dir}")
    print(f"Summary file: {evidence_dir}/execution_summary.json")


if __name__ == "__main__":
    main()
