# Run Fetchers Configuration Guide

This guide explains how to configure the evidence fetchers to work with your specific AWS environment and requirements.

## Environment Variables

### Required Variables
- `PARAMIFY_UPLOAD_API_TOKEN`: Your Paramify API token for uploading evidence
- `PARAMIFY_API_BASE_URL`: Paramify API base URL (default: https://app.paramify.com/api/v0)

### AWS Configuration
- `AWS_PROFILE`: AWS profile to use (eg: "gov_readonly")
- `AWS_DEFAULT_REGION`: AWS region to use (eg: "us-gov-west-1")

### Fetcher Configuration
- `FETCHER_TIMEOUT`: Timeout in seconds for each fetcher script (default: 300 = 5 minutes)

### Fetcher-Specific Flags
You can pass additional flags to specific fetcher scripts using environment variables:

- `IAM_ROLES_FETCHER`: Additional flags for the iam_roles fetcher
- `S3_ENCRYPTION_STATUS_FETCHER`: Additional flags for the s3_encryption_status fetcher
- `<SCRIPT_NAME>_FETCHER`: Additional flags for any specific script (use uppercase)

**Note**: The system also supports the legacy `FETCHER_FLAGS_<SCRIPT_NAME>` format for backward compatibility.

### Multi-Instance Configuration

The system supports running the same fetcher against multiple projects or regions:

#### GitLab Multi-Project Support
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
```

#### AWS Multi-Region Support
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

## Examples

### Basic Configuration
```bash
export AWS_PROFILE=gov_readonly
export AWS_DEFAULT_REGION=us-gov-west-1
export FETCHER_TIMEOUT=300  # 5 minutes (default)
export PARAMIFY_UPLOAD_API_TOKEN=your_token_here
```

### Using Fetcher-Specific Flags
```bash
# Exclude AWS-managed roles from IAM roles fetcher
export IAM_ROLES_FETCHER="--exclude-aws-managed-roles"

# Include bucket policies in S3 encryption status fetcher
export S3_ENCRYPTION_STATUS_FETCHER="--include-bucket-policies"

# Multiple flags for a single fetcher
export IAM_USERS_GROUPS_FETCHER="--include-inactive-users --verbose"
```

### .env File Example
Create a `.env` file in the project root:
```bash
# Required: Paramify API Configuration
PARAMIFY_UPLOAD_API_TOKEN=your_paramify_api_token_here

# Optional: Paramify API Base URL (defaults to https://app.paramify.com/api/v0)
# PARAMIFY_API_BASE_URL=https://app.paramify.com/api/v0

# Optional: Fetcher Configuration
# FETCHER_TIMEOUT=300      # 5 minutes (default)

# Optional: AWS Configuration
# AWS_PROFILE=gov_readonly  # Replace with your actual AWS profile
# AWS_DEFAULT_REGION=us-gov-west-1  # Replace with your actual AWS region

# Optional: Fetcher-specific flags
# IAM_ROLES_FETCHER=--exclude-aws-managed-roles  # Exclude AWS managed roles from iam_roles fetcher
# S3_ENCRYPTION_STATUS_FETCHER=--include-bucket-policies  # Include bucket policies in S3 encryption status fetcher

# Other service configurations (if needed)
# KNOWBE4_API_KEY=your_knowbe4_api_key
# KNOWBE4_REGION=us
# OKTA_API_TOKEN=your_okta_api_token
# OKTA_ORG_URL=https://your-org.okta.com
```

## Running the Fetchers

1. Set up your environment variables (either in `.env` file or export them)
2. Run the fetchers:
   ```bash
   python 3-run-fetchers/run_fetchers.py
   ```

## Troubleshooting

### Empty Results
If fetcher scripts return empty results:
1. Check your AWS profile and region configuration
2. Verify your AWS credentials have the necessary permissions
3. Check if the fetcher script supports the flags you're using

### Timeout Issues
If scripts are timing out:
1. Increase the `FETCHER_TIMEOUT` value
2. Consider using fetcher-specific flags to reduce the scope (e.g., `--exclude-aws-managed-roles`)

### Permission Issues
Make sure your AWS credentials have the necessary permissions for the services you're trying to fetch evidence from.

## Available Fetcher Flags

### IAM Roles Fetcher (`iam_roles`)
- `--exclude-aws-managed-roles`: Exclude AWS-managed roles from the results

### IAM Users/Groups Fetcher (`iam_users_groups`)
- `--include-inactive-users`: Include inactive users in the results
- `--verbose`: Enable verbose output

### S3 Encryption Status Fetcher (`s3_encryption_status`)
- `--include-bucket-policies`: Include bucket policies in the analysis

Note: Not all fetcher scripts support additional flags. Check the individual script documentation for available options.
