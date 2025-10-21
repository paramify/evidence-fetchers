# 7) Evidence Requirement Mapping

This directory contains tools for mapping evidence to requirements from Paramify YAML files and updating evidence sets with KSI (Key Security Indicator) requirements.

## Files

- `map_requirements.py` - Basic mapping script (simple version)
- `extract_evidence_ksi_mappings.py` - Advanced KSI mapping extraction script
- `mapping_summary.py` - Analysis script to summarize the mappings
- `paramify_evidence_mappings.json` - Existing evidence mappings
- `evidence_sets_with_requirements.json` - Updated evidence sets with KSI requirements
- `README.md` - This documentation file

## What This Does

The requirement mapping system:

1. **Reads YAML Files**: Loads Paramify machine readable YAML files
2. **Extracts KSI Mappings**: Finds evidence-KSI associations from YAML
3. **Updates Evidence Sets**: Adds requirements to evidence sets JSON
4. **Creates Output**: Generates updated evidence sets file with requirements
5. **Analyzes Results**: Provides summary and analysis of mappings

## Usage

### Basic Mapping (Simple)
```bash
python map_requirements.py
```

### Advanced KSI Mapping (Recommended)
```bash
# Use default files
python extract_evidence_ksi_mappings.py

# Specify custom YAML file
python extract_evidence_ksi_mappings.py my_assessment.yaml

# Specify all custom files
python extract_evidence_ksi_mappings.py my_assessment.yaml my_evidence_sets.json my_output.json

# Enable verbose output
python extract_evidence_ksi_mappings.py --verbose
```

### Analyze Mappings
```bash
# Use default file
python mapping_summary.py

# Specify custom file
python mapping_summary.py my_evidence_sets_with_requirements.json
```

## Default Files

- YAML file: `../8_29_25_paramify_coalfire_20x_machine_readable.yaml`
- Evidence sets: `../evidence_sets.json`
- Output: `evidence_sets_with_requirements.json`

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
      "validationRules": [
        {
          "id": 1,
          "regex": "regex_pattern_here",
          "logic": "IF match.group(1) == expected_value THEN PASS"
        }
      ],
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

## Next Steps

After mapping requirements:

1. **Create Evidence Sets in Paramify** (option 2): Upload with requirements
2. **Run Fetchers** (option 3): Execute evidence collection
