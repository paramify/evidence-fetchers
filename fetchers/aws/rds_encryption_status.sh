#!/bin/bash

# Helper script for AWS RDS Encryption at Rest Validation

# Steps:
# 1. List and check RDS instance encryption at rest
#    aws rds describe-db-instances --query "DBInstances[*].DBInstanceIdentifier"
#    aws rds describe-db-instances --db-instance-identifier [instance-name]

# 2. List and check RDS Aurora cluster encryption at rest
#    aws rds describe-db-clusters --query "DBClusters[*].DBClusterIdentifier"
#    aws rds describe-db-clusters --db-cluster-identifier [cluster-name]

# Output: Creates JSON report with RDS encryption at rest status

# Load environment and parse args
source "$(dirname "$0")/../common/env_loader.sh" "$@"

# Initialize counters
total_databases=0
encrypted_databases=0

# Get caller identity for metadata
CALLER_IDENTITY=$(aws sts get-caller-identity --profile "$PROFILE" --output json 2>/dev/null || echo '{"Account":"unknown","Arn":"unknown"}')
ACCOUNT_ID=$(echo "$CALLER_IDENTITY" | jq -r '.Account // "unknown"')
ARN=$(echo "$CALLER_IDENTITY" | jq -r '.Arn // "unknown"')
DATETIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Check RDS instances
rds_results=()
for instance in $(aws rds describe-db-instances --profile "$PROFILE" --region "$REGION" --query "DBInstances[*].DBInstanceIdentifier" --output text); do
    total_databases=$((total_databases + 1))
    instance_details=$(aws rds describe-db-instances --db-instance-identifier "$instance" --profile "$PROFILE" --region "$REGION")
    encrypted=$(echo "$instance_details" | jq -r '.DBInstances[0].StorageEncrypted')
    kms_key_id=$(echo "$instance_details" | jq -r '.DBInstances[0].KmsKeyId // "None"')
    engine=$(echo "$instance_details" | jq -r '.DBInstances[0].Engine')
    
    rds_results+=("$(jq -n \
        --arg name "$instance" \
        --arg type "rds_instance" \
        --argjson enc "$encrypted" \
        --arg kms "$kms_key_id" \
        --arg eng "$engine" \
        '{
            name: $name,
            type: $type,
            encrypted: $enc,
            kms_key_id: $kms,
            engine: $eng
        }')")
    if [ "$encrypted" = "true" ]; then
        encrypted_databases=$((encrypted_databases + 1))
    fi
done

# Check RDS Aurora clusters
aurora_results=()
for cluster in $(aws rds describe-db-clusters --profile "$PROFILE" --region "$REGION" --query "DBClusters[*].DBClusterIdentifier" --output text); do
    total_databases=$((total_databases + 1))
    cluster_details=$(aws rds describe-db-clusters --db-cluster-identifier "$cluster" --profile "$PROFILE" --region "$REGION")
    encrypted=$(echo "$cluster_details" | jq -r '.DBClusters[0].StorageEncrypted')
    kms_key_id=$(echo "$cluster_details" | jq -r '.DBClusters[0].KmsKeyId // "None"')
    engine=$(echo "$cluster_details" | jq -r '.DBClusters[0].Engine')
    
    aurora_results+=("$(jq -n \
        --arg name "$cluster" \
        --arg type "rds_aurora" \
        --argjson enc "$encrypted" \
        --arg kms "$kms_key_id" \
        --arg eng "$engine" \
        '{
            name: $name,
            type: $type,
            encrypted: $enc,
            kms_key_id: $kms,
            engine: $eng
        }')")
    if [ "$encrypted" = "true" ]; then
        encrypted_databases=$((encrypted_databases + 1))
    fi
done

# Combine results with metadata
results_json=$(jq -n \
    --arg profile "$PROFILE" \
    --arg region "$REGION" \
    --arg datetime "$DATETIME" \
    --arg account_id "$ACCOUNT_ID" \
    --arg arn "$ARN" \
    --argjson rds "[$(IFS=,; echo "${rds_results[*]}")]" \
    --argjson aurora "[$(IFS=,; echo "${aurora_results[*]}")]" \
    --arg total "$total_databases" \
    --arg encrypted "$encrypted_databases" \
    --arg percentage "$(( (encrypted_databases * 100) / total_databases ))" \
    '{
        metadata: {
            profile: $profile,
            region: $region,
            datetime: $datetime,
            account_id: $account_id,
            arn: $arn
        },
        results: {
            storage_inventory: {
                instances: $rds,
                clusters: $aurora
            },
            summary: {
                total_storage: ($total | tonumber),
                encrypted_storage: ($encrypted | tonumber),
                encryption_percentage: ($percentage | tonumber)
            }
        }
    }')

# Write results to JSON file
echo "$results_json" > "$OUTPUT_DIR/rds_encryption_status.json"


exit 0 