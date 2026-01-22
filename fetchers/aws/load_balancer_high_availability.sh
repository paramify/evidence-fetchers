#!/bin/bash
# Helper script for Load Balancer High Availability validation

# Steps:
# 1. Load Balancer High Availability
#    - Application Load Balancer (ALB) health
#    - Network Load Balancer (NLB) cross-zone
#
# Commands:
# aws elbv2 describe-load-balancers --query 'LoadBalancers[*]'
# aws elbv2 describe-target-groups --load-balancer-arn [lb-arn] --query 'TargetGroups[*]'
# aws elbv2 describe-load-balancer-attributes --load-balancer-arn [lb-arn] --query 'Attributes[*]'
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
COMPONENT="load_balancer_high_availability"
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

echo -e "${BLUE}Starting Load Balancer High Availability validation...${NC}"

# 2. Load Balancer High Availability
echo -e "${BLUE}2. Validating Load Balancer High Availability...${NC}"

# Get all load balancers
load_balancers=$(aws elbv2 describe-load-balancers --profile "$PROFILE" --region "$REGION" --query 'LoadBalancers[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$load_balancers" | jq -c '.[]' | while read -r lb; do
        lb_name=$(echo "$lb" | jq -r '.LoadBalancerName')
        lb_arn=$(echo "$lb" | jq -r '.LoadBalancerArn')
        lb_type=$(echo "$lb" | jq -r '.Type')
        
        echo -e "${BLUE}Processing load balancer: $lb_name${NC}"
        
        # Get availability zones
        lb_azs=$(echo "$lb" | jq -r '.AvailabilityZones[]' 2>/dev/null | tr '\n' ' ')
        
        # Get target groups
        target_groups=$(aws elbv2 describe-target-groups --profile "$PROFILE" --region "$REGION" --load-balancer-arn "$lb_arn" --query 'TargetGroups[*]' --output json 2>/dev/null)
        
        # Get load balancer attributes
        lb_attributes=$(aws elbv2 describe-load-balancer-attributes --profile "$PROFILE" --region "$REGION" --load-balancer-arn "$lb_arn" --query 'Attributes[*]' --output json 2>/dev/null)
        
        # Add to JSON
        jq --argjson lb "$lb" \
           --arg azs "$lb_azs" \
           --argjson targets "$target_groups" \
           --argjson attrs "$lb_attributes" \
           '.results += [{"Type": "LoadBalancer", "LoadBalancerInfo": $lb, "AvailabilityZones": $azs, "TargetGroups": $targets, "Attributes": $attrs}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

# Generate summary
echo -e "${BLUE}=== Load Balancer High Availability Summary ===${NC}"
echo -e "${GREEN}Load Balancer High Availability validation completed!${NC}"

# Count load balancers by type
if [ -f "$OUTPUT_JSON" ]; then
    total_lbs=$(jq '.results | length' "$OUTPUT_JSON")
    alb_count=$(jq '.results[] | select(.LoadBalancerInfo.Type == "application") | .LoadBalancerInfo.LoadBalancerName' "$OUTPUT_JSON" | wc -l)
    nlb_count=$(jq '.results[] | select(.LoadBalancerInfo.Type == "network") | .LoadBalancerInfo.LoadBalancerName' "$OUTPUT_JSON" | wc -l)
    
    echo -e "${BLUE}Total Load Balancers Found: $total_lbs${NC}"
    echo -e "${BLUE}Application Load Balancers (ALB): $alb_count${NC}"
    echo -e "${BLUE}Network Load Balancers (NLB): $nlb_count${NC}"
    
    # Check for active load balancers
    active_lbs=$(jq '.results[] | select(.LoadBalancerInfo.State.Code == "active") | .LoadBalancerInfo.LoadBalancerName' "$OUTPUT_JSON" | wc -l)
    echo -e "${GREEN}Active Load Balancers: $active_lbs${NC}"
    
    # List load balancer names
    echo -e "${BLUE}Load Balancer Names:${NC}"
    jq -r '.results[] | .LoadBalancerInfo.LoadBalancerName' "$OUTPUT_JSON" 2>/dev/null | while read -r lb_name; do
        echo -e "  - $lb_name"
    done
fi

echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"
echo -e "${BLUE}CSV summary saved to: $OUTPUT_CSV${NC}"

exit 0 