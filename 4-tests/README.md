# 4) Tests

This directory contains test scripts and validation tools.

## Files

- `run_tests.py` - Main test runner
- `simple_test.py` - Simple functionality test
- `test_system.py` - System integration test
- `demo.py` - Demo functionality
- `README.md` - This documentation file

## What This Does

The testing system:

1. **Checks Files**: Validates required files and directories exist
2. **Runs Validation**: Executes catalog validation
3. **Tests Fetchers**: Runs evidence fetcher tests
4. **Demo Tests**: Executes demo functionality
5. **Provides Summary**: Shows comprehensive test results

## Usage

```bash
python run_tests.py
```

## Next Steps

After running tests:

1. **Add New Fetcher** (option 5): Contribute new scripts
2. **Evidence Requirement Mapping** (option 6): Map requirements