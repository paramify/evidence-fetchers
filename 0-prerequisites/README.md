# 0) Prerequisites

This directory contains scripts and documentation for setting up the prerequisites for using the Evidence Fetchers system.

## Files

- `prerequisites.py` - Main prerequisites setup script
- `README.md` - This documentation file

## What This Does

The prerequisites script helps you:

1. **Check Environment Variables**: Verifies that your `.env` file exists and contains required variables
2. **Validate Dependencies**: Checks that all required tools are installed
3. **Provide Setup Instructions**: Shows detailed setup instructions for Paramify, AWS, and Kubernetes

## Usage

```bash
python prerequisites.py
```

## Required Environment Variables

Create a `.env` file in the root directory with:

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
```

## Required Dependencies

- **Python 3.x**: Python interpreter
- **AWS CLI**: AWS command line interface
- **jq**: JSON processor
- **curl**: HTTP client
- **kubectl**: Kubernetes CLI (if using K8s scripts)

## Setup Instructions

### Paramify Setup

1. Log into the Paramify application (app.paramify.com)
2. Navigate to Settings (Gear Icon in top right) > API Keys
3. Create a new API key (+ API Key) with the following permissions:
   - Name: choose an appropriate name
   - Expiration Time: choose 1 month - 1 year
   - Permissions: View Evidences & Write Evidences
4. Copy the API key and add it to your `.env` file
5. Note your Paramify base URL (usually https://app.paramify.com/api/v0)

### AWS Setup

1. Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
2. Configure AWS credentials:
   ```bash
   aws configure
   ```
3. Or use AWS profiles:
   ```bash
   aws configure --profile your-profile-name
   ```
4. Test your configuration:
   ```bash
   aws sts get-caller-identity
   ```

### Kubernetes Setup

1. Install kubectl: https://kubernetes.io/docs/tasks/tools/
2. Configure kubectl for your cluster:
   ```bash
   aws eks update-kubeconfig --region us-west-2 --name your-cluster-name
   ```
3. Test your configuration:
   ```bash
   kubectl cluster-info
   ```

## Troubleshooting

### Common Issues

1. **"File not found" errors**: Ensure you're running from the correct directory
2. **"Permission denied" errors**: Check file permissions and ensure scripts are executable
3. **"Environment variable not set" errors**: Verify your `.env` file exists and contains the required variables
4. **"Command not found" errors**: Install the missing dependencies

### Getting Help

1. Check the main README.md for general information
2. Review the error messages for specific guidance
3. Ensure all dependencies are properly installed
4. Verify your environment variables are set correctly

## Next Steps

After completing the prerequisites:

1. **Select Fetchers** (option 1): Choose which evidence fetcher scripts to use
2. **Create Evidence Sets in Paramify** (option 2): Upload evidence sets to Paramify
3. **Run Fetchers** (option 3): Execute the evidence fetcher scripts
