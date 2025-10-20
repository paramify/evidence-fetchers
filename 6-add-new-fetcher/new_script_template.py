#!/usr/bin/env python3
"""
Fetcher: [SCRIPT_NAME] validation

[DESCRIPTION_OF_WHAT_THIS_SCRIPT_COLLECTS]

AWS CLI Command:
    [AWS_CLI_COMMAND_EXAMPLE]

AWS API Call:
    [BOTO3_API_CALL_EXAMPLE]

Validator Rules:
    [VALIDATION_RULE_1]
    [VALIDATION_RULE_2]

Expected Outcome:
    [EXPECTED_OUTCOME_DESCRIPTION]
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple, Optional


def run_aws_cli_command(command: str) -> Optional[dict]:
    """Run AWS CLI command and return JSON result"""
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running AWS CLI command: {e}")
        print(f"stderr: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None


def validate_response(data: dict, validation_rules: list) -> bool:
    """Apply regex validation rules to the response data"""
    data_str = json.dumps(data, sort_keys=True)
    
    for rule in validation_rules:
        if not re.search(rule, data_str):
            print(f"Validation rule failed: {rule}")
            return False
    
    return True


def run(target_resource: str, evidence_dir: str) -> Tuple[str, str]:
    """
    Run [SCRIPT_NAME] check for the specified resource
    
    Args:
        target_resource: The resource to check (e.g., bucket name, instance ID)
        evidence_dir: Directory to save evidence files
        
    Returns:
        Tuple of (status, evidence_file_path)
        status: "PASS", "FAIL", or "ERROR"
        evidence_file_path: Path to the saved evidence file
    """
    
    # Create evidence directory if it doesn't exist
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    
    # AWS CLI command
    command = f"aws [service] [command] --[resource-param] {target_resource} --output json"
    
    print(f"Running [SCRIPT_NAME] check for resource: {target_resource}")
    print(f"Command: {command}")
    
    # Execute AWS CLI command
    result = run_aws_cli_command(command)
    
    if result is None:
        return "ERROR", ""
    
    # Validation rules
    validation_rules = [
        r'[VALIDATION_RULE_1]',
        r'[VALIDATION_RULE_2]'
    ]
    
    # Apply validation
    is_compliant = validate_response(result, validation_rules)
    status = "PASS" if is_compliant else "FAIL"
    
    # Save evidence file
    evidence_filename = f"[script_name]_{target_resource}.json"
    evidence_path = Path(evidence_dir) / evidence_filename
    
    with open(evidence_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"Status: {status}")
    print(f"Evidence saved to: {evidence_path}")
    
    return status, str(evidence_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python [script_name].py <resource-name> <evidence-dir>")
        sys.exit(1)
    
    resource_name = sys.argv[1]
    evidence_directory = sys.argv[2]
    
    status, evidence_file = run(resource_name, evidence_directory)
    print(f"Final result: {status}")
    if evidence_file:
        print(f"Evidence file: {evidence_file}")
