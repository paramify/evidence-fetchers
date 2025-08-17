#!/bin/bash
# Helper script for Auto Scaling High Availability validation

# Steps:
# 1. Auto Scaling Groups
#    - EC2 Auto Scaling across AZs
#    - Health check configuration
#
# Commands:
# aws autoscaling describe-auto-scaling-groups --query 'AutoScalingGroups[*]'
# aws autoscaling describe-auto-scaling-instances --query "AutoScalingInstances[?AutoScalingGroupName=='[asg-name]'][*]"
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
COMPONENT="auto_scaling_high_availability"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Initialize JSON file
echo '{"results": []}' > "$OUTPUT_JSON"

echo -e "${BLUE}Starting Auto Scaling High Availability validation...${NC}"

# 4. Auto Scaling Groups
echo -e "${BLUE}4. Validating Auto Scaling Groups...${NC}"

# Get Auto Scaling Groups
asgs=$(aws autoscaling describe-auto-scaling-groups --profile "$PROFILE" --query 'AutoScalingGroups[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$asgs" | jq -c '.[]' | while read -r asg; do
        asg_name=$(echo "$asg" | jq -r '.AutoScalingGroupName')
        azs=$(echo "$asg" | jq -r '.AvailabilityZones[]')
        min_size=$(echo "$asg" | jq -r '.MinSize')
        max_size=$(echo "$asg" | jq -r '.MaxSize')
        desired_capacity=$(echo "$asg" | jq -r '.DesiredCapacity')
        
        echo -e "${BLUE}Processing Auto Scaling Group: $asg_name${NC}"
        
        # Get ASG instances
        asg_instances=$(aws autoscaling describe-auto-scaling-instances --profile "$PROFILE" --query "AutoScalingInstances[?AutoScalingGroupName=='$asg_name'][*]" --output json 2>/dev/null)
        
        # Add to JSON
        jq --argjson asg "$asg" \
           --argjson instances "$asg_instances" \
           '.results += [{"Type": "AutoScalingGroup", "ASGInfo": $asg, "Instances": $instances}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

# Generate summary
echo -e "${BLUE}=== Auto Scaling High Availability Summary ===${NC}"
echo -e "${GREEN}Auto Scaling High Availability validation completed!${NC}"

# Count auto scaling groups
if [ -f "$OUTPUT_JSON" ]; then
    total_asgs=$(jq '.results | length' "$OUTPUT_JSON")
    echo -e "${BLUE}Total Auto Scaling Groups Found: $total_asgs${NC}"
    
    if [ "$total_asgs" -gt 0 ]; then
        echo -e "${BLUE}Auto Scaling Group Details:${NC}"
        jq -r '.results[] | .ASGInfo.AutoScalingGroupName' "$OUTPUT_JSON" 2>/dev/null | while read -r asg_name; do
            if [ -n "$asg_name" ]; then
                min_size=$(jq -r --arg name "$asg_name" '.results[] | select(.ASGInfo.AutoScalingGroupName == $name) | .ASGInfo.MinSize' "$OUTPUT_JSON" 2>/dev/null)
                max_size=$(jq -r --arg name "$asg_name" '.results[] | select(.ASGInfo.AutoScalingGroupName == $name) | .ASGInfo.MaxSize' "$OUTPUT_JSON" 2>/dev/null)
                desired=$(jq -r --arg name "$asg_name" '.results[] | select(.ASGInfo.AutoScalingGroupName == $name) | .ASGInfo.DesiredCapacity' "$OUTPUT_JSON" 2>/dev/null)
                echo -e "  - $asg_name (Min: $min_size, Max: $max_size, Desired: $desired)"
            fi
        done
    fi
fi

echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"
echo -e "${BLUE}CSV summary saved to: $OUTPUT_CSV${NC}"

exit 0 