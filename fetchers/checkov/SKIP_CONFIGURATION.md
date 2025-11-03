# Checkov Skip Configuration Pattern

## Overview

The Checkov fetchers use a two-tier approach for skipping checks and resources:

1. **Default Sets** (automatically loaded from repo)
2. **User Additions** (specified via `.env` file)

This provides a clean starting point with common low-severity checks and non-production resources, while allowing easy customization via `.env` configuration.

## Skip Checks Configuration

### Default Skip Checks
- **Location**: `fetchers/checkov/skip-checks.default.txt`
- **Purpose**: Contains low-severity checks that are usually skipped
- **Format**: One Checkov ID per line, comments start with `#`
- **Example**:
  ```
  CKV_AWS_250
  CKV_AWS_21
  CKV_AWS_144
  ```

### User-Specified Skip Checks
- **Location**: `.env` file
- **Variable**: `CHECKOV_SKIP_CHECKS` (global) or `GITLAB_PROJECT_1_CHECKOV_SKIP_CHECKS` (project-specific)
- **Format**: Comma-separated list of Checkov IDs
- **Example**:
  ```bash
  CHECKOV_SKIP_CHECKS=CKV_AWS_20,CKV_AWS_57
  GITLAB_PROJECT_1_CHECKOV_SKIP_CHECKS=CKV_AWS_20,CKV_AWS_57
  ```

### How It Works
1. Default checks are loaded from `fetchers/checkov/skip-checks.default.txt`
2. User-specified checks are added from `.env` variables
3. Both lists are merged and passed to Checkov
4. Result: Default checks + user additions = final skip list

## Skip Resources Configuration

### Default Skip Resources
- **Location**: `fetchers/checkov/skip-resources.default.txt`
- **Purpose**: Contains non-production resource patterns that are usually skipped
- **Format**: One resource pattern per line, supports wildcards with `*`, comments start with `#`
- **Example**:
  ```
  aws_s3_bucket.gitlab_*
  aws_s3_bucket.gitlab_runner_cache
  aws_s3_bucket.nessus_scan_export
  ```

### User-Specified Skip Resources
- **Location**: `.env` file
- **Variable**: `CHECKOV_SKIP_RESOURCES` (global) or `GITLAB_PROJECT_1_CHECKOV_SKIP_RESOURCES` (project-specific)
- **Format**: Comma-separated list of resource patterns (supports wildcards with `*`)
- **Example**:
  ```bash
  CHECKOV_SKIP_RESOURCES=aws_s3_bucket.gitlab_*,aws_s3_bucket.nessus_scan_export
  GITLAB_PROJECT_1_CHECKOV_SKIP_RESOURCES=aws_s3_bucket.gitlab_runner_cache,aws_s3_bucket.dev_*
  ```

### How It Works
1. Default resource patterns are loaded from `fetchers/checkov/skip-resources.default.txt`
2. User-specified resource patterns are added from `.env` variables
3. Both lists are merged
4. Post-scan: Failed checks for matching resources are filtered out
5. Summary statistics are recalculated after filtering

## Configuration Examples

### Global Configuration (.env)
```bash
# Default skip checks are automatically loaded from skip-checks.default.txt
# Add your own checks here:
CHECKOV_SKIP_CHECKS=CKV_AWS_20,CKV_AWS_57

# Default skip resources are automatically loaded from skip-resources.default.txt
# Add your own resource patterns here:
CHECKOV_SKIP_RESOURCES=aws_s3_bucket.gitlab_*,aws_s3_bucket.nessus_scan_export
```

### Project-Specific Configuration (.env)
```bash
# GitLab Project 1
GITLAB_PROJECT_1_URL=https://gitlab.company.com
GITLAB_PROJECT_1_API_ACCESS_TOKEN=glpat-xxxxx
GITLAB_PROJECT_1_ID=123
GITLAB_PROJECT_1_FETCHERS=checkov_terraform

# Project-specific skip checks (merged with defaults)
GITLAB_PROJECT_1_CHECKOV_SKIP_CHECKS=CKV_AWS_20,CKV_AWS_57

# Project-specific skip resources (merged with defaults)
GITLAB_PROJECT_1_CHECKOV_SKIP_RESOURCES=aws_s3_bucket.gitlab_runner_cache
```

## Benefits

1. **Default Starting Set**: Common low-severity checks and non-production resources are pre-configured
2. **Easy Customization**: Add more checks/resources via simple `.env` variables
3. **No File Management**: No need to maintain separate skip files
4. **Project-Specific**: Each GitLab project can have its own skip configuration
5. **Version Controlled**: Default files are in the repository, easy to update
6. **Merged Automatically**: Defaults + user additions = final configuration

## Populating Default Files

To populate the default skip files with common checks/resources:

1. **Edit `fetchers/checkov/skip-checks.default.txt`**:
   - Add common low-severity Checkov check IDs
   - One per line
   - Comments start with `#`

2. **Edit `fetchers/checkov/skip-resources.default.txt`**:
   - Add common non-production resource patterns
   - Supports wildcards with `*`
   - One per line
   - Comments start with `#`

These defaults will be automatically loaded for all Checkov scans, and users can add more via `.env` variables.
