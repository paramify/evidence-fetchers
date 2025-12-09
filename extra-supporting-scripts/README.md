# Extra Supporting Scripts

Supporting tools for evidence management, requirement mapping, and workspace operations.

## Evidence Management

### Delete All Evidence

⚠️ **WARNING**: This operation is irreversible and will permanently delete all evidence and artifacts.

**Usage**:
```bash
python extra-supporting-scripts/delete_all_evidence.py
```

**Environment Variables**:
- `PARAMIFY_UPLOAD_API_TOKEN` - API token (required)
- `PARAMIFY_API_BASE_URL` - API base URL (optional, defaults to `https://app.paramify.com/api/v0`)

**Features**:
- Displays workspace/program information
- Shows summary of evidence to be deleted
- Requires two confirmations before proceeding
- Provides deletion summary with success/failure counts

## Evidence Export/Import

Transfer evidence sets and artifacts between Paramify workspaces across different environments.

**Usage**:
```bash
# Interactive mode
python extra-supporting-scripts/export_import_evidence.py

# Command line mode
python extra-supporting-scripts/export_import_evidence.py \
  --export-env prod \
  --import-env stage \
  --export-token <token> \
  --import-token <token>
```

**Environment Variables**:
- `PARAMIFY_EXPORT_API_TOKEN` - API token for export workspace
- `PARAMIFY_IMPORT_API_TOKEN` - API token for import workspace

**Options**:
- `--export-env` / `--import-env` - Environment: stage, prod, or demo
- `--export-token` / `--import-token` - API tokens
- `--export-dir` - Directory to store exported evidence (optional)
- `--keep-export` - Keep exported files after import (default: delete)

## CSV to Paramify Evidence Sets

Convert CSV files (like Coalfire Evidence Request Lists) to JSON format and upload evidence sets to Paramify.

**Scripts**:
- `csv_to_evidence_json.py` - Convert CSV to evidence sets JSON format
- `json_to_paramify.py` - Upload evidence sets from JSON to Paramify
- `csv_to_paramify.py` - Unified workflow: CSV → JSON → Paramify

**Usage**:

```bash
# Convert CSV to JSON only
python extra-supporting-scripts/csv_to_evidence_json.py \
  --csv "Coalfire FedRAMP 20x Evidence Request List.csv" \
  --output evidence_sets.json \
  --prefix "COALFIRE"

# Convert and upload to Paramify
python extra-supporting-scripts/csv_to_paramify.py \
  --csv input.csv \
  --prefix "CUSTOM" \
  --upload

# Upload existing JSON to Paramify
python extra-supporting-scripts/json_to_paramify.py \
  --json evidence_sets.json
```

**CSV Format**: CSV files should have columns: Evidence ID, Evidence Title, Evidence Description, Evidence Domain, Evidence Category, Requirements

## FedRAMP JSON to Paramify

Parse FedRAMP JSON files from GitHub and convert to evidence sets in Paramify.

**Scripts**:
- `fedramp_json_parser.py` - Parse FedRAMP JSON files to evidence sets format
- `fedramp_to_paramify.py` - Unified workflow: FedRAMP JSON → Paramify
- `fedramp_batch_processor.py` - Process all FedRAMP standards in batch

**Usage**:

```bash
# Process all FedRAMP standards and save JSON files
python extra-supporting-scripts/fedramp_batch_processor.py \
  --output-dir fedramp_evidence_sets/

# Process and upload all to Paramify
python extra-supporting-scripts/fedramp_batch_processor.py \
  --upload \
  --output-dir fedramp_evidence_sets/

# Process specific standards only
python extra-supporting-scripts/fedramp_batch_processor.py \
  --standards FRMR.ADS.authorization-data-sharing FRMR.MAS.minimum-assessment-scope \
  --upload

# Parse single file from GitHub URL and upload
python extra-supporting-scripts/fedramp_to_paramify.py \
  --url https://raw.githubusercontent.com/FedRAMP/docs/main/data/FRMR.ADS.authorization-data-sharing.json \
  --upload

# Parse local file
python extra-supporting-scripts/fedramp_json_parser.py \
  --file FRMR.MAS.minimum-assessment-scope.json \
  --output evidence_sets.json
```

**FedRAMP Standards**: Processes all FedRAMP 20x standards including:
- ADS (Authorization Data Sharing)
- CCM (Collaborative Continuous Monitoring)
- FRD (FedRAMP Definitions)
- FSI (FedRAMP Security Inbox)
- ICP (Incident Communications Procedures)
- KSI (Key Security Indicators)
- MAS (Minimum Assessment Scope)
- PVA (Persistent Validation and Assessment)
- RSC (Recommended Secure Configuration)
- SCN (Significant Change Notifications)
- UCM (Using Cryptographic Modules)
- VDR (Vulnerability Detection and Response)

All standards are available at: https://github.com/FedRAMP/docs/tree/main/data

## Evidence Requirement Mapping

Map evidence to requirements from Paramify machine readable YAML files and add requirement mappings to evidence sets.

**Files**:
- `map_requirements.py` - Basic mapping script
- `extract_evidence_ksi_mappings.py` - Advanced KSI mapping extraction (recommended)
- `mapping_summary.py` - Analysis script to summarize mappings
- `paramify_evidence_mappings.json` - Existing evidence mappings
- `evidence_sets_with_requirements.json` - Updated evidence sets with KSI requirements

**Usage**:

```bash
# Basic mapping
python map_requirements.py

# Advanced KSI mapping (recommended)
python extract_evidence_ksi_mappings.py
python extract_evidence_ksi_mappings.py my_assessment.yaml
python extract_evidence_ksi_mappings.py --verbose

# Analyze mappings
python mapping_summary.py
```

**Default Files**:
- YAML file: `../8_29_25_paramify_coalfire_20x_machine_readable.yaml`
- Evidence sets: `../evidence_sets.json`
- Output: `evidence_sets_with_requirements.json`

**How It Works**:
1. Parses Paramify YAML files to extract KSI categories and evidence entries
2. Matches evidence by script names, evidence names, and GitHub URLs
3. Adds a `requirements` field to each evidence set with associated KSI IDs

**Output**: Adds a `requirements` field to each evidence set containing associated KSI IDs (e.g., `["CED-01", "CNA-01", "IAM-04"]`).

**KSI Categories**: CNA, CIA, CSC, SVC, IAM, CMT, MLA, PIY, TPR, CED, RPL, INR

**Requirements**: Python 3.6+, PyYAML (`pip install pyyaml`)
