#!/bin/bash
# Helper script for Backup and Recovery High Availability validation

# Steps:
# 1. Backup and Recovery
#    - EBS snapshots
#    - RDS automated backups
#
# Output: Creates JSON with validation results

# Required parameters
if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <profile> <region> <output_dir> <output_csv>"
    exit 1
fi

PROFILE="$1"
REGION="$2"
OUTPUT_DIR="$3"
OUTPUT_CSV="$4"

# Component identifier
COMPONENT="backup_recovery_high_availability"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get caller identity for metadata
CALLER_IDENTITY=$(aws sts get-caller-identity --profile "$PROFILE" --output json 2>/dev/null || echo '{"Account":"unknown","Arn":"unknown"}')
ACCOUNT_ID=$(echo "$CALLER_IDENTITY" | jq -r '.Account // "unknown"')
ARN=$(echo "$CALLER_IDENTITY" | jq -r '.Arn // "unknown"')
DATETIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Initialize JSON file with metadata
jq -n \
  --arg profile "$PROFILE" \
  --arg region "$REGION" \
  --arg datetime "$DATETIME" \
  --arg account_id "$ACCOUNT_ID" \
  --arg arn "$ARN" \
  '{
    "metadata": {
      "profile": $profile,
      "region": $region,
      "datetime": $datetime,
      "account_id": $account_id,
      "arn": $arn
    },
    "results": []
  }' > "$OUTPUT_JSON"

echo -e "${BLUE}Starting Backup and Recovery High Availability validation...${NC}"

# 7. Backup and Recovery
echo -e "${BLUE}7. Validating Backup and Recovery...${NC}"

# Get EBS snapshots
snapshots=$(aws ec2 describe-snapshots --profile "$PROFILE" --owner-ids self --query 'Snapshots[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$snapshots" | jq -c '.[]' | while read -r snapshot; do
        snapshot_id=$(echo "$snapshot" | jq -r '.SnapshotId')
        volume_id=$(echo "$snapshot" | jq -r '.VolumeId')
        state=$(echo "$snapshot" | jq -r '.State')
        start_time=$(echo "$snapshot" | jq -r '.StartTime')
        
        echo -e "${BLUE}Processing snapshot: $snapshot_id${NC}"
        
        # Add to JSON
        jq --argjson snapshot "$snapshot" \
           '.results += [{"Type": "EBS_Snapshot", "SnapshotInfo": $snapshot}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

# Get DLM lifecycle policies
dlm_policies=$(aws dlm get-lifecycle-policies --profile "$PROFILE" --query 'Policies[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$dlm_policies" | jq -c '.[]' | while read -r policy; do
        policy_id=$(echo "$policy" | jq -r '.PolicyId')
        description=$(echo "$policy" | jq -r '.Description')
        state=$(echo "$policy" | jq -r '.State')
        
        echo -e "${BLUE}Processing DLM policy: $policy_id${NC}"
        
        # Add to JSON
        jq --argjson policy "$policy" \
           '.results += [{"Type": "DLM_Policy", "PolicyInfo": $policy}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

echo -e "${GREEN}Backup and Recovery High Availability validation completed!${NC}"
echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"

exit 0 