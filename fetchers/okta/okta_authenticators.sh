#!/bin/bash
# Helper script for Okta authenticators validation
#
# Requirements:
# - Okta API Access Management SKU is required for accessing these APIs
# - OKTA_API_TOKEN environment variable must be set
# - OKTA_ORG_URL environment variable must be set
#
# Steps:
# 1. Pull Okta application list and correlate authentication policies
#    GET /api/v1/apps
#    GET /api/v1/apps/{appId}/policies
#
# 2. Pull Okta authenticator enrollment policy and rules
#    GET /api/v1/policies?type=AUTHENTICATOR_ENROLLMENT
#    GET /api/v1/policies/{policyId}/rules
#
# 3. Run policy simulation to validate phishing resistant MFA
#    POST /api/v1/policies/simulate
#
# 4. Get FIDO2 authenticator configuration
#    GET /api/v1/authenticators
#
# Output: Creates JSON with validation results

# Check if required parameters are provided
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <profile> <region> <output_dir>"
    exit 1
fi

PROFILE="$1"
REGION="$2"
OUTPUT_DIR="$3"

# Component identifier
COMPONENT="okta_authenticators"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Initialize JSON file
echo '{"results": {"applications": [], "enrollment_policies": [], "simulation_results": [], "fido2_config": []}}' > "$OUTPUT_JSON"

# Check if Okta API token is set
if [ -z "$OKTA_API_TOKEN" ]; then
    echo "${RED}Error:${NC} OKTA_API_TOKEN environment variable is not set." >&2
    exit 1
fi

# Check if Okta org URL is set
if [ -z "$OKTA_ORG_URL" ]; then
    echo "${RED}Error:${NC} OKTA_ORG_URL environment variable is not set." >&2
    exit 1
fi

# F. Get FIDO2 authenticator configuration
echo -e "${BLUE}Retrieving FIDO2 authenticator configuration...${NC}"
fido2_config=$(curl -s -H "Authorization: SSWS $OKTA_API_TOKEN" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    "$OKTA_ORG_URL/api/v1/authenticators" | jq '.')

# Process FIDO2 configuration
echo "$fido2_config" | jq -c '.[]' | while read -r authenticator; do
    auth_id=$(echo "$authenticator" | jq -r '.id')
    auth_name=$(echo "$authenticator" | jq -r '.name')
    auth_type=$(echo "$authenticator" | jq -r '.type')
    
    # Only process FIDO2/WebAuthn authenticators
    if [[ "$auth_type" == "security_key" || "$auth_type" == "webauthn" ]]; then
        echo -e "${BLUE}Processing FIDO2 authenticator: $auth_name${NC}"
        
        # Get detailed configuration
        auth_details=$(curl -s -H "Authorization: SSWS $OKTA_API_TOKEN" \
            -H "Accept: application/json" \
            -H "Content-Type: application/json" \
            "$OKTA_ORG_URL/api/v1/authenticators/$auth_id" | jq '.')
        
        # Analyze configuration
        analysis=$(jq -n --argjson auth "$auth_details" '{
            "status": "PASS",
            "checks": {
                "user_verification": {
                    "required": ($auth.settings.userVerification == "required"),
                    "recommended": true,
                    "description": "User verification should be required for phishing resistance"
                },
                "resident_key": {
                    "required": ($auth.settings.residentKey == "required"),
                    "recommended": true,
                    "description": "Resident keys should be required for better security"
                },
                "attestation": {
                    "required": ($auth.settings.attestation == "required"),
                    "recommended": true,
                    "description": "Attestation should be required to verify authenticator authenticity"
                },
                "timeout": {
                    "within_limits": ($auth.settings.timeout <= 300),
                    "recommended": true,
                    "description": "Timeout should be 300 seconds or less"
                }
            }
        }')
        
        # Add analysis to results
        jq --argjson auth "$auth_details" --argjson analysis "$analysis" '.results.fido2_config += [$auth + {"Analysis": $analysis}]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
        
        # Print analysis results
        echo -e "${GREEN}Configuration Analysis for $auth_name:${NC}"
        echo "$analysis" | jq -r '.checks | to_entries[] | "  \(.key): \(if .value.required then "✓" else "✗" end) - \(.value.description)"'
    fi
done

# C. Get Okta applications and their policies
echo -e "${BLUE}Retrieving Okta applications...${NC}"
applications=$(curl -s -H "Authorization: SSWS $OKTA_API_TOKEN" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    "$OKTA_ORG_URL/api/v1/apps" | jq '.')

# Process each application
echo "$applications" | jq -c '.[]' | while read -r app; do
    app_id=$(echo "$app" | jq -r '.id')
    app_name=$(echo "$app" | jq -r '.name')
    
    echo -e "${BLUE}Processing application: $app_name${NC}"
    
    # Get application policies
    app_policies=$(curl -s -H "Authorization: SSWS $OKTA_API_TOKEN" \
        -H "Accept: application/json" \
        -H "Content-Type: application/json" \
        "$OKTA_ORG_URL/api/v1/apps/$app_id/policies" | jq '.')
    
    # Add application to results
    jq --argjson app "$app" --argjson policies "$app_policies" '.results.applications += [$app + {"Policies": $policies}]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
    
done

# D. Get authenticator enrollment policies
echo -e "${BLUE}Retrieving authenticator enrollment policies...${NC}"
enrollment_policies=$(curl -s -H "Authorization: SSWS $OKTA_API_TOKEN" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    "$OKTA_ORG_URL/api/v1/policies?type=AUTHENTICATOR_ENROLLMENT" | jq '.')

# Process each enrollment policy
echo "$enrollment_policies" | jq -c '.[]' | while read -r policy; do
    policy_id=$(echo "$policy" | jq -r '.id')
    policy_name=$(echo "$policy" | jq -r '.name')
    
    echo -e "${BLUE}Processing enrollment policy: $policy_name${NC}"
    
    # Get policy rules
    policy_rules=$(curl -s -H "Authorization: SSWS $OKTA_API_TOKEN" \
        -H "Accept: application/json" \
        -H "Content-Type: application/json" \
        "$OKTA_ORG_URL/api/v1/policies/$policy_id/rules" | jq '.')
    
    # Check for phishing resistant MFA requirement
    has_phishing_resistant=$(echo "$policy_rules" | jq 'any(.conditions.authenticators[] | select(.type == "security_key" or .type == "webauthn"))')
    
    # Add policy to results
    jq --argjson policy "$policy" --argjson rules "$policy_rules" --arg has_pr "$has_phishing_resistant" \
        '.results.enrollment_policies += [$policy + {"Rules": $rules, "HasPhishingResistantMFA": ($has_pr | test("true"))}]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
    
done

# E. Run policy simulation
echo -e "${BLUE}Running policy simulation...${NC}"

# Test cases for simulation
test_cases=(
    '{"user": {"id": "test_user"}, "context": {"network": {"ip": "192.168.1.1"}, "device": {"os": "Windows"}}, "authenticators": []}'
    '{"user": {"id": "test_user"}, "context": {"network": {"ip": "192.168.1.1"}, "device": {"os": "Windows"}}, "authenticators": [{"type": "password"}]}'
    '{"user": {"id": "test_user"}, "context": {"network": {"ip": "192.168.1.1"}, "device": {"os": "Windows"}}, "authenticators": [{"type": "password"}, {"type": "security_key"}]}'
)

for test_case in "${test_cases[@]}"; do
    # Run simulation
    simulation_result=$(curl -s -X POST -H "Authorization: SSWS $OKTA_API_TOKEN" \
        -H "Accept: application/json" \
        -H "Content-Type: application/json" \
        -d "$test_case" \
        "$OKTA_ORG_URL/api/v1/policies/simulate" | jq '.')
    
    # Add simulation result
    jq --argjson result "$simulation_result" '.results.simulation_results += [$result]' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
    
done

exit 0 