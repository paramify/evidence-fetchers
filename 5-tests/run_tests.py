#!/usr/bin/env python3
"""
Run Tests

This script runs validation and test scripts to ensure the system is working correctly.
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header():
    """Print the run tests header."""
    print("=" * 60)
    print("RUN TESTS")
    print("=" * 60)
    print()


def run_script(script_path: str, description: str, cwd: str | None = None, python_executable: str | None = None) -> bool:
    """Run a test script and return success status."""
    print(f"Running {description}...")
    
    try:
        executable = python_executable or sys.executable
        result = subprocess.run(
            [executable, script_path],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        
        if result.returncode == 0:
            print(f"  ✓ {description} passed")
            return True
        else:
            print(f"  ✗ {description} failed")
            if result.stderr:
                print(f"    Error: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"  ✗ {description} failed with error: {e}")
        return False


def run_bash_script(script_path: str, description: str, cwd: str | None = None) -> bool:
    """Run a bash test script and return success status."""
    print(f"Running {description}...")
    
    try:
        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        
        if result.returncode == 0:
            print(f"  ✓ {description} passed")
            return True
        else:
            print(f"  ✗ {description} failed")
            if result.stderr:
                print(f"    Error: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"  ✗ {description} failed with error: {e}")
        return False


def check_file_exists(file_path: str, description: str) -> bool:
    """Check if a file exists."""
    if os.path.exists(file_path):
        print(f"  ✓ {description} found")
        return True
    else:
        print(f"  ✗ {description} not found")
        return False


def main():
    """Main test function."""
    print_header()

    print("This script will run various tests to ensure the system is working correctly.")
    print()

    # Resolve important directories regardless of invocation CWD
    tests_dir = Path(__file__).resolve().parent
    repo_root = tests_dir.parent

    # Prefer project venv Python if available
    venv_python = repo_root / "venv" / "bin" / "python"
    preferred_python = str(venv_python) if venv_python.exists() else sys.executable
    
    # Test results
    test_results = []
    
    # Check for required files
    print("Checking required files...")
    print("-" * 30)
    
    required_files = [
        (repo_root / "evidence_sets.json", "Evidence sets configuration"),
        (repo_root / ".env", "Environment variables file"),
        (repo_root / "fetchers", "Fetchers directory"),
        (repo_root / "evidence", "Evidence directory"),
    ]
    
    for file_path, description in required_files:
        result = check_file_exists(str(file_path), description)
        test_results.append(("File Check", description, result))
    
    print()
    
    # Run validation tests
    print("Running validation tests...")
    print("-" * 30)
    
    # Check if validation script exists
    validation_script = repo_root / "6-add-new-fetcher" / "validate_catalog.py"
    if validation_script.exists():
        result = run_script(str(validation_script), "Catalog validation", cwd=str(validation_script.parent), python_executable=preferred_python)
        test_results.append(("Validation", "Catalog validation", result))
    else:
        print("  ⚠ Catalog validation script not found")
        test_results.append(("Validation", "Catalog validation", False))
    
    print()
    
    # Run evidence fetcher tests
    print("Running evidence fetcher tests...")
    print("-" * 30)
    
    # Check if test scripts exist
    test_scripts = [
        (tests_dir / "simple_test.py", "Simple functionality test"),
        (tests_dir / "test_system.py", "System integration test"),
    ]
    
    for script_path, description in test_scripts:
        if script_path.exists():
            result = run_script(str(script_path), description, cwd=str(tests_dir), python_executable=preferred_python)
            test_results.append(("Fetcher Test", description, result))
        else:
            print(f"  ⚠ {description} script not found")
            test_results.append(("Fetcher Test", description, False))
    
    print()
    
    # Run demo tests
    print("Running demo tests...")
    print("-" * 30)
    
    demo_script = tests_dir / "demo.py"
    if demo_script.exists():
        result = run_script(str(demo_script), "Demo functionality", cwd=str(tests_dir), python_executable=preferred_python)
        test_results.append(("Demo", "Demo functionality", result))
    else:
        print("  ⚠ Demo script not found")
        test_results.append(("Demo", "Demo functionality", False))
    
    print()
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for _, _, result in test_results if result)
    failed_tests = total_tests - passed_tests
    
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print()
    
    if failed_tests > 0:
        print("Failed tests:")
        for category, test_name, result in test_results:
            if not result:
                print(f"  ✗ {category}: {test_name}")
        print()
    
    if passed_tests == total_tests:
        print("✓ All tests passed! The system is ready to use.")
    else:
        print("⚠ Some tests failed. Please check the issues above.")
        print("You may still be able to use the system, but some features may not work correctly.")
    
    print("=" * 60)


if __name__ == "__main__":
    main()