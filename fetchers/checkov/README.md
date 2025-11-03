# Checkov Integration Guide

## Overview

Infrastructure as Code (IaC) security scanning for Terraform and Kubernetes manifests. Integrates with the existing GitLab multi-project configuration pattern.

## Installation

```bash
# Install Checkov
pip install checkov

# Make scripts executable
chmod +x fetchers/checkov/*.sh
```

## Configuration

### Global Settings (.env)

```bash
# Basic settings
CHECKOV_REPO_ID=evidence-fetchers-terraform
CHECKOV_BRANCH=main
CHECKOV_SOFT_FAIL=true
CHECKOV_COMPACT=true
CHECKOV_DOWNLOAD_EXTERNAL_MODULES=true
CHECKOV_EVALUATE_VARIABLES=true

# Check filtering (merged with defaults from skip-checks.default.txt)
CHECKOV_SKIP_CHECKS=CKV_AWS_20,CKV_AWS_57
CHECKOV_CHECKS=CKV_AWS_21,CKV_AWS_23,CKV_AWS_24

# Resource filtering (merged with defaults from skip-resources.default.txt)
CHECKOV_SKIP_RESOURCES=aws_s3_bucket.gitlab_*,aws_s3_bucket.nessus_scan_export

# Path filtering
CHECKOV_SKIP_PATHS=modules,examples,test
```

### Project-Specific Settings (.env)

```bash
# GitLab Project 1
GITLAB_PROJECT_1_URL=https://gitlab.company.com
GITLAB_PROJECT_1_API_ACCESS_TOKEN=glpat-xxxxx
GITLAB_PROJECT_1_ID=123
GITLAB_PROJECT_1_FETCHERS=checkov_terraform,checkov_kubernetes

# Project-specific Checkov settings (merged with defaults)
GITLAB_PROJECT_1_CHECKOV_SKIP_CHECKS=CKV_AWS_20,CKV_AWS_57
GITLAB_PROJECT_1_CHECKOV_SKIP_RESOURCES=aws_s3_bucket.gitlab_runner_cache
GITLAB_PROJECT_1_CHECKOV_SEVERITY=HIGH,MEDIUM  # Used with --skip-check
```

### Skip Configuration

**Default Skip Checks** (`fetchers/checkov/skip-checks.default.txt`):
- Automatically loaded, contains low-severity checks
- Add more via `CHECKOV_SKIP_CHECKS` in `.env`

**Default Skip Resources** (`fetchers/checkov/skip-resources.default.txt`):
- Automatically loaded, contains non-production resource patterns
- Add more via `CHECKOV_SKIP_RESOURCES` in `.env` (supports wildcards with `*`)

## Advanced Features

### Terraform Plan File Support

```bash
# Scan Terraform plan JSON instead of directories
GITLAB_PROJECT_1_CHECKOV_TERRAFORM_PLAN_FILE=/path/to/tfplan.json
GITLAB_PROJECT_1_CHECKOV_REPO_ROOT=/path/to/repo
```

Or place `tfplan.json` in repository root - automatically detected.

**Benefits**: Scan planned changes, respect skip comments, accurate file references

### Plan Enrichment

```bash
# Enables skip comment support and file references
GITLAB_PROJECT_1_CHECKOV_REPO_ROOT=/path/to/repo
```

Automatically uses cloned repository as repo root if not specified.

**Benefits**: Checkov respects inline skip comments (`# checkov:skip=...`) and shows accurate file paths and line numbers

### Deep Analysis

```bash
# Combines graph of Plan file and Terraform files scans (requires --repo-root-for-plan-enrichment)
GITLAB_PROJECT_1_CHECKOV_DEEP_ANALYSIS=true
GITLAB_PROJECT_1_CHECKOV_REPO_ROOT=/path/to/repo
```

**Benefits**: Allows Checkov to make graph connections where there is incomplete information in the plan file (e.g., locals connections). See [Checkov Terraform Plan Scanning docs](https://www.checkov.io/7.Scan%20Examples/Terraform%20Plan%20Scanning.html) for details.

### Severity Filtering

**Note**: `--severity` is not a valid Checkov flag. Use severity values with `--check` or `--skip-check`:

```bash
# Skip LOW and MEDIUM severity checks
CHECKOV_SEVERITY=LOW,MEDIUM  # Applied via --skip-check
```

## Usage

1. **Select Fetchers**: `python main.py` → Option 1 → Select `checkov_terraform` and/or `checkov_kubernetes`
2. **Configure**: Add settings to `.env` file
3. **Run**: `python main.py` → Option 3 → Execute scans
4. **Upload**: `python main.py` → Option 4 → Upload to Paramify

## Output Format

Structured JSON evidence with summary and detailed results:

```json
{
  "framework": "terraform",
  "scan_timestamp": "2025-01-15T10:30:00Z",
  "source_type": "gitlab",
  "source": "https://gitlab.company.com/123",
  "summary": {
    "passed_checks": 15,
    "failed_checks": 3,
    "skipped_checks": 1,
    "total_checks": 19
  },
  "results": [...]
}
```

## Troubleshooting

- **Checkov not found**: `pip install checkov`
- **Git clone fails**: Verify credentials and repository access
- **Permission denied**: `chmod +x fetchers/checkov/*.sh`
- **Debug mode**: `LOG_LEVEL=DEBUG`

## References

- [Checkov Documentation](https://www.checkov.io/)
- [Checkov CLI Reference](https://www.checkov.io/2.Basics/CLI%20Command%20Reference.html)
- See `SKIP_CONFIGURATION.md` for detailed skip configuration guide