#!/bin/bash
# Helper script for Developer-Specific Training Validation
#
# Purpose:
# This script validates completion of developer-specific security training
# campaigns in KnowBe4. It identifies users who belong to developer-related
# groups, checks their enrollment and completion status for the configured
# developer training campaigns, and produces a structured JSON report with
# per-user status and summary metrics.
#
# Scope:
# - Targets users who are members of developer-related groups (e.g. Engineering,
#   Developer, Dev).
# - Evaluates training completion only for explicitly defined developer
#   training campaigns (for example, "Developers Training").
# - Tracks training status as: completed, in_progress, past_due, or not_started.
#
# Data Sources:
# - KnowBe4 Users API
# - KnowBe4 Training Campaigns API
# - KnowBe4 Training Enrollments API
# - KnowBe4 Groups and Group Members APIs
#
# Output:
# - Generates a unique JSON file containing:
#   - Developer users
#   - Developer groups
#   - Developer training campaigns
#   - Training enrollments
#   - Per-user training status
#   - Summary statistics and completion rate
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
# 1. Retrieve all users from KnowBe4
# 2. Retrieve all training campaigns
# 3. Retrieve all training enrollments
# 4. Retrieve all groups and identify developer-related groups
# 5. Resolve developer users from those groups
# 6. Match developer users to developer training enrollments
# 7. Calculate per-user training status and summary metrics
#
# Usage:
#   ./developer_specific_training.sh <profile> <region> <output_dir> <csv_file>

# Required parameters
if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <profile> <region> <output_dir> <csv_file>"
    exit 1
fi

OUTPUT_DIR="$3"

# Component identifier
COMPONENT="developer_specific_training"
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
    "developer_users": [],
    "developer_campaigns": [],
    "enrollments": [],
    "user_training_status": {},
    "developer_groups": [],
    "summary": {
      "total_developer_users": 0,
      "completed_training": 0,
      "in_progress": 0,
      "past_due": 0,
      "not_started": 0,
      "completion_rate": 0,
      "total_campaigns": 0,
      "total_groups": 0
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

# Fetch all users
echo -e "${BLUE}Fetching users from KnowBe4...${NC}"
users_response=$(make_paginated_api_call "users")
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to fetch users${NC}" >&2
    exit 1
fi

# Fetch all training campaigns
echo -e "${BLUE}Fetching training campaigns...${NC}"
campaigns_response=$(make_paginated_api_call "training/campaigns")
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to fetch campaigns${NC}" >&2
    exit 1
fi

# Fetch all training enrollments
echo -e "${BLUE}Fetching training enrollments...${NC}"
enrollments_response=$(make_paginated_api_call "training/enrollments?exclude_archived_users=true&include_campaign_id=true")
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to fetch enrollments${NC}" >&2
    exit 1
fi

# Fetch all groups
echo -e "${BLUE}Fetching groups...${NC}"
groups_response=$(make_paginated_api_call "groups")
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to fetch groups${NC}" >&2
    exit 1
fi

# Store Developers Training campaign
for campaign_name in "${DEVELOPER_CAMPAIGNS[@]}"; do
    echo "$campaigns_response" | jq -c --arg name "$campaign_name" \
      '.[] | select(.name == $name)' | while read -r campaign; do
        jq --argjson campaign "$campaign" \
          '.results.developer_campaigns += [$campaign]' \
          "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
    done
done

# Identify developer groups and users
# Developer-related groups
developer_groups=("Engineering" "Developer" "Developers" "Dev")
developer_users=()

while read -r group_json; do
    group_name=$(echo "$group_json" | jq -r '.name')
    group_id=$(echo "$group_json" | jq -r '.id')
    for group in "${developer_groups[@]}"; do
        if [[ "$group_name" == *"$group"* ]]; then
            group_members=$(make_paginated_api_call "groups/$group_id/members")
            jq --arg name "$group_name" --arg id "$group_id" \
               '.results.developer_groups += [{"name": $name, "id": $id}]' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
            while read -r user_json; do
                user_email=$(echo "$user_json" | jq -r '.email')
                if [[ ! " ${developer_users[@]} " =~ " ${user_email} " ]]; then
                    developer_users+=("$user_email")
                    minimal_user=$(echo "$user_json" | jq '{id: .id, email: .email, status: .status}')
                    jq --argjson user "$minimal_user" '.results.developer_users += [$user]' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
                fi
            done < <(echo "$group_members" | jq -c '.[] | select(.status == "active")')
            break
        fi
    done
done < <(echo "$groups_response" | jq -c '.[]')

# Process developer users
for email in "${developer_users[@]}"; do
    user=$(echo "$users_response" | jq -c --arg email "$email" '.[] | select(.email == $email)')
    user_id=$(echo "$user" | jq -r '.id')

    # Get user's enrollments for role-specific campaigns
    campaign_filter=$(printf ' or .campaign_name == "%s"' "${DEVELOPER_CAMPAIGNS[@]}")
    campaign_filter=${campaign_filter# or }

    user_enrollments=$(echo "$enrollments_response" | jq -c \
    --arg user_id "$user_id" \
    ".[] | select(
        .user.id == (\$user_id|tonumber)
        and ( $campaign_filter )
    )" | jq -s '.')

    # Determine user's training status
    user_status="not_started"
    if [ "$user_enrollments" != "[]" ]; then
        # Add enrollments to the results, removing policy_acknowledged
        echo "$user_enrollments" | jq -c '.[] | del(.policy_acknowledged)' | while read -r e; do
            jq --argjson enrollment "$e" \
              '.results.enrollments += [$enrollment]' \
              "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
        done

        if echo "$user_enrollments" | jq -e 'all(.status == "Passed")' >/dev/null; then
            user_status="completed"
        elif echo "$user_enrollments" | jq -e 'any(.status == "Past Due")' >/dev/null; then
            user_status="past_due"
        elif echo "$user_enrollments" | jq -e 'any(.status == "In Progress")' >/dev/null; then
            user_status="in_progress"
        fi
    fi

    jq --arg email "$email" --arg status "$user_status" \
      '.results.user_training_status[$email] = $status' \
      "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
done

# Summary
total_developer_users=$(jq '.results.developer_users | length' "$UNIQUE_JSON")
completed_training=$(jq '.results.user_training_status | to_entries | map(select(.value=="completed")) | length' "$UNIQUE_JSON")
in_progress=$(jq '.results.user_training_status | to_entries | map(select(.value=="in_progress")) | length' "$UNIQUE_JSON")
past_due=$(jq '.results.user_training_status | to_entries | map(select(.value=="past_due")) | length' "$UNIQUE_JSON")
not_started=$(jq '.results.user_training_status | to_entries | map(select(.value=="not_started")) | length' "$UNIQUE_JSON")
campaigns=$(jq '.results.developer_campaigns | length' "$UNIQUE_JSON")
groups=$(jq '.results.developer_groups | length' "$UNIQUE_JSON")
completion_rate=0
if [ "$total_developer_users" -gt 0 ]; then
    completion_rate=$((completed_training * 100 / total_developer_users))
fi

# Update summary in JSON
jq --arg total "$total_developer_users" \
   --arg completed "$completed_training" \
   --arg in_progress "$in_progress" \
   --arg past_due "$past_due" \
   --arg not_started "$not_started" \
   --arg rate "$completion_rate" \
   --arg campaigns "$campaigns" \
   --arg groups "$groups" \
   '.results.summary = {
     "total_developer_users": ($total|tonumber),
     "completed_training": ($completed|tonumber),
     "in_progress": ($in_progress|tonumber),
     "past_due": ($past_due|tonumber),
     "not_started": ($not_started|tonumber),
     "completion_rate": ($rate|tonumber),
     "total_campaigns": ($campaigns|tonumber),
     "total_groups": ($groups|tonumber)
   }' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"

# Generate summary
echo -e "\n${GREEN}Validation Summary:${NC}"
echo "Total Developer Groups: $groups"
echo "Total Developer Users: $total_developer_users"
echo "Developers Training Campaigns: $campaigns"
echo "Completed Training: $completed_training"
echo "In Progress: $in_progress"
echo "Past Due: $past_due"
echo "Not Started: $not_started"
echo "Completion Rate: ${completion_rate}%"

exit 0
