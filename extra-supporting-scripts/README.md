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

## Evidence Export for KSI Mapping

Export evidence UUIDs mapped to KSI indicators from Paramify for use in HTML walkthroughs or other documentation.

**Usage**:
```bash
# Using default program ID and output directory
python extra-supporting-scripts/export_evidence_mappings.py

# Custom program ID and output directory
python extra-supporting-scripts/export_evidence_mappings.py \
  --program-id 69a50ce5-ddb7-4472-863c-2f42c88d37fa \
  --output-dir /path/to/output

# With custom API token
python extra-supporting-scripts/export_evidence_mappings.py \
  --api-token <your-token>
```

**Environment Variables**:
- `PARAMIFY_UPLOAD_API_TOKEN` - API token (required if not provided via --api-token)
- `PARAMIFY_API_BASE_URL` - API base URL (optional, defaults to `https://app.paramify.com/api/v0`)

**Options**:
- `--program-id` - Paramify program ID (default: FedRAMP 20x Phase Two Moderate)
- `--output-dir` - Output directory for export files (default: `/Users/isaacteuscher/fedramp-20x-pilot`)
- `--api-token` - Paramify API token (optional if env var is set)
- `--base-url` - Paramify API base URL (optional)

**Output Files**:
- `evidence_mappings.json` - JSON format mapping KSI IDs to evidence UUID arrays
- `evidence_mappings.csv` - CSV format with columns: KSI_ID, Evidence_UUID, Evidence_Name, Evidence_ReferenceId

**Example Output**:
```json
{
  "CNA-01": [
    "c19ebbfe-ea5e-4c4e-97a8-037e8cfc0bdf",
    "another-evidence-uuid-here"
  ],
  "CNA-02": [
    "evidence-uuid-for-cna-02"
  ]
}
```

**Requirements**: Python 3.6+, requests (`pip install requests`)

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
