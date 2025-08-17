# Evidence Fetchers

A system for collecting compliance evidence from AWS and other services and uploading it to Paramify.

## Overview

This system consists of:

1. **Fetchers** - Individual Python modules and bash scripts that collect evidence from AWS services
2. **Evidence Sets** - JSON configuration defining evidence sets in Paramify
3. **Main Fetcher** - Main orchestrator that runs bash scripts for different providers (AWS, KnowBe4, etc.)
4. **Paramify Pusher** - Uploads evidence to Paramify via API with automatic Evidence Object creation

## Architecture

### Fetcher Structure

The system supports both Python modules and bash scripts:

**Bash Scripts (Primary):**
- Located in `fetchers/{provider}/` directories (e.g., `fetchers/aws/`, `fetchers/knowbe4/`)
- Each script outputs a single JSON file with evidence
- Scripts are executed by the main fetcher with provider-specific parameters

**Python Modules (Legacy):**
- Located in `fetchers/` directory
- Follow the template structure below

**Python Fetcher Template:**
```python
"""
Fetcher: S3 MFA Delete for CloudTrail bucket

AWS CLI Command:
    aws s3api get-bucket-versioning --bucket DOC-EXAMPLE-BUCKET1 --output json

AWS API Call:
    boto3.client("s3").get_bucket_versioning(Bucket="DOC-EXAMPLE-BUCKET1")

Validator Rules:
    "Status":\s*"Enabled"
    "MFADelete":\s*"Enabled"

Expected Outcome:
    JSON contains both Status=Enabled and MFADelete=Enabled
"""

def run(target_resource, evidence_dir):
    # 1. Call AWS CLI or Boto3 to get raw data
    # 2. Save JSON exactly as returned to evidence_dir
    # 3. Apply validator regex rules to check compliance
    # 4. Return (status, evidence_file_path)
    pass
```

### Evidence Storage

**Folder layout:**
```
evidence/
  2025_08_15_151101/
    auto_scaling_high_availability.json
    aws_config_conformance_packs.json
    block_storage_encryption_status.json
    summary.json
```

**File naming rule:** `<script-name>.json`

**Contents:** Exactly the JSON returned by AWS CLI or scripts (no extra metadata)

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Set up AWS credentials:**
   ```bash
   aws configure
   # or set AWS_PROFILE in .env file
   ```

## Usage

### Running the Main Fetcher

**Show help and available options:**
```bash
python main_fetcher.py --help
```

**Basic usage (runs all AWS scripts):**
```bash
python main_fetcher.py
```

**With specific AWS profile:**
```bash
python main_fetcher.py --profile my-aws-profile
```

**With specific provider:**
```bash
python main_fetcher.py --provider aws
python main_fetcher.py --provider knowbe4
```

**With timeout (prevents hanging scripts):**
```bash
python main_fetcher.py --timeout 300
```

**List available providers and scripts:**
```bash
python main_fetcher.py --list
```

### Uploading to Paramify

**Upload evidence from a run:**
```bash
python paramify_pusher.py evidence/2025_08_15_151101/summary.json
```

**With custom API token:**
```bash
python paramify_pusher.py evidence/2025_08_15_151101/summary.json --api-token your-token
```

**With custom base URL:**
```bash
python paramify_pusher.py evidence/2025_08_15_151101/summary.json --base-url https://stage.paramify.com/api/v0
```

## Configuration

### Environment Variables (`.env`)

```bash
# Paramify Configuration
PARAMIFY_UPLOAD_API_TOKEN=your-api-token
PARAMIFY_API_BASE_URL=https://stage.paramify.com/api/v0

# AWS Configuration
AWS_PROFILE=your-aws-profile
AWS_REGION=us-east-1

# KnowBe4 Configuration
KNOWBE4_API_KEY=your-knowbe4-api-key
KNOWBE4_REGION=us

# Default Provider
DEFAULT_PROVIDER=aws
```

### Evidence Sets (`evidence_sets.json`)

Defines evidence sets in Paramify with:
- `id`: Paramify evidence set ID (e.g., "EVD-AUTO-SCALING-HA")
- `name`: Human-readable name
- `description`: Description of the evidence
- `service`: Service provider (e.g., "AWS")
- `instructions`: CLI/API commands used
- `validation_rules`: Regex patterns to validate compliance
- `expected_outcome`: Description of expected result

Example:
```json
{
  "evidence_sets": {
    "auto_scaling_high_availability": {
      "id": "EVD-AUTO-SCALING-HA",
      "name": "Auto Scaling High Availability",
      "description": "Evidence for Auto Scaling group high availability configurations",
      "service": "AWS",
      "instructions": "Script: auto_scaling_high_availability.sh. Commands executed: aws autoscaling describe-auto-scaling-groups",
      "validation_rules": [],
      "expected_outcome": "JSON contains Auto Scaling group configurations"
    }
  }
}
```

## Output Format

### Summary JSON

```json
{
  "timestamp": "2025-08-15T15:18:02.227871Z",
  "provider": "aws",
  "evidence_directory": "evidence/2025_08_15_151101",
  "results": [
    {
      "script": "auto_scaling_high_availability",
      "provider": "aws",
      "status": "PASS",
      "evidence_file": "evidence/2025_08_15_151101/auto_scaling_high_availability.json"
    }
  ]
}
```

### Upload Log

```json
{
  "upload_timestamp": "2025-08-15T22:07:00Z",
  "results": [
    {
      "check": "auto_scaling_high_availability",
      "resource": "unknown",
      "status": "PASS",
      "evidence_file": "evidence/2025_08_15_151101/auto_scaling_high_availability.json",
      "evidence_object_id": "662817ec-093e-4515-b511-76df1fa9519c",
      "upload_success": true,
      "timestamp": "2025-08-15T22:07:00Z"
    }
  ]
}
```

## Supported Providers

### AWS
- **Location:** `fetchers/aws/`
- **Scripts:** 25+ compliance scripts covering:
  - High Availability (Auto Scaling, RDS, EKS, etc.)
  - Security (IAM, Security Groups, WAF, etc.)
  - Encryption (S3, RDS, EBS, etc.)
  - Monitoring (CloudWatch, Config, GuardDuty, etc.)
- **Parameters:** `profile region output_dir output_csv`

### KnowBe4
- **Location:** `fetchers/knowbe4/`
- **Scripts:** Security awareness training and role-specific training
- **Parameters:** `output_dir`

### Extending to New Providers
1. Create `fetchers/{provider}/` directory
2. Add bash scripts that output JSON files
3. Update `main_fetcher.py` to handle provider-specific parameters
4. Add evidence set mappings in `evidence_sets.json`

## Paramify Integration

The system automatically:

1. **Creates Evidence Objects** in Paramify using reference IDs from `evidence_sets.json`
2. **Checks for existing Evidence Objects** to avoid duplicates
3. **Uploads evidence files** as artifacts with metadata
4. **Handles errors gracefully** and logs all operations

**API Endpoints Used:**
- `GET /evidence` - Check for existing Evidence Objects
- `POST /evidence` - Create new Evidence Objects
- `POST /evidence/{id}/artifacts/upload` - Upload evidence files

## Testing

The system includes comprehensive tests in the `tests/` directory:

### Run all tests:
```bash
python tests/run_tests.py
```

### Run individual tests:
```bash
python tests/test_system.py    # System validation
python tests/demo.py           # Demo with mocked AWS
python tests/simple_test.py    # Validation function test
python tests/debug_s3.py       # S3 MFA Delete debug
```

### Test environment:
Tests use mocked AWS responses and don't require real AWS credentials.

## Troubleshooting

### Common Issues

1. **AWS credentials not configured:**
   ```bash
   aws configure
   # or set AWS_PROFILE in .env file
   ```

2. **Paramify API token not set:**
   ```bash
   # Add to .env file:
   PARAMIFY_UPLOAD_API_TOKEN=your-api-token
   ```

3. **Script execution errors:**
   ```bash
   # Make scripts executable:
   chmod +x fetchers/aws/*.sh
   ```

4. **Timeout issues:**
   ```bash
   # Use timeout option:
   python main_fetcher.py --timeout 600
   ```

5. **Upload failures:**
   - Check API token permissions
   - Verify staging vs production URLs
   - Check network connectivity

### Debug Mode

Run individual scripts with verbose output:
```bash
# Test a specific script:
./fetchers/aws/auto_scaling_high_availability.sh profile region output_dir /dev/null
```

## Contributing

1. Follow the bash script template for new fetchers
2. Include comprehensive documentation
3. Test with real AWS resources
4. Update evidence sets configuration
5. Add to test configuration

