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
3. **Associates Solution Capabilities**: Matches catalog SC names against the
   workspace (case-insensitive, whitespace-normalized) and associates the
   evidence. Unmatched names are logged and skipped.
4. **Associates Validators**: For each catalog validator, reuses the existing
   workspace validator by name or creates a new one via `POST /validators`,
   then associates it with the evidence. Validators referencing `{{tokens}}`
   not present in `config/validator_parameters.json` are skipped.
5. **Uploads Scripts**: Optionally uploads fetcher scripts as evidence artifacts
6. **Records Results**: Logs upload results in upload_log.json

## Usage

```bash
python create_evidence_sets.py
```

## Prerequisites

- Evidence sets configuration (evidence_sets.json)
- Paramify API token in .env file
- Paramify API access
- Optional: `config/validator_parameters.json` (copy from
  `config/validator_parameters.example.json`) — required only for catalog
  validators that reference `{{tokens}}`. Run
  `python scripts/configure_parameters.py` to audit which tokens the catalog
  currently needs.

## Validator API Behavior

- Paramify enforces unique validator names per workspace — the pusher caches
  the `GET /validators` list once per run and looks up by normalized name.
- There is no `PATCH /validators` endpoint; regex drift on existing validators
  must be resolved manually in the Paramify UI.
- Duplicate association attempts (HTTP 400/409 with "already"/"duplicate" in
  the error) are swallowed so re-runs are idempotent.

## Next Steps

After creating evidence sets:

1. **Run Fetchers** (option 3): Execute the evidence fetcher scripts
2. **Tests** (option 4): Validate your setup
