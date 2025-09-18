
# FedRAMP 20x Validation Scripts

This repository contains a collection of validation scripts designed to help assess and validate AWS environments against FedRAMP 20x requirements. The scripts are organized by control families and provide automated checks for various AWS services and configurations.

## Recent Changes (2025)

- **Script-Level Evidence Sets:**
  - Each helper script now uploads its own evidence file to a dedicated Evidence Set in Paramify, rather than grouping by family.
  - Evidence Set names are concise (no redundant 'Evidence' suffix).
  - Instructions for each Evidence Set now include the exact script name and all AWS CLI/API/kubectl commands executed to generate the evidence.

- **CSV Output Removed:**
  - All CSV output and parameters have been removed from helper scripts and orchestrators. JSON is now the sole output format for evidence.

- **Execution Orchestrators:**
  - Main family scripts now act as orchestrators, tracking which helper scripts ran, their status, and timing, rather than aggregating results.

- **Paramify Integration Improvements:**
  - Uploads are now granular (per-script) and include detailed, reproducible instructions.
  - Existing Evidence Sets are reused; metadata is only set on creation.
  - Batch uploader and main runner updated to support new evidence model.

- **Documentation:**
  - Helper script documentation now details the commands used for each evidence type.
  - Evidence instructions in Paramify are now fully transparent and auditor-friendly.

See below for usage, structure, and more details.

## Repository Structure

```
.
├── Evidence/                    # Validation results organized by control/KSI families
│   ├── CONFIG-MGMT/
│   │   ├── System-Operations/
│   │   │   ├── System-Operations.sh
│   │   │   ├── detect_new_aws_resource.sh
│   │   │   ├── System-Operations.csv
│   │   │   └── System-Operations.json
│   ├── DATA-PROTECTION/
│   ├── IDENTITY-ACCESS/
│   └── ... (other control/KSI families)
├── paramify_integration/        # Paramify Evidence API integration
│   ├── README.md
│   ├── paramify_evidence_uploader.sh
│   ├── paramify_env_template.txt
│   └── paramify-REST-API-documentation-0.2.0.json
├── run_evidence_validations.sh  # Main validation runner script
├── README.md
└── helper_script_template.md
```

## Prerequisites

- AWS CLI installed and configured
- `jq` command-line tool installed
- Appropriate AWS credentials and permissions
- AWS SSO configured (if using SSO authentication)
- `curl` for Paramify API integration (optional)

## 🔗 Paramify Evidence API Integration

This repository includes automated integration with the **Paramify Evidence API** for streamlined compliance evidence management.

### Quick Setup

1. **Configure API Access:**
   ```bash
   cp paramify_integration/paramify_env_template.txt .env
   # Edit .env and add your Paramify API token
   ```

2. **Run Validations with Automatic Upload:**
   ```bash
   ./run_evidence_validations.sh --all --upload
   ```

### Benefits
- **Automated Evidence Collection** - Results automatically uploaded to Paramify
- **Organized by Control Families** - Evidence Sets created for each validation family
- **Audit Trail** - Complete history of validation runs with timestamps
- **Compliance Ready** - Structured evidence for auditors

### Learn More
See the [Paramify Integration Documentation](paramify_integration/README.md) for:
- Detailed setup instructions
- API architecture explanation
- Advanced configuration options
- Troubleshooting guide

## Usage

### Main Validation Runner

Use the main validation runner script for comprehensive validation across all control families:

```bash
# Run all validations
./run_evidence_validations.sh --all

# Run specific family (e.g., Data Protection)
./run_evidence_validations.sh --family RS-DP

# Skip kubectl validations (useful if EKS access is limited)
./run_evidence_validations.sh --all --skip-kubectl

# Run validations and upload to Paramify
./run_evidence_validations.sh --all --upload

# Upload existing results without running validations
./run_evidence_validations.sh --upload-all
```

**Available Options:**
- `--all` - Run all validation families
- `--family FAMILY_ID` - Run specific family (RS-IA, RS-DP, RS-CM, etc.)
- `--skip-kubectl` - Skip Kubernetes/EKS validations
- `--graceful` - Continue on errors instead of failing
- `--upload` - Upload results to Paramify Evidence API after validation
- `--upload-all` - Upload existing results without running validations

### Running Individual Control Scripts

Each control family has a main script that orchestrates the validation process:

```bash
./Evidence/CONFIG-MGMT/System-Operations/System-Operations.sh
```

**Direct script parameters:**
- `profile`: AWS profile name to use
- `region`: AWS region to validate
- `output_dir`: Directory to store validation results
- `output_csv`: Path to the CSV output file

Example:
```bash
./System-Operations.sh my-profile us-east-1 ./results ./results/System-Operations.csv
```

### Helper Scripts

Helper scripts perform specific validation tasks and are called by the main control scripts. They follow a standard format defined in `helper_script_template.md`. Each helper script:

1. Validates specific AWS resources or configurations
2. Generates JSON and CSV output
3. Provides clear validation results

Example helper script output:
```json
{
    "results": {
        "aws_config": {
            "recorders": [...],
            "status": [...],
            "delivery_channels": [...]
        },
        "eventbridge": {
            "rules": {...}
        },
        "sns": {
            "topics": {...}
        },
        "validation_results": {
            "interval_checks": {...}
        }
    }
}
```


## Output Format

### JSON Output
Each validation generates a JSON file containing:
- Detailed validation results
- Resource configurations
- Validation status

### CSV Output
A CSV file is generated with:
- Control identifiers
- Resource names
- Validation status
- Additional metrics

## Contributing

1. Follow the helper script template format
2. Include proper documentation
3. Test scripts thoroughly
4. Submit pull requests with clear descriptions