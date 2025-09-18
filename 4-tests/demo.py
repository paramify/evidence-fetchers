#!/usr/bin/env python3
"""
Demo script for the evidence fetcher system

This script demonstrates how to use the system with mocked AWS responses.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.append('..')


def demo_fetcher_runner():
    """Demo the fetcher runner with mocked AWS responses"""
    print("=== Demo: Fetcher Runner ===\n")
    
    # Mock AWS CLI responses
    mock_responses = {
        "s3_mfa_delete": {
            "Status": "Enabled",
            "MFADelete": "Enabled"
        },
        "ebs_encryption": {
            "Volumes": [
                {
                    "VolumeId": "vol-0123456789abcdef",
                    "Encrypted": True,
                    "State": "in-use"
                }
            ]
        }
    }
    
    # Mock both fetcher modules - use the actual module paths
    with patch('subprocess.run') as mock_run:
        
        # Configure mock to return different responses based on command
        def mock_run_side_effect(command, *args, **kwargs):
            mock_result = MagicMock()
            mock_result.returncode = 0
            
            if "s3api get-bucket-versioning" in command:
                mock_result.stdout = json.dumps(mock_responses["s3_mfa_delete"])
            elif "ec2 describe-volumes" in command:
                mock_result.stdout = json.dumps(mock_responses["ebs_encryption"])
            else:
                mock_result.stdout = json.dumps({})
            
            return mock_result
        
        mock_run.side_effect = mock_run_side_effect
        
        # Create a temporary evidence directory
        evidence_dir = Path("demo_evidence")
        evidence_dir.mkdir(exist_ok=True)
        
        # Run fetchers
        print("Running fetchers with mocked AWS responses...")
        
        # Test individual fetchers
        import importlib.util
        
        # Test S3 MFA Delete fetcher
        s3_fetcher_path = Path("../fetchers/s3_mfa_delete.py")
        if not s3_fetcher_path.exists():
            s3_fetcher_path = Path("fetchers/s3_mfa_delete.py")
        
        spec = importlib.util.spec_from_file_location("s3_mfa_delete", str(s3_fetcher_path))
        s3_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(s3_module)
        
        status, evidence_file = s3_module.run("demo-bucket", str(evidence_dir))
        print(f"S3 MFA Delete: {status} -> {evidence_file}")
        
        # Test EBS Encryption fetcher
        ebs_fetcher_path = Path("../fetchers/ebs_encryption.py")
        if not ebs_fetcher_path.exists():
            ebs_fetcher_path = Path("fetchers/ebs_encryption.py")
        
        spec = importlib.util.spec_from_file_location("ebs_encryption", str(ebs_fetcher_path))
        ebs_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ebs_module)
        
        status, evidence_file = ebs_module.run("vol-0123456789abcdef", str(evidence_dir))
        print(f"EBS Encryption: {status} -> {evidence_file}")
        
        # Show generated files
        print(f"\nGenerated evidence files in {evidence_dir}:")
        for file_path in evidence_dir.glob("*.json"):
            print(f"  - {file_path.name}")
        
        # Clean up
        import shutil
        shutil.rmtree(evidence_dir)


def demo_evidence_sets():
    """Demo the evidence sets configuration"""
    print("\n=== Demo: Evidence Sets Configuration ===\n")
    
    # Handle both running from tests/ and from project root
    evidence_sets_path = Path("../evidence_sets.json")
    if not evidence_sets_path.exists():
        evidence_sets_path = Path("evidence_sets.json")
    
    with open(evidence_sets_path, 'r') as f:
        evidence_sets = json.load(f)
    
    print("Available evidence sets:")
    for name, config in evidence_sets["evidence_sets"].items():
        print(f"\n{name}:")
        print(f"  ID: {config['id']}")
        print(f"  Name: {config['name']}")
        print(f"  Service: {config['service']}")
        print(f"  Description: {config['description']}")
        print(f"  Validation Rules: {len(config['validation_rules'])} rules")


def demo_paramify_pusher():
    """Demo the Paramify pusher (without actually uploading)"""
    print("\n=== Demo: Paramify Pusher ===\n")
    
    # Create a mock summary file
    summary_data = {
        "timestamp": "2025-01-15T12:00:00Z",
        "evidence_directory": "demo_evidence",
        "results": [
            {
                "check": "s3_mfa_delete",
                "resource": "demo-bucket",
                "status": "PASS",
                "evidence_file": "demo_evidence/s3_mfa_delete_demo-bucket.json"
            },
            {
                "check": "ebs_encryption",
                "resource": "vol-0123456789abcdef",
                "status": "PASS",
                "evidence_file": "demo_evidence/ebs_encryption_vol-0123456789abcdef.json"
            }
        ]
    }
    
    # Save mock summary
    with open("demo_summary.json", 'w') as f:
        json.dump(summary_data, f, indent=2)
    
    print("Created mock summary file: demo_summary.json")
    print("This would be uploaded to Paramify with the following structure:")
    
    for result in summary_data["results"]:
        print(f"\nEvidence Set for {result['check']}:")
        print(f"  - Check: {result['check']}")
        print(f"  - Resource: {result['resource']}")
        print(f"  - Status: {result['status']}")
        print(f"  - Evidence File: {result['evidence_file']}")
    
    # Clean up
    Path("demo_summary.json").unlink(missing_ok=True)


def main():
    """Run all demos"""
    print("🎯 Evidence Fetcher System Demo\n")
    print("This demo shows how the system works with mocked AWS responses.\n")
    
    try:
        demo_evidence_sets()
        demo_fetcher_runner()
        demo_paramify_pusher()
        
        print("\n✅ Demo completed successfully!")
        print("\nTo use the system with real AWS resources:")
        print("1. Configure AWS credentials: aws configure")
        print("2. Set Paramify API token: export PARAMIFY_API_TOKEN='your-token'")
        print("3. Run fetchers: python fetcher_runner.py --config tests/test_config.json")
        print("4. Upload to Paramify: python paramify_pusher.py evidence/YYYYMMDD_HHMMSS/summary.json")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
