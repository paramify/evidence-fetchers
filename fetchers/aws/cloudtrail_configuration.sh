#!/bin/bash
# Helper script for AWS CloudTrail validation

# Steps:
# 1. Check CloudTrail setup
#    - List all trails
#    aws cloudtrail list-trails
#    - Get trail configuration details
#    aws cloudtrail get-trail --name <trail-name>
#    - Get trail logging status
#    aws cloudtrail get-trail-status --name <trail-name>
#
# Output: Creates unique JSON file and appends to directory-based monitoring files

# Check if required parameters are provided
if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <profile> <region> <output_dir> <output_csv>"
    exit 1
fi

PROFILE="$1"
REGION="$2"
OUTPUT_DIR="$3"
OUTPUT_CSV="$4"

# Component identifier
COMPONENT="cloudtrail_configuration"
UNIQUE_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Initialize unique JSON file
echo '{
    "results": {
        "trails": [],
        "trail_details": {},
        "trail_status": {},
        "summary": {}
    }
}' > "$UNIQUE_JSON"



# 1. Check CloudTrail setup
# Get all trails
trails=$(aws cloudtrail list-trails --profile "$PROFILE" --region "$REGION" --query 'Trails[*].[Name,TrailARN]' --output json 2>/dev/null)

# Check if API call was successful
if [ $? -ne 0 ] || [ -z "$trails" ] || [ "$trails" = "null" ] || [ "$trails" = "[]" ]; then
    trails="[]"
fi

# Update trails list in unique JSON
jq --argjson trails "$trails" '.results.trails = ($trails // [])' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"



# Main processing loop: build up summary JSON object
summary_json='{"trails":{}}'

# Process each trail if any exist
if [ "$(echo "$trails" | jq 'length')" -gt 0 ]; then
    while read -r trail; do
        trail_name=$(echo "$trail" | jq -r '.[0]')
        trail_arn=$(echo "$trail" | jq -r '.[1]')
        
        # Get trail details
        trail_details=$(aws cloudtrail get-trail --profile "$PROFILE" --name "$trail_name" --output json 2>/dev/null)
        if [ $? -ne 0 ] || [ -z "$trail_details" ] || ! echo "$trail_details" | jq . >/dev/null 2>&1; then
            continue
        fi
        
        # Get trail status
        trail_status=$(aws cloudtrail get-trail-status --profile "$PROFILE" --name "$trail_name" --output json 2>/dev/null)
        if [ $? -ne 0 ] || [ -z "$trail_status" ] || ! echo "$trail_status" | jq . >/dev/null 2>&1; then
            continue
        fi
        
        # Extract trail information
        trail_info=$(echo "$trail_details" | jq '.Trail')
        is_logging=$(echo "$trail_status" | jq -r '.IsLogging // false')
        is_multi_region=$(echo "$trail_info" | jq -r '.IsMultiRegionTrail // false')
        s3_bucket=$(echo "$trail_info" | jq -r '.S3BucketName // "N/A"')
        include_global_service_events=$(echo "$trail_info" | jq -r '.IncludeGlobalServiceEvents // false')
        has_cloudwatch_logs=$(echo "$trail_info" | jq -r '.CloudWatchLogsLogGroupArn != null and .CloudWatchLogsLogGroupArn != ""')
        cloudwatch_logs_arn=$(echo "$trail_info" | jq -r '.CloudWatchLogsLogGroupArn // "N/A"')
        kms_key_id=$(echo "$trail_info" | jq -r '.KmsKeyId // "N/A"')
        is_organization_trail=$(echo "$trail_info" | jq -r '.IsOrganizationTrail // false')
        log_file_validation_enabled=$(echo "$trail_info" | jq -r '.LogFileValidationEnabled // false')
        
        # Get management events configuration
        has_management_events=$(echo "$trail_info" | jq -r '.HasCustomEventSelectors // false')
        event_selectors=$(echo "$trail_info" | jq '.EventSelectors // []')
        read_write_type=$(echo "$event_selectors" | jq -r '.[0].ReadWriteType // "All"')
        
        # Add trail details to unique JSON
        jq --arg name "$trail_name" \
           --argjson details "$trail_info" \
           '.results.trail_details[$name] = $details' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
        
        # Add trail status to unique JSON
        jq --arg name "$trail_name" \
           --argjson status "$trail_status" \
           '.results.trail_status[$name] = $status' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"
        
        # Create trail summary JSON
        trail_summary=$(jq -n \
            --arg name "$trail_name" \
            --arg arn "$trail_arn" \
            --arg logging "$is_logging" \
            --arg multi_region "$is_multi_region" \
            --arg s3 "$s3_bucket" \
            --arg global_events "$include_global_service_events" \
            --arg has_cw "$has_cloudwatch_logs" \
            --arg cw_arn "$cloudwatch_logs_arn" \
            --arg kms "$kms_key_id" \
            --arg org_trail "$is_organization_trail" \
            --arg validation "$log_file_validation_enabled" \
            --arg read_write "$read_write_type" \
            '{
                "trail_name": $name,
                "trail_arn": $arn,
                "is_logging": ($logging == "true"),
                "is_multi_region": ($multi_region == "true"),
                "s3_bucket": $s3,
                "include_global_service_events": ($global_events == "true"),
                "has_cloudwatch_logs": ($has_cw == "true"),
                "cloudwatch_logs_arn": $cw_arn,
                "kms_key_id": $kms,
                "is_organization_trail": ($org_trail == "true"),
                "log_file_validation_enabled": ($validation == "true"),
                "read_write_type": $read_write
            }')
        
        # Add trail summary to summary_json
        summary_json=$(echo "$summary_json" | jq --arg name "$trail_name" --argjson trailsum "$trail_summary" '.trails[$name] = $trailsum')
    done < <(echo "$trails" | jq -c '.[]')
fi

# After processing all trails, create overall summary
# Recalculate from the summary_json we built
trail_count=$(echo "$trails" | jq 'length')
enabled_trails=0
multi_region_trails=0
all_logging=false
issues_list=()

# Recalculate from the summary_json we built
if [ "$trail_count" -gt 0 ]; then
    enabled_trails=$(echo "$summary_json" | jq '[.trails[] | select(.is_logging == true)] | length')
    multi_region_trails=$(echo "$summary_json" | jq '[.trails[] | select(.is_multi_region == true)] | length')
    
    # Check if at least one trail is logging
    if [ "$enabled_trails" -gt 0 ]; then
        all_logging=true
    fi
    
    # Build issues list
    if [ "$enabled_trails" -eq 0 ]; then
        issues_list+=("no_trails_logging")
    fi
else
    issues_list+=("no_trails_configured")
fi

# Convert issues array to JSON array format
if [ ${#issues_list[@]} -eq 0 ]; then
    issues_json="[]"
else
    issues_json=$(printf '%s\n' "${issues_list[@]}" | jq -R . | jq -s .)
fi

# Create overall summary JSON
if [ "$trail_count" -gt 0 ]; then
    summary_json=$(echo "$summary_json" | jq \
        --arg count "$trail_count" \
        --arg enabled "$enabled_trails" \
        --arg multi "$multi_region_trails" \
        --arg health "$(if [ "$all_logging" = true ]; then echo "HEALTHY"; else echo "REQUIRES_ATTENTION"; fi)" \
        --argjson issues "$issues_json" \
        '{
            trail_count: ($count | tonumber),
            enabled_trails: ($enabled | tonumber),
            multi_region_trails: ($multi | tonumber),
            health_status: $health,
            issues: $issues
        } + .')
else
    summary_json=$(jq -n \
        --arg count "0" \
        --arg enabled "0" \
        --arg multi "0" \
        --arg health "REQUIRES_ATTENTION" \
        --argjson issues "$issues_json" \
        '{
            trail_count: ($count | tonumber),
            enabled_trails: ($enabled | tonumber),
            multi_region_trails: ($multi | tonumber),
            health_status: $health,
            issues: $issues,
            trails: {}
        }')
fi

# Update unique JSON with combined summary
jq --argjson summary "$summary_json" '.results.summary = $summary' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"

exit 0

