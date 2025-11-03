#!/bin/bash
# Checkov Kubernetes Security Evidence Fetcher
# Flexible fetcher that supports multiple source types and configurations
# Scans Kubernetes manifest files for security compliance evidence

# Usage: ./checkov_kubernetes.sh <profile> <region> <output_dir> <output_csv>
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
COMPONENT="checkov_kubernetes"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========== CHECKOV KUBERNETES SECURITY SCAN ==========${NC}"

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
    # Use GitLab API to download only Kubernetes manifest files (faster, less storage)
    echo -e "${BLUE}Downloading Kubernetes manifest files from GitLab repository via API (branch: $BRANCH)${NC}"
    
    API_ENDPOINT="${GITLAB_URL%/}/api/v4"
    ENCODED_PROJECT=$(echo "$GITLAB_PROJECT_ID" | sed 's/\//%2F/g')
    ENCODED_BRANCH=$(echo "$BRANCH" | sed 's/\//%2F/g')
    
    # Get repository tree to find Kubernetes manifest files
    TREE_URL="${API_ENDPOINT}/projects/${ENCODED_PROJECT}/repository/tree"
    HEADERS="PRIVATE-TOKEN: ${GITLAB_API_TOKEN}"
    
    # Fetch repository tree recursively
    TREE_JSON=$(curl -s -H "$HEADERS" "${TREE_URL}?recursive=true&per_page=100&ref=${ENCODED_BRANCH}" 2>/dev/null)
    
    if [ -z "$TREE_JSON" ] || echo "$TREE_JSON" | grep -q "error\|404\|401"; then
        echo -e "${YELLOW}Warning:${NC} Failed to access GitLab repository tree via API, falling back to clone${NC}" >&2
        CHECKOV_CLONE_REPO="true"
    else
        # Find all Kubernetes manifest files (.yaml, .yml) - prioritize k8s-related files
        K8S_FILES=$(echo "$TREE_JSON" | jq -r '.[] | select(.type == "blob") | select(.path | endswith(".yaml") or endswith(".yml")) | .path' 2>/dev/null | head -20)
        
        if [ -z "$K8S_FILES" ]; then
            echo -e "${YELLOW}Warning:${NC} No Kubernetes manifest files found in repository" >&2
            # Create empty result
            echo '{"framework": "kubernetes", "scan_timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "summary": {"passed_checks": 0, "failed_checks": 0, "skipped_checks": 0, "total_checks": 0}, "results": [], "error": "No Kubernetes manifest files found"}' > "$OUTPUT_JSON"
            rm -rf "$TEMP_DIR"
            exit 0
        fi
        
        # Download each Kubernetes manifest file while preserving directory structure
        echo "$K8S_FILES" | while IFS= read -r file_path; do
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

echo -e "${BLUE}Found Kubernetes manifest files:${NC}"
find "$TEMP_DIR" -name "*.yaml" -o -name "*.yml" | sed 's|^'"$TEMP_DIR"'/||' | sed 's/^/  /'

# Initialize JSON output with metadata
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SOURCE_INFO=""
case "$SOURCE_TYPE" in
    "gitlab") SOURCE_INFO="$GITLAB_URL/$GITLAB_PROJECT_ID" ;;
    "github") SOURCE_INFO="$GITHUB_URL/$GITHUB_REPO" ;;
    "local") SOURCE_INFO="$CHECKOV_LOCAL_PATH" ;;
    "url") SOURCE_INFO="$CHECKOV_SOURCE_URL" ;;
esac

echo "{
  \"framework\": \"kubernetes\",
  \"scan_timestamp\": \"$TIMESTAMP\",
  \"source_type\": \"$SOURCE_TYPE\",
  \"source\": \"$SOURCE_INFO\",
  \"summary\": {
    \"passed_checks\": 0,
    \"failed_checks\": 0,
    \"skipped_checks\": 0,
    \"total_checks\": 0
  },
  \"results\": []
}" > "$OUTPUT_JSON"

# Build flexible Checkov command arguments
CHECKOV_ARGS="--framework kubernetes --output json --quiet"

# Add repository identification
REPO_ID="${CHECKOV_REPO_ID:-evidence-fetchers-kubernetes}"
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

# Add specific checks to run (if specified)
if [ -n "$CHECKOV_CHECKS" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --check $CHECKOV_CHECKS"
    echo -e "${BLUE}Running specific checks: $CHECKOV_CHECKS${NC}"
fi

# Add checks to skip (if specified)
if [ -n "$CHECKOV_SKIP_CHECKS" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --skip-check $CHECKOV_SKIP_CHECKS"
    echo -e "${BLUE}Skipping checks: $CHECKOV_SKIP_CHECKS${NC}"
fi

# Add severity filtering (if specified)
# Note: --severity is not a valid Checkov flag. Use --check or --skip-check with severity values instead
# Example: --skip-check LOW,MEDIUM or --check HIGH,CRITICAL
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

# Add skip paths (if specified)
if [ -n "$CHECKOV_SKIP_PATHS" ]; then
    for path in $(echo "$CHECKOV_SKIP_PATHS" | tr ',' ' '); do
        CHECKOV_ARGS="$CHECKOV_ARGS --skip-path $path"
    done
    echo -e "${BLUE}Skipping paths: $CHECKOV_SKIP_PATHS${NC}"
fi

# Generate dynamic Checkov YAML configuration based on environment variables
CHECKOV_CONFIG_FILE="$TEMP_DIR/.checkov.yaml"
echo -e "${BLUE}Generating dynamic Checkov configuration: $CHECKOV_CONFIG_FILE${NC}"

cat > "$CHECKOV_CONFIG_FILE" << EOF
# Dynamically generated Checkov configuration
# Generated from environment variables

framework:
  - kubernetes

output: json
repo-id: $REPO_ID
branch: $BRANCH
soft-fail: $([ "${CHECKOV_SOFT_FAIL:-true}" = "true" ] && echo "true" || echo "false")
compact: $([ "${CHECKOV_COMPACT:-true}" = "true" ] && echo "true" || echo "false")
quiet: true
EOF

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

# Add severity filter if specified
if [ -n "$CHECKOV_SEVERITY" ]; then
    echo "severity: $CHECKOV_SEVERITY" >> "$CHECKOV_CONFIG_FILE"
fi

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

# Run Checkov on Kubernetes manifests
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
TOTAL_CHECKS=0

echo -e "${BLUE}Scanning Kubernetes manifests${NC}"

# Use the dynamically generated config file
CONFIG_FILE="--config-file $CHECKOV_CONFIG_FILE"
echo -e "${BLUE}Using generated config: $CHECKOV_CONFIG_FILE${NC}"

# Run Checkov with flexible arguments
CHECKOV_OUTPUT=$(mktemp)
if checkov --directory "$TEMP_DIR" $CHECKOV_ARGS $CONFIG_FILE > "$CHECKOV_OUTPUT" 2>/dev/null; then
    echo -e "${GREEN}✓ Checkov Kubernetes scan completed${NC}"
    
    # Parse Checkov JSON output
    if [ -s "$CHECKOV_OUTPUT" ]; then
        # Extract summary statistics
        PASSED=$(jq -r '.summary.passed_checks // 0' "$CHECKOV_OUTPUT")
        FAILED=$(jq -r '.summary.failed_checks // 0' "$CHECKOV_OUTPUT")
        SKIPPED=$(jq -r '.summary.skipped_checks // 0' "$CHECKOV_OUTPUT")
        CHECKS=$(jq -r '.summary.total_checks // 0' "$CHECKOV_OUTPUT")
        
        TOTAL_PASSED=$PASSED
        TOTAL_FAILED=$FAILED
        TOTAL_SKIPPED=$SKIPPED
        TOTAL_CHECKS=$CHECKS
        
        # Copy results to main JSON
        cp "$CHECKOV_OUTPUT" "$OUTPUT_JSON"
    fi
else
    echo -e "${RED}✗ Checkov Kubernetes scan failed${NC}"
    # Add error result
    ERROR_RESULT=$(jq -n --arg error "Checkov Kubernetes scan failed" '{
        "error": $error,
        "status": "ERROR"
    }')
    jq --argjson error_result "$ERROR_RESULT" '.results += [$error_result]' "$OUTPUT_JSON" > "${OUTPUT_JSON}.tmp" && mv "${OUTPUT_JSON}.tmp" "$OUTPUT_JSON"
fi

rm -f "$CHECKOV_OUTPUT"

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
