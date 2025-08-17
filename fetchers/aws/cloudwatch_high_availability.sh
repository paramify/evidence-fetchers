#!/bin/bash
# Helper script for CloudWatch High Availability validation

# Steps:
# 1. CloudWatch Monitoring
#    - Auto Scaling policies
#    - CloudWatch alarms
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
COMPONENT="cloudwatch_high_availability"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Initialize JSON file
echo '{"results": []}' > "$OUTPUT_JSON"

echo -e "${BLUE}Starting CloudWatch High Availability validation...${NC}"

# 6. CloudWatch Monitoring
echo -e "${BLUE}6. Validating CloudWatch Monitoring...${NC}"

# Get scaling policies
scaling_policies=$(aws autoscaling describe-policies --profile "$PROFILE" --query 'ScalingPolicies[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$scaling_policies" | jq -c '.[]' | while read -r policy; do
        policy_name=$(echo "$policy" | jq -r '.PolicyName')
        asg_name=$(echo "$policy" | jq -r '.AutoScalingGroupName')
        policy_type=$(echo "$policy" | jq -r '.PolicyType')
        
        echo -e "${BLUE}Processing scaling policy: $policy_name${NC}"
        
        # Add to JSON
        jq --argjson policy "$policy" \
           '.results += [{"Type": "ScalingPolicy", "PolicyInfo": $policy}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

# Get CloudWatch alarms
cloudwatch_alarms=$(aws cloudwatch describe-alarms --profile "$PROFILE" --query 'MetricAlarms[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$cloudwatch_alarms" | jq -c '.[]' | while read -r alarm; do
        alarm_name=$(echo "$alarm" | jq -r '.AlarmName')
        state=$(echo "$alarm" | jq -r '.StateValue')
        metric_name=$(echo "$alarm" | jq -r '.MetricName')
        
        echo -e "${BLUE}Processing CloudWatch alarm: $alarm_name${NC}"
        
        # Add to JSON
        jq --argjson alarm "$alarm" \
           '.results += [{"Type": "CloudWatch_Alarm", "AlarmInfo": $alarm}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

echo -e "${GREEN}CloudWatch High Availability validation completed!${NC}"
echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"

exit 0 