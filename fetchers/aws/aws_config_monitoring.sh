#!/bin/bash
# Helper script for AWS Config validation

# Steps:
# 1. Check AWS Config setup
#    - Get configuration recorder status
#    aws configservice describe-configuration-recorder-status
#    - View configuration recorder details
#    aws configservice describe-configuration-recorders
#    - Check delivery channel configuration
#    aws configservice describe-delivery-channels
#
# Output: Creates unique JSON file and appends to System-Monitoring files

# Load environment and parse args
source "$(dirname "$0")/../common/env_loader.sh" "$@"

# Component identifier
COMPONENT="aws_config_monitoring"
UNIQUE_JSON="$OUTPUT_DIR/$COMPONENT.json"

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

# Initialize unique JSON file with metadata
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
    "results": {
      "configuration_recorders": [],
      "recorder_status": [],
      "delivery_channels": [],
      "summary": {}
    }
  }' > "$UNIQUE_JSON"



# 1. Check AWS Config setup
echo -e "${BLUE}Checking AWS Config setup...${NC}"

# Get configuration recorder status
recorder_status=$(aws configservice describe-configuration-recorder-status --profile "$PROFILE" --region "$REGION" --query 'ConfigurationRecordersStatus[*]' --output json)

# Get configuration recorder details
config_recorders=$(aws configservice describe-configuration-recorders --profile "$PROFILE" --region "$REGION" --query 'ConfigurationRecorders[*]' --output json)

# Get delivery channel configuration
delivery_channels=$(aws configservice describe-delivery-channels --profile "$PROFILE" --region "$REGION" --query 'DeliveryChannels[*]' --output json)

# Update unique JSON with results
jq --argjson status "$recorder_status" \
   --argjson recorders "$config_recorders" \
   --argjson channels "$delivery_channels" \
   '.results = {
       "configuration_recorders": ($recorders // []),
       "recorder_status": ($status // []),
       "delivery_channels": ($channels // [])
   }' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"



# Append results to CSV
# Add configuration recorder status
recording_status=$(echo "$recorder_status" | jq -r '.[0].recording // "false"')

# Add delivery channel status
if [ "$(echo "$delivery_channels" | jq 'length')" -gt 0 ]; then
else
fi

# Generate summary information
recorder_count=$(echo "$config_recorders" | jq 'length')
channel_count=$(echo "$delivery_channels" | jq 'length')
all_resources=$(echo "$config_recorders" | jq -r '.[0].recordingGroup.allSupported // false')
global_resources=$(echo "$config_recorders" | jq -r '.[0].recordingGroup.includeGlobalResources // false')
last_status=$(echo "$recorder_status" | jq -r '.[0].lastStatus // "N/A"')
last_error=$(echo "$recorder_status" | jq -r '.[0].lastErrorCode // "NONE"')
s3_bucket=$(echo "$delivery_channels" | jq -r '.[0].s3BucketName // "N/A"')
sns_topic=$(echo "$delivery_channels" | jq -r '.[0].snsTopicARN // "N/A"')
delivery_freq=$(echo "$delivery_channels" | jq -r '.[0].configSnapshotDeliveryProperties.deliveryFrequency // "N/A"')

# Create summary JSON
summary_json=$(jq -n \
  --arg status "$recording_status" \
  --arg channels "$channel_count" \
  --arg recorders "$recorder_count" \
  --arg all_res "$all_resources" \
  --arg global_res "$global_resources" \
  --arg last_stat "$last_status" \
  --arg last_err "$last_error" \
  --arg s3 "$s3_bucket" \
  --arg sns "$sns_topic" \
  --arg freq "$delivery_freq" \
  '{
    "summary": {
      "basic_status": {
        "recording_enabled": $status,
        "delivery_channels_configured": $channels
      },
      "configuration_details": {
        "recorder_count": $recorders,
        "all_resources_recorded": $all_res,
        "global_resources_included": $global_res
      },
      "status_details": {
        "last_status": $last_stat,
        "last_error": $last_err
      },
      "delivery_details": {
        "s3_bucket": $s3,
        "sns_topic": $sns,
        "delivery_frequency": $freq
      },
      "health_assessment": {
        "status": (if $status == "true" and $channels != "0" then "HEALTHY" else "REQUIRES_ATTENTION" end),
        "issues": (if $status != "true" then ["recording_disabled"] else [] end + if $channels == "0" then ["no_delivery_channel"] else [] end)
      }
    }
  }')

# Update unique JSON with summary
jq --argjson summary "$summary_json" '.results.summary = $summary.summary' "$UNIQUE_JSON" > tmp.json && mv tmp.json "$UNIQUE_JSON"



# Add summary to CSV

# Generate console output
echo -e "\n${GREEN}Validation Summary:${NC}"

# Basic status
echo "AWS Config Recording Status: $recording_status"
echo "Delivery Channel Status: $(if [ "$channel_count" -gt 0 ]; then echo "CONFIGURED"; else echo "NOT_CONFIGURED"; fi)"

# Detailed statistics
echo -e "\n${BLUE}Detailed Statistics:${NC}"

# Configuration Recorder Details
echo "Configuration Recorder Details:"
echo "  - Number of Recorders: $recorder_count"
if [ "$recorder_count" -gt 0 ]; then
    echo "  - Recording All Resources: $all_resources"
    echo "  - Include Global Resources: $global_resources"
fi

# Recorder Status Details
echo -e "\nRecorder Status Details:"
if [ "$(echo "$recorder_status" | jq 'length')" -gt 0 ]; then
    echo "  - Last Status: $last_status"
    echo "  - Last Error Code: $last_error"
fi

# Delivery Channel Details
echo -e "\nDelivery Channel Details:"
echo "  - Number of Delivery Channels: $channel_count"
if [ "$channel_count" -gt 0 ]; then
    echo "  - S3 Bucket: $s3_bucket"
    echo "  - SNS Topic: $sns_topic"
    echo "  - Delivery Frequency: $delivery_freq"
fi

# Overall Health Assessment
echo -e "\n${YELLOW}Overall Health Assessment:${NC}"
if [ "$recording_status" = "true" ] && [ "$channel_count" -gt 0 ]; then
    echo "✅ AWS Config is properly configured and operational"
else
    echo "⚠️ AWS Config requires attention:"
    [ "$recording_status" != "true" ] && echo "  - Configuration recording is not enabled"
    [ "$channel_count" -eq 0 ] && echo "  - No delivery channel configured"
fi

exit 0
