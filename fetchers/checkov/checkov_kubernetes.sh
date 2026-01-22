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

# Component identifier - include GitLab project ID to avoid overwriting
COMPONENT="checkov_kubernetes"
# Sanitize project ID for filename (replace / with _)
PROJECT_ID_SANITIZED=$(echo "${GITLAB_PROJECT_ID:-unknown}" | sed 's/\//_/g' | sed 's/[^a-zA-Z0-9_-]/_/g')
OUTPUT_JSON="$OUTPUT_DIR/${COMPONENT}_${PROJECT_ID_SANITIZED}.json"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

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

# Get project metadata
PROJECT_NAME=$(echo "$GITLAB_PROJECT_ID" | sed 's|.*/||')
PROJECT_GROUP=$(echo "$GITLAB_PROJECT_ID" | sed 's|/.*||')

echo "{
  \"metadata\": {
    \"project_id\": \"${GITLAB_PROJECT_ID:-unknown}\",
    \"project_name\": \"${PROJECT_NAME:-unknown}\",
    \"project_group\": \"${PROJECT_GROUP:-unknown}\",
    \"gitlab_url\": \"${GITLAB_URL:-unknown}\",
    \"branch\": \"${GITLAB_BRANCH:-main}\",
    \"scan_timestamp\": \"$TIMESTAMP\"
  },
  \"framework\": \"kubernetes\",
  \"scan_timestamp\": \"$TIMESTAMP\",
  \"source_type\": \"$SOURCE_TYPE\",
  \"source\": \"$SOURCE_INFO\",
  \"summary\": {
    \"passed_checks\": 0,
    \"failed_checks\": 0,
    \"skipped_checks\": 0,
    \"total_checks\": 0,
    \"passed_percentage\": 0
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

# Note: We'll add specific checks to the config file instead of CLI args
# This allows us to filter out skipped checks properly
# Store the requested checks for later use in config file generation
if [ -n "$CHECKOV_K8S_CHECKS" ]; then
    REQUESTED_CHECKS_FOR_CONFIG="$CHECKOV_K8S_CHECKS"
    echo -e "${BLUE}Will run specific Kubernetes checks: $CHECKOV_K8S_CHECKS${NC}"
elif [ -n "$CHECKOV_CHECKS" ]; then
    # Fallback: Filter CHECKOV_CHECKS to only include Kubernetes-related checks
    K8S_CHECKS=""
    IFS=',' read -ra ALL_CHECKS <<< "$CHECKOV_CHECKS"
    for check in "${ALL_CHECKS[@]}"; do
        check=$(echo "$check" | xargs)  # Trim whitespace
        if [[ "$check" =~ ^CKV_K8S_ ]] || [[ "$check" =~ ^CKV2_K8S_ ]]; then
            if [ -z "$K8S_CHECKS" ]; then
                K8S_CHECKS="$check"
            else
                K8S_CHECKS="$K8S_CHECKS,$check"
            fi
        fi
    done
    REQUESTED_CHECKS_FOR_CONFIG="$K8S_CHECKS"
    if [ -n "$K8S_CHECKS" ]; then
        echo -e "${BLUE}Will run filtered Kubernetes checks: $K8S_CHECKS${NC}"
    fi
fi

# Combine skip checks from defaults and .env configuration
# But exclude any checks that are explicitly requested via CHECKOV_K8S_CHECKS
SKIP_CHECKS_LIST=""
REQUESTED_CHECKS=""

# Get list of requested checks to exclude from skip list
if [ -n "$CHECKOV_K8S_CHECKS" ]; then
    REQUESTED_CHECKS="$CHECKOV_K8S_CHECKS"
elif [ -n "$CHECKOV_CHECKS" ]; then
    # Extract Kubernetes checks from CHECKOV_CHECKS
    K8S_CHECKS=""
    IFS=',' read -ra ALL_CHECKS <<< "$CHECKOV_CHECKS"
    for check in "${ALL_CHECKS[@]}"; do
        check=$(echo "$check" | xargs)  # Trim whitespace
        if [[ "$check" =~ ^CKV_K8S_ ]] || [[ "$check" =~ ^CKV2_K8S_ ]]; then
            if [ -z "$K8S_CHECKS" ]; then
                K8S_CHECKS="$check"
            else
                K8S_CHECKS="$K8S_CHECKS,$check"
            fi
        fi
    done
    REQUESTED_CHECKS="$K8S_CHECKS"
fi

# 1) Load default skip checks for Kubernetes (if file exists)
# Skip list takes priority - if a check is in skip list, it will be skipped even if explicitly requested
DEFAULT_SKIP_CHECKS_FILE="fetchers/checkov/skip-checks-k8s.default.txt"
if [ -f "$DEFAULT_SKIP_CHECKS_FILE" ]; then
    while IFS= read -r check || [ -n "$check" ]; do
        [[ -z "$check" || "$check" =~ ^[[:space:]]*# ]] && continue
        # Add to skip list (skip list takes priority over requested checks)
        if [ -z "$SKIP_CHECKS_LIST" ]; then
            SKIP_CHECKS_LIST="$check"
        else
            SKIP_CHECKS_LIST="$SKIP_CHECKS_LIST,$check"
        fi
    done < "$DEFAULT_SKIP_CHECKS_FILE"
    echo -e "${BLUE}Loaded default K8S skip checks from: $DEFAULT_SKIP_CHECKS_FILE${NC}"
fi

# 2) Add user-specified skip checks from .env (comma-separated)
# Skip list takes priority - if a check is in skip list, it will be skipped even if explicitly requested
if [ -n "$CHECKOV_SKIP_CHECKS" ]; then
    IFS=',' read -ra USER_SKIP_CHECKS <<< "$CHECKOV_SKIP_CHECKS"
    for check in "${USER_SKIP_CHECKS[@]}"; do
        check=$(echo "$check" | xargs)  # Trim whitespace
        # Only add K8S checks to skip list
        if [[ "$check" =~ ^CKV_K8S_ ]] || [[ "$check" =~ ^CKV2_K8S_ ]]; then
            if [ -z "$SKIP_CHECKS_LIST" ]; then
                SKIP_CHECKS_LIST="$check"
            else
                SKIP_CHECKS_LIST="$SKIP_CHECKS_LIST,$check"
            fi
        fi
    done
    echo -e "${BLUE}Added skip checks from .env: $CHECKOV_SKIP_CHECKS${NC}"
fi

# Add all skip checks to Checkov arguments
if [ -n "$SKIP_CHECKS_LIST" ]; then
    CHECKOV_ARGS="$CHECKOV_ARGS --skip-check $SKIP_CHECKS_LIST"
    echo -e "${BLUE}Skipping K8S checks: $SKIP_CHECKS_LIST${NC}"
fi

# Add severity filtering (if specified)
# Note: Checkov doesn't support direct severity filtering via CLI flags
# Severity filtering requires using the Prisma Cloud API or filtering results post-scan
# This option is ignored to prevent Checkov failures
if [ -n "$CHECKOV_SEVERITY" ]; then
    echo -e "${YELLOW}Warning:${NC} CHECKOV_SEVERITY is set but Checkov CLI doesn't support direct severity filtering. This option is ignored.${NC}"
    echo -e "${YELLOW}Note:${NC} To filter by severity, use CHECKOV_CHECKS to specify specific check IDs or use Prisma Cloud API.${NC}"
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
# Use CHECKOV_K8S_CHECKS if set, otherwise fall back to filtering CHECKOV_CHECKS
# Filter out any checks that are in the skip list
if [ -n "$REQUESTED_CHECKS_FOR_CONFIG" ]; then
    # Use the stored requested checks
    CHECKOV_K8S_CHECKS="$REQUESTED_CHECKS_FOR_CONFIG"
fi

if [ -n "$CHECKOV_K8S_CHECKS" ]; then
    # Track if we have any checks to add
    CHECKS_ADDED=0
    IFS=',' read -ra CHECKS <<< "$CHECKOV_K8S_CHECKS"
    for check in "${CHECKS[@]}"; do
        check=$(echo "$check" | xargs)  # Trim whitespace
        # Skip this check if it's in the skip list
        if [ -n "$SKIP_CHECKS_LIST" ] && [[ ",$SKIP_CHECKS_LIST," =~ ,$check, ]]; then
            continue  # Don't add checks that are in the skip list
        fi
        # Add check: section header only on first check
        if [ $CHECKS_ADDED -eq 0 ]; then
            echo "check:" >> "$CHECKOV_CONFIG_FILE"
        fi
        echo "  - $check" >> "$CHECKOV_CONFIG_FILE"
        CHECKS_ADDED=$((CHECKS_ADDED + 1))
    done
    # If all checks were filtered out, don't add check: section (let Checkov run all checks)
    if [ $CHECKS_ADDED -eq 0 ]; then
        echo -e "${YELLOW}Warning:${NC} All checks in CHECKOV_K8S_CHECKS are in the skip list. Running all Kubernetes checks instead.${NC}"
    fi
elif [ -n "$CHECKOV_CHECKS" ]; then
    # Fallback: Filter CHECKOV_CHECKS to only include Kubernetes-related checks
    K8S_CHECKS=""
    IFS=',' read -ra ALL_CHECKS <<< "$CHECKOV_CHECKS"
    for check in "${ALL_CHECKS[@]}"; do
        check=$(echo "$check" | xargs)  # Trim whitespace
        if [[ "$check" =~ ^CKV_K8S_ ]] || [[ "$check" =~ ^CKV2_K8S_ ]]; then
            if [ -z "$K8S_CHECKS" ]; then
                K8S_CHECKS="$check"
            else
                K8S_CHECKS="$K8S_CHECKS,$check"
            fi
        fi
    done
    
    if [ -n "$K8S_CHECKS" ]; then
        # Track if we have any checks to add
        CHECKS_ADDED=0
        IFS=',' read -ra CHECKS <<< "$K8S_CHECKS"
        for check in "${CHECKS[@]}"; do
            check=$(echo "$check" | xargs)  # Trim whitespace
            # Skip this check if it's in the skip list
            if [ -n "$SKIP_CHECKS_LIST" ] && [[ ",$SKIP_CHECKS_LIST," =~ ,$check, ]]; then
                continue  # Don't add checks that are in the skip list
            fi
            # Add check: section header only on first check
            if [ $CHECKS_ADDED -eq 0 ]; then
                echo "check:" >> "$CHECKOV_CONFIG_FILE"
            fi
            echo "  - $check" >> "$CHECKOV_CONFIG_FILE"
            CHECKS_ADDED=$((CHECKS_ADDED + 1))
        done
        # If all checks were filtered out, don't add check: section (let Checkov run all checks)
        if [ $CHECKS_ADDED -eq 0 ]; then
            echo -e "${YELLOW}Warning:${NC} All filtered Kubernetes checks are in the skip list. Running all Kubernetes checks instead.${NC}"
        fi
    fi
fi

# Add skip checks if specified (use the same SKIP_CHECKS_LIST from above)
if [ -n "$SKIP_CHECKS_LIST" ]; then
    echo "skip-check:" >> "$CHECKOV_CONFIG_FILE"
    IFS=',' read -ra SKIP_CHECKS <<< "$SKIP_CHECKS_LIST"
    for check in "${SKIP_CHECKS[@]}"; do
        echo "  - $check" >> "$CHECKOV_CONFIG_FILE"
    done
elif [ -n "$CHECKOV_SKIP_CHECKS" ]; then
    # Fallback to CHECKOV_SKIP_CHECKS if SKIP_CHECKS_LIST wasn't built
    echo "skip-check:" >> "$CHECKOV_CONFIG_FILE"
    IFS=',' read -ra SKIP_CHECKS <<< "$CHECKOV_SKIP_CHECKS"
    for check in "${SKIP_CHECKS[@]}"; do
        # Only add K8S checks
        if [[ "$check" =~ ^CKV_K8S_ ]] || [[ "$check" =~ ^CKV2_K8S_ ]]; then
            echo "  - $check" >> "$CHECKOV_CONFIG_FILE"
        fi
    done
fi

# Note: Severity filtering is not supported in Checkov YAML config
# This option is ignored to prevent Checkov failures

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
CHECKOV_ERROR=$(mktemp)
# Capture stderr to see actual errors
# Use eval to properly handle arguments with spaces/quotes
CHECKOV_CMD="checkov --directory \"$TEMP_DIR\" $CHECKOV_ARGS $CONFIG_FILE"
if eval "$CHECKOV_CMD" > "$CHECKOV_OUTPUT" 2>"$CHECKOV_ERROR"; then
    echo -e "${GREEN}✓ Checkov Kubernetes scan completed${NC}"
    
    # Parse Checkov JSON output
    if [ -s "$CHECKOV_OUTPUT" ]; then
        # Extract summary statistics - Checkov uses 'passed', 'failed', 'skipped' not 'passed_checks'
        PASSED=$(jq -r '.summary.passed // 0' "$CHECKOV_OUTPUT")
        FAILED=$(jq -r '.summary.failed // 0' "$CHECKOV_OUTPUT")
        SKIPPED=$(jq -r '.summary.skipped // 0' "$CHECKOV_OUTPUT")
        TOTAL_CHECKS=$((PASSED + FAILED + SKIPPED))
        
        TOTAL_PASSED=$PASSED
        TOTAL_FAILED=$FAILED
        TOTAL_SKIPPED=$SKIPPED
        
        # Calculate percentage and update output with correct field names
        if [ $TOTAL_CHECKS -gt 0 ]; then
            PASSED_PERCENTAGE=$(awk "BEGIN {printf \"%.2f\", ($PASSED / $TOTAL_CHECKS) * 100}")
        else
            PASSED_PERCENTAGE=0
        fi
        
        # Merge Checkov output with our metadata and fix summary fields
        # Preserve check_type and results from Checkov output
        jq --argjson passed "$PASSED" \
           --argjson failed "$FAILED" \
           --argjson skipped "$SKIPPED" \
           --argjson total "$TOTAL_CHECKS" \
           --argjson percentage "$PASSED_PERCENTAGE" \
           --arg project_id "${GITLAB_PROJECT_ID:-unknown}" \
           --arg project_name "${PROJECT_NAME:-unknown}" \
           --arg project_group "${PROJECT_GROUP:-unknown}" \
           --arg gitlab_url "${GITLAB_URL:-unknown}" \
           --arg branch "${GITLAB_BRANCH:-main}" \
           --arg timestamp "$TIMESTAMP" \
           --arg source_info "$SOURCE_INFO" \
           --arg source_type "$SOURCE_TYPE" \
           '. + {
               metadata: {
                   project_id: $project_id,
                   project_name: $project_name,
                   project_group: $project_group,
                   gitlab_url: $gitlab_url,
                   branch: $branch,
                   scan_timestamp: $timestamp
               },
               framework: "kubernetes",
               scan_timestamp: $timestamp,
               source_type: $source_type,
               source: $source_info,
               summary: (.summary + {
                   passed_checks: $passed,
                   failed_checks: $failed,
                   skipped_checks: $skipped,
                   total_checks: $total,
                   passed_percentage: $percentage
               })
           } |
           # Preserve check_type if it exists
           if has("check_type") then . else . end' "$CHECKOV_OUTPUT" > "$OUTPUT_JSON"
    fi
else
    echo -e "${RED}✗ Checkov Kubernetes scan failed${NC}"
    # Show the actual error
    if [ -s "$CHECKOV_ERROR" ]; then
        ERROR_MSG=$(cat "$CHECKOV_ERROR" | head -10 | tr '\n' '; ')
        echo -e "${YELLOW}Checkov error:${NC} $ERROR_MSG" >&2
    fi
    # Create error output if file doesn't exist
    if [ ! -f "$OUTPUT_JSON" ]; then
        # Create basic error structure
        jq -n --arg project_id "${GITLAB_PROJECT_ID:-unknown}" \
           --arg project_name "${PROJECT_NAME:-unknown}" \
           --arg project_group "${PROJECT_GROUP:-unknown}" \
           --arg gitlab_url "${GITLAB_URL:-unknown}" \
           --arg branch "${GITLAB_BRANCH:-main}" \
           --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
           '{
               metadata: {
                   project_id: $project_id,
                   project_name: $project_name,
                   project_group: $project_group,
                   gitlab_url: $gitlab_url,
                   branch: $branch,
                   scan_timestamp: $timestamp
               },
               framework: "kubernetes",
               scan_timestamp: $timestamp,
               source_type: "",
               source: "",
               summary: {
                   passed_checks: 0,
                   failed_checks: 0,
                   skipped_checks: 0,
                   total_checks: 0,
                   passed_percentage: 0
               },
               results: [{
                   error: "Checkov Kubernetes scan failed",
                   status: "ERROR"
               }]
           }' > "$OUTPUT_JSON"
    else
        # Add error result to existing file
        ERROR_RESULT=$(jq -n --arg error "Checkov Kubernetes scan failed" '{
            "error": $error,
            "status": "ERROR"
        }')
        jq --argjson error_result "$ERROR_RESULT" '.results += [$error_result]' "$OUTPUT_JSON" > "${OUTPUT_JSON}.tmp" && mv "${OUTPUT_JSON}.tmp" "$OUTPUT_JSON"
    fi
fi

rm -f "$CHECKOV_OUTPUT" "$CHECKOV_ERROR"

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
