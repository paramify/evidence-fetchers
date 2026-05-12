# Checkov Fetcher Setup (GitLab-backed)

Checkov fetchers scan Terraform and Kubernetes manifests for IaC security issues. In this repo, the Checkov fetchers commonly **pull source code from GitLab** (via API download or git clone) using GitLab credentials, then run the local `checkov` CLI.

## Environment Variables

### Required (when scanning GitLab projects)

These fetchers use GitLab to retrieve IaC source files.

| Variable | Required | Description | Example |
|---|---:|---|---|
| `GITLAB_URL` | Yes | GitLab base URL | `https://gitlab.example.com` |
| `GITLAB_API_TOKEN` | Yes | GitLab token used for API downloads and clone auth | `glpat-...` |
| `GITLAB_PROJECT_ID` | Yes | GitLab project path or numeric ID | `group/project` |
| `GITLAB_BRANCH` | No | Branch/ref (default `main`) | `main` |
| `CHECKOV_CLONE_REPO` | No | `true` to clone full repo; default `false` uses API downloads | `false` |

### Optional Checkov behavior

| Variable | Required | Description |
|---|---:|---|
| `CHECKOV_REPO_ID` | No | Repo ID label used in Checkov output |
| `CHECKOV_BRANCH` | No | Branch label used in Checkov output |
| `CHECKOV_SOFT_FAIL` | No | If `true`, Checkov won’t exit non-zero on findings |
| `CHECKOV_COMPACT` | No | Compact output |
| `CHECKOV_DOWNLOAD_EXTERNAL_MODULES` | No | Download external Terraform modules |
| `CHECKOV_EVALUATE_VARIABLES` | No | Evaluate variables during scan |
| `CHECKOV_TERRAFORM_CHECKS` | No | Comma-separated Terraform check IDs to run |
| `CHECKOV_K8S_CHECKS` | No | Comma-separated Kubernetes check IDs to run |
| `CHECKOV_CHECKS` | No | Combined checks (auto-filtered by framework) |
| `CHECKOV_SKIP_CHECKS` | No | Additional checks to skip (merged with defaults) |
| `CHECKOV_SKIP_RESOURCES` | No | Resource patterns to skip (merged with defaults) |
| `CHECKOV_SKIP_PATHS` | No | Paths to skip during scan |
| `CHECKOV_EXTERNAL_CHECKS_DIR` | No | Path to custom checks directory |
| `CHECKOV_TERRAFORM_PLAN_FILE` | No | Terraform plan JSON file to scan instead of directory |
| `CHECKOV_REPO_ROOT` | No | Repo root for plan enrichment / skip comments |
| `CHECKOV_DEEP_ANALYSIS` | No | Enable deep analysis (requires plan + repo root) |

## Fetchers Covered

- `checkov_terraform.sh`
- `checkov_kubernetes.sh`

## API Endpoints Used (GitLab)

The scripts use GitLab API v4 to enumerate and download files:

| Purpose | Endpoint(s) | Method(s) |
|---|---|---|
| List repository tree | `/api/v4/projects/:id/repository/tree` | GET |
| Download raw file | `/api/v4/projects/:id/repository/files/:path/raw` | GET |

If `CHECKOV_CLONE_REPO=true`, the scripts also use `git clone` with the token embedded in the clone URL.

## Required Permissions (Least Privilege)

- **GitLab token scopes**: `read_api` (and `read_repository` if required by your GitLab instance).
- **Project access**: read-only access to the target repo.

## Creating a New GitLab Token

Follow the GitLab guidance in `fetchers/gitlab/API_KEY_SETUP.md`.

## Rotating the Token

Rotate `GITLAB_API_TOKEN` per the GitLab guide, then re-run a Checkov fetcher as a smoke test.

## Smoke Test

```bash
# Ensure checkov is installed
python -c "import shutil; assert shutil.which('checkov'), 'checkov not found (pip install checkov)'"

# Run one of the fetchers (expects GitLab env vars to be set)
bash fetchers/checkov/checkov_terraform.sh --output-dir /tmp/evidence
```

## Notes

- See `fetchers/checkov/README.md` for detailed configuration examples and skip lists.

