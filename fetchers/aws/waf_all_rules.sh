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
    # Extract ID from ARN if necessary (ARN format: arn:partition:wafv2:region:account:scope/webacl/name/id)
    # The ID is the last segment after the final slash
    if [[ "$acl_id" == arn:* ]]; then
        acl_id=$(echo "$acl_id" | awk -F'/' '{print $NF}')
    fi
    
    # Skip if we don't have both ID and name
    if [ -z "$acl_id" ] || [ -z "$acl_name" ]; then
        echo -e "${YELLOW}Skipping invalid entry: id='$acl_id', name='$acl_name'${NC}" >&2
        continue
    fi
    
    echo -e "${BLUE}========== WEB ACL: $acl_name ($acl_id) ==========\n${NC}"
    echo -e "${GREEN}Retrieving detailed configuration...${NC}"
    acl_details=$(aws wafv2 get-web-acl --scope REGIONAL --region "$REGION" --profile "$PROFILE" --name "$acl_name" --id "$acl_id" 2>&1)
    
    # Check if the command failed
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error retrieving Web ACL: $acl_name ($acl_id)${NC}" >&2
        echo "$acl_details" >&2
        continue
    fi
    
    # Extract the full WebACL object and store it
    # This captures ALL WebACL data: Id, Name, ARN, Description, Scope, DefaultAction, Rules (with full details), VisibilityConfig, Capacity, etc.
    webacl_full=$(echo "$acl_details" | jq '.WebACL')
    
    # Extract rules count for display
    rules_count=$(echo "$webacl_full" | jq '.Rules | length')
    if [ "$rules_count" -eq 0 ]; then
        echo -e "${YELLOW}No rules found for this Web ACL.${NC}"
        # Store the full WebACL even if it has no rules (includes all metadata)
        jq --argjson webacl "$webacl_full" '.results += [$webacl]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        continue
    fi
    
    echo -e "${BLUE}RULES (Name | Priority | Type | Details | Action | Status):${NC}"
    # Display summary for each rule (full rule objects are already in webacl_full)
    for i in $(seq 0 $((rules_count-1))); do
        rule=$(echo "$webacl_full" | jq ".Rules[$i]")
        rule_name=$(echo "$rule" | jq -r '.Name')
        rule_priority=$(echo "$rule" | jq -r '.Priority // "N/A"')
        rule_id=$(echo "$rule" | jq -r '.RuleId // "N/A"')
        enabled=$(echo "$rule" | jq -r '.VisibilityConfig.Enabled // false')
        if [ "$enabled" = "true" ]; then
            rule_status="Enabled"
        else
            rule_status="Disabled"
        fi
        
        # Determine rule type and details for display
        if echo "$rule" | jq -e '.Statement.RateBasedStatement' > /dev/null; then
            rule_type="Rate-Based"
            rate_limit=$(echo "$rule" | jq -r '.Statement.RateBasedStatement.Limit')
            rule_action=$(echo "$rule" | jq -r '.Action | keys[0] // "N/A"')
            details="Rate Limit: $rate_limit req/5min"
        elif echo "$rule" | jq -e '.Statement.ManagedRuleGroupStatement' > /dev/null; then
            vendor=$(echo "$rule" | jq -r '.Statement.ManagedRuleGroupStatement.VendorName')
            name=$(echo "$rule" | jq -r '.Statement.ManagedRuleGroupStatement.Name')
            rule_type="Managed ($vendor)"
            details="Group: $name"
            rule_action=$(echo "$rule" | jq -r '.OverrideAction | keys[0] // "None"')
        elif echo "$rule" | jq -e '.Statement.RuleGroupReferenceStatement' > /dev/null; then
            rule_type="Rule Group Reference"
            arn=$(echo "$rule" | jq -r '.Statement.RuleGroupReferenceStatement.ARN')
            details="ARN: $arn"
            rule_action=$(echo "$rule" | jq -r '.OverrideAction | keys[0] // "None"')
        else
            rule_type="Regular"
            details="Custom Rule"
            rule_action=$(echo "$rule" | jq -r '.Action | keys[0] // "N/A"')
        fi
        echo -e "| $rule_name | $rule_priority | $rule_type | $details | $rule_action | $rule_status |"
    done
    
    # Store the complete WebACL object with ALL its data (including full rule objects with all fields)
    jq --argjson webacl "$webacl_full" '.results += [$webacl]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
    echo ""
done <<< "$web_acls"

exit 0 