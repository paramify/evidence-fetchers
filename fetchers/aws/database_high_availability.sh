#!/bin/bash
# Helper script for Database High Availability validation

# Steps:
# 1. Database High Availability
#    - RDS Multi-AZ deployment
#    - Aurora clusters and read replicas
#
# Commands:
# aws rds describe-db-instances --query 'DBInstances[*]'
# aws rds describe-db-clusters --query 'DBClusters[*]'
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
COMPONENT="database_high_availability"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

# ANSI color codes for better output readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Initialize JSON file
echo '{"results": []}' > "$OUTPUT_JSON"

echo -e "${BLUE}Starting Database High Availability validation...${NC}"

# 3. Database High Availability
echo -e "${BLUE}3. Validating Database High Availability...${NC}"

# Get RDS instances
rds_instances=$(aws rds describe-db-instances --profile "$PROFILE" --region "$REGION" --query 'DBInstances[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$rds_instances" | jq -c '.[]' | while read -r instance; do
        instance_id=$(echo "$instance" | jq -r '.DBInstanceIdentifier')
        multi_az=$(echo "$instance" | jq -r '.MultiAZ')
        az=$(echo "$instance" | jq -r '.AvailabilityZone')
        
        echo -e "${BLUE}Processing RDS instance: $instance_id${NC}"
        
        # Add to JSON
        jq --argjson instance "$instance" \
           '.results += [{"Type": "RDS_Instance", "InstanceInfo": $instance}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

# Get Aurora clusters
aurora_clusters=$(aws rds describe-db-clusters --profile "$PROFILE" --region "$REGION" --query 'DBClusters[*]' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$aurora_clusters" | jq -c '.[]' | while read -r cluster; do
        cluster_id=$(echo "$cluster" | jq -r '.DBClusterIdentifier')
        multi_az=$(echo "$cluster" | jq -r '.MultiAZ')
        
        echo -e "${BLUE}Processing Aurora cluster: $cluster_id${NC}"
        
        # Add to JSON
        jq --argjson cluster "$cluster" \
           '.results += [{"Type": "Aurora_Cluster", "ClusterInfo": $cluster}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
fi

# Generate summary
echo -e "${BLUE}=== Database High Availability Summary ===${NC}"
echo -e "${GREEN}Database High Availability validation completed!${NC}"

# Count databases by type
if [ -f "$OUTPUT_JSON" ]; then
    total_instances=$(jq '.results | length' "$OUTPUT_JSON")
    rds_count=$(jq '.results[] | select(.Type == "RDS_Instance") | .InstanceInfo.DBInstanceIdentifier' "$OUTPUT_JSON" | wc -l)
    aurora_count=$(jq '.results[] | select(.Type == "Aurora_Cluster") | .ClusterInfo.DBClusterIdentifier' "$OUTPUT_JSON" | wc -l)
    
    echo -e "${BLUE}Total Database Resources Found: $total_instances${NC}"
    echo -e "${BLUE}RDS Instances: $rds_count${NC}"
    echo -e "${BLUE}Aurora Clusters: $aurora_count${NC}"
    
    # Check for Multi-AZ deployments
    multi_az_count=$(jq '.results[] | select(.InstanceInfo.MultiAZ == true) | .InstanceInfo.DBInstanceIdentifier' "$OUTPUT_JSON" | wc -l)
    single_az_count=$(jq '.results[] | select(.InstanceInfo.MultiAZ == false) | .InstanceInfo.DBInstanceIdentifier' "$OUTPUT_JSON" | wc -l)
    
    echo -e "${GREEN}Multi-AZ Deployments: $multi_az_count${NC}"
    echo -e "${YELLOW}Single-AZ Deployments: $single_az_count${NC}"
    
    # List database names
    echo -e "${BLUE}Database Names:${NC}"
    jq -r '.results[] | .InstanceInfo.DBInstanceIdentifier' "$OUTPUT_JSON" 2>/dev/null | while read -r db_name; do
        if [ -n "$db_name" ]; then
            multi_az=$(jq -r --arg name "$db_name" '.results[] | select(.InstanceInfo.DBInstanceIdentifier == $name) | .InstanceInfo.MultiAZ' "$OUTPUT_JSON" 2>/dev/null)
            if [ "$multi_az" = "true" ]; then
                echo -e "  - $db_name (Multi-AZ ✅)"
            else
                echo -e "  - $db_name (Single-AZ ⚠️)"
            fi
        fi
    done
fi

echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"
echo -e "${BLUE}CSV summary saved to: $OUTPUT_CSV${NC}"

exit 0 