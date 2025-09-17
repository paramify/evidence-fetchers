# Evidence Fetchers

A comprehensive system for collecting, managing, and uploading evidence for compliance and security assessments.

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

**4) Tests** - Run validation and test scripts  

**5) Add New Fetcher Script** - Add a new fetcher to the library with GitHub contribution instructions  

**6) Evidence Requirement Mapping** - Map evidence to requirements from Paramify YAML files  

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
- Executes each fetcher script with appropriate parameters
- Stores evidence files in timestamped directories under /evidence
- Optionally uploads evidence files to Paramify via API
- Creates execution summary and CSV reports

**Files**:
- `3-run-fetchers/run_fetchers.py` - Main execution script
- `3-run-fetchers/main_fetcher.py` - Legacy fetcher execution script
- `3-run-fetchers/README.md` - Detailed execution guide

**Usage**:
```bash
python 3-run-fetchers/run_fetchers.py
```

### 4) Tests

**Purpose**: Run validation and test scripts to ensure the system is working correctly.

**What it does**:
- Checks for required files and directories
- Runs catalog validation
- Executes evidence fetcher tests
- Runs demo functionality tests
- Provides comprehensive test summary

**Files**:
- `4-tests/run_tests.py` - Main test runner
- `4-tests/simple_test.py` - Simple functionality test
- `4-tests/test_system.py` - System integration test
- `4-tests/debug_s3.py` - S3 debugging test
- `4-tests/demo.py` - Demo functionality
- `4-tests/README.md` - Test documentation

**Usage**:
```bash
python 4-tests/run_tests.py
```

### 5) Add New Fetcher Script

**Purpose**: Add a new evidence fetcher script to the library with proper integration and GitHub contribution instructions.

**What it does**:
- Provides interactive and command-line modes for adding scripts
- Automatically extracts metadata from script files
- Updates the evidence fetchers catalog
- Validates catalog integrity
- Provides GitHub contribution instructions

**Files**:
- `5-add-new-fetcher/add_new_fetcher.py` - Main addition script
- `5-add-new-fetcher/add_evidence_fetcher.py` - Core addition functionality
- `5-add-new-fetcher/validate_catalog.py` - Catalog validation
- `5-add-new-fetcher/new_script_template.sh` - Bash script template
- `5-add-new-fetcher/new_script_template.py` - Python script template
- `5-add-new-fetcher/DEVELOPER_GUIDE.md` - Comprehensive developer guide
- `5-add-new-fetcher/README.md` - Quick start guide

**Usage**:
```bash
python 5-add-new-fetcher/add_new_fetcher.py
```

### 6) Evidence Requirement Mapping

**Purpose**: Map evidence to requirements from Paramify machine readable YAML files and add requirement mappings to evidence sets.

**What it does**:
- Reads Paramify YAML files containing evidence-requirement mappings
- Extracts evidence mappings from YAML data
- Adds requirement mappings to evidence sets JSON
- Creates updated evidence sets file with requirements

**Files**:
- `6-evidence-requirement-mapping/map_requirements.py` - Main mapping script
- `6-evidence-requirement-mapping/paramify_evidence_mappings.json` - Existing evidence mappings
- `6-evidence-requirement-mapping/README.md` - Mapping documentation

**Usage**:
```bash
python 6-evidence-requirement-mapping/map_requirements.py
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
│   ├── k8s/                        # Kubernetes scripts
│   ├── knowbe4/                    # KnowBe4 scripts
│   └── okta/                       # Okta scripts
├── 0-prerequisites/                # Prerequisites setup
├── 1-select-fetchers/              # Fetcher selection
├── 2-create-evidence-sets/         # Paramify upload
├── 3-run-fetchers/                 # Script execution
├── 4-tests/                        # Testing and validation
├── 5-add-new-fetcher/              # Adding new scripts
└── 6-evidence-requirement-mapping/ # Requirement mapping
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

## Environment Variables

Create a `.env` file with the following variables:

```bash
# Paramify API Configuration
PARAMIFY_API_TOKEN=your_api_token_here
PARAMIFY_API_BASE_URL=https://app.paramify.com/api/v0

# Optional: KnowBe4 Configuration
KNOWBE4_API_KEY=your_knowbe4_api_key
KNOWBE4_REGION=us

# Optional: Okta Configuration
OKTA_API_TOKEN=your_okta_api_token
OKTA_ORG_URL=https://your-org.okta.com
```

## Dependencies

- Python 3.x
- AWS CLI
- jq (JSON processor)
- curl (HTTP client)
- kubectl (for Kubernetes scripts)

## Support

For detailed instructions on each component, see the README.md files in each numbered directory.

For developer information, see `5-add-new-fetcher/DEVELOPER_GUIDE.md`.

For customer setup, see `1-select-fetchers/CUSTOMER_SETUP_GUIDE.md`.