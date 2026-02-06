#!/bin/bash
# Helper script for Module-Based Training Completion Evidence
#
# Purpose:
# This script generates evidence of security training completion in KnowBe4
# by summarizing training results at the individual module level. It is
# designed for scenarios where relevant training does not map cleanly to a
# single campaign (for example, incident response or disaster recovery training
# delivered as part of broader campaigns).
#
# Scope:
# - Evaluates all active training enrollments returned by the KnowBe4 API.
# - Does NOT rely on campaign names, group membership, or role assignments.
# - Aggregates results by training module name.
# - Calculates per-module assignment counts, completion counts, and completion rates.
#
# Completion Logic:
# - "Assigned" is defined as the total number of enrollments for a module.
# - "Passed" is defined as enrollments with status == "Passed".
# - Completion rate is calculated as:
#     floor((passed / assigned) * 100)
#   This ensures completion percentages are never overstated.
#
# Data Sources:
# - KnowBe4 Training Enrollments API
#
# Output:
# - Generates a unique JSON file containing:
#   - A normalized list of training enrollments
#   - A per-module training summary including:
#       - assigned
#       - passed
#       - completion_rate
#
# Intended Use Cases:
# - Incident Response training validation
# - Disaster Recovery training validation
# - Role-specific training delivered through mixed or shared campaigns
# - Audit and compliance evidence where module-level proof is required
#
# Note: KnowBe4 API Requirements
# Source:
# https://help.sumologic.com/docs/send-data/hosted-collectors/cloud-to-cloud-integration-framework/knowbe4-api-source/
#
# KnowBe4 APIs are only available to Platinum and Diamond customers.
#
# Prerequisites:
# - KNOWBE4_API_KEY must be set as an environment variable
# - KNOWBE4_REGION must be set as an environment variable
#
# Region:
# The region where your KnowBe4 account is hosted. To determine your region:
# 1. Sign in to the KnowBe4 console
# 2. Inspect the region in the browser URL
# 3. Supported values include:
#    - US
#    - EU
#    - CA
#    - UK
#    - DE
#
# API Token:
# The KnowBe4 Reporting API token is required.
# To obtain it:
# 1. Sign in as a KnowBe4 Admin
# 2. Navigate to Account Settings → Account Integrations → API
# 3. Enable Reporting API Access
# 4. Copy and securely store the API token
#
# High-Level Workflow:
# 1. Retrieve all training enrollments from KnowBe4
# 2. Normalize enrollment data for reporting
# 3. Group enrollments by module name
# 4. Calculate per-module assignment and completion metrics
# 5. Output results as structured JSON
#
# Usage:
# ./module_based_summary.sh <profile> <region> <output_dir> <csv_file>

# Required parameters
if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <profile> <region> <output_dir> <csv_file>"
    exit 1
fi

OUTPUT_DIR="$3"

# Component identifier
COMPONENT="module_based_summary"
UNIQUE_JSON="$OUTPUT_DIR/$COMPONENT.json"

# Developers Training campaign (exact name)
DEVELOPER_CAMPAIGNS=(
  "Developers Training"
)

# ANSI color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Initialize output JSON
echo '{
  "results": {
    "enrollments": [],
    "summary": {
      "training_module_summary": {}
    }
  }
}' > "$UNIQUE_JSON"

# Validate env vars
if [ -z "$KNOWBE4_API_KEY" ] || [ -z "$KNOWBE4_REGION" ]; then
    echo -e "${RED}Error: KNOWBE4_API_KEY or KNOWBE4_REGION not set${NC}" >&2
    exit 1
fi

# Function to make API calls
make_api_call() {
    local endpoint=$1
    local url="https://${KNOWBE4_REGION}.api.knowbe4.com/v1/${endpoint}"
    local response
    response=$(curl -s -H "Authorization: Bearer ${KNOWBE4_API_KEY}" -H "Content-Type: application/json" "${url}")
    # Check if response is valid JSON
    if ! echo "$response" | jq . >/dev/null 2>&1; then
        echo "{}"
        return 1
    fi
    # Check for 404 status
    if echo "$response" | jq -e '.status == 404' >/dev/null 2>&1; then
        echo "{}"
        return 1
    fi

    echo "$response"
    return 0
}

# Pagination helper
make_paginated_api_call() {
    local endpoint="$1"
    local page=1
    local all_results="[]"
    local separator

    if [[ "$endpoint" == *\?* ]]; then
        separator="&"
    else
        separator="?"
    fi

    while true; do
        response=$(make_api_call "${endpoint}${separator}page=${page}")

        count=$(echo "$response" | jq 'length')
        if [ "$count" -eq 0 ]; then
            break
        fi

        all_results=$(jq -s '.[0] + .[1]' \
            <(echo "$all_results") <(echo "$response"))

        page=$((page + 1))
    done

    echo "$all_results"
}

# Fetch all training enrollments
echo -e "${BLUE}Fetching training enrollments...${NC}"
enrollments_response=$(make_paginated_api_call "training/enrollments?exclude_archived_users=true&include_campaign_id=true")
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to fetch enrollments${NC}" >&2
    exit 1
fi

# Store enrollments (remove noisy fields)
echo "$enrollments_response" | jq -c '.[] | del(.policy_acknowledged)' | while read -r enrollment; do
    jq --argjson e "$enrollment" \
      '.results.enrollments += [$e]' \
      "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
done

# Build per-module training summary
module_summary=$(jq '
    .results.enrollments
    | sort_by(.module_name)
    | group_by(.module_name)
    | map(
        . as $group
        | {
            module: $group[0].module_name,
            assigned: ($group | length),
            passed: ($group | map(select(.status == "Passed")) | length),
            completion_rate:
            (if ($group | length) > 0
            then (
                (($group | map(select(.status == "Passed")) | length) * 100.0
                / ($group | length)
                ) | floor
            )
            else 0
            end)
        }
    )
    | map({
        (.module): {
        assigned: .assigned,
        passed: .passed,
        completion_rate: .completion_rate
        }
    })
    | add
' "$UNIQUE_JSON")

# Store module summary
jq --argjson module_summary "$module_summary" \
  '.results.summary.training_module_summary = $module_summary' \
  "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"

# Output summary
echo -e "\n${GREEN}Module-Based Training Summary:${NC}"
echo "$module_summary" | jq .

exit 0
