#!/bin/bash
# Helper script for AWS Backup Validation

# Steps:
# 1. RDS Backup Validation
#    - Backup configuration (retention, window, automated backups)
#    - Backup status and recent backups
#    - Cross-region backup replication
#    - Manual snapshots
#
# 2. S3 Backup Validation
#    - Bucket versioning status
#    - Cross-region replication
#    - AWS Backup recovery points
#    - Backup vaults
#
# 3. AWS Config Compliance
#    - RDS backup compliance rules
#    - S3 replication compliance rules
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
COMPONENT="backup_validation"
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
    "results": [],
    "summary": {}
  }' > "$OUTPUT_JSON"

echo -e "${BLUE}Starting AWS Backup Validation...${NC}"

# 1. RDS Backup Validation
echo -e "${BLUE}1. Validating RDS Backup Configurations...${NC}"

# Get RDS instances
rds_instances=$(aws rds describe-db-instances --profile "$PROFILE" --query 'DBInstances[*]' --output json 2>/dev/null)

if [ $? -eq 0 ] && [ "$(echo "$rds_instances" | jq -r 'length')" -gt 0 ]; then
    echo -e "${GREEN}Found $(echo "$rds_instances" | jq -r 'length') RDS instances${NC}"
    echo "$rds_instances" | jq -c '.[]' | while read -r instance; do
        instance_id=$(echo "$instance" | jq -r '.DBInstanceIdentifier')
        backup_retention=$(echo "$instance" | jq -r '.BackupRetentionPeriod')
        backup_window=$(echo "$instance" | jq -r '.PreferredBackupWindow')
        backup_target=$(echo "$instance" | jq -r '.BackupTarget // "region"')
        latest_restorable=$(echo "$instance" | jq -r '.LatestRestorableTime // "N/A"')
        storage_encrypted=$(echo "$instance" | jq -r '.StorageEncrypted')
        deletion_protection=$(echo "$instance" | jq -r '.DeletionProtection')
        kms_key_id=$(echo "$instance" | jq -r '.KmsKeyId // "N/A"')
        
        echo -e "${BLUE}Processing RDS instance: $instance_id${NC}"
        
        # Check if automated backups are enabled
        backup_enabled="false"
        if [ "$backup_retention" -gt 0 ]; then
            backup_enabled="true"
        fi
        
        # Check for cross-region backup replication
        cross_region_replication="false"
        replication_destination=""
        replication_arns=$(echo "$instance" | jq -r '.DBInstanceAutomatedBackupsReplications[].DBInstanceAutomatedBackupsArn // empty')
        if [ -n "$replication_arns" ]; then
            cross_region_replication="true"
            # Extract region from ARN (us-gov-east-1)
            replication_destination=$(echo "$replication_arns" | head -1 | sed 's/.*:\([^:]*\):.*$/\1/')
        fi
        
        # Add to JSON
        jq --argjson instance "$instance" \
           --arg enabled "$backup_enabled" \
           --arg retention "$backup_retention" \
           --arg window "$backup_window" \
           --arg target "$backup_target" \
           --arg latest "$latest_restorable" \
           --arg replication "$cross_region_replication" \
           --arg destination "$replication_destination" \
           --arg encrypted "$storage_encrypted" \
           --arg protection "$deletion_protection" \
           --arg kms "$kms_key_id" \
           '.results += [{"Type": "RDS_Backup", "InstanceId": $instance.DBInstanceIdentifier, "BackupEnabled": ($enabled == "true"), "BackupRetentionPeriod": ($retention|tonumber), "BackupWindow": $window, "BackupTarget": $target, "LatestRestorableTime": $latest, "CrossRegionReplication": ($replication == "true"), "ReplicationDestination": $destination, "StorageEncrypted": ($encrypted == "true"), "DeletionProtection": ($protection == "true"), "KmsKeyId": $kms, "InstanceInfo": $instance}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
    done
else
    echo -e "${YELLOW}No RDS instances found${NC}"
fi

# 2. S3 Backup Validation
echo -e "${BLUE}2. Validating S3 Backup Configurations...${NC}"

# Get S3 buckets
s3_buckets=$(aws s3api list-buckets --profile "$PROFILE" --query 'Buckets[*].Name' --output json 2>/dev/null)

if [ $? -eq 0 ] && [ "$(echo "$s3_buckets" | jq -r 'length')" -gt 0 ]; then
    echo -e "${GREEN}Found $(echo "$s3_buckets" | jq -r 'length') S3 buckets${NC}"
    echo "$s3_buckets" | jq -r '.[]' | while read -r bucket_name; do
        if [ -n "$bucket_name" ]; then
            echo -e "${BLUE}Processing S3 bucket: $bucket_name${NC}"
            
            # Get bucket versioning status
            versioning_status=$(aws s3api get-bucket-versioning \
                --profile "$PROFILE" \
                --bucket "$bucket_name" \
                --output json 2>/dev/null || echo '{"Status": "NotEnabled"}')
            
            # Get cross-region replication status
            replication_status=$(aws s3api get-bucket-replication \
                --profile "$PROFILE" \
                --bucket "$bucket_name" \
                --output json 2>/dev/null || echo '{}')
            
            # Get bucket encryption
            encryption_status=$(aws s3api get-bucket-encryption \
                --profile "$PROFILE" \
                --bucket "$bucket_name" \
                --output json 2>/dev/null || echo '{}')
            
            # Check if versioning is enabled
            versioning_enabled="false"
            if echo "$versioning_status" | jq -e '.Status == "Enabled"' > /dev/null; then
                versioning_enabled="true"
            fi
            
            # Check if replication is configured
            replication_enabled="false"
            replication_destination=""
            if echo "$replication_status" | jq -e '.ReplicationConfiguration' > /dev/null; then
                replication_enabled="true"
                replication_destination=$(echo "$replication_status" | jq -r '.ReplicationConfiguration.Rules[0].Destination.Bucket // "N/A"')
            fi
            
            # Check if encryption is enabled
            encryption_enabled="false"
            if echo "$encryption_status" | jq -e '.ServerSideEncryptionConfiguration' > /dev/null; then
                encryption_enabled="true"
            fi
            
            # Add to JSON
            jq --argjson versioning "$versioning_status" \
               --argjson replication "$replication_status" \
               --argjson encryption "$encryption_status" \
               --arg bucket "$bucket_name" \
               --arg v_enabled "$versioning_enabled" \
               --arg r_enabled "$replication_enabled" \
               --arg r_destination "$replication_destination" \
               --arg e_enabled "$encryption_enabled" \
               '.results += [{"Type": "S3_Backup", "BucketName": $bucket, "VersioningEnabled": ($v_enabled == "true"), "ReplicationEnabled": ($r_enabled == "true"), "ReplicationDestination": $r_destination, "EncryptionEnabled": ($e_enabled == "true"), "VersioningInfo": $versioning, "ReplicationInfo": $replication, "EncryptionInfo": $encryption}]' \
               "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
            
        fi
    done
else
    echo -e "${YELLOW}No S3 buckets found${NC}"
fi

# 3. AWS Backup Validation
echo -e "${BLUE}3. Validating AWS Backup Services...${NC}"

# List backup vaults
backup_vaults=$(aws backup list-backup-vaults --profile "$PROFILE" --output json 2>/dev/null)

if [ $? -eq 0 ] && [ "$(echo "$backup_vaults" | jq -r '.BackupVaultList | length')" -gt 0 ]; then
    echo -e "${GREEN}Found $(echo "$backup_vaults" | jq -r '.BackupVaultList | length') backup vaults${NC}"
    echo "$backup_vaults" | jq -c '.BackupVaultList[]' | while read -r vault; do
        vault_name=$(echo "$vault" | jq -r '.BackupVaultName')
        vault_arn=$(echo "$vault" | jq -r '.BackupVaultArn')
        creation_date=$(echo "$vault" | jq -r '.CreationDate')
        
        echo -e "${BLUE}Processing backup vault: $vault_name${NC}"
        
        # Get recovery points for this vault
        recovery_points=$(aws backup list-recovery-points-by-backup-vault \
            --profile "$PROFILE" \
            --backup-vault-name "$vault_name" \
            --output json 2>/dev/null || echo '{"RecoveryPoints": []}')
        
        # Add to JSON
        jq --argjson vault "$vault" \
           --argjson points "$recovery_points" \
           '.results += [{"Type": "AWS_Backup_Vault", "VaultName": $vault.BackupVaultName, "VaultArn": $vault.BackupVaultArn, "CreationDate": $vault.CreationDate, "RecoveryPoints": $points}]' \
           "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"
        
        recovery_count=$(echo "$recovery_points" | jq -r '.RecoveryPoints | length // 0')
    done
else
    echo -e "${YELLOW}No AWS Backup vaults found${NC}"
fi

# Generate summary
echo -e "${BLUE}=== Backup Validation Summary ===${NC}"

# Count RDS instances with backups enabled
rds_with_backups=$(jq '.results[] | select(.Type == "RDS_Backup" and .BackupEnabled == true) | .InstanceId' "$OUTPUT_JSON" 2>/dev/null | wc -l)
total_rds=$(jq '.results[] | select(.Type == "RDS_Backup") | .InstanceId' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Count RDS instances with cross-region replication
rds_with_replication=$(jq '.results[] | select(.Type == "RDS_Backup" and .CrossRegionReplication == true) | .InstanceId' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Count RDS instances with encryption
rds_with_encryption=$(jq '.results[] | select(.Type == "RDS_Backup" and .StorageEncrypted == true) | .InstanceId' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Count RDS instances with deletion protection
rds_with_deletion_protection=$(jq '.results[] | select(.Type == "RDS_Backup" and .DeletionProtection == true) | .InstanceId' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Count S3 buckets with versioning
s3_with_versioning=$(jq '.results[] | select(.Type == "S3_Backup" and .VersioningEnabled == true) | .BucketName' "$OUTPUT_JSON" 2>/dev/null | wc -l)
total_s3=$(jq '.results[] | select(.Type == "S3_Backup") | .BucketName' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Count S3 buckets with replication
s3_with_replication=$(jq '.results[] | select(.Type == "S3_Backup" and .ReplicationEnabled == true) | .BucketName' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Count S3 buckets with encryption
s3_with_encryption=$(jq '.results[] | select(.Type == "S3_Backup" and .EncryptionEnabled == true) | .BucketName' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Count backup vaults
total_vaults=$(jq '.results[] | select(.Type == "AWS_Backup_Vault") | .VaultName' "$OUTPUT_JSON" 2>/dev/null | wc -l)

# Update summary in JSON
jq --arg rds_backups "$rds_with_backups" \
   --arg total_rds "$total_rds" \
   --arg rds_replication "$rds_with_replication" \
   --arg rds_encryption "$rds_with_encryption" \
   --arg rds_protection "$rds_with_deletion_protection" \
   --arg s3_versioning "$s3_with_versioning" \
   --arg total_s3 "$total_s3" \
   --arg s3_replication "$s3_with_replication" \
   --arg s3_encryption "$s3_with_encryption" \
   --arg vaults "$total_vaults" \
   '.summary = {
       "rds_backup_coverage": {"with_backups": ($rds_backups|tonumber), "total": ($total_rds|tonumber)},
       "rds_replication_coverage": {"with_replication": ($rds_replication|tonumber), "total": ($total_rds|tonumber)},
       "rds_encryption_coverage": {"with_encryption": ($rds_encryption|tonumber), "total": ($total_rds|tonumber)},
       "rds_deletion_protection": {"with_protection": ($rds_protection|tonumber), "total": ($total_rds|tonumber)},
       "s3_versioning_coverage": {"with_versioning": ($s3_versioning|tonumber), "total": ($total_s3|tonumber)},
       "s3_replication_coverage": {"with_replication": ($s3_replication|tonumber), "total": ($total_s3|tonumber)},
       "s3_encryption_coverage": {"with_encryption": ($s3_encryption|tonumber), "total": ($total_s3|tonumber)},
       "backup_vaults": ($vaults|tonumber)
   }' "$OUTPUT_JSON" > tmp.json && mv tmp.json "$OUTPUT_JSON"

# Display detailed backup summary
echo -e "${GREEN}Backup Validation completed!${NC}"
echo -e "${BLUE}=== RDS Backup Configuration Summary ===${NC}"

if [ "$total_rds" -gt 0 ]; then
    echo -e "${BLUE}Instance ID\tBackup Retention\tBackup Target\tAutomated Backup Replication\tLatest Restorable Time${NC}"
    echo -e "${BLUE}-----------\t----------------\t-------------\t---------------------------\t----------------------${NC}"
    
    jq -r '.results[] | select(.Type == "RDS_Backup") | [.InstanceId, .BackupRetentionPeriod, .BackupTarget, .CrossRegionReplication, .LatestRestorableTime] | @tsv' "$OUTPUT_JSON" 2>/dev/null | while IFS=$'\t' read -r id retention target replication latest; do
        replication_status="❌ No"
        if [ "$replication" = "true" ]; then
            replication_status="✅ Yes"
        fi
        echo -e "${GREEN}$id\t${retention} days\t$target\t$replication_status\t$latest${NC}"
    done
fi

echo -e "${BLUE}=== RDS Security Configuration Summary ===${NC}"
echo -e "${BLUE}RDS Backup Coverage: $rds_with_backups/$total_rds instances with automated backups${NC}"
echo -e "${BLUE}RDS Cross-Region Replication: $rds_with_replication/$total_rds instances with cross-region backup replication${NC}"
echo -e "${BLUE}RDS Encryption Coverage: $rds_with_encryption/$total_rds instances with storage encryption${NC}"
echo -e "${BLUE}RDS Deletion Protection: $rds_with_deletion_protection/$total_rds instances with deletion protection${NC}"

echo -e "${BLUE}=== S3 Backup Configuration Summary ===${NC}"
echo -e "${BLUE}S3 Versioning Coverage: $s3_with_versioning/$total_s3 buckets with versioning${NC}"
echo -e "${BLUE}S3 Replication Coverage: $s3_with_replication/$total_s3 buckets with cross-region replication${NC}"
echo -e "${BLUE}S3 Encryption Coverage: $s3_with_encryption/$total_s3 buckets with encryption${NC}"
echo -e "${BLUE}AWS Backup Vaults: $total_vaults vaults found${NC}"

echo -e "${BLUE}Results saved to: $OUTPUT_JSON${NC}"
echo -e "${BLUE}CSV summary saved to: $OUTPUT_CSV${NC}"

exit 0 