# AWS Fetcher Credential Setup (IAM / AWS CLI)

AWS fetchers in this repo use the **AWS CLI** (and your local AWS credential chain) rather than a single API token.

## Environment Variables

Most AWS shell fetchers source `fetchers/common/env_loader.sh`, which reads:

| Variable | Required | Description | Example |
|---|---:|---|---|
| `AWS_PROFILE` | Usually | AWS CLI profile name to use | `gov_readonly` |
| `AWS_DEFAULT_REGION` | Usually | Default AWS region for regional APIs | `us-gov-west-1` |
| `EVIDENCE_DIR` | No | Output directory (defaults to `./evidence`) | `./evidence` |

Some fetchers also accept fetcher-specific flags via environment variables. Example:

| Variable | Required | Description | Example |
|---|---:|---|---|
| `IAM_ROLES_FETCHER` | No | Extra flags for `iam_roles.sh` | `--exclude-aws-managed-roles` |

## Fetchers Covered

All `*.sh` scripts in `fetchers/aws/` that call `aws ...` commands using `--profile "$PROFILE"` and `--region "$REGION"` from the shared env loader.

## APIs / Commands Used

AWS fetchers call AWS service APIs via the AWS CLI (examples include):

- `aws sts get-caller-identity`
- `aws iam list-roles`, `aws iam get-role`, `aws iam list-attached-role-policies`, …
- `aws guardduty list-detectors`, `aws guardduty get-detector`
- Many other service-specific `aws <service> <operation>` calls depending on the script

## Required Permissions (Least Privilege)

- Prefer a dedicated **read-only role** or **read-only IAM policy** for evidence collection.
- Minimum permissions depend on which AWS fetchers you run. As a baseline:
  - `sts:GetCallerIdentity`
  - Read/list permissions for each service used (IAM, GuardDuty, Config, CloudTrail, S3, RDS, EKS, WAFv2, etc.)

If you want strict least privilege, build a policy by enumerating only the services used by the fetchers you select.

## Setting Up Credentials

### Option A: AWS SSO (recommended for humans)

1. Configure SSO profiles in `~/.aws/config` (outside this repo).
2. Set:

```bash
export AWS_PROFILE="gov_readonly"
export AWS_DEFAULT_REGION="us-gov-west-1"
```

3. Authenticate:

```bash
aws sso login --profile "$AWS_PROFILE"
```

### Option B: AssumeRole / static access keys (automation)

Use a CI-friendly credential method (instance profile, OIDC, or access keys) that yields a role with the permissions above. Then set `AWS_DEFAULT_REGION` and optionally `AWS_PROFILE`.

## Rotating Credentials

- Rotation depends on your credential type:
  - **SSO**: re-auth via `aws sso login` as needed.
  - **Access keys**: rotate keys per your IAM policy and update the secret in your secrets manager.
  - **OIDC/instance roles**: no manual rotation (short-lived credentials).

## Smoke Test

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --output json | python3 -m json.tool | head -20
```

## Notes

- Region matters for most services; set `AWS_DEFAULT_REGION` even if some IAM calls are global.

