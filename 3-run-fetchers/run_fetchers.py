#!/usr/bin/env python3
"""
Run Fetchers

This script executes the selected evidence fetcher scripts and stores evidence
in timestamped directories. Optionally uploads evidence files to Paramify.

Notes:
- AWS-based fetchers require a valid AWS CLI session. If you are using AWS SSO,
  run `aws sso login --profile <your-profile>` before running this script.
"""

import importlib
import json
import os
import shutil
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


# Mapping from catalog dependency names to binary names and install instructions
_DEPENDENCY_BINARY_MAP = {
    "aws-cli": ("aws", "Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"),
    "kubectl": ("kubectl", "Install kubectl: https://kubernetes.io/docs/tasks/tools/"),
    "checkov": ("checkov", "pip install checkov"),
    "curl": ("curl", "Install curl for your OS"),
    "jq": ("jq", "Install jq: https://jqlang.github.io/jq/download/"),
    "git": ("git", "Install git: https://git-scm.com/downloads"),
}

# Python package dependencies that need import-based checking
_PYTHON_PACKAGE_DEPS = {
    "requests": "pip install requests",
    "python3": None,  # Skip — we're already running Python
}


def check_tool_dependencies(evidence_sets: dict) -> None:
    """Check if required tool dependencies are available for selected fetchers.

    Reads the catalog to find dependencies for each selected fetcher, then
    checks whether the required binaries are on the PATH. Prints warnings
    for any missing tools but does not block execution.
    """
    catalog_path = Path("1-select-fetchers/evidence_fetchers_catalog.json")
    if not catalog_path.exists():
        return  # Can't check without catalog

    try:
        catalog = load_json_file(str(catalog_path))
    except SystemExit:
        return  # load_json_file calls sys.exit on error; don't block here

    # Build a map: dependency_name -> set of fetcher names that need it
    dep_to_fetchers: Dict[str, set] = {}
    selected_fetchers = set(evidence_sets.get("evidence_sets", {}).keys())

    # Walk the catalog to find dependencies for selected fetchers
    categories = {}
    if "evidence_fetchers_catalog" in catalog and "categories" in catalog["evidence_fetchers_catalog"]:
        categories = catalog["evidence_fetchers_catalog"]["categories"]
    elif "evidence_fetchers" in catalog:
        # Legacy flat structure
        categories = {"_legacy": {"scripts": catalog["evidence_fetchers"]}}

    for _cat_name, cat_data in categories.items():
        scripts = cat_data.get("scripts", {})
        for script_name, script_data in scripts.items():
            if script_name not in selected_fetchers:
                continue
            for dep in script_data.get("dependencies", []):
                dep_to_fetchers.setdefault(dep, set()).add(script_name)

    if not dep_to_fetchers:
        return

    print("\nChecking tool dependencies for selected fetchers...")
    missing_count = 0

    for dep_name in sorted(dep_to_fetchers.keys()):
        fetchers = dep_to_fetchers[dep_name]

        # Skip python3 — we're already running Python
        if dep_name == "python3":
            continue

        # Check Python packages via import
        if dep_name in _PYTHON_PACKAGE_DEPS:
            install_hint = _PYTHON_PACKAGE_DEPS[dep_name]
            if install_hint is None:
                continue
            try:
                importlib.import_module(dep_name)
                print(f"  ✓ {dep_name}")
            except ImportError:
                missing_count += 1
                print(f"  ✗ {dep_name} not found — {install_hint}")
                print(f"    Required by: {', '.join(sorted(fetchers))}")
            continue

        # Check CLI tools via PATH lookup
        if dep_name in _DEPENDENCY_BINARY_MAP:
            binary, install_hint = _DEPENDENCY_BINARY_MAP[dep_name]
        else:
            # Unknown dependency — try the name directly as a binary
            binary = dep_name
            install_hint = f"Install {dep_name}"

        if shutil.which(binary):
            print(f"  ✓ {dep_name}" + (f" ({binary})" if binary != dep_name else ""))
        else:
            missing_count += 1
            print(f"  ✗ {dep_name} not found — {install_hint}")
            print(f"    Required by: {', '.join(sorted(fetchers))}")

    if missing_count > 0:
        print(f"\n  ⚠ {missing_count} missing {'dependency' if missing_count == 1 else 'dependencies'}. Affected fetchers will fail.")
    else:
        print("  ✓ All tool dependencies available")


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


def check_aws_auth(profile: str = "", region: str = "") -> bool:
    """Verify that the AWS CLI is authenticated for the given profile/region.

    This is used to fail AWS-based fetchers early when the user has not
    established an AWS session (for example, by running `aws sso login`).
    """
    cmd = ["aws", "sts", "get-caller-identity", "--output", "json"]

    if profile:
        cmd.extend(["--profile", profile])
    if region:
        cmd.extend(["--region", region])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        print("  ✗ AWS CLI not found on PATH.")
        print("    Please install the AWS CLI and ensure it is available on your PATH.")
        return False
    except subprocess.TimeoutExpired:
        print("  ✗ AWS authentication check timed out when calling STS.")
        print("    Please verify network connectivity and your AWS CLI configuration.")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error while checking AWS authentication: {e}")
        return False

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(f"  ✗ AWS authentication failed for profile '{profile}' and region '{region}'.")
            print(f"    AWS CLI error: {stderr}")
        else:
            print(f"  ✗ AWS authentication failed for profile '{profile}' and region '{region}'.")
        print("    Ensure you have valid AWS credentials and, if using AWS SSO,")
        print(f"    run 'aws sso login --profile {profile}' before running the fetchers.")
        return False

    return True


def validate_aws_evidence(script_name: str, evidence_dir: Path) -> bool:
    """Validate AWS evidence JSON to detect runs without real AWS identity.

    If the evidence file exists and its metadata account_id/arn are \"unknown\",
    we treat the run as failed due to missing AWS authentication.
    """
    evidence_path = evidence_dir / f"{script_name}.json"
    if not evidence_path.exists():
        return True

    try:
        with open(evidence_path, "r") as f:
            data = json.load(f)
    except Exception:
        # If we cannot read/parse the file, do not guess; leave result unchanged.
        return True

    metadata = data.get("metadata", {})
    account_id = metadata.get("account_id")
    arn = metadata.get("arn")

    if account_id == "unknown" or arn == "unknown":
        print(f"  ✗ Evidence for '{script_name}' indicates unknown AWS identity (account_id/arn).")
        print("    This typically means AWS CLI was not authenticated when the fetcher ran.")
        print("    Please run 'aws sso login' for the appropriate profile and re-run the fetchers.")
        return False

    return True


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
                        "AWS_DEFAULT_REGION": region["region"]
                    }
                }
                
                # Add region-specific overrides (use AWS_DEFAULT_REGION for region key)
                for key, value in region["config"].items():
                    env_key = "AWS_DEFAULT_REGION" if key.upper() == "REGION" else f"AWS_{key.upper()}"
                    instance["config"][env_key] = value
                
                instances.append(instance)
    
    return instances


def run_fetcher_instance(
    instance: Dict[str, Any],
    evidence_dir: Path,
    timeout: int,
    error_reasons: Optional[Dict[str, str]] = None,
) -> bool:
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
        # Try to load from catalog to get the script_file (mirrors run_fetcher_script logic)
        catalog_path = Path("1-select-fetchers/evidence_fetchers_catalog.json")
        if catalog_path.exists():
            try:
                catalog = load_json_file(str(catalog_path))
                # Support both new catalog structure (evidence_fetchers_catalog.categories)
                # and legacy structure (evidence_fetchers)
                if "evidence_fetchers_catalog" in catalog and "categories" in catalog["evidence_fetchers_catalog"]:
                    for category_name, category_data in catalog["evidence_fetchers_catalog"]["categories"].items():
                        if "scripts" in category_data and script_name in category_data["scripts"]:
                            if "script_file" in category_data["scripts"][script_name]:
                                script_path = Path(category_data["scripts"][script_name]["script_file"])
                                break
                if script_path is None and "evidence_fetchers" in catalog and script_name in catalog["evidence_fetchers"]:
                    if "script_file" in catalog["evidence_fetchers"][script_name]:
                        script_path = Path(catalog["evidence_fetchers"][script_name]["script_file"])
            except Exception:
                # If catalog loading or parsing fails, fall back to constructed paths
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

    # Resolve AWS profile and region for this instance (used for both auth check and parameters)
    profile = config.get("AWS_PROFILE", os.environ.get("AWS_PROFILE", ""))
    region = config.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", ""))

    # For AWS-based instances, verify that the AWS CLI is authenticated before running
    if provider == "aws":
        if not check_aws_auth(profile, region):
            print(f"  ✗ {instance_name} could not run due to missing or invalid AWS CLI authentication.")
            print("    Please run 'aws sso login' for the appropriate profile and try again.")
            if error_reasons is not None:
                error_reasons[instance_name] = (
                    "AWS authentication missing or invalid; "
                    f"run 'aws sso login --profile {profile}' and re-run this fetcher."
                )
            return False
    
    # Prepare command
    if script_path.suffix == '.py':
        cmd = [sys.executable, str(script_path)]
    else:
        cmd = ["bash", str(script_path)]
    
    # Add common parameters - CSV disabled in favor of JSON
    cmd.extend([
        profile,  # profile
        region,   # region
        str(evidence_dir),  # output directory
        "/dev/null"  # CSV file disabled - JSON output preferred
    ])
    
    # Pass configuration as named arguments (only when non-empty)
    instance_profile = config.get("AWS_PROFILE", os.environ.get("AWS_PROFILE", ""))
    instance_region = config.get("AWS_DEFAULT_REGION", os.environ.get("AWS_DEFAULT_REGION", ""))
    if instance_profile:
        cmd.extend(["--profile", instance_profile])
    if instance_region:
        cmd.extend(["--region", instance_region])
    cmd.extend(["--output-dir", str(evidence_dir)])

    try:
        # Set instance-specific environment variables
        env = os.environ.copy()
        env["EVIDENCE_DIR"] = str(evidence_dir)
        for key, value in config.items():
            env[key] = value
        
        # Run the script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        
        if result.returncode == 0:
            # For AWS instances, validate the evidence metadata to catch \"unknown\" identities
            if provider == "aws" and not validate_aws_evidence(script_name, evidence_dir):
                print(f"  ✗ {instance_name} marked as failed due to invalid AWS identity in evidence.")
                if error_reasons is not None:
                    error_reasons[instance_name] = (
                        "Evidence metadata shows unknown AWS identity; "
                        "AWS CLI was likely not authenticated when this fetcher ran."
                    )
                return False

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


def run_fetcher_script(
    script_name: str,
    script_data: dict,
    evidence_dir: Path,
    aws_profile: str = None,
    aws_region: str = None,
    timeout: int = 300,
    additional_flags: list = None,
    error_reasons: Optional[Dict[str, str]] = None,
) -> bool:
def run_fetcher_script(script_name: str, script_data: dict, evidence_dir: Path,
                      aws_profile: str = None, aws_region: str = None, timeout: int = 300) -> bool:
    """Run a single fetcher script."""
    print(f"Running {script_name}...")
    
    # Determine script path - use script_file from script_data if available
    script_path: Optional[Path] = None
    
    if "script_file" in script_data:
        script_path = Path(script_data["script_file"])
    else:
        # Try to load from catalog to get the script_file (mirrors run_fetcher_instance logic)
        catalog_path = Path("1-select-fetchers/evidence_fetchers_catalog.json")
        if catalog_path.exists():
            try:
                catalog = load_json_file(str(catalog_path))
                # Support both new catalog structure (evidence_fetchers_catalog.categories)
                # and legacy structure (evidence_fetchers)
                if "evidence_fetchers_catalog" in catalog and "categories" in catalog["evidence_fetchers_catalog"]:
                    for category_name, category_data in catalog["evidence_fetchers_catalog"]["categories"].items():
                        if "scripts" in category_data and script_name in category_data["scripts"]:
                            if "script_file" in category_data["scripts"][script_name]:
                                script_path = Path(category_data["scripts"][script_name]["script_file"])
                                break
                if script_path is None and "evidence_fetchers" in catalog and script_name in catalog["evidence_fetchers"]:
                    if "script_file" in catalog["evidence_fetchers"][script_name]:
                        script_path = Path(catalog["evidence_fetchers"][script_name]["script_file"])
            except Exception:
                # If catalog loading or parsing fails, fall back to constructed paths
                pass
        
        # Fallback to constructing from script name if catalog lookup failed
        if script_path is None or not script_path.exists():
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

    # For AWS-based fetchers, verify that the AWS CLI is authenticated before running
    service = script_data.get('service', 'aws').lower()
    if service == 'aws':
        if not check_aws_auth(profile, region):
            print(f"  ✗ {script_name} could not run due to missing or invalid AWS CLI authentication.")
            print("    Please run 'aws sso login' for the appropriate profile and try again.")
            if error_reasons is not None:
                error_reasons[script_name] = (
                    "AWS authentication missing or invalid; "
                    f"run 'aws sso login --profile {profile}' and re-run this fetcher."
                )
            return False
    
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
    
    # Pass configuration as named arguments (only when non-empty)
    if profile:
        cmd.extend(["--profile", profile])
    if region:
        cmd.extend(["--region", region])
    cmd.extend(["--output-dir", str(evidence_dir)])

    try:
        # Set environment variables for the subprocess
        env = os.environ.copy()
        env["EVIDENCE_DIR"] = str(evidence_dir)
        if profile:
            env["AWS_PROFILE"] = profile
        if region:
            env["AWS_DEFAULT_REGION"] = region

        # Run the script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        
        if result.returncode == 0:
            # For AWS-based fetchers, validate the evidence metadata to catch \"unknown\" identities
            if service == "aws" and not validate_aws_evidence(script_name, evidence_dir):
                print(f"  ✗ {script_name} marked as failed due to invalid AWS identity in evidence.")
                if error_reasons is not None:
                    error_reasons[script_name] = (
                        "Evidence metadata shows unknown AWS identity; "
                        "AWS CLI was likely not authenticated when this fetcher ran."
                    )
                return False

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


def create_summary_file(
    evidence_dir: Path,
    results: dict,
    instance_info: dict = None,
    error_reasons: Optional[Dict[str, str]] = None,
):
    """Create a summary file with execution results.
    
    Args:
        evidence_dir: Directory containing evidence files
        results: Dict mapping script_name/instance_name to success bool
        instance_info: Optional dict mapping instance_name to instance config (for resource extraction)
        error_reasons: Optional dict mapping script_name/instance_name to a human-readable
            error description (for example, missing AWS authentication)
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
            
            # Try to match with base name (exact match)
            if base_name in json_files:
                evidence_file = str(json_files[base_name])
            else:
                # Try to find any file that starts with the base name followed by underscore
                # This handles cases like: base_name_paramify_project.json
                # Priority: exact prefix match (base_name_*), then any file starting with base_name
                matching_files = []
                for file_stem, file_path in json_files.items():
                    if file_stem == base_name:
                        # Exact match (already checked above, but keep for completeness)
                        matching_files.insert(0, (file_path, 0))  # Priority 0
                    elif file_stem.startswith(base_name + "_"):
                        # File starts with base_name_ (e.g., gitlab_merge_request_summary_paramify_paramify)
                        matching_files.append((file_path, 1))  # Priority 1
                    elif file_stem.startswith(base_name):
                        # File starts with base_name but no underscore (less specific)
                        matching_files.append((file_path, 2))  # Priority 2
                
                if matching_files:
                    # Sort by priority and take the first (best match)
                    matching_files.sort(key=lambda x: x[1])
                    evidence_file = str(matching_files[0][0])
        
        # Extract resource information from instance_name or instance_info
        resource = None
        if instance_info:
            # Try to get instance info for this script_name
            instance = instance_info.get(script_name)
            if instance:
                if instance.get("provider") == "gitlab" and "GITLAB_PROJECT_ID" in instance.get("config", {}):
                    resource = instance["config"]["GITLAB_PROJECT_ID"]
                elif instance.get("provider") == "aws" and "AWS_DEFAULT_REGION" in instance.get("config", {}):
                    resource = instance["config"]["AWS_DEFAULT_REGION"]
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
        if error_reasons and script_name in error_reasons:
            result_entry["error_reason"] = error_reasons[script_name]
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

    # Check tool dependencies for selected fetchers (warnings only)
    check_tool_dependencies(evidence_sets)

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

    # Set EVIDENCE_DIR so fetchers can read it from the environment
    os.environ["EVIDENCE_DIR"] = str(evidence_dir)

    # Run fetchers
    print(f"\nExecuting evidence fetchers...")
    print("-" * 40)
    
    # Get configuration from environment or use defaults
    timeout = int(os.environ.get("FETCHER_TIMEOUT", "300"))  # 5 minutes default
    
    print(f"Configuration:")
    print(f"  Timeout: {timeout} seconds")
    print()
    
    results = {}
    error_reasons: Dict[str, str] = {}
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
            success = run_fetcher_instance(instance, evidence_dir, timeout, error_reasons)
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
                                       aws_profile, aws_region, timeout, additional_flags, error_reasons)

            success = run_fetcher_script(script_name, script_data, evidence_dir,
                                       aws_profile, aws_region, timeout)
            results[script_name] = success
    
    # Create summary
    create_summary_file(
        evidence_dir,
        results,
        instance_info_map if instance_info_map else None,
        error_reasons if error_reasons else None,
    )
    
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
    print(f"Summary file: {evidence_dir}/summary.json")


if __name__ == "__main__":
    main()
