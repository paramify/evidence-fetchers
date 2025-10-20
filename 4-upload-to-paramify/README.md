# Upload Evidence to Paramify

This directory contains the standalone evidence upload functionality.

## Purpose

The upload script finds the latest evidence directory (based on timestamp) and uploads all evidence files to Paramify via the API.

## Usage

### From Main Menu
- Run option 4 from the main menu
- The script will automatically find the latest evidence directory
- Confirm the upload and proceed

### Standalone
```bash
python 4-upload-to-paramify/upload_to_paramify.py
```

## Features

- **Automatic Discovery**: Finds the latest evidence directory based on timestamp
- **Flexible Summary Detection**: Works with `summary.json`, `execution_summary.json`, or `evidence_summary.json`
- **Validation**: Checks that required files exist before uploading
- **Confirmation**: Asks for user confirmation before proceeding
- **Error Handling**: Graceful handling of missing files or API errors

## Requirements

- Environment variables must be set (see Prerequisites)
- Evidence directory must exist with valid summary file
- Valid Paramify API credentials

## Integration

This script is designed to work independently but can also be integrated into the main workflow. It replaces the paramify upload functionality that was previously embedded in the run fetchers script.
