#!/bin/bash
# Helper script for Network Resilience High Availability validation

# Steps:
# 1. Network Resilience
#    - VPC and subnet distribution
#    - NAT Gateways redundancy
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
COMPONENT="network_resilience_high_availability"
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

echo -e "${BLUE}Starting Network Resilience High Availability validation...${NC}"

# 8. Network Resilience
echo -e "${BLUE}8. Validating Network Resilience...${NC}"

# Get VPC subnets
subnets=$(aws ec2 describe-subnets --profile "$PROFILE" --query 'Subnets[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$subnets" | jq -c '.[]' | while read -r subnet; do
        subnet_id=$(echo "$subnet" | jq -r '.SubnetId')
        az=$(echo "$subnet" | jq -r '.AvailabilityZone')
        cidr=$(echo "$subnet" | jq -r '.CidrBlock')
        state=$(echo "$subnet" | jq -r '.State')
        
        echo -e "${BLUE}Processing subnet: $subnet_id${NC}"
        
        # Add to JSON
        jq --argjson subnet "$subnet" \
           '.results += [{"Type": "VPC_Subnet", "SubnetInfo": $subnet}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

# Get NAT Gateways
nat_gateways=$(aws ec2 describe-nat-gateways --profile "$PROFILE" --query 'NatGateways[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$nat_gateways" | jq -c '.[]' | while read -r nat; do
        nat_id=$(echo "$nat" | jq -r '.NatGatewayId')
        subnet_id=$(echo "$nat" | jq -r '.SubnetId')
        state=$(echo "$nat" | jq -r '.State')
        
        echo -e "${BLUE}Processing NAT Gateway: $nat_id${NC}"
        
        # Add to JSON
        jq --argjson nat "$nat" \
           '.results += [{"Type": "NAT_Gateway", "NATInfo": $nat}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

echo -e "${GREEN}Network Resilience High Availability validation completed!${NC}"
echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"

exit 0 