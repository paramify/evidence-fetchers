# Kubernetes / EKS Fetcher Setup (AWS + kubectl)

Kubernetes fetchers in this repo primarily target **Amazon EKS** clusters. They use:

- **AWS CLI** to enumerate clusters and update kubeconfig (`aws eks ...`)
- **kubectl** to query cluster resources for evidence

## Environment Variables

These scripts source `fetchers/common/env_loader.sh`, which reads:

| Variable | Required | Description | Example |
|---|---:|---|---|
| `AWS_PROFILE` | Usually | AWS CLI profile name to use | `gov_readonly` |
| `AWS_DEFAULT_REGION` | Usually | AWS region containing EKS clusters | `us-gov-west-1` |
| `EVIDENCE_DIR` | No | Output directory (defaults to `./evidence`) | `./evidence` |

## Fetchers Covered

- `kubectl_security.sh`
- `eks_microservice_segmentation.sh`
- `eks_pod_inventory.sh`

## Commands / Endpoints Used

### AWS (via AWS CLI)

- `aws eks list-clusters`
- `aws eks update-kubeconfig` (requires access to describe cluster)
- `aws ec2 describe-instances` (used by `eks_microservice_segmentation.sh`)
- `aws sso login` (used by `eks_pod_inventory.sh` when running with SSO profiles)

### Kubernetes (via kubectl)

- `kubectl cluster-info`, `kubectl get nodes`
- `kubectl get pods -A ...`
- `kubectl get networkpolicies -A ...`
- `kubectl get validatingwebhookconfigurations -A ...`
- `kubectl get securitygrouppolicies.vpcresources.k8s.aws -A ...` (if the CRD is installed)

## Required Permissions (Least Privilege)

### AWS IAM permissions

Minimum AWS permissions depend on the scripts you run, but commonly include:

- `eks:ListClusters`
- `eks:DescribeCluster`
- `ec2:DescribeInstances` (for node security group lookups)

### EKS / Kubernetes RBAC permissions

Your AWS identity must also be mapped into the cluster (e.g., via the `aws-auth` ConfigMap or access entries) with read permissions for:

- Pods (all namespaces)
- NetworkPolicies (all namespaces)
- ValidatingWebhookConfigurations (cluster-scoped)
- Nodes (cluster-scoped)
- Any additional CRDs queried by the scripts (e.g., `securitygrouppolicies.vpcresources.k8s.aws`)

## Setup Steps

1. Install dependencies:
   - `aws` CLI
   - `kubectl`
   - `jq`
2. Ensure your AWS credentials work (SSO or assumed role).
3. Set the environment variables:

```bash
export AWS_PROFILE="gov_readonly"
export AWS_DEFAULT_REGION="us-gov-west-1"
```

4. Confirm you can reach EKS:

```bash
aws eks list-clusters --profile "$AWS_PROFILE" --region "$AWS_DEFAULT_REGION" --output json \
  | python3 -m json.tool | head -30
```

5. Run a fetcher; it will call `aws eks update-kubeconfig` per-cluster and then query via `kubectl`.

## Rotation

Rotation follows your AWS credential mechanism:

- **SSO**: re-auth via `aws sso login`
- **OIDC/instance roles**: no manual rotation (short-lived creds)
- **Access keys**: rotate in IAM and update your secrets store

## Notes

- These scripts assume `kubectl` can access each cluster after `aws eks update-kubeconfig` runs. If you get auth errors, fix the EKS access mapping/RBAC for the AWS identity you’re using.

