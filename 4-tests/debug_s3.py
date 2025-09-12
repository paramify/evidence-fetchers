#!/usr/bin/env python3
"""
Debug script for S3 MFA Delete validation
"""

import json
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.append('..')

def test_s3_mfa_delete():
    """Test S3 MFA Delete with mock data"""
    print("Testing S3 MFA Delete validation...")
    
    # Mock data
    mock_response = {
        "Status": "Enabled",
        "MFADelete": "Enabled"
    }
    
    print(f"Mock response: {mock_response}")
    
    # Test validation function directly
    from fetchers.aws.s3_mfa_delete import validate_response
    
    validation_rules = [
        r'"MFADelete":\s*"Enabled"',
        r'"Status":\s*"Enabled"'
    ]
    
    # Test validation
    result = validate_response(mock_response, validation_rules)
    print(f"Validation result: {result}")
    
    # Show JSON string
    json_str = json.dumps(mock_response, sort_keys=True)
    print(f"JSON string: {json_str}")
    
    # Test each rule
    import re
    for i, rule in enumerate(validation_rules):
        match = re.search(rule, json_str)
        print(f"Rule {i+1} ({rule}): {'✓' if match else '✗'}")
        if match:
            print(f"  Matched: {match.group()}")
    
    # Now test with the actual fetcher
    print("\nTesting with actual fetcher...")
    
    with patch('fetchers.s3_mfa_delete.subprocess.run') as mock_run:
        # Configure mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_response)
        mock_run.return_value = mock_result
        
        # Import and test fetcher
        import importlib.util
        spec = importlib.util.spec_from_file_location("s3_mfa_delete", "../fetchers/s3_mfa_delete.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Test the run function
        status, evidence_file = module.run("test-bucket", "debug_evidence")
        
        print(f"Fetcher result: {status}")
        print(f"Evidence file: {evidence_file}")
        
        # Show the generated evidence file
        if evidence_file and Path(evidence_file).exists():
            with open(evidence_file, 'r') as f:
                content = f.read()
                print(f"Generated evidence content: {content}")
        
        # Clean up
        import shutil
        if Path("debug_evidence").exists():
            shutil.rmtree("debug_evidence")

if __name__ == "__main__":
    from pathlib import Path
    test_s3_mfa_delete()
