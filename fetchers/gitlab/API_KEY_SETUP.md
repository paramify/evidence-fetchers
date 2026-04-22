# GitLab API Token Setup

## Environment Variables

All GitLab fetchers in this folder use the GitLab REST API v4.

| Variable | Required | Description | Example |
|---|---:|---|---|
| `GITLAB_URL` | Yes | GitLab base URL (no trailing slash preferred) | `https://gitlab.example.com` |
| `GITLAB_API_TOKEN` | Yes | GitLab access token used as `PRIVATE-TOKEN` header | `glpat-...` |
| `GITLAB_PROJECT_ID` | No | Project path or numeric ID (defaults to `group/project`) | `mygroup/myrepo` |
| `GITLAB_BRANCH` | No | Branch/ref for repository file endpoints (default `main`) | `main` |
| `GITLAB_FILE_PATTERNS` | No | Comma-separated patterns for project inventory | `.tf,.yml,Dockerfile` |
| `GITLAB_MR_STATE` | No | MR state filter (default `merged`) | `merged` |
| `GITLAB_MR_DAYS_BACK` | No | How far back to query MRs (default `30`) | `30` |
| `GITLAB_MR_MAX_RESULTS` | No | Max MRs to retrieve (default `50`) | `50` |

## Fetchers Covered

- `gitlab_project_summary.py`
- `gitlab_ci_cd_pipeline_config.py`
- `gitlab_merge_request_summary.py`

## API Endpoints Used

| Fetcher | Endpoint(s) | Method(s) |
|---|---|---|
| `gitlab_project_summary.py` | `/api/v4/projects/:id/repository/tree` | GET |
| `gitlab_ci_cd_pipeline_config.py` | `/api/v4/projects/:id/repository/files/.gitlab-ci.yml` | GET |
| `gitlab_merge_request_summary.py` | `/api/v4/projects/:id/merge_requests` | GET |
| `gitlab_merge_request_summary.py` | `/api/v4/projects/:id/merge_requests/:iid/approvals` | GET |
| `gitlab_merge_request_summary.py` | `/api/v4/projects/:id/merge_requests/:iid/approval_state` | GET |
| `gitlab_merge_request_summary.py` | `/api/v4/projects/:id/merge_requests/:iid/discussions` | GET |
| `gitlab_merge_request_summary.py` | `/api/v4/projects/:id/merge_requests/:iid/changes` | GET |

## Required Permissions (Least Privilege)

- **Token type**: Prefer a **Project Access Token** scoped to the specific project being scanned.
- **Scopes**: **`read_api`** (and **`read_repository`** if your GitLab requires it for repository file/tree endpoints).
- **Project role**: Read-only role sufficient to read repository + MRs (e.g., Reporter or equivalent).

## Creating a New Token (Recommended: Project Access Token)

1. Open your GitLab project.
2. Navigate to **Settings → Access Tokens** (may appear as **Settings → Access Tokens** or **Settings → Access Tokens → Project access tokens** depending on GitLab version).
3. Create a token named `paramify-evidence-fetchers`.
4. Select the scopes:
   - `read_api`
   - `read_repository` (if needed for repo file/tree APIs)
5. Set an expiration date aligned with your rotation policy.
6. Copy the token and store it in your secrets manager as `GITLAB_API_TOKEN`.

## Rotating the Token

1. Create a second token (don’t revoke the old one yet).
2. Update `GITLAB_API_TOKEN` in your secrets store/runtime environment.
3. Smoke test:

```bash
curl -s -H "PRIVATE-TOKEN: $GITLAB_API_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$(python3 -c 'import os,urllib.parse;print(urllib.parse.quote(os.getenv(\"GITLAB_PROJECT_ID\",\"group/project\"), safe=\"\"))')?simple=true" \
  | python3 -m json.tool | head -30
```

4. Revoke the old token once the smoke test succeeds.

## Notes

- The GitLab fetchers paginate via `per_page` + `page` and will make multiple requests for large repositories/MR sets.
- If you use the orchestrator’s multi-project support, it may set project-specific variables (e.g., `GITLAB_PROJECT_1_*`) and map them into the fetcher environment.

