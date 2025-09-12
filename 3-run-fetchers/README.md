# 3) Run Fetchers

This directory contains scripts for executing evidence fetcher scripts and storing evidence.

## Files

- `run_fetchers.py` - Main execution script
- `main_fetcher.py` - Legacy fetcher execution script
- `README.md` - This documentation file

## What This Does

The fetcher execution system:

1. **Reads Configuration**: Loads evidence_sets.json to determine which scripts to run
2. **Executes Scripts**: Runs each fetcher script with appropriate parameters
3. **Stores Evidence**: Saves evidence files in timestamped directories
4. **Uploads to Paramify**: Optionally uploads evidence files via API
5. **Creates Reports**: Generates execution summary and CSV reports

## Usage

```bash
python run_fetchers.py
```

## Prerequisites

- Evidence sets configuration (evidence_sets.json)
- Environment variables (.env file)
- Required dependencies installed

## Next Steps

After running fetchers:

1. **Tests** (option 4): Validate your results
2. **Add New Fetcher** (option 5): Contribute new scripts
