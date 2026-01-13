#!/bin/bash
# Checkov Terraform Security Evidence Fetcher
# Flexible fetcher that supports multiple source types and configurations
# Scans Terraform files for security compliance evidence

# Usage: ./checkov_terraform.sh <profile> <region> <output_dir> <output_csv>
# Note: profile and region are kept for consistency but not used for Checkov

if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <profile> <region> <output_dir> <output_csv>"
    exit 1
fi

PROFILE="$1"
REGION="$2"
OUTPUT_DIR="$3"
OUTPUT_CSV="$4"

# Component identifier
COMPONENT="checkov_terraform"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========== CHECKOV TERRAFORM SECURITY SCAN ==========${NC}"

# Check if Checkov is installed
if ! command -v checkov &> /dev/null; then
    echo -e "${RED}Error:${NC} Checkov is not installed. Please install it with: pip install checkov" >&2
    exit 1
fi

# Use existing GitLab multi-project configuration
# The fetcher will be called with GitLab project environment variables already set
# by the run_fetchers.py multi-instance system

echo -e "${BLUE}Using GitLab project configuration${NC}"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
BRANCH="${GITLAB_BRANCH:-main}"

# Choose between cloning repository or downloading files via API
# Default to API downloads (faster, less storage) but allow cloning if preferred
CHECKOV_CLONE_REPO="${CHECKOV_CLONE_REPO:-false}"

if [ "${CHECKOV_CLONE_REPO}" = "true" ]; then
    # Clone the entire repository (slower but more complete)
    echo -e "${BLUE}Cloning GitLab repository (branch: $BRANCH) to: $TEMP_DIR${NC}"
    if ! git clone --depth 1 --branch "$BRANCH" "https://oauth2:$GITLAB_API_TOKEN@${GITLAB_URL#https://}/$GITLAB_PROJECT_ID.git" "$TEMP_DIR" 2>/dev/null; then
        echo -e "${RED}Error:${NC} Failed to clone GitLab repository" >&2
        rm -rf "$TEMP_DIR"
        exit 1
    fi
else
    # Use GitLab API to download only Terraform files (faster, less storage)
    echo -e "${BLUE}Downloading Terraform files from GitLab repository via API (branch: $BRANCH)${NC}"
    
    API_ENDPOINT="${GITLAB_URL%/}/api/v4"
    ENCODED_PROJECT=$(echo "$GITLAB_PROJECT_ID" | sed 's/\//%2F/g')
    ENCODED_BRANCH=$(echo "$BRANCH" | sed 's/\//%2F/g')
    
    # Get repository tree to find Terraform files
    TREE_URL="${API_ENDPOINT}/projects/${ENCODED_PROJECT}/repository/tree"
    HEADERS="PRIVATE-TOKEN: ${GITLAB_API_TOKEN}"
    
    # Fetch repository tree recursively
    TREE_JSON=$(curl -s -H "$HEADERS" "${TREE_URL}?recursive=true&per_page=100&ref=${ENCODED_BRANCH}" 2>/dev/null)
    
    if [ -z "$TREE_JSON" ] || echo "$TREE_JSON" | grep -q "error\|404\|401"; then
        echo -e "${YELLOW}Warning:${NC} Failed to access GitLab repository tree via API, falling back to clone${NC}" >&2
        CHECKOV_CLONE_REPO="true"
    else
        # Find all Terraform files (.tf, .tfvars) and download them
        TERRAFORM_FILES=$(echo "$TREE_JSON" | jq -r '.[] | select(.type == "blob") | select(.path | endswith(".tf") or endswith(".tfvars")) | .path' 2>/dev/null)
        
        if [ -z "$TERRAFORM_FILES" ]; then
            echo -e "${YELLOW}Warning:${NC} No Terraform files found in repository" >&2
            # Create empty result
            echo '{"framework": "terraform", "scan_timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "summary": {"passed_checks": 0, "failed_checks": 0, "skipped_checks": 0, "total_checks": 0}, "results": [], "error": "No Terraform files found"}' > "$OUTPUT_JSON"
            rm -rf "$TEMP_DIR"
            exit 0
        fi
        
        # Download each Terraform file while preserving directory structure
        echo "$TERRAFORM_FILES" | while IFS= read -r file_path; do
            if [ -n "$file_path" ]; then
                # Create directory structure
                file_dir=$(dirname "$file_path")
                mkdir -p "$TEMP_DIR/$file_dir"
                
                # Download file via API
                ENCODED_FILE_PATH=$(echo "$file_path" | sed 's/\//%2F/g')
                FILE_URL="${API_ENDPOINT}/projects/${ENCODED_PROJECT}/repository/files/${ENCODED_FILE_PATH}/raw?ref=${ENCODED_BRANCH}"
                
                if curl -s -H "$HEADERS" -o "$TEMP_DIR/$file_path" "$FILE_URL" 2>/dev/null; then
                    echo -e "${GREEN}✓${NC} Downloaded: $file_path"
                else
                    echo -e "${YELLOW}Warning:${NC} Failed to download: $file_path" >&2
                fi
            fi
        done
    fi
fi

# If clone fallback was needed, try cloning now
if [ "${CHECKOV_CLONE_REPO}" = "true" ] && [ ! -d "$TEMP_DIR/.git" ]; then
    rm -rf "$TEMP_DIR"
    TEMP_DIR=$(mktemp -d)
    echo -e "${BLUE}Cloning GitLab repository (branch: $BRANCH) to: $TEMP_DIR${NC}"
    if ! git clone --depth 1 --branch "$BRANCH" "https://oauth2:$GITLAB_API_TOKEN@${GITLAB_URL#https://}/$GITLAB_PROJECT_ID.git" "$TEMP_DIR" 2>/dev/null; then
        echo -e "${RED}Error:${NC} Failed to clone GitLab repository" >&2
        rm -rf "$TEMP_DIR"
        exit 1
    fi
fi

# Find Terraform directories
TERRAFORM_DIRS=$(find "$TEMP_DIR" -name "*.tf" -exec dirname {} \; | sort -u)
if [ -z "$TERRAFORM_DIRS" ]; then
    echo -e "${YELLOW}Warning:${NC} No Terraform files found in source" >&2
    # Create empty result
    echo '{"framework": "terraform", "scan_timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "summary": {"passed_checks": 0, "failed_checks": 0, "skipped_checks": 0, "total_checks": 0}, "results": [], "error": "No Terraform files found"}' > "$OUTPUT_JSON"
    rm -rf "$TEMP_DIR"
    exit 0
fi

echo -e "${BLUE}Found Terraform directories:${NC}"
echo "$TERRAFORM_DIRS" | sed 's/^/  /'

# Initialize JSON output with metadata
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "{
  \"framework\": \"terraform\",
  \"scan_timestamp\": \"$TIMESTAMP\",
  \"source_type\": \"gitlab\",
  \"source\": \"$GITLAB_URL/$GITLAB_PROJECT_ID\",
  \"summary\": {
    \"passed_checks\": 0,
    \"failed_checks\": 0,
    \"skipped_checks\": 0,
    \"total_checks\": 0
  },
  \"results\": []
}" > "$OUTPUT_JSON"

# Build flexible Checkov command arguments using project-specific configuration
CHECKOV_ARGS="--framework terraform --output json --quiet"

# Add repository identification (use project-specific or defaults)
REPO_ID="${CHECKOV_REPO_ID:-evidence-fetchers-terraform}"
BRANCH="${CHECKOV_BRANCH:-main}"
CHECKOV_ARGS="$CHECKOV_ARGS --repo-id $REPO_ID --branch $BRANCH"

# Add soft-fail option (don't exit on failures)
if [ "${CHECKOV_SOFT_FAIL:-true}" = "true" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --soft-fail"
fi

# Add compact output
if [ "${CHECKOV_COMPACT:-true}" = "true" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --compact"
fi

# Add repo root for plan enrichment (allows Checkov to respect skip comments and show file references)
# This is required for --deep-analysis to work
REPO_ROOT_SET=false
if [ -n "$CHECKOV_REPO_ROOT" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --repo-root-for-plan-enrichment $CHECKOV_REPO_ROOT"
    echo -e "${BLUE}Using repo root for plan enrichment: $CHECKOV_REPO_ROOT${NC}"
    REPO_ROOT_SET=true
elif [ -d "$TEMP_DIR" ]; then
    # Use cloned repository as repo root
    CHECKOV_ARGS="$CHECKOV_ARGS --repo-root-for-plan-enrichment $TEMP_DIR"
    echo -e "${BLUE}Using cloned repository as repo root for plan enrichment${NC}"
    REPO_ROOT_SET=true
fi

# Add deep analysis for plan file scanning (requires --repo-root-for-plan-enrichment)
# According to docs: --deep-analysis combines graph of Plan file and Terraform files scans
# This allows Checkov to make graph connections where there is incomplete information in the plan file
# See: https://www.checkov.io/7.Scan%20Examples/Terraform%20Plan%20Scanning.html
if [ "${CHECKOV_DEEP_ANALYSIS:-false}" = "true" ] && [ "$SCAN_MODE" = "plan" ] && [ "$REPO_ROOT_SET" = "true" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --deep-analysis"
    echo -e "${BLUE}Using deep analysis for improved graph connections${NC}"
elif [ "${CHECKOV_DEEP_ANALYSIS:-false}" = "true" ] && [ "$SCAN_MODE" = "plan" ] && [ "$REPO_ROOT_SET" = "false" ]; then
    echo -e "${YELLOW}Warning: --deep-analysis requires --repo-root-for-plan-enrichment. Skipping deep analysis.${NC}"
fi

# Add project-specific checks to run (if specified in .env)
if [ -n "$CHECKOV_CHECKS" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --check $CHECKOV_CHECKS"
    echo -e "${BLUE}Running specific checks: $CHECKOV_CHECKS${NC}"
fi

# Combine skip checks from defaults and .env configuration
SKIP_CHECKS_LIST=""

# 1) Load default skip checks (low-severity checks to usually skip)
DEFAULT_SKIP_CHECKS_FILE="fetchers/checkov/skip-checks.default.txt"
if [ -f "$DEFAULT_SKIP_CHECKS_FILE" ]; then
    while IFS= read -r check || [ -n "$check" ]; do
        [[ -z "$check" || "$check" =~ ^[[:space:]]*# ]] && continue
        if [ -z "$SKIP_CHECKS_LIST" ]; then
            SKIP_CHECKS_LIST="$check"
        else
            SKIP_CHECKS_LIST="$SKIP_CHECKS_LIST,$check"
        fi
    done < "$DEFAULT_SKIP_CHECKS_FILE"
    echo -e "${BLUE}Loaded default skip checks from: $DEFAULT_SKIP_CHECKS_FILE${NC}"
fi

# 2) Add user-specified skip checks from .env (comma-separated)
if [ -n "$CHECKOV_SKIP_CHECKS" ]; then
    if [ -z "$SKIP_CHECKS_LIST" ]; then
        SKIP_CHECKS_LIST="$CHECKOV_SKIP_CHECKS"
    else
        SKIP_CHECKS_LIST="$SKIP_CHECKS_LIST,$CHECKOV_SKIP_CHECKS"
    fi
    echo -e "${BLUE}Added skip checks from .env: $CHECKOV_SKIP_CHECKS${NC}"
fi

# Add all skip checks to Checkov arguments
if [ -n "$SKIP_CHECKS_LIST" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --skip-check $SKIP_CHECKS_LIST"
    echo -e "${BLUE}Skipping checks: $SKIP_CHECKS_LIST${NC}"
fi

# Add project-specific severity filtering (if specified in .env)
# Note: --severity is not a valid Checkov flag. Use --check or --skip-check with severity values instead
# Example: --skip-check LOW,MEDIUM or --check HIGH,CRITICAL
# Note: Plan JSON doesn't include severities without API key, so this may not work for plan files
if [ -n "$CHECKOV_SEVERITY" ]; then
    # Use severity with --skip-check to filter by severity
    CHECKOV_ARGS="$CHECKOV_ARGS --skip-check $CHECKOV_SEVERITY"
    echo -e "${BLUE}Severity filter (via --skip-check): $CHECKOV_SEVERITY${NC}"
fi

# Add external checks directory (if specified)
if [ -n "$CHECKOV_EXTERNAL_CHECKS_DIR" ] && [ -d "$CHECKOV_EXTERNAL_CHECKS_DIR" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --external-checks-dir $CHECKOV_EXTERNAL_CHECKS_DIR"
    echo -e "${BLUE}Using external checks: $CHECKOV_EXTERNAL_CHECKS_DIR${NC}"
fi

# Add download external modules (for Terraform)
# According to docs: --download-external-modules DOWNLOAD_EXTERNAL_MODULES [env var: DOWNLOAD_EXTERNAL_MODULES]
# Note: Using environment variable for compatibility (documented approach)
if [ "${CHECKOV_DOWNLOAD_EXTERNAL_MODULES:-true}" = "true" ]; then
    export DOWNLOAD_EXTERNAL_MODULES=True
fi

# Add external modules download path
# According to docs: --external-modules-download-path EXTERNAL_MODULES_DOWNLOAD_PATH [env var: EXTERNAL_MODULES_DIR]
if [ -n "$CHECKOV_EXTERNAL_MODULES_PATH" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --external-modules-download-path $CHECKOV_EXTERNAL_MODULES_PATH"
fi

# Add evaluate variables (for Terraform)
# According to docs: --evaluate-variables EVALUATE_VARIABLES [env var: CKV_EVAL_VARS]
# Note: Using environment variable for compatibility (documented approach)
if [ "${CHECKOV_EVALUATE_VARIABLES:-true}" = "true" ]; then
    export CKV_EVAL_VARS=True
fi

# Add project-specific skip paths (if specified in .env)
if [ -n "$CHECKOV_SKIP_PATHS" ]; then
    for path in $(echo "$CHECKOV_SKIP_PATHS" | tr ',' ' '); do
        CHECKOV_ARGS="$CHECKOV_ARGS --skip-path $path"
    done
    echo -e "${BLUE}Skipping paths: $CHECKOV_SKIP_PATHS${NC}"
fi

# Check if we should scan a Terraform plan JSON file instead of directories
TERRAFORM_PLAN_FILE="${CHECKOV_TERRAFORM_PLAN_FILE:-}"
if [ -n "$TERRAFORM_PLAN_FILE" ] && [ -f "$TERRAFORM_PLAN_FILE" ]; then
    echo -e "${BLUE}Found Terraform plan file: $TERRAFORM_PLAN_FILE${NC}"
    SCAN_MODE="plan"
elif [ -f "$TEMP_DIR/tfplan.json" ]; then
    TERRAFORM_PLAN_FILE="$TEMP_DIR/tfplan.json"
    echo -e "${BLUE}Found Terraform plan file in repository: $TERRAFORM_PLAN_FILE${NC}"
    SCAN_MODE="plan"
else
    SCAN_MODE="directory"
fi

# Generate dynamic Checkov YAML configuration based on environment variables
CHECKOV_CONFIG_FILE="$TEMP_DIR/.checkov.yaml"
echo -e "${BLUE}Generating dynamic Checkov configuration: $CHECKOV_CONFIG_FILE${NC}"

cat > "$CHECKOV_CONFIG_FILE" << EOF
# Dynamically generated Checkov configuration
# Generated from environment variables

framework:
  - terraform

output: json
repo-id: $REPO_ID
branch: $BRANCH
soft-fail: $([ "${CHECKOV_SOFT_FAIL:-true}" = "true" ] && echo "true" || echo "false")
compact: $([ "${CHECKOV_COMPACT:-true}" = "true" ] && echo "true" || echo "false")
quiet: true

# Terraform-specific options
download-external-modules: $([ "${CHECKOV_DOWNLOAD_EXTERNAL_MODULES:-true}" = "true" ] && echo "true" || echo "false")
evaluate-variables: $([ "${CHECKOV_EVALUATE_VARIABLES:-true}" = "true" ] && echo "true" || echo "false")
EOF

# Add external modules path if specified
if [ -n "$CHECKOV_EXTERNAL_MODULES_PATH" ]; then
    echo "external-modules-download-path: $CHECKOV_EXTERNAL_MODULES_PATH" >> "$CHECKOV_CONFIG_FILE"
fi

# Add specific checks if specified
if [ -n "$CHECKOV_CHECKS" ]; then
    echo "check:" >> "$CHECKOV_CONFIG_FILE"
    IFS=',' read -ra CHECKS <<< "$CHECKOV_CHECKS"
    for check in "${CHECKS[@]}"; do
        echo "  - $check" >> "$CHECKOV_CONFIG_FILE"
    done
fi

# Add skip checks if specified
if [ -n "$CHECKOV_SKIP_CHECKS" ]; then
    echo "skip-check:" >> "$CHECKOV_CONFIG_FILE"
    IFS=',' read -ra SKIP_CHECKS <<< "$CHECKOV_SKIP_CHECKS"
    for check in "${SKIP_CHECKS[@]}"; do
        echo "  - $check" >> "$CHECKOV_CONFIG_FILE"
    done
fi

# Note: severity is not a valid YAML config option
# Severity filtering is handled via --check or --skip-check with severity values (LOW, MEDIUM, HIGH, CRITICAL)
# This is already handled in the CLI args above

# Add skip paths if specified
if [ -n "$CHECKOV_SKIP_PATHS" ]; then
    echo "skip-path:" >> "$CHECKOV_CONFIG_FILE"
    IFS=',' read -ra PATHS <<< "$CHECKOV_SKIP_PATHS"
    for path in "${PATHS[@]}"; do
        echo "  - \"**/$path/**\"" >> "$CHECKOV_CONFIG_FILE"
    done
fi

# Add external checks directory if specified
if [ -n "$CHECKOV_EXTERNAL_CHECKS_DIR" ] && [ -d "$CHECKOV_EXTERNAL_CHECKS_DIR" ]; then
    echo "external-checks-dir:" >> "$CHECKOV_CONFIG_FILE"
    echo "  - $CHECKOV_EXTERNAL_CHECKS_DIR" >> "$CHECKOV_CONFIG_FILE"
fi

echo -e "${BLUE}Generated Checkov configuration:${NC}"
cat "$CHECKOV_CONFIG_FILE" | sed 's/^/  /'

echo -e "${BLUE}Checkov command: checkov $CHECKOV_ARGS${NC}"

# Run Checkov based on scan mode
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
TOTAL_CHECKS=0

CHECKOV_RAW_OUTPUT=$(mktemp)
CHECKOV_FILTERED_OUTPUT=$(mktemp)

# Use the dynamically generated config file
CONFIG_FILE="--config-file $CHECKOV_CONFIG_FILE"
echo -e "${BLUE}Using generated config: $CHECKOV_CONFIG_FILE${NC}"

if [ "$SCAN_MODE" = "plan" ]; then
    # Scan Terraform plan JSON file
    echo -e "${BLUE}Scanning Terraform plan file: $TERRAFORM_PLAN_FILE${NC}"
    
    if checkov --file "$TERRAFORM_PLAN_FILE" $CHECKOV_ARGS $CONFIG_FILE > "$CHECKOV_RAW_OUTPUT" 2>/dev/null; then
        echo -e "${GREEN}✓ Checkov scan completed for plan file${NC}"
    else
        echo -e "${RED}✗ Checkov scan failed for plan file${NC}"
        # Create empty result with error
        echo '{"results": {"passed_checks": [], "failed_checks": [], "skipped_checks": []}, "summary": {"passed_checks": 0, "failed_checks": 0, "skipped_checks": 0, "total_checks": 0}, "error": "Checkov scan failed"}' > "$CHECKOV_RAW_OUTPUT"
    fi
else
    # Scan Terraform directories
    echo -e "${BLUE}Scanning Terraform directories${NC}"
    
    # Combine all directories into one scan
    if checkov --directory "$TEMP_DIR" $CHECKOV_ARGS $CONFIG_FILE > "$CHECKOV_RAW_OUTPUT" 2>/dev/null; then
        echo -e "${GREEN}✓ Checkov scan completed${NC}"
    else
        echo -e "${RED}✗ Checkov scan failed${NC}"
        # Create empty result with error
        echo '{"results": {"passed_checks": [], "failed_checks": [], "skipped_checks": []}, "summary": {"passed_checks": 0, "failed_checks": 0, "skipped_checks": 0, "total_checks": 0}, "error": "Checkov scan failed"}' > "$CHECKOV_RAW_OUTPUT"
    fi
fi

# Combine skip resources from defaults and .env configuration
SKIP_RESOURCES_LIST=""

# 1) Load default skip resources (non-production resources to usually skip)
DEFAULT_SKIP_RESOURCES_FILE="fetchers/checkov/skip-resources.default.txt"
if [ -f "$DEFAULT_SKIP_RESOURCES_FILE" ]; then
    while IFS= read -r resource || [ -n "$resource" ]; do
        [[ -z "$resource" || "$resource" =~ ^[[:space:]]*# ]] && continue
        if [ -z "$SKIP_RESOURCES_LIST" ]; then
            SKIP_RESOURCES_LIST="$resource"
        else
            SKIP_RESOURCES_LIST="$SKIP_RESOURCES_LIST,$resource"
        fi
    done < "$DEFAULT_SKIP_RESOURCES_FILE"
    echo -e "${BLUE}Loaded default skip resources from: $DEFAULT_SKIP_RESOURCES_FILE${NC}"
fi

# 2) Add user-specified skip resources from .env (comma-separated)
if [ -n "$CHECKOV_SKIP_RESOURCES" ]; then
    if [ -z "$SKIP_RESOURCES_LIST" ]; then
        SKIP_RESOURCES_LIST="$CHECKOV_SKIP_RESOURCES"
    else
        SKIP_RESOURCES_LIST="$SKIP_RESOURCES_LIST,$CHECKOV_SKIP_RESOURCES"
    fi
    echo -e "${BLUE}Added skip resources from .env: $CHECKOV_SKIP_RESOURCES${NC}"
fi

# Filter out resources if skip-resources are specified
if [ -n "$SKIP_RESOURCES_LIST" ]; then
    # Convert comma-separated list to JSON array and convert * to regex .*
    SKIP_RESOURCES_JSON=$(mktemp)
    echo "$SKIP_RESOURCES_LIST" | tr ',' '\n' | sed 's/\*/.*/g' | jq -R . | jq -s . > "$SKIP_RESOURCES_JSON"
    
    # Filter failed checks based on resource patterns
    jq --slurpfile patterns "$SKIP_RESOURCES_JSON" '
        .results.failed_checks |= map(
            . as $check |
            ($check.resource // "") as $resource |
            if $resource == "" then $check
            else
                # Check if resource matches any skip pattern
                if any($patterns[0][]; $resource | test(.)) then
                    empty  # Skip this check
                else
                    $check  # Keep this check
                end
            end
        )
    ' "$CHECKOV_RAW_OUTPUT" > "$CHECKOV_FILTERED_OUTPUT"
    
    # Recalculate summary after filtering
    jq --argjson passed "$(jq '.results.passed_checks | length' "$CHECKOV_FILTERED_OUTPUT")" \
       --argjson failed "$(jq '.results.failed_checks | length' "$CHECKOV_FILTERED_OUTPUT")" \
       --argjson skipped "$(jq '.results.skipped_checks | length' "$CHECKOV_FILTERED_OUTPUT")" '
        .summary.passed_checks = $passed |
        .summary.failed_checks = $failed |
        .summary.skipped_checks = $skipped |
        .summary.total_checks = ($passed + $failed + $skipped)
    ' "$CHECKOV_FILTERED_OUTPUT" > "${CHECKOV_FILTERED_OUTPUT}.tmp" && mv "${CHECKOV_FILTERED_OUTPUT}.tmp" "$CHECKOV_FILTERED_OUTPUT"
    
    cp "$CHECKOV_FILTERED_OUTPUT" "$CHECKOV_RAW_OUTPUT"
    rm -f "$SKIP_RESOURCES_JSON"
    echo -e "${BLUE}Filtered resources using patterns: $SKIP_RESOURCES_LIST${NC}"
else
    cp "$CHECKOV_RAW_OUTPUT" "$CHECKOV_FILTERED_OUTPUT"
fi

# Parse Checkov JSON output
if [ -s "$CHECKOV_FILTERED_OUTPUT" ]; then
    # Extract summary statistics
    TOTAL_PASSED=$(jq -r '.summary.passed_checks // (.results.passed_checks | length) // 0' "$CHECKOV_FILTERED_OUTPUT")
    TOTAL_FAILED=$(jq -r '.summary.failed_checks // (.results.failed_checks | length) // 0' "$CHECKOV_FILTERED_OUTPUT")
    TOTAL_SKIPPED=$(jq -r '.summary.skipped_checks // (.results.skipped_checks | length) // 0' "$CHECKOV_FILTERED_OUTPUT")
    TOTAL_CHECKS=$(jq -r '.summary.total_checks // (([.results.passed_checks, .results.failed_checks, .results.skipped_checks] | map(length) | add) // 0) // 0' "$CHECKOV_FILTERED_OUTPUT")
    
    # Copy filtered results to main output
    cp "$CHECKOV_FILTERED_OUTPUT" "$OUTPUT_JSON"
    
    # Add metadata to output
    jq --arg timestamp "$TIMESTAMP" \
       --arg source "$GITLAB_URL/$GITLAB_PROJECT_ID" \
       --arg scan_mode "$SCAN_MODE" \
       '. + {
           framework: "terraform",
           scan_timestamp: $timestamp,
           source_type: "gitlab",
           source: $source,
           scan_mode: $scan_mode
       }' "$OUTPUT_JSON" > "${OUTPUT_JSON}.tmp" && mv "${OUTPUT_JSON}.tmp" "$OUTPUT_JSON"
fi

rm -f "$CHECKOV_RAW_OUTPUT" "$CHECKOV_FILTERED_OUTPUT"

# Update summary with totals
jq --argjson passed "$TOTAL_PASSED" --argjson failed "$TOTAL_FAILED" --argjson skipped "$TOTAL_SKIPPED" --argjson total "$TOTAL_CHECKS" '
    .summary.passed_checks = $passed |
    .summary.failed_checks = $failed |
    .summary.skipped_checks = $skipped |
    .summary.total_checks = $total |
    .summary.aggregate_percentage = (if $total > 0 then ($passed / $total) * 100 else 0 end)
' "$OUTPUT_JSON" > "${OUTPUT_JSON}.tmp" && mv "${OUTPUT_JSON}.tmp" "$OUTPUT_JSON"

# Clean up
rm -rf "$TEMP_DIR"

# Display summary
echo -e "${BLUE}========== SCAN SUMMARY ==========${NC}"
echo -e "Total Checks: ${TOTAL_CHECKS}"
echo -e "Passed: ${GREEN}${TOTAL_PASSED}${NC}"
echo -e "Failed: ${RED}${TOTAL_FAILED}${NC}"
echo -e "Skipped: ${YELLOW}${TOTAL_SKIPPED}${NC}"
echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"

exit 0
