# Evidence Fetchers

Let's go fetch some evidence! And don't forget, screenshots are so 2012. 

## Quick Start

Run the main script to access all functionality:

```bash
python main.py
```

## Main Options

**0) Prerequisites** - Set up environment variables and check dependencies  

**1) Select Fetchers** - Choose which evidence fetcher scripts to use and generate evidence_sets.json  

**2) Create Evidence Sets in Paramify** - Upload evidence sets to Paramify via API  

**3) Run Fetchers** - Execute evidence fetcher scripts and store evidence files  

**4) Upload Evidence to Paramify** - Find latest evidence directory and upload to Paramify  

**5) Tests** - Run validation and test scripts  

**6) Add New Fetcher Script** - Add a new fetcher to the library with GitHub contribution instructions  

**7) Evidence Requirement Mapping** - Map evidence to requirements from Paramify YAML files  

---

## Detailed Documentation

### 0) Prerequisites

**Purpose**: Set up the environment and check dependencies before using the system.

**What it does**:
- Checks for required environment variables (.env file)
- Validates that all dependencies are installed
- Provides setup instructions for Paramify, AWS, and Kubernetes

**Files**:
- `0-prerequisites/prerequisites.py` - Main prerequisites script
- `0-prerequisites/README.md` - Detailed setup instructions

**Usage**:
```bash
python 0-prerequisites/prerequisites.py
```

### 1) Select Fetchers

**Purpose**: Choose which evidence fetcher scripts you want to use and generate a custom evidence_sets.json file.

**What it does**:
- Shows available evidence fetcher scripts by category
- Allows interactive selection of scripts
- Generates evidence_sets.json for Paramify upload
- Creates customer_config.json for your selections

**Files**:
- `1-select-fetchers/select_fetchers.py` - Main selection script
- `1-select-fetchers/generate_evidence_sets.py` - Evidence sets generator
- `1-select-fetchers/customer_config_template.json` - Template for customer configuration
- `1-select-fetchers/evidence_fetchers_catalog.json` - Complete catalog of all available scripts
- `1-select-fetchers/README.md` - Detailed selection guide

**Usage**:
```bash
python 1-select-fetchers/select_fetchers.py
```

### 2) Create Evidence Sets in Paramify

**Purpose**: Upload evidence sets to Paramify via API and optionally upload fetcher scripts as evidence artifacts.

**What it does**:
- Reads evidence_sets.json generated in step 1
- Creates evidence sets in Paramify via API
- Optionally uploads fetcher scripts as evidence artifacts
- Records upload results in upload_log.json

**Files**:
- `2-create-evidence-sets/create_evidence_sets.py` - Main upload script
- `2-create-evidence-sets/paramify_pusher.py` - Paramify API integration
- `2-create-evidence-sets/README.md` - Detailed upload instructions

**Usage**:
```bash
python 2-create-evidence-sets/create_evidence_sets.py
```

### 3) Run Fetchers

**Purpose**: Execute the selected evidence fetcher scripts and store evidence in timestamped directories.

**What it does**:
- Reads evidence_sets.json to determine which scripts to run
- Supports **multi-instance execution** for AWS regions and GitLab projects
- Executes each fetcher script with appropriate parameters
- Stores evidence files in timestamped directories under /evidence
- Creates execution summary and CSV reports

**Multi-Instance Support**:
- **AWS Regions**: Run the same fetcher against multiple AWS regions with different profiles
- **GitLab Projects**: Run the same fetcher against multiple GitLab projects with different access tokens
- **Environment Variables**: Configure multiple instances using `GITLAB_PROJECT_N_*` and `AWS_REGION_N_*` patterns

**Files**:
- `3-run-fetchers/run_fetchers.py` - Main execution script with multi-instance support
- `3-run-fetchers/main_fetcher.py` - Legacy fetcher execution script
- `3-run-fetchers/README.md` - Detailed execution guide

**Usage**:
```bash
python 3-run-fetchers/run_fetchers.py
```

### 4) Upload Evidence to Paramify

**Purpose**: Find the latest evidence directory and upload evidence files to Paramify via API.

**What it does**:
- Automatically finds the latest evidence directory based on timestamp
- Validates that required summary files exist
- Uploads evidence files to Paramify via API
- Provides user confirmation before proceeding
- Handles errors gracefully with detailed logging

**Files**:
- `4-upload-to-paramify/upload_to_paramify.py` - Main upload script
- `4-upload-to-paramify/README.md` - Upload documentation

**Usage**:
```bash
python 4-upload-to-paramify/upload_to_paramify.py
```

### 5) Tests

**Purpose**: Run validation and test scripts to ensure the system is working correctly.

**What it does**:
- Checks for required files and directories
- Runs catalog validation
- Executes evidence fetcher tests
- Runs demo functionality tests
- Provides comprehensive test summary

**Files**:
- `5-tests/run_tests.py` - Main test runner
- `5-tests/simple_test.py` - Simple functionality test
- `5-tests/test_system.py` - System integration test
- `5-tests/demo.py` - Demo functionality
- `5-tests/README.md` - Test documentation

**Usage**:
```bash
python 5-tests/run_tests.py
```

### 6) Add New Fetcher Script

**Purpose**: Add a new evidence fetcher script to the library with proper integration and GitHub contribution instructions.

**What it does**:
- Provides interactive and command-line modes for adding scripts
- Automatically extracts metadata from script files
- Updates the evidence fetchers catalog
- Validates catalog integrity
- Provides GitHub contribution instructions

**Files**:
- `6-add-new-fetcher/add_new_fetcher.py` - Main addition script
- `6-add-new-fetcher/add_evidence_fetcher.py` - Core addition functionality
- `6-add-new-fetcher/validate_catalog.py` - Catalog validation
- `6-add-new-fetcher/new_script_template.sh` - Bash script template
- `6-add-new-fetcher/new_script_template.py` - Python script template
- `6-add-new-fetcher/DEVELOPER_GUIDE.md` - Comprehensive developer guide
- `6-add-new-fetcher/README.md` - Quick start guide

**Usage**:
```bash
python 6-add-new-fetcher/add_new_fetcher.py
```

### 7) Evidence Requirement Mapping

**Purpose**: Map evidence to requirements from Paramify machine readable YAML files and add requirement mappings to evidence sets.

**What it does**:
- Reads Paramify YAML files containing evidence-requirement mappings
- Extracts evidence mappings from YAML data
- Adds requirement mappings to evidence sets JSON
- Creates updated evidence sets file with requirements

**Files**:
- `7-evidence-requirement-mapping/map_requirements.py` - Main mapping script
- `7-evidence-requirement-mapping/paramify_evidence_mappings.json` - Existing evidence mappings
- `7-evidence-requirement-mapping/README.md` - Mapping documentation

**Usage**:
```bash
python 7-evidence-requirement-mapping/map_requirements.py
```

## Directory Structure

```
evidence-fetchers/
├── main.py                          # Main menu system
├── README.md                        # This file
├── requirements.txt                 # Python dependencies
├── .env                            # Environment variables (create this)
├── evidence/                       # Evidence storage directory
├── fetchers/                       # Evidence fetcher scripts
│   ├── aws/                        # AWS-specific scripts
│   ├── gitlab/                     # GitLab CI/CD and change management scripts
│   ├── k8s/                        # Kubernetes scripts
│   ├── knowbe4/                    # KnowBe4 scripts
│   ├── okta/                       # Okta scripts
│   └── rippling/                   # Rippling HR management scripts
├── 0-prerequisites/                # Prerequisites setup
├── 1-select-fetchers/              # Fetcher selection
├── 2-create-evidence-sets/         # Evidence sets creation in Paramify
├── 3-run-fetchers/                 # Script execution
├── 4-upload-to-paramify/           # Evidence upload to Paramify
├── 5-tests/                        # Testing and validation
├── 6-add-new-fetcher/              # Adding new scripts
└── 7-evidence-requirement-mapping/ # Requirement mapping
```

## Getting Started

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd evidence-fetchers
   ```

2. **Set up prerequisites**:
   ```bash
   python main.py
   # Choose option 0
   ```

3. **Select your fetchers**:
   ```bash
   python main.py
   # Choose option 1
   ```

4. **Create evidence sets in Paramify**:
   ```bash
   python main.py
   # Choose option 2
   ```

5. **Run the fetchers**:
   ```bash
   python main.py
   # Choose option 3
   ```

6. **Upload evidence to Paramify**:
   ```bash
   python main.py
   # Choose option 4
   ```

## Environment Variables

Create a `.env` file with the following variables:

```bash
# Paramify API Configuration
PARAMIFY_UPLOAD_API_TOKEN=your_api_token_here
PARAMIFY_API_BASE_URL=https://app.paramify.com/api/v0

# Optional: KnowBe4 Configuration
KNOWBE4_API_KEY=your_knowbe4_api_key
KNOWBE4_REGION=us

# Optional: Okta Configuration
OKTA_API_TOKEN=your_okta_api_token
OKTA_ORG_URL=https://your-org.okta.com

# Optional: Rippling Configuration
RIPPLING_API_TOKEN=your_rippling_api_token
```

## Available Services

The evidence fetchers support multiple cloud providers and services:

### AWS Scripts (28 available)
- **Security**: IAM, encryption, security groups, WAF
- **High Availability**: Auto scaling, load balancers, databases
- **Monitoring**: CloudWatch, Config, GuardDuty
- **Storage**: S3, EBS, EFS encryption and policies
- **Networking**: VPC, Route53, network policies

### GitLab Scripts (3 available)
- **CI/CD**: Pipeline configuration and security scanning
- **Repository**: File inventory and configuration analysis
- **Change Management**: Merge request process and approval metrics

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

### Rippling Scripts (2 available)
- **HR Management**: Current employee data and access management
- **Historical Data**: All employee data including historical records

## Dependencies

- Python 3.x
- AWS CLI
- jq (JSON processor)
- curl (HTTP client)
- kubectl (for Kubernetes scripts)

## Support

For detailed instructions on each component, see the README.md files in each numbered directory.

For developer information, see `6-add-new-fetcher/DEVELOPER_GUIDE.md`.

For customer setup, see `1-select-fetchers/CUSTOMER_SETUP_GUIDE.md`.