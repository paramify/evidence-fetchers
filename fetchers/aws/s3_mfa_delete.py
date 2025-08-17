"""
Fetcher: S3 MFA Delete for CloudTrail bucket

AWS CLI Command:
    aws s3api get-bucket-versioning --bucket DOC-EXAMPLE-BUCKET1 --output json

AWS API Call:
    boto3.client("s3").get_bucket_versioning(Bucket="DOC-EXAMPLE-BUCKET1")

Validator Rules:
    "Status":\\s*"Enabled"
    "MFADelete":\\s*"Enabled"

Expected Outcome:
    JSON contains both Status=Enabled and MFADelete=Enabled
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


def run(target_bucket: str, evidence_dir: str) -> Tuple[str, str]:
    """
    Run S3 MFA Delete check for the specified bucket
    
    Args:
        target_bucket: The S3 bucket name to check
        evidence_dir: Directory to save evidence files
        
    Returns:
        Tuple of (status, evidence_file_path)
        status: "PASS", "FAIL", or "ERROR"
        evidence_file_path: Path to the saved evidence file
    """
    
    # Create evidence directory if it doesn't exist
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    
    # AWS CLI command
    command = f"aws s3api get-bucket-versioning --bucket {target_bucket} --output json"
    
    print(f"Running S3 MFA Delete check for bucket: {target_bucket}")
    print(f"Command: {command}")
    
    # Execute AWS CLI command
    result = run_aws_cli_command(command)
    
    if result is None:
        return "ERROR", ""
    
    # Validation rules - look for the values in the JSON string (order doesn't matter due to sort_keys=True)
    validation_rules = [
        r'"MFADelete":\s*"Enabled"',
        r'"Status":\s*"Enabled"'
    ]
    
    # Apply validation
    is_compliant = validate_response(result, validation_rules)
    status = "PASS" if is_compliant else "FAIL"
    
    # Save evidence file
    evidence_filename = f"s3_mfa_delete_{target_bucket}.json"
    evidence_path = Path(evidence_dir) / evidence_filename
    
    with open(evidence_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"Status: {status}")
    print(f"Evidence saved to: {evidence_path}")
    
    return status, str(evidence_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python s3_mfa_delete.py <bucket-name> <evidence-dir>")
        sys.exit(1)
    
    bucket_name = sys.argv[1]
    evidence_directory = sys.argv[2]
    
    status, evidence_file = run(bucket_name, evidence_directory)
    print(f"Final result: {status}")
    if evidence_file:
        print(f"Evidence file: {evidence_file}")
