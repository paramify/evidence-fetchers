#!/bin/bash

# Helper script for AWS RDS TLS/SSL Configuration Validation

# Steps:
# 1. List all RDS instances with engine version and CA certificate
#    aws rds describe-db-instances

# 2. List all RDS parameter groups in use
#    aws rds describe-db-parameter-groups

# 3. Check TLS parameters for each parameter group
#    aws rds describe-db-parameters (ssl_min_protocol_version, ssl_max_protocol_version, rds.force_ssl)

# 4. Check parameter group sync status per instance
#    aws rds describe-db-instances (ParameterApplyStatus)

# 5. List available CA certificates
#    aws rds describe-certificates

# Output: Creates JSON report with RDS TLS/SSL configuration status

# Load environment and parse args
source "$(dirname "$0")/../common/env_loader.sh" "$@"

# Get caller identity for metadata
CALLER_IDENTITY=$(aws sts get-caller-identity --profile "$PROFILE" --output json 2>/dev/null || echo '{"Account":"unknown","Arn":"unknown"}')
ACCOUNT_ID=$(echo "$CALLER_IDENTITY" | jq -r '.Account // "unknown"')
ARN=$(echo "$CALLER_IDENTITY" | jq -r '.Arn // "unknown"')
DATETIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Get all RDS instances
instances_raw=$(aws rds describe-db-instances \
    --profile "$PROFILE" --region "$REGION" \
    --query 'DBInstances[*].{
        id:DBInstanceIdentifier,
        engine:Engine,
        engine_version:EngineVersion,
        ca_cert:CACertificateIdentifier,
        param_group:DBParameterGroups[0].DBParameterGroupName,
        param_status:DBParameterGroups[0].ParameterApplyStatus,
        status:DBInstanceStatus
    }' \
    --output json 2>/dev/null || echo '[]')

# Get unique parameter groups in use
param_groups=$(echo "$instances_raw" | jq -r '[.[].param_group] | unique[]')

# For each parameter group, fetch TLS-related parameters
pg_results=()
for pg in $param_groups; do
    pg_params=$(aws rds describe-db-parameters \
        --db-parameter-group-name "$pg" \
        --profile "$PROFILE" --region "$REGION" \
        --query 'Parameters[?ParameterName==`ssl_min_protocol_version` || ParameterName==`ssl_max_protocol_version` || ParameterName==`rds.force_ssl`].{name:ParameterName,value:ParameterValue,source:Source,apply_method:ApplyMethod,allowed_values:AllowedValues}' \
        --output json 2>/dev/null || echo '[]')

    force_ssl=$(echo "$pg_params" | jq -r '.[] | select(.name=="rds.force_ssl") | .value // "unknown"')
    ssl_min=$(echo "$pg_params" | jq -r '.[] | select(.name=="ssl_min_protocol_version") | .value // "unknown"')
    ssl_max=$(echo "$pg_params" | jq -r '.[] | select(.name=="ssl_max_protocol_version") | .value // ""')
    force_ssl_source=$(echo "$pg_params" | jq -r '.[] | select(.name=="rds.force_ssl") | .source // "unknown"')
    ssl_min_source=$(echo "$pg_params" | jq -r '.[] | select(.name=="ssl_min_protocol_version") | .source // "unknown"')

    pg_results+=("$(jq -n \
        --arg pg "$pg" \
        --arg force_ssl "$force_ssl" \
        --arg force_ssl_source "$force_ssl_source" \
        --arg ssl_min "$ssl_min" \
        --arg ssl_min_source "$ssl_min_source" \
        --arg ssl_max "$ssl_max" \
        --argjson raw_params "$pg_params" \
        '{
            parameter_group_name: $pg,
            force_ssl: ($force_ssl == "1"),
            force_ssl_source: $force_ssl_source,
            ssl_min_protocol_version: $ssl_min,
            ssl_min_source: $ssl_min_source,
            ssl_max_protocol_version: (if $ssl_max == "" then "unrestricted" else $ssl_max end),
            raw_parameters: $raw_params
        }')")
done

# Get CA certificates
certs_raw=$(aws rds describe-certificates \
    --profile "$PROFILE" --region "$REGION" \
    --query 'Certificates[*].{id:CertificateIdentifier,type:CertificateType,valid_from:ValidFrom,valid_till:ValidTill}' \
    --output json 2>/dev/null || echo '[]')

# Build instance results enriched with parameter group TLS data
instance_results=()
while IFS= read -r instance; do
    instance_id=$(echo "$instance" | jq -r '.id')
    instance_pg=$(echo "$instance" | jq -r '.param_group')
    instance_status=$(echo "$instance" | jq -r '.status')
    instance_param_status=$(echo "$instance" | jq -r '.param_status')
    instance_engine=$(echo "$instance" | jq -r '.engine')
    instance_engine_version=$(echo "$instance" | jq -r '.engine_version')
    instance_ca=$(echo "$instance" | jq -r '.ca_cert')

    # Find matching param group data
    pg_data="{}"
    for pg_entry in "${pg_results[@]}"; do
        if [ "$(echo "$pg_entry" | jq -r '.parameter_group_name')" = "$instance_pg" ]; then
            pg_data="$pg_entry"
            break
        fi
    done

    instance_results+=("$(jq -n \
        --arg id "$instance_id" \
        --arg engine "$instance_engine" \
        --arg version "$instance_engine_version" \
        --arg ca "$instance_ca" \
        --arg pg "$instance_pg" \
        --arg pg_sync "$instance_param_status" \
        --arg status "$instance_status" \
        --argjson pg_tls "$pg_data" \
        '{
            instance_id: $id,
            engine: $engine,
            engine_version: $version,
            ca_certificate: $ca,
            parameter_group: $pg,
            parameter_group_sync_status: $pg_sync,
            instance_status: $status,
            tls_configuration: $pg_tls
        }')")
done < <(echo "$instances_raw" | jq -c '.[]')

# Summary counts
total_instances=$(echo "$instances_raw" | jq 'length')
force_ssl_enabled=$(printf '%s\n' "${instance_results[@]}" | jq -s '[.[] | select(.tls_configuration.force_ssl == true)] | length')
tls12_min=$(printf '%s\n' "${instance_results[@]}" | jq -s '[.[] | select(.tls_configuration.ssl_min_protocol_version == "TLSv1.2")] | length')
params_in_sync=$(printf '%s\n' "${instance_results[@]}" | jq -s '[.[] | select(.parameter_group_sync_status == "in-sync")] | length')

# Combine all results
results_json=$(jq -n \
    --arg profile "$PROFILE" \
    --arg region "$REGION" \
    --arg datetime "$DATETIME" \
    --arg account_id "$ACCOUNT_ID" \
    --arg arn "$ARN" \
    --argjson instances "[$(IFS=,; echo "${instance_results[*]}")]" \
    --argjson parameter_groups "[$(IFS=,; echo "${pg_results[*]}")]" \
    --argjson certificates "$certs_raw" \
    --argjson total "$total_instances" \
    --argjson force_ssl_count "$force_ssl_enabled" \
    --argjson tls12_count "$tls12_min" \
    --argjson in_sync_count "$params_in_sync" \
    '{
        metadata: {
            profile: $profile,
            region: $region,
            datetime: $datetime,
            account_id: $account_id,
            arn: $arn
        },
        results: {
            instances: $instances,
            parameter_groups: $parameter_groups,
            ca_certificates: $certificates,
            summary: {
                total_instances: $total,
                force_ssl_enabled: $force_ssl_count,
                tls_1_2_minimum_enforced: $tls12_count,
                parameter_groups_in_sync: $in_sync_count
            }
        }
    }')

# Write results to JSON file
echo "$results_json" > "$OUTPUT_DIR/rds_tls_configuration.json"

exit 0