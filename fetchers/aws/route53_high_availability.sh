#!/bin/bash
# Helper script for Route 53 High Availability validation

# Steps:
# 1. Route 53 Health Checks
#    - DNS failover configuration
#    - Health check status
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
COMPONENT="route53_high_availability"
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

echo -e "${BLUE}Starting Route 53 High Availability validation...${NC}"

# 5. Route 53 Health Checks
echo -e "${BLUE}5. Validating Route 53 Health Checks...${NC}"

# Get health checks
health_checks=$(aws route53 list-health-checks --profile "$PROFILE" --region "$REGION" --query 'HealthChecks[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$health_checks" | jq -c '.[]' | while read -r hc; do
        hc_id=$(echo "$hc" | jq -r '.Id')
        hc_type=$(echo "$hc" | jq -r '.HealthCheckConfig.Type')
        
        echo -e "${BLUE}Processing health check: $hc_id${NC}"
        
        # Get health check status
        hc_status=$(aws route53 get-health-check-status --profile "$PROFILE" --region "$REGION" --health-check-id "$hc_id" --query 'HealthCheckObservations[*]' --output json 2>/dev/null)
        
        # Add to JSON
        jq --argjson hc "$hc" \
           --argjson status "$hc_status" \
           '.results += [{"Type": "Route53_HealthCheck", "HealthCheckInfo": $hc, "Status": $status}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

echo -e "${GREEN}Route 53 High Availability validation completed!${NC}"
echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"

exit 0 