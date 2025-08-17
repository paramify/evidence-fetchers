#!/usr/bin/env python3
"""
Test runner for the evidence fetcher system

This script runs all tests from the tests directory.
"""

import sys
import subprocess
from pathlib import Path

def run_test_file(test_file: str) -> bool:
    """Run a single test file and return success status"""
    print(f"\n{'='*50}")
    print(f"Running {test_file}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              cwd=Path(__file__).parent,
                              capture_output=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {test_file}: {e}")
        return False

def main():
    """Run all test files"""
    test_dir = Path(__file__).parent
    
    # List of test files to run
    test_files = [
        "test_system.py",
        "simple_test.py",
        "debug_s3.py",
        "demo.py"
    ]
    
    print("🧪 Running Evidence Fetcher System Tests")
    print(f"Test directory: {test_dir}")
    
    passed = 0
    total = len(test_files)
    
    for test_file in test_files:
        if run_test_file(test_file):
            passed += 1
            print(f"✅ {test_file} passed")
        else:
            print(f"❌ {test_file} failed")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} test files passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
