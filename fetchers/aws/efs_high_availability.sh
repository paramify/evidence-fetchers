#!/bin/bash
# Helper script for EFS High Availability validation

# Steps:
# 1. EFS High Availability
#    - EFS mount targets across AZs
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
COMPONENT="efs_high_availability"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Initialize JSON file
echo '{"results": []}' > "$OUTPUT_JSON"

echo -e "${BLUE}Starting EFS High Availability validation...${NC}"

# 9. EFS High Availability
echo -e "${BLUE}9. Validating EFS High Availability...${NC}"

# Get EFS file systems
efs_filesystems=$(aws efs describe-file-systems --profile "$PROFILE" --query 'FileSystems[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$efs_filesystems" | jq -c '.[]' | while read -r efs; do
        fs_id=$(echo "$efs" | jq -r '.FileSystemId')
        creation_time=$(echo "$efs" | jq -r '.CreationTime')
        mount_target_count=$(echo "$efs" | jq -r '.NumberOfMountTargets')
        
        echo -e "${BLUE}Processing EFS file system: $fs_id${NC}"
        
        # Get mount targets
        mount_targets=$(aws efs describe-mount-targets --profile "$PROFILE" --file-system-id "$fs_id" --query 'MountTargets[*]' --output json 2>/dev/null)
        
        # Add to JSON
        jq --argjson efs "$efs" \
           --argjson targets "$mount_targets" \
           '.results += [{"Type": "EFS_FileSystem", "EFSInfo": $efs, "MountTargets": $targets}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

echo -e "${GREEN}EFS High Availability validation completed!${NC}"
echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"

exit 0 