# 3) Run Fetchers

This directory contains scripts for executing evidence fetcher scripts and storing evidence with support for multi-instance execution.

## Files

- `run_fetchers.py` - Main execution script with multi-instance support
- `main_fetcher.py` - Legacy fetcher execution script
- `README.md` - This documentation file

## What This Does

The fetcher execution system:

1. **Reads Configuration**: Loads evidence_sets.json to determine which scripts to run
2. **Multi-Instance Support**: Automatically detects and runs multiple instances of the same fetcher
3. **Executes Scripts**: Runs each fetcher script with appropriate parameters
4. **Stores Evidence**: Saves evidence files in timestamped directories
5. **Uploads to Paramify**: Optionally uploads evidence files via API
6. **Creates Reports**: Generates execution summary and CSV reports

## Multi-Instance Execution

The system supports running the same fetcher against multiple projects or regions:

### GitLab Multi-Project Support

Configure multiple GitLab projects using environment variables:

```bash
# Project 1: Change Management
GITLAB_PROJECT_1_URL=https://gitlab.example.com
GITLAB_PROJECT_1_ID=group/change-management
GITLAB_PROJECT_1_API_ACCESS_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_PROJECT_1_FETCHERS=gitlab_ci_cd_pipeline_config,gitlab_project_summary,gitlab_merge_request_summary

# Project 2: Terraform
GITLAB_PROJECT_2_URL=https://gitlab.example.com
GITLAB_PROJECT_2_ID=group/terraform
GITLAB_PROJECT_2_API_ACCESS_TOKEN=glpat-yyyyyyyyyyyyyyyyyyyy
GITLAB_PROJECT_2_FETCHERS=gitlab_ci_cd_pipeline_config,gitlab_project_summary

# Project 3: Main Application
GITLAB_PROJECT_3_URL=https://gitlab.example.com
GITLAB_PROJECT_3_ID=group/main-application
GITLAB_PROJECT_3_API_ACCESS_TOKEN=glpat-zzzzzzzzzzzzzzzzzzzz
GITLAB_PROJECT_3_FETCHERS=gitlab_merge_request_summary
```

### AWS Multi-Region Support

Configure multiple AWS regions using environment variables:

```bash
# Region 1: US East
AWS_REGION_1=us-east-1
AWS_REGION_1_PROFILE=production
AWS_REGION_1_FETCHERS=s3_encryption_status,iam_policies

# Region 2: US West
AWS_REGION_2=us-west-2
AWS_REGION_2_PROFILE=production
AWS_REGION_2_FETCHERS=s3_encryption_status,iam_policies
```

### Project-Specific Overrides

You can override global settings for specific projects:

```bash
# Override branch for CI/CD fetcher in project 1
GITLAB_PROJECT_1_BRANCH_CICD=dev-branch

# Override file patterns for project 2
GITLAB_PROJECT_2_FILE_PATTERNS=.py,.ini

# Override MR settings for project 3
GITLAB_PROJECT_3_MR_STATE=closed
GITLAB_PROJECT_4_MR_MAX_RESULTS=20
```

## Usage

```bash
python run_fetchers.py
```

## Execution Flow

1. **Parse Environment**: Scans for `GITLAB_PROJECT_N_*` and `AWS_REGION_N_*` patterns
2. **Create Instances**: Generates multiple instances based on `*_FETCHERS` lists
3. **Run Instances**: Executes each instance with project/region-specific environment variables
4. **Generate Evidence**: Creates evidence files with instance-specific names

## Backward Compatibility

The system maintains full backward compatibility:
- If no multi-instance configuration is found, falls back to single-instance mode
- Existing single-instance setups continue to work without changes
- Legacy environment variable patterns are still supported

## Prerequisites

- Evidence sets configuration (evidence_sets.json)
- Environment variables (.env file)
- Required dependencies installed
- Project access tokens for GitLab (if using GitLab fetchers)

## Next Steps

After running fetchers:

1. **Tests** (option 4): Validate your results
2. **Add New Fetcher** (option 5): Contribute new scripts
