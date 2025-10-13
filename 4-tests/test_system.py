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

# Add repo root to path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def test_evidence_sets_loading():
    """Test loading evidence sets configuration"""
    print("Testing evidence sets loading...")
    
    try:
        with open(str(repo_root / "evidence_sets.json"), 'r') as f:
            evidence_sets = json.load(f)
        
        # Check structure
        assert "evidence_sets" in evidence_sets
        assert len(evidence_sets["evidence_sets"]) > 0
        
        # Check required fields for each evidence set
        for name, config in evidence_sets["evidence_sets"].items():
            required_fields = ["id", "name", "description", "service", "instructions"]
            for field in required_fields:
                assert field in config, f"Missing field '{field}' in evidence set '{name}'"
            # Accept either 'validation_rules' or 'validationRules'
            rules = config.get('validation_rules', config.get('validationRules', None))
            assert rules is not None, f"Missing validation rules in evidence set '{name}'"
        
        print("✓ Evidence sets configuration is valid")
        return True
    except Exception as e:
        print(f"✗ Error loading evidence sets: {e}")
        return False


def test_fetcher_imports():
    """Test that a Python fetcher module can be imported"""
    print("Testing fetcher imports...")
    
    fetcher_file = str(repo_root / "fetchers/rippling/rippling_current_employees.py")
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_fetcher", fetcher_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        assert hasattr(module, 'main'), f"Missing 'main' function in {fetcher_file}"
        print(f"✓ Successfully imported {fetcher_file}")
        return True
    except Exception as e:
        print(f"✗ Error importing {fetcher_file}: {e}")
        return False


def test_fetcher_runner_import():
    """Test that fetcher runner can be imported"""
    print("Testing fetcher runner import...")
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fetcher_runner", str(repo_root / "3-run-fetchers" / "run_fetchers.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print("✓ Successfully imported fetcher_runner")
        return True
    except Exception as e:
        print(f"✗ Error importing fetcher_runner: {e}")
        return False


def test_paramify_pusher_import():
    """Test that paramify pusher can be imported (with requests mocked)"""
    print("Testing paramify pusher import...")
    
    try:
        from unittest.mock import patch, MagicMock
        import importlib.util
        with patch('requests.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"ok": True}
            mock_post.return_value = mock_resp
            
            spec = importlib.util.spec_from_file_location("paramify_pusher", str(repo_root / "2-create-evidence-sets" / "paramify_pusher.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        print("✓ Successfully imported paramify_pusher")
        return True
    except Exception as e:
        print(f"✗ Error importing paramify_pusher: {e}")
        return False


def test_directory_structure():
    """Test that required directories exist"""
    print("Testing directory structure...")
    
    required_dirs = [str(repo_root / "fetchers"), str(repo_root / "evidence")]
    
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            print(f"✗ Required directory '{dir_name}' does not exist")
            return False
    
    print("✓ All required directories exist")
    return True


def test_config_files():
    """Test that configuration files exist and are valid JSON"""
    print("Testing configuration files...")
    
    config_files = [str(repo_root / "evidence_sets.json"), str(Path(__file__).resolve().parent / "test_config.json")]
    
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
    """Test a Python fetcher with mocked HTTP requests"""
    print("Testing fetcher with mocked HTTP...")
    
    # Mock Rippling API response
    mock_response = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    
    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("rippling_current_employees", str(repo_root / "fetchers/rippling/rippling_current_employees.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Simulate writing to a temp directory
        tmp_dir = Path("test_evidence")
        if tmp_dir.exists():
            import shutil
            shutil.rmtree(tmp_dir)
        
        # Call main-like behavior
        # Ensure token is present for the module under test
        os.environ.setdefault("RIPPLING_API_TOKEN", "test-token")
        employees = module.fetch_current_employees()
        assert len(employees) == 2
        
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
