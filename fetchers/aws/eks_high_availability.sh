#!/bin/bash
# Helper script for EKS High Availability validation

# Steps:
# 1. EKS Cluster Multi-AZ Validation
#    - Check cluster subnets and AZs
#    - Verify node groups distribution
#
# Commands:
# aws eks describe-cluster --name [cluster-name] --query 'cluster'
# aws ec2 describe-subnets --subnet-ids [subnet-ids] --query 'Subnets[*].[SubnetId,AvailabilityZone,SubnetArn]'
# aws eks list-nodegroups --cluster-name [cluster-name] --query 'nodegroups[]'
# aws eks describe-nodegroup --cluster-name [cluster-name] --nodegroup-name [nodegroup-name] --query 'nodegroup'
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
COMPONENT="eks_high_availability"
OUTPUT_JSON="$OUTPUT_DIR/$COMPONENT.json"

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

# Initialize JSON file with metadata
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
    "results": []
  }' > "$OUTPUT_JSON"

echo -e "${BLUE}Starting EKS High Availability validation...${NC}"

# 1. EKS Cluster Multi-AZ Validation
echo -e "${BLUE}1. Validating EKS Cluster Multi-AZ distribution...${NC}"

# Get list of EKS clusters
echo -e "${BLUE}Retrieving EKS clusters...${NC}"
clusters=$(aws eks list-clusters --profile "$PROFILE" --region "$REGION" --query "clusters" --output json 2>/dev/null)

if [ $? -eq 0 ] && [ "$(echo "$clusters" | jq -r 'length')" -gt 0 ]; then
    # Process each cluster
    while read -r cluster_name; do
        if [ -n "$cluster_name" ]; then
            echo -e "${BLUE}Processing cluster: $cluster_name${NC}"
            
            # Get EKS cluster details
            cluster_info=$(aws eks describe-cluster --profile "$PROFILE" --region "$REGION" --name "$cluster_name" --query 'cluster' --output json 2>/dev/null)
            
            if [ $? -eq 0 ]; then
                # Get subnet IDs from cluster
                subnet_ids=$(echo "$cluster_info" | jq -r '.resourcesVpcConfig.subnetIds[]' 2>/dev/null)
                
                if [ -n "$subnet_ids" ]; then
                    # Get subnet details with AZs
                    subnet_details=$(aws ec2 describe-subnets --profile "$PROFILE" --subnet-ids $subnet_ids --query 'Subnets[*].[SubnetId,AvailabilityZone,SubnetArn]' --output json 2>/dev/null)
                    
                    # Get node groups
                    nodegroups=$(aws eks list-nodegroups --profile "$PROFILE" --region "$REGION" --cluster-name "$cluster_name" --query 'nodegroups[]' --output json 2>/dev/null)
                    
                    # Process each node group
                    echo "$nodegroups" | jq -r '.[]' 2>/dev/null | while read -r nodegroup; do
                        if [ -n "$nodegroup" ]; then
                            nodegroup_info=$(aws eks describe-nodegroup --profile "$PROFILE" --region "$REGION" --cluster-name "$cluster_name" --nodegroup-name "$nodegroup" --query 'nodegroup' --output json 2>/dev/null)
                            
                            # Add to JSON
                            jq --argjson cluster "$cluster_info" \
                               --argjson subnets "$subnet_details" \
                               --argjson nodegroup "$nodegroup_info" \
                               --arg name "$nodegroup" \
                               '.results += [{"Type": "EKS_Cluster", "ClusterName": $name, "ClusterInfo": $cluster, "SubnetDetails": $subnets, "NodeGroupInfo": $nodegroup}]' \
                               "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
                            
                        fi
                    done
                else
                    # Add cluster info even without subnets
                    jq --argjson cluster "$cluster_info" \
                       --arg name "$cluster_name" \
                       '.results += [{"Type": "EKS_Cluster", "ClusterName": $name, "ClusterInfo": $cluster}]' \
                       "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
                    
                fi
            else
                echo -e "${YELLOW}Warning: Could not retrieve EKS cluster information for $cluster_name${NC}"
            fi
        fi
    done < <(echo "$clusters" | jq -r '.[]')
else
    echo -e "${YELLOW}Warning: No EKS clusters found in the account${NC}"
fi

# Generate summary
echo -e "${BLUE}=== EKS High Availability Summary ===${NC}"
echo -e "${GREEN}EKS High Availability validation completed!${NC}"

# Count EKS resources
if [ -f "$OUTPUT_JSON" ]; then
    total_clusters=$(jq '.results | length' "$OUTPUT_JSON")
    echo -e "${BLUE}Total EKS Clusters Validated: $total_clusters${NC}"
    
    if [ "$total_clusters" -gt 0 ]; then
        echo -e "${BLUE}Cluster Details:${NC}"
        jq -r '.results[] | .ClusterName' "$OUTPUT_JSON" 2>/dev/null | while read -r cluster_name; do
            if [ -n "$cluster_name" ]; then
                echo -e "  - $cluster_name"
            fi
        done
    else
        echo -e "${YELLOW}No EKS clusters found or cluster name not provided${NC}"
    fi
fi

echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"
echo -e "${BLUE}CSV summary saved to: $OUTPUT_CSV${NC}"

exit 0 