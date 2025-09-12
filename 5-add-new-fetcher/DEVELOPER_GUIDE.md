# Developer Guide: Adding New Evidence Fetcher Scripts

This guide explains how to add new evidence fetcher scripts to the repository and ensure they're properly integrated into the catalog system.

## Overview

The evidence fetchers repository uses a catalog-driven approach where:
- All available scripts are listed in `evidence_fetchers_catalog.json`
- Customers can select which scripts they want via `customer_config.json`
- The `generate_evidence_sets.py` script creates custom evidence sets based on selections

## Quick Start: Adding a New Script

### 1. Create the Script
Use one of the provided templates:
- **Bash scripts**: Copy `new_script_template.sh`
- **Python scripts**: Copy `new_script_template.py`

### 2. Add to Catalog
```bash
# Interactive mode (recommended)
python add_evidence_fetcher.py --interactive

# Command line mode
python add_evidence_fetcher.py --script-file fetchers/aws/my_new_script.sh --category aws --name "My New Script"
```

### 3. Validate
```bash
python validate_catalog.py
```

### 4. Test
```bash
python generate_evidence_sets.py
```

## Detailed Process

### Step 1: Create the Script

#### For Bash Scripts
```bash
cp new_script_template.sh fetchers/aws/my_new_script.sh
chmod +x fetchers/aws/my_new_script.sh
```

Edit the template and replace:
- `[SCRIPT_NAME]` with your script name
- `[DESCRIPTION_OF_WHAT_THIS_SCRIPT_COLLECTS]` with a clear description
- `[STEP_1_DESCRIPTION]` with your collection steps
- `[COMMAND_1]`, `[COMMAND_2]` with actual AWS CLI commands
- `[WHAT_THE_OUTPUT_CONTAINS]` with output description

#### For Python Scripts
```bash
cp new_script_template.py fetchers/aws/my_new_script.py
chmod +x fetchers/aws/my_new_script.py
```

Edit the template and replace:
- `[SCRIPT_NAME]` with your script name
- `[DESCRIPTION_OF_WHAT_THIS_SCRIPT_COLLECTS]` with a clear description
- `[AWS_CLI_COMMAND_EXAMPLE]` with actual commands
- `[VALIDATION_RULE_1]` with regex patterns for validation
- `[EXPECTED_OUTCOME_DESCRIPTION]` with expected results

### Step 2: Script Requirements

#### Required Elements
1. **Header Comments**: Must include script purpose and evidence description
2. **Command Documentation**: List all AWS CLI commands used
3. **JSON Output**: Must produce valid JSON output
4. **Error Handling**: Proper error handling and exit codes
5. **CSV Output**: Must append to CSV file for summary
6. **Validation Rules**: Include regex patterns for compliance checking

#### Script Structure
```bash
#!/bin/bash
# Helper script for [Script Name] validation
# Evidence for [What this collects]

# Steps:
# 1. [Step description]
#    aws [service] [command]
#
# Output: Creates JSON report with [output description]

set -e

# Parameter validation
if [ "$#" -ne 4 ]; then
    echo "Usage: $0 <profile> <region> <output_dir> <csv_file>"
    exit 1
fi

# Main logic here
# JSON output to $OUTPUT_JSON
# CSV summary to $CSV_FILE
```

### Step 3: Add to Catalog

#### Interactive Mode (Recommended)
```bash
python add_evidence_fetcher.py --interactive
```

The script will:
1. Ask for the script file path
2. Ask for the category (aws, k8s, knowbe4, okta)
3. Extract metadata from the script
4. Allow you to override extracted information
5. Generate a unique ID
6. Add to the catalog
7. Update the customer template

#### Command Line Mode
```bash
python add_evidence_fetcher.py \
    --script-file fetchers/aws/my_new_script.sh \
    --category aws \
    --name "My New Script"
```

### Step 4: Metadata Extraction

The `add_evidence_fetcher.py` script automatically extracts:
- **Name**: From `# Helper script for [Name]` comment
- **Description**: From `# Evidence for [Description]` comment
- **Commands**: From `# aws [command]` comments
- **Dependencies**: Based on script content (aws-cli, kubectl, curl, jq, python3)
- **Tags**: Based on content analysis (encryption, security, iam, s3, etc.)

You can override any extracted information during the interactive process.

### Step 5: ID Generation

Script IDs are automatically generated in the format: `EVD-[CATEGORY]-[SCRIPT-NAME]`

Examples:
- `aws_s3_encryption` → `EVD-AWS-S3-ENCRYPTION`
- `iam_roles` → `EVD-IAM-ROLES`
- `eks_security` → `EVD-EKS-SECURITY`

### Step 6: Validation

Run the validation script to ensure everything is correct:
```bash
python validate_catalog.py
```

This checks:
- Catalog structure integrity
- All required fields are present
- Script files exist
- IDs are unique
- Customer template is in sync
- No uncatalogued scripts

### Step 7: Testing

Test the integration:
```bash
# Generate evidence sets with default template
python generate_evidence_sets.py

# Test with a custom configuration
python generate_evidence_sets.py my_test_config.json test_output.json
```

## Categories and Organization

### AWS Scripts (`fetchers/aws/`)
- **Security**: IAM, encryption, security groups, WAF
- **High Availability**: Auto scaling, load balancers, databases
- **Monitoring**: CloudWatch, Config, GuardDuty
- **Storage**: S3, EBS, EFS encryption and policies
- **Networking**: VPC, Route53, network policies

### Kubernetes Scripts (`fetchers/k8s/`)
- **EKS**: Cluster configuration, node groups, add-ons
- **Security**: RBAC, network policies, pod security
- **Monitoring**: Pod inventory, resource limits

### KnowBe4 Scripts (`fetchers/knowbe4/`)
- **Training**: Security awareness, role-specific training
- **Compliance**: Training completion, user status

### Okta Scripts (`fetchers/okta/`)
- **Authentication**: MFA, authenticators, policies
- **Identity**: User management, access policies

## Best Practices

### Script Development
1. **Follow Templates**: Use the provided templates as starting points
2. **Document Commands**: Include all AWS CLI commands in comments
3. **Error Handling**: Always handle errors gracefully
4. **JSON Output**: Ensure valid JSON structure
5. **CSV Summary**: Include summary data for reporting
6. **Validation Rules**: Add regex patterns for compliance checking

### Metadata
1. **Clear Names**: Use descriptive, consistent naming
2. **Detailed Descriptions**: Explain what evidence is collected
3. **Complete Instructions**: List all commands executed
4. **Relevant Tags**: Add tags for easy filtering
5. **Accurate Dependencies**: List all required tools

### Testing
1. **Test Script**: Verify the script works with sample data
2. **Test Integration**: Ensure it works with the catalog system
3. **Test Generation**: Verify evidence sets are generated correctly
4. **Test Validation**: Run the validation script

### Documentation
1. **Update README**: Add new scripts to documentation
2. **Update Examples**: Include in customer configuration examples
3. **Update Dependencies**: List any new tool requirements

## Troubleshooting

### Common Issues

1. **"Script not found in catalog"**
   - Run `python add_evidence_fetcher.py --interactive` to add the script
   - Check the script file path is correct

2. **"Invalid JSON in catalog"**
   - Run `python validate_catalog.py` to identify issues
   - Check for missing commas, brackets, or quotes

3. **"Missing required fields"**
   - Ensure all required metadata fields are present
   - Use the interactive mode to fill in missing information

4. **"Script file not found"**
   - Verify the script file exists at the specified path
   - Check file permissions (should be executable for .sh files)

5. **"Duplicate ID"**
   - The script ID must be unique across all categories
   - The system will suggest a new ID if there's a conflict

### Validation Errors

Run `python validate_catalog.py` to get detailed error information:
- **Structure errors**: Missing required fields or sections
- **File errors**: Script files that don't exist
- **Sync errors**: Customer template out of sync with catalog
- **Uniqueness errors**: Duplicate IDs or names

### Getting Help

1. **Check Templates**: Review the template files for examples
2. **Run Validation**: Use `python validate_catalog.py` for diagnostics
3. **Test Generation**: Use `python generate_evidence_sets.py` to test
4. **Review Existing Scripts**: Look at similar scripts for patterns

## Advanced Usage

### Custom Categories
To add a new category (e.g., "azure"):
1. Add the category to `evidence_fetchers_catalog.json`
2. Update the customer template
3. Modify the validation script to include the new category

### Custom Dependencies
To add new dependencies:
1. Update the `valid_dependencies` list in `validate_catalog.py`
2. Update the dependency detection logic in `add_evidence_fetcher.py`
3. Update documentation

### Custom Tags
To add new tags:
1. Update the tag detection logic in `add_evidence_fetcher.py`
2. Update the customer setup guide with new tag meanings
3. Consider adding tag-based filtering in the future

## Maintenance

### Regular Tasks
1. **Validate Catalog**: Run `python validate_catalog.py` regularly
2. **Update Documentation**: Keep guides current with new scripts
3. **Test Generation**: Verify evidence sets generation works
4. **Review Scripts**: Ensure all scripts follow current standards

### Version Control
1. **Commit Scripts**: Add new scripts to version control
2. **Update Catalog**: Commit catalog changes
3. **Update Templates**: Commit template updates
4. **Tag Releases**: Tag releases with version numbers

### Monitoring
1. **Script Health**: Monitor script execution success rates
2. **Catalog Usage**: Track which scripts are most commonly selected
3. **Customer Feedback**: Gather feedback on script usefulness
4. **Performance**: Monitor script execution times

This developer guide ensures that new evidence fetcher scripts are properly integrated into the catalog system and maintain consistency with existing scripts.
