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

## Key Features

- **Multi-Instance Support**: Run the same fetcher against multiple AWS regions or GitLab projects
- **Evidence Sets**: Selectively choose which fetchers to run based on your needs
- **Paramify Integration**: Automatic upload of evidence sets and evidence files
- **Timestamped Storage**: All evidence stored in organized, timestamped directories

## Directory Structure

```
evidence-fetchers/
├── main.py                    # Main menu system
├── fetchers/                  # Evidence fetcher scripts
│   ├── aws/                  # AWS scripts (29 available)
│   ├── gitlab/               # GitLab scripts (3 available)
│   ├── k8s/                  # Kubernetes scripts (3 available)
│   ├── knowbe4/              # KnowBe4 scripts (2 available)
│   ├── okta/                 # Okta scripts (9 available)
│   └── rippling/             # Rippling scripts (2 available)
├── 0-prerequisites/          # Setup and dependencies
├── 1-select-fetchers/        # Fetcher selection
├── 2-create-evidence-sets/   # Create evidence sets in Paramify
├── 3-run-fetchers/           # Execute fetchers
├── 4-upload-to-paramify/     # Upload evidence to Paramify
├── 5-tests/                  # Testing and validation
├── 6-add-new-fetcher/        # Add new fetchers
└── extra-supporting-scripts/ # Additional tools
```

## Environment Variables

Create a `.env` file with:

```bash
# Required: Paramify API Configuration
PARAMIFY_UPLOAD_API_TOKEN=your_api_token_here
PARAMIFY_API_BASE_URL=https://app.paramify.com/api/v0

# Optional: Service-specific configuration
AWS_PROFILE=your_aws_profile
AWS_REGION=us-east-1
KNOWBE4_API_KEY=your_knowbe4_api_key
OKTA_API_TOKEN=your_okta_api_token
OKTA_ORG_URL=https://your-org.okta.com
RIPPLING_API_TOKEN=your_rippling_api_token
```

## Dependencies

- Python 3.x
- AWS CLI (for AWS scripts)
- jq (JSON processor)
- curl (HTTP client)
- kubectl (for Kubernetes scripts)

## Documentation

- **Component docs**: See `README.md` in each numbered directory
- **Developer guide**: `6-add-new-fetcher/DEVELOPER_GUIDE.md`
- **Customer setup**: `1-select-fetchers/CUSTOMER_SETUP_GUIDE.md`
