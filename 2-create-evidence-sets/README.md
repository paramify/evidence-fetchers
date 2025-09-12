# 2) Create Evidence Sets in Paramify

This directory contains scripts for uploading evidence sets to Paramify via API.

## Files

- `create_evidence_sets.py` - Main upload script
- `paramify_pusher.py` - Paramify API integration
- `README.md` - This documentation file

## What This Does

The evidence sets creation system:

1. **Reads Evidence Sets**: Loads evidence_sets.json generated in step 1
2. **Creates Evidence Sets**: Uploads evidence sets to Paramify via API
3. **Uploads Scripts**: Optionally uploads fetcher scripts as evidence artifacts
4. **Records Results**: Logs upload results in upload_log.json

## Usage

```bash
python create_evidence_sets.py
```

## Prerequisites

- Evidence sets configuration (evidence_sets.json)
- Paramify API token in .env file
- Paramify API access

## Next Steps

After creating evidence sets:

1. **Run Fetchers** (option 3): Execute the evidence fetcher scripts
2. **Tests** (option 4): Validate your setup
