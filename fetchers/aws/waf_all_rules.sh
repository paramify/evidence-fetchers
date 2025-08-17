#!/bin/bash
# Helper script for WAF rules validation (ALL RULES VERSION)
#
# This version outputs ALL rules in each WAF WebACL, not just DoS-related ones.
#
# Steps:
# 1. List all WAFv2 Web ACLs in the region
#    aws wafv2 list-web-acls --scope REGIONAL --query 'WebACLs[*].[Id, Name]'
# 2. For each Web ACL, get detailed configuration:
#    aws wafv2 get-web-acl --scope REGIONAL --name <name> --id <id>
# 3. Extract and output ALL rules (no filtering)
# Output: Creates JSON with validation results

# Check if required parameters are provided
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <profile> <region> <output_dir>"
    exit 1
fi

PROFILE="$1"
REGION="$2"
OUTPUT_DIR="$3"

COMPONENT="waf_all_rules"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo '{"results": []}' > "$OUTPUT_JSON"

if ! aws wafv2 list-web-acls --scope REGIONAL --region "$REGION" --profile "$PROFILE"> /dev/null 2>&1; then
    echo "${RED}Error:${NC} Failed to retrieve WAFv2 web ACLs." >&2
    exit 1
fi

echo -e "${GREEN}Retrieving Web ACLs in region $REGION...${NC}"
web_acls=$(aws wafv2 list-web-acls --scope REGIONAL --region "$REGION" --profile "$PROFILE" --query 'WebACLs[*].[Id, Name]' --output text)

if [ -z "$web_acls" ]; then
    echo -e "${YELLOW}No Web ACLs found in region $REGION.${NC}"
    exit 0
fi

while IFS=$'\t' read -r acl_id acl_name; do
    echo -e "${BLUE}========== WEB ACL: $acl_name ($acl_id) ==========\n${NC}"
    acl_data=$(jq -n --arg id "$acl_id" --arg name "$acl_name" '{"WebACLId": $id, "WebACLName": $name, "Rules": []}')
    echo -e "${GREEN}Retrieving detailed configuration...${NC}"
    acl_details=$(aws wafv2 get-web-acl --scope REGIONAL --region "$REGION" --profile "$PROFILE" --name "$acl_name" --id "$acl_id")
    rules_count=$(echo "$acl_details" | jq '.WebACL.Rules | length')
    if [ "$rules_count" -eq 0 ]; then
        echo -e "${YELLOW}No rules found for this Web ACL.${NC}"
        jq --argjson data "$acl_data" '.results += [$data]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        continue
    fi
    echo -e "${BLUE}RULES (Name | Type | Details | Action | Status):${NC}"
    rules_json="[]"
    for i in $(seq 0 $((rules_count-1))); do
        rule=$(echo "$acl_details" | jq ".WebACL.Rules[$i]")
        rule_name=$(echo "$rule" | jq -r '.Name')
        rule_id=$(echo "$rule" | jq -r '.RuleId // "N/A"')
        rule_status=$(echo "$rule" | jq -r '.VisibilityConfig.SampledRequestsEnabled // empty')
        if [ -z "$rule_status" ]; then
            rule_status=$(echo "$rule" | jq -r '.Action | keys[0] // "N/A"')
        fi
        enabled=$(echo "$rule" | jq -r '.VisibilityConfig.Enabled // .VisibilityConfig.SampledRequestsEnabled // empty')
        if [ "$enabled" = "true" ]; then
            rule_status="Enabled"
        elif [ "$enabled" = "false" ]; then
            rule_status="Disabled"
        fi
        # Determine rule type and details
        if echo "$rule" | jq -e '.Statement.RateBasedStatement' > /dev/null; then
            rule_type="Rate-Based"
            rate_limit=$(echo "$rule" | jq -r '.Statement.RateBasedStatement.Limit')
            rule_action=$(echo "$rule" | jq -r '.Action | keys[0]')
            details="Rate Limit: $rate_limit req/5min"
        elif echo "$rule" | jq -e '.Statement.ManagedRuleGroupStatement' > /dev/null; then
            vendor=$(echo "$rule" | jq -r '.Statement.ManagedRuleGroupStatement.VendorName')
            name=$(echo "$rule" | jq -r '.Statement.ManagedRuleGroupStatement.Name')
            rule_type="Managed ($vendor)"
            details="Group: $name"
            rule_action=$(echo "$rule" | jq -r '.OverrideAction | keys[0] // "None"')
        else
            rule_type="Regular"
            details="N/A"
            rule_action=$(echo "$rule" | jq -r '.Action | keys[0] // "N/A"')
        fi
        echo -e "| $rule_name | $rule_type | $details | $rule_action | $rule_status |"
        rules_json=$(echo "$rules_json" | jq --arg id "$rule_id" --arg name "$rule_name" --arg type "$rule_type" --arg details "$details" --arg action "$rule_action" --arg status "$rule_status" '. += [{"RuleId": $id, "RuleName": $name, "RuleType": $type, "Details": $details, "Action": $action, "Status": $status}]')
    done
    acl_data=$(echo "$acl_data" | jq --argjson rules "$rules_json" '.Rules = $rules')
    jq --argjson data "$acl_data" '.results += [$data]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
    echo ""
done <<< "$web_acls"

exit 0 