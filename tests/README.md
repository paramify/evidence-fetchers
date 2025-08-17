# Tests

This directory contains all test and demo files for the evidence fetcher system.

## Test Files

### `test_system.py`
Comprehensive system test that validates:
- Directory structure
- Configuration files
- Evidence sets loading
- Fetcher imports
- Fetcher runner import
- Paramify pusher import
- Fetcher functionality with mocked AWS responses

### `simple_test.py`
Simple validation test that verifies the regex validation function works correctly.

### `debug_s3.py`
Debug script specifically for testing S3 MFA Delete validation with detailed output.

### `demo.py`
Demo script that shows how the system works with mocked AWS responses, including:
- Evidence sets configuration
- Fetcher runner functionality
- Paramify pusher workflow

### `run_tests.py`
Test runner script that executes all test files in sequence.

## Running Tests

### Run all tests:
```bash
cd tests
python run_tests.py
```

### Run individual tests:
```bash
cd tests
python test_system.py
python simple_test.py
python debug_s3.py
python demo.py
```

### Run from project root:
```bash
python tests/run_tests.py
python tests/test_system.py
python tests/demo.py
```

## Test Files and Configuration

### Configuration Files
- `test_config.json` - Test configuration with fetcher-resource mappings
- `test_evidence/` - Directory for test evidence files generated during testing

### Test Environment

Tests use mocked AWS responses to avoid requiring real AWS credentials or resources. The mock responses simulate:

- S3 bucket versioning with MFA delete enabled
- EBS volume encryption status
- CloudTrail configuration
- RDS encryption settings

## Adding New Tests

When adding new test files:

1. Place them in this `tests/` directory
2. Add `sys.path.append('..')` to import from parent directory
3. Update file paths to use `../` prefix for parent directory files
4. Add the test file to `run_tests.py` if it should be run automatically

## Test Dependencies

Tests require the same dependencies as the main system:
- `requests`
- `boto3`
- Python standard library modules

Run tests from the project root with the virtual environment activated:
```bash
source venv/bin/activate
python tests/run_tests.py
```
