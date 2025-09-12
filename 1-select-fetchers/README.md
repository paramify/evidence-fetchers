# 1) Select Fetchers

This directory contains scripts and configuration files for selecting which evidence fetcher scripts to use and generating custom evidence sets.

## Files

- `select_fetchers.py` - Main selection script with interactive mode
- `generate_evidence_sets.py` - Evidence sets generator with automatic regex escaping
- `customer_config_template.json` - Template for customer configuration
- `evidence_fetchers_catalog.json` - Complete catalog of all available scripts
- `escape_regex_for_json.py` - Utility for escaping regex patterns for JSON storage
- `regex_examples.py` - Examples of regex escaping functionality
- `update_evidence_sets_regex.py` - Script to update existing evidence sets with escaped regex
- `REGEX_ESCAPE_README.md` - Documentation for regex escaping utilities
- `REGEX_ESCAPING_INTEGRATION.md` - Integration documentation
- `README.md` - This documentation file

## What This Does

The fetcher selection system allows you to:

1. **Browse Available Scripts**: View all available evidence fetcher scripts by category
2. **Interactive Selection**: Choose which scripts you want to use
3. **Generate Evidence Sets**: Create a custom evidence_sets.json file with automatic regex escaping
4. **Save Configuration**: Store your selections for future use
5. **Regex Escaping**: Automatically escape regex patterns for safe JSON storage

## Usage

```bash
python select_fetchers.py
```

## Regex Escaping

The `generate_evidence_sets.py` script automatically escapes regex patterns for safe JSON storage. This ensures that all validation rules with regex patterns are properly formatted for Paramify.

### Automatic Escaping

When generating evidence sets, the script:
- Converts catalog string format to evidence set object format
- Escapes all regex patterns using `json.dumps()`
- Assigns sequential IDs to validation rules
- Provides detailed logging of the escaping process

### Manual Escaping (if needed)

For manual regex escaping, use the utility scripts:

```bash
# Escape a single regex pattern
python3 escape_regex_for_json.py '"total_storage":\s*(\d+),\s*"encrypted_storage":\s*(\d+)'

# Create a complete validation rule
python3 escape_regex_for_json.py --create-rule '"total_storage":\s*(\d+),\s*"encrypted_storage":\s*(\d+)'

# Interactive mode
python3 escape_regex_for_json.py --interactive

# Update existing evidence sets
python3 update_evidence_sets_regex.py
```

### Example

**Input (from catalog):**
```json
"validationRules": ["\"Encrypted\":\\s*true"]
```

**Output (in evidence_sets.json):**
```json
"validationRules": [
  {
    "id": 1,
    "regex": "\"\\\"Encrypted\\\":\\\\s*true\"",
    "logic": "IF match.group(1) == expected_value THEN PASS"
  }
]
```

## Available Categories

### AWS Scripts (28 available)
- **Security**: IAM, encryption, security groups, WAF
- **High Availability**: Auto scaling, load balancers, databases
- **Monitoring**: CloudWatch, Config, GuardDuty
- **Storage**: S3, EBS, EFS encryption and policies
- **Networking**: VPC, Route53, network policies

### Kubernetes Scripts (3 available)
- **EKS**: Cluster configuration, node groups, add-ons
- **Security**: RBAC, network policies, pod security
- **Monitoring**: Pod inventory, resource limits

### KnowBe4 Scripts (2 available)
- **Training**: Security awareness, role-specific training
- **Compliance**: Training completion, user status

### Okta Scripts (1 available)
- **Authentication**: MFA, authenticators, policies
- **Identity**: User management, access policies

## Selection Options

### 1) Interactive Selection (Recommended)
- Guided step-by-step process
- Shows script descriptions and dependencies
- Allows you to enable/disable categories
- Select individual scripts within categories

### 2) Use Template Configuration
- Uses the default template with all scripts enabled
- Good for getting started quickly
- You can modify the generated configuration later

### 3) Load Existing Configuration
- Load a previously saved configuration
- Useful for reusing configurations
- Allows you to modify and regenerate evidence sets

## Output Files

### evidence_sets.json
Contains the evidence sets configuration for Paramify upload:
```json
{
  "evidence_sets": {
    "script_name": {
      "id": "EVD-SCRIPT-ID",
      "name": "Script Display Name",
      "description": "What this script collects",
      "service": "AWS",
      "instructions": "How to run the script",
      "validationRules": [
        {
          "id": 1,
          "regex": "regex_pattern_here",
          "logic": "IF match.group(1) == expected_value THEN PASS"
        }
      ]
    }
  }
}
```

### customer_config.json
Contains your selection configuration:
```json
{
  "customer_configuration": {
    "metadata": {
      "customer_name": "Your Company",
      "configuration_version": "1.0.0"
    },
    "selected_evidence_fetchers": {
      "aws": {
        "enabled": true,
        "selected_scripts": ["script1", "script2"]
      }
    }
  }
}
```

## Configuration Examples

### AWS-Only Customer
```json
{
  "selected_evidence_fetchers": {
    "aws": {
      "enabled": true,
      "selected_scripts": [
        "iam_policies",
        "iam_roles",
        "s3_encryption_status",
        "rds_encryption_status",
        "security_groups"
      ]
    },
    "k8s": {"enabled": false, "selected_scripts": []},
    "knowbe4": {"enabled": false, "selected_scripts": []},
    "okta": {"enabled": false, "selected_scripts": []}
  }
}
```

### Multi-Cloud Customer
```json
{
  "selected_evidence_fetchers": {
    "aws": {
      "enabled": true,
      "selected_scripts": [
        "iam_policies",
        "eks_high_availability",
        "s3_encryption_status"
      ]
    },
    "k8s": {
      "enabled": true,
      "selected_scripts": [
        "eks_microservice_segmentation",
        "kubectl_security"
      ]
    },
    "okta": {
      "enabled": true,
      "selected_scripts": ["okta_authenticators"]
    }
  }
}
```

## Best Practices

1. **Start Small**: Begin with a minimal set of scripts and add more as needed
2. **Test First**: Always test your configuration before production use
3. **Document Changes**: Keep track of which scripts you've selected and why
4. **Regular Updates**: Review and update your selection as your infrastructure changes
5. **Environment Variables**: Use a `.env` file for sensitive configuration

## Troubleshooting

### Common Issues

1. **"Catalog not found"**: Ensure you're running from the correct directory
2. **"Invalid JSON"**: Check your configuration file syntax
3. **"Script not found"**: Verify the script exists in the catalog
4. **"Category not found"**: Use the correct category names (aws, k8s, knowbe4, okta)

### Getting Help

1. Check the main README.md for general information
2. Review the evidence_fetchers_catalog.json for available scripts
3. Use the interactive mode for guided selection
4. Test with a minimal configuration first

## Next Steps

After selecting your fetchers:

1. **Create Evidence Sets in Paramify** (option 2): Upload evidence sets to Paramify
2. **Run Fetchers** (option 3): Execute the evidence fetcher scripts
3. **Tests** (option 4): Validate your configuration
