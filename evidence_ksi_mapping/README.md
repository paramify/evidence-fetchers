# Evidence-KSI Mapping Tools

This directory contains tools to extract evidence-KSI (Key Security Indicator) associations from Paramify machine readable YAML files and update evidence sets with the corresponding requirements.

## Files

- `extract_evidence_ksi_mappings.py` - Main script to extract mappings from YAML and update evidence sets
- `mapping_summary.py` - Analysis script to summarize the mappings
- `evidence_sets_with_requirements.json` - Updated evidence sets with KSI requirements
- `README.md` - This documentation file

## Directory Structure

```
evidence_ksi_mapping/
├── extract_evidence_ksi_mappings.py
├── mapping_summary.py
├── evidence_sets_with_requirements.json
└── README.md
```

The scripts expect to find the source files in the parent directory:
- `../8_29_25_paramify_coalfire_20x_machine_readable.yaml` - Machine readable YAML file
- `../evidence_sets.json` - Original evidence sets file

## Usage

### Extract Evidence-KSI Mappings

The main script can be used in several ways:

```bash
# Use default files
python extract_evidence_ksi_mappings.py

# Specify custom YAML file
python extract_evidence_ksi_mappings.py my_assessment.yaml

# Specify all custom files
python extract_evidence_ksi_mappings.py my_assessment.yaml my_evidence_sets.json my_output.json

# Enable verbose output
python extract_evidence_ksi_mappings.py --verbose

# Show help
python extract_evidence_ksi_mappings.py --help
```

**Default Files:**
- YAML file: `../8_29_25_paramify_coalfire_20x_machine_readable.yaml`
- Evidence sets: `../evidence_sets.json`
- Output: `evidence_sets_with_requirements.json`

### Analyze Mappings

```bash
# Use default file
python mapping_summary.py

# Specify custom file
python mapping_summary.py my_evidence_sets_with_requirements.json

# Show help
python mapping_summary.py --help
```

## How It Works

1. **YAML Parsing**: The script parses the machine readable YAML file to extract:
   - KSI categories (e.g., CNA, SVC, IAM)
   - Validation short names (e.g., CNA-01, SVC-02)
   - Evidence entries with names, descriptions, and artifacts

2. **Evidence Matching**: The script matches evidence by:
   - **Script names**: Extracts `.sh` script names from artifact references
   - **Evidence names**: Exact and partial name matching
   - **GitHub URLs**: Extracts script names from GitHub repository URLs

3. **Requirements Addition**: Adds a `requirements` field to each evidence set containing the associated KSI IDs

## Output Structure

The updated evidence sets include a new `requirements` field:

```json
{
  "evidence_sets": {
    "security_groups": {
      "id": "EVD-SECURITY-GROUPS",
      "name": "Security Groups",
      "description": "Evidence for security group configurations and rules",
      "service": "AWS",
      "instructions": "Script: security_groups.sh...",
      "validation_rules": [],
      "expected_outcome": "JSON contains security group rules and configurations",
      "requirements": [
        "CED-01",
        "CNA-01", 
        "CNA-03",
        "CNA-04",
        "IAM-04",
        "IAM-05",
        "PIY-02",
        "PIY-06",
        "SVC-01"
      ]
    }
  }
}
```

## KSI Categories

The script recognizes these KSI categories:

- **CNA**: Cloud Native Architecture
- **CIA**: Confidentiality, Integrity, Availability  
- **CSC**: Cloud Security Controls
- **SVC**: Service Controls
- **IAM**: Identity and Access Management
- **CMT**: Change Management
- **MLA**: Monitoring and Logging
- **PIY**: Program Implementation
- **TPR**: Third Party Risk
- **CED**: Continuous Education
- **RPL**: Recovery Planning
- **INR**: Incident Response

## Requirements

- Python 3.6+
- PyYAML library (`pip install pyyaml`)

## Examples

### Basic Usage
```bash
# Extract mappings with default files
python extract_evidence_ksi_mappings.py

# Analyze the results
python mapping_summary.py
```

### Custom Files
```bash
# Process a different assessment
python extract_evidence_ksi_mappings.py new_assessment.yaml custom_evidence_sets.json new_output.json

# Analyze custom output
python mapping_summary.py new_output.json
```

### Verbose Output
```bash
# See detailed processing information
python extract_evidence_ksi_mappings.py --verbose
```

## Troubleshooting

- **File not found errors**: Ensure the YAML and evidence sets files exist
- **No mappings found**: Check that the YAML file contains evidence entries with proper structure
- **Missing requirements**: Some evidence sets may not have direct mappings in the YAML file
