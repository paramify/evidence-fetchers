# Customer Setup Guide: Evidence Fetchers Selection

This guide explains how customers can customize the evidence fetchers repository to select only the scripts they need for their specific environment and compliance requirements.

## Overview

The evidence fetchers repository contains scripts for multiple cloud providers and services:
- **AWS**: 28 evidence collection scripts
- **Kubernetes (K8s)**: 3 evidence collection scripts  
- **KnowBe4**: 2 security awareness training scripts
- **Okta**: 1 identity management script
- **GitLab**: 3 CI/CD and change management scripts
- **Rippling**: 2 HR management scripts

## Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd evidence-fetchers
```

### 2. Create Your Customer Configuration
```bash
cp customer_config_template.json customer_config.json
```

### 3. Customize Your Selection
Edit `customer_config.json` to select only the evidence fetchers you need.

### 4. Generate Your Evidence Sets
```bash
python generate_evidence_sets.py
```

### 5. Set Up Environment Variables
Copy the example environment file and customize it:
```bash
cp .env.example .env
```

Then edit the `.env` file with your configuration (see Environment Variables section below).

### 6. Upload to Paramify
Upload the generated `evidence_sets.json` file to your Paramify instance.

## Detailed Configuration

### Customer Configuration File Structure

The `customer_config.json` file has the following structure:

```json
{
  "customer_configuration": {
    "metadata": {
      "customer_name": "YOUR_COMPANY_NAME",
      "configuration_version": "1.0.0",
      "created_date": "2025-01-15",
      "description": "Customer-specific evidence fetcher selection configuration"
    },
    "selected_evidence_fetchers": {
      "aws": {
        "enabled": true,
        "selected_scripts": [
          "script_name_1",
          "script_name_2"
        ]
      },
      "k8s": {
        "enabled": false,
        "selected_scripts": []
      }
    }
  }
}
```

### Available Categories and Scripts

#### AWS Scripts (28 available)
- `auto_scaling_high_availability` - Auto Scaling group configurations
- `aws_component_ssl_enforcement` - SSL/TLS enforcement across AWS components
- `aws_config_conformance_packs` - AWS Config conformance pack compliance
- `aws_config_monitoring` - AWS Config service monitoring
- `backup_recovery_high_availability` - Backup and recovery configurations
- `backup_validation` - Backup validation and compliance
- `block_storage_encryption_status` - EBS/EFS encryption status
- `cloudwatch_high_availability` - CloudWatch monitoring
- `database_high_availability` - RDS/Aurora high availability
- `detect_new_aws_resource` - New resource detection monitoring
- `efs_high_availability` - EFS high availability
- `eks_high_availability` - EKS cluster high availability
- `eks_least_privilege` - EKS least privilege access controls
- `guard_duty` - GuardDuty threat detection
- `iam_identity_center` - IAM Identity Center configurations
- `iam_policies` - IAM policy configurations
- `iam_roles` - IAM role configurations
- `iam_users_groups` - IAM users and groups
- `kms_key_rotation` - KMS key rotation policies
- `load_balancer_encryption_status` - Load balancer encryption
- `load_balancer_high_availability` - Load balancer high availability
- `network_resilience_high_availability` - Network resilience
- `rds_encryption_status` - RDS encryption status
- `route53_high_availability` - Route 53 high availability
- `s3_encryption_status` - S3 bucket encryption
- `security_groups` - Security group configurations
- `waf_all_rules` - WAF rule configurations
- `waf_dos_rules` - WAF DoS protection rules

#### Kubernetes Scripts (3 available)
- `eks_microservice_segmentation` - EKS microservice segmentation
- `eks_pod_inventory` - EKS pod inventory and security
- `kubectl_security` - Kubernetes security configuration

#### KnowBe4 Scripts (2 available)
- `role_specific_training` - Role-specific training compliance
- `security_awareness_training` - Security awareness training

#### Okta Scripts (1 available)
- `okta_authenticators` - Okta authenticator configuration

#### GitLab Scripts (3 available)
- `gitlab_ci_cd_pipeline_config` - CI/CD pipeline configuration and security scanning
- `gitlab_project_summary` - Repository file inventory and configuration analysis
- `gitlab_merge_request_summary` - Change management process and approval metrics

#### Rippling Scripts (2 available)
- `rippling_current_employees` - Current employee data and access management
- `rippling_all_employees` - All employee data including historical records

## Configuration Examples

### Example 1: AWS-Only Customer
```json
{
  "customer_configuration": {
    "metadata": {
      "customer_name": "AWS-Only Corp",
      "description": "AWS-only evidence collection"
    },
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
      "k8s": {
        "enabled": false,
        "selected_scripts": []
      },
      "knowbe4": {
        "enabled": false,
        "selected_scripts": []
      },
      "okta": {
        "enabled": false,
        "selected_scripts": []
      },
      "rippling": {
        "enabled": false,
        "selected_scripts": []
      }
    }
  }
}
```

### Example 2: Multi-Cloud Customer
```json
{
  "customer_configuration": {
    "metadata": {
      "customer_name": "Multi-Cloud Corp",
      "description": "AWS + Kubernetes + Okta evidence collection"
    },
    "selected_evidence_fetchers": {
      "aws": {
        "enabled": true,
        "selected_scripts": [
          "iam_policies",
          "iam_roles",
          "eks_high_availability",
          "eks_least_privilege",
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
      "knowbe4": {
        "enabled": false,
        "selected_scripts": []
      },
      "okta": {
        "enabled": true,
        "selected_scripts": [
          "okta_authenticators"
        ]
      },
      "rippling": {
        "enabled": false,
        "selected_scripts": []
      }
    }
  }
}
```

### Example 3: Training-Focused Customer
```json
{
  "customer_configuration": {
    "metadata": {
      "customer_name": "Training Corp",
      "description": "Focus on training and awareness evidence"
    },
    "selected_evidence_fetchers": {
      "aws": {
        "enabled": true,
        "selected_scripts": [
          "iam_policies",
          "iam_users_groups"
        ]
      },
      "k8s": {
        "enabled": false,
        "selected_scripts": []
      },
      "knowbe4": {
        "enabled": true,
        "selected_scripts": [
          "security_awareness_training",
          "role_specific_training"
        ]
      },
      "okta": {
        "enabled": false,
        "selected_scripts": []
      },
      "rippling": {
        "enabled": false,
        "selected_scripts": []
      }
    }
  }
}
```

## Environment Variables

Some scripts require environment variables to be set. The project includes a comprehensive `.env.example` file that shows all available configuration options.

### Environment File Setup

1. Copy the example file: `cp .env.example .env`
2. Edit `.env` with your actual values
3. Uncomment and modify the settings you need

The `.env.example` file includes:
- **Paramify API Configuration** (required)
- **Multi-Instance Support** for GitLab projects and AWS regions
- **Provider-specific settings** for AWS, GitLab, KnowBe4, Okta, and Rippling
- **Fetcher-specific flags** for advanced configuration

### KnowBe4 Scripts
```bash
export KNOWBE4_API_KEY="your_api_key_here"
export KNOWBE4_REGION="us"  # or eu, ca, uk, de
```

### Okta Scripts
```bash
export OKTA_API_TOKEN="your_api_token_here"
export OKTA_ORG_URL="https://your-org.okta.com"
```

### GitLab Scripts

#### Single Project Configuration
```bash
# Required global settings
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_API_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
export GITLAB_PROJECT_ID="group/project"

# Optional global defaults
export GITLAB_BRANCH="main"
export GITLAB_FILE_PATTERNS=".tf,.tfvars,.yml,.yaml,.json,Dockerfile,.sh"
export GITLAB_MR_STATE="merged"
export GITLAB_MR_DAYS_BACK="30"
export GITLAB_MR_MAX_RESULTS="50"
```

#### Multi-Project Configuration
```bash
# Project 1: Change Management
export GITLAB_PROJECT_1_URL="https://gitlab.example.com"
export GITLAB_PROJECT_1_ID="group/change-management"
export GITLAB_PROJECT_1_API_ACCESS_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
export GITLAB_PROJECT_1_FETCHERS="gitlab_ci_cd_pipeline_config,gitlab_project_summary,gitlab_merge_request_summary"

# Project 2: Terraform
export GITLAB_PROJECT_2_URL="https://gitlab.example.com"
export GITLAB_PROJECT_2_ID="group/terraform"
export GITLAB_PROJECT_2_API_ACCESS_TOKEN="glpat-yyyyyyyyyyyyyyyyyyyy"
export GITLAB_PROJECT_2_FETCHERS="gitlab_ci_cd_pipeline_config,gitlab_project_summary"

# Project 3: Main Application
export GITLAB_PROJECT_3_URL="https://gitlab.example.com"
export GITLAB_PROJECT_3_ID="group/main-application"
export GITLAB_PROJECT_3_API_ACCESS_TOKEN="glpat-zzzzzzzzzzzzzzzzzzzz"
export GITLAB_PROJECT_3_FETCHERS="gitlab_merge_request_summary"

# Optional project-specific overrides
# export GITLAB_PROJECT_1_BRANCH_CICD="dev-branch"
# export GITLAB_PROJECT_2_FILE_PATTERNS=".py,.ini"
# export GITLAB_PROJECT_3_MR_STATE="closed"
# export GITLAB_PROJECT_4_MR_MAX_RESULTS="20"
```

### Rippling Scripts
```bash
export RIPPLING_API_TOKEN="your_rippling_api_token_here"
```

## GitLab Authentication Setup

The GitLab fetcher scripts use **Project Access Tokens** for authentication. Project tokens are scoped to specific projects only, providing better security for automated scripts.

### Step 1: Create a Project Access Token

1. Navigate to your project in GitLab
2. Select **Settings** → **Access tokens**
3. Select **Add new token**
4. Configure the token:
   - **Token name**: `evidence-fetchers`
   - **Expiration date**: Set appropriate expiration (max 365 days)
   - **Role**: Select appropriate role (Reporter or Developer recommended)
   - **Scopes**: Select `read_api` and `read_repository`
5. Select **Create project access token**
6. Copy the token immediately (starts with `glpat-`)

**Availability**: 
- GitLab Self-Managed: All tiers
- GitLab.com: Premium and Ultimate only

For detailed information, see the [GitLab Project Access Tokens documentation](https://docs.gitlab.com/user/project/settings/project_access_tokens/).

### Step 2: Configure Environment Variables

Add the token to your `.env` file:

```bash
GITLAB_URL=https://gitlab.example.com
GITLAB_API_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_PROJECT_ID=group/project
```

### Step 3: Test Authentication

```bash
curl --header "PRIVATE-TOKEN: $GITLAB_API_TOKEN" \
  --url "$GITLAB_URL/api/v4/projects"
```

### Security Best Practices

- Use minimal scopes (`read_api`, `read_repository`)
- Set token expiration dates (max 365 days)
- Store tokens in `.env` files, never in code
- Rotate tokens regularly
- Monitor token usage

### Troubleshooting

**401 Unauthorized**: Verify token and expiration
**403 Forbidden**: Check project access and permissions  
**404 Not Found**: Verify URL and project ID

## Dependencies

Ensure you have the required tools installed:

### Common Dependencies
- `jq` - JSON processor
- `curl` - HTTP client
- `aws-cli` - AWS command line interface
- `kubectl` - Kubernetes command line tool
- `python3` - Python interpreter
- `PyYAML` - YAML parser for GitLab CI/CD configuration files

### Installation Commands

#### macOS
```bash
brew install jq awscli kubernetes-cli
pip3 install PyYAML
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install jq curl awscli kubectl python3 python3-yaml
```

#### CentOS/RHEL
```bash
sudo yum install jq curl awscli kubectl python3 python3-pyyaml
```

#### Python Dependencies (if not using system packages)
```bash
pip3 install PyYAML requests
```

## Multi-Instance Execution

The system supports running the same fetcher against multiple projects or regions:

### GitLab Multi-Project Support

Configure multiple GitLab projects using the `GITLAB_PROJECT_N_*` pattern:

```bash
# Each project can have its own URL, token, and project ID
GITLAB_PROJECT_1_URL=https://gitlab.example.com
GITLAB_PROJECT_1_ID=group/change-management
GITLAB_PROJECT_1_API_ACCESS_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_PROJECT_1_FETCHERS=gitlab_ci_cd_pipeline_config,gitlab_project_summary,gitlab_merge_request_summary

GITLAB_PROJECT_2_URL=https://gitlab.example.com
GITLAB_PROJECT_2_ID=group/terraform
GITLAB_PROJECT_2_API_ACCESS_TOKEN=glpat-yyyyyyyyyyyyyyyyyyyy
GITLAB_PROJECT_2_FETCHERS=gitlab_ci_cd_pipeline_config,gitlab_project_summary
```

### AWS Multi-Region Support

Configure multiple AWS regions using the `AWS_REGION_N_*` pattern:

```bash
# Each region can have its own profile and configuration
AWS_REGION_1=us-east-1
AWS_REGION_1_PROFILE=production
AWS_REGION_1_FETCHERS=s3_encryption_status,iam_policies

AWS_REGION_2=us-west-2
AWS_REGION_2_PROFILE=production
AWS_REGION_2_FETCHERS=s3_encryption_status,iam_policies
```

### Benefits of Multi-Instance Execution

- **Security**: Each project uses its own scoped access token
- **Flexibility**: Different configurations per project/region
- **Scalability**: Easy to add more projects or regions
- **Backward Compatibility**: Single-instance mode still works

## Usage Commands

### Generate Evidence Sets
```bash
# Use default files
python generate_evidence_sets.py

# Specify custom files
python generate_evidence_sets.py my_config.json my_evidence_sets.json
```

### View Available Scripts
```bash
# View the complete catalog
cat evidence_fetchers_catalog.json | jq '.evidence_fetchers_catalog.categories'

# View only AWS scripts
cat evidence_fetchers_catalog.json | jq '.evidence_fetchers_catalog.categories.aws.scripts | keys'
```

### Validate Configuration
```bash
# Check if your configuration is valid JSON
python -m json.tool customer_config.json

# Test the generation process
python generate_evidence_sets.py customer_config.json test_output.json
```

## Troubleshooting

### Common Issues

1. **"Script not found in catalog"**
   - Check the script name spelling in your configuration
   - Verify the script exists in the catalog

2. **"Category not found in catalog"**
   - Ensure you're using the correct category names: `aws`, `k8s`, `knowbe4`, `okta`

3. **"Invalid JSON"**
   - Validate your JSON syntax using `python -m json.tool customer_config.json`

4. **"Environment variables not set"**
   - Set required environment variables for KnowBe4, Okta, and GitLab scripts

5. **"GitLab API authentication failed"**
   - Verify `GITLAB_URL` and `GITLAB_API_TOKEN` are set correctly
   - Check that the token has the required scopes (`read_api`, `read_repository`, `read_user`)
   - Ensure the token hasn't expired

### Getting Help

1. Check the script files in the `fetchers/` directory for detailed documentation
2. Review the `evidence_fetchers_catalog.json` for complete script metadata
3. Test with a minimal configuration first

## Best Practices

1. **Start Small**: Begin with a minimal set of scripts and add more as needed
2. **Test First**: Always test your configuration before production use
3. **Document Changes**: Keep track of which scripts you've selected and why
4. **Regular Updates**: Review and update your selection as your infrastructure changes
5. **Environment Variables**: Use a `.env` file for sensitive configuration

## Next Steps

After generating your `evidence_sets.json`:

1. Upload it to your Paramify instance
2. Configure your evidence collection schedule
3. Set up monitoring and alerting
4. Review the collected evidence regularly
5. Update your configuration as your infrastructure evolves

For additional support, refer to the main README.md file or contact your implementation team.
