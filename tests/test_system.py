#!/usr/bin/env python3
"""
Test script for the evidence fetcher system

This script tests the system components without requiring real AWS resources.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.append('..')


def test_evidence_sets_loading():
    """Test loading evidence sets configuration"""
    print("Testing evidence sets loading...")
    
    try:
        with open("../evidence_sets.json", 'r') as f:
            evidence_sets = json.load(f)
        
        # Check structure
        assert "evidence_sets" in evidence_sets
        assert len(evidence_sets["evidence_sets"]) > 0
        
        # Check required fields for each evidence set
        for name, config in evidence_sets["evidence_sets"].items():
            required_fields = ["id", "name", "description", "service", "instructions", "validation_rules"]
            for field in required_fields:
                assert field in config, f"Missing field '{field}' in evidence set '{name}'"
        
        print("✓ Evidence sets configuration is valid")
        return True
    except Exception as e:
        print(f"✗ Error loading evidence sets: {e}")
        return False


def test_fetcher_imports():
    """Test that fetcher modules can be imported"""
    print("Testing fetcher imports...")
    
    fetcher_files = ["../fetchers/s3_mfa_delete.py", "../fetchers/ebs_encryption.py"]
    
    for fetcher_file in fetcher_files:
        try:
            # Test import
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_fetcher", fetcher_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Check that run function exists
            assert hasattr(module, 'run'), f"Missing 'run' function in {fetcher_file}"
            
            print(f"✓ Successfully imported {fetcher_file}")
        except Exception as e:
            print(f"✗ Error importing {fetcher_file}: {e}")
            return False
    
    return True


def test_fetcher_runner_import():
    """Test that fetcher runner can be imported"""
    print("Testing fetcher runner import...")
    
    try:
        import fetcher_runner
        print("✓ Successfully imported fetcher_runner")
        return True
    except Exception as e:
        print(f"✗ Error importing fetcher_runner: {e}")
        return False


def test_paramify_pusher_import():
    """Test that paramify pusher can be imported"""
    print("Testing paramify pusher import...")
    
    try:
        import paramify_pusher
        print("✓ Successfully imported paramify_pusher")
        return True
    except Exception as e:
        print(f"✗ Error importing paramify_pusher: {e}")
        return False


def test_directory_structure():
    """Test that required directories exist"""
    print("Testing directory structure...")
    
    required_dirs = ["../fetchers", "../evidence"]
    
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            print(f"✗ Required directory '{dir_name}' does not exist")
            return False
    
    print("✓ All required directories exist")
    return True


def test_config_files():
    """Test that configuration files exist and are valid JSON"""
    print("Testing configuration files...")
    
    config_files = ["../evidence_sets.json", "test_config.json"]
    
    for config_file in config_files:
        try:
            with open(config_file, 'r') as f:
                json.load(f)
            print(f"✓ {config_file} is valid JSON")
        except Exception as e:
            print(f"✗ Error with {config_file}: {e}")
            return False
    
    return True


def test_fetcher_with_mock():
    """Test a fetcher with mocked AWS CLI"""
    print("Testing fetcher with mocked AWS CLI...")
    
    # Mock AWS CLI response for S3 MFA Delete
    mock_response = {
        "Status": "Enabled",
        "MFADelete": "Enabled"
    }
    
    with patch('subprocess.run') as mock_run:
        # Configure mock
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(mock_response)
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Import and test fetcher
        import importlib.util
        spec = importlib.util.spec_from_file_location("s3_mfa_delete", "../fetchers/s3_mfa_delete.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Test the run function
        status, evidence_file = module.run("test-bucket", "test_evidence")
        
        assert status == "PASS", f"Expected PASS, got {status}"
        assert evidence_file != "", "Expected evidence file path"
        
        print("✓ Fetcher test passed")
        return True


def main():
    """Run all tests"""
    print("Running evidence fetcher system tests...\n")
    
    tests = [
        test_directory_structure,
        test_config_files,
        test_evidence_sets_loading,
        test_fetcher_imports,
        test_fetcher_runner_import,
        test_paramify_pusher_import,
        test_fetcher_with_mock
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            print()
    
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The system is ready to use.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
