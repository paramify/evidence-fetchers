# SentinelOne API Key Setup

## Environment Variables

All fetchers in this folder require two environment variables:

```bash
export SENTINELONE_API_URL="https://your-instance.s1gov.net"   # no trailing slash
export SENTINELONE_API_TOKEN="<your-api-token>"
```

## API Endpoints Used

| Fetcher | Endpoint | Method |
|---|---|---|
| `sentinelone_activities.py` | `/web/api/v2.1/activities` | GET |
| `sentinelone_agents.py` | `/web/api/v2.1/agents`, `/web/api/v2.1/agents/count` | GET |
| `sentinelone_cloud_detection_rules.py` | `/web/api/v2.1/cloud-detection/rules`, `/sdl/api/powerQuery` | GET, POST |
| `sentinelone_user_config.py` | `/web/api/v2.1/users` | GET |
| `sentinelone_xdr_assets.py` | `/web/api/v2.1/xdr/assets` | GET |

## Creating a New API Token

1. Log in to the SentinelOne console.
2. Navigate to **Settings → Users → Service Users**.
3. Create a new service user (e.g. `paramify-evidence-fetchers`).
4. Set the scope to **Account** level.
5. Assign the **Viewer** role — all fetchers are read-only.
6. Select the service user, click **Actions → Generate API Token**.
7. Set expiration to **1 Month** (SentinelOne's recommended maximum) or another time length.
8. Complete SSO re-authentication if prompted.
9. Click **Copy API Token** and store it in your secrets manager.

## Rotating the API Token

1. Navigate to **Settings → Users → Service Users**.
2. Select the `paramify-evidence-fetchers` service user.
3. Click **Actions → Regenerate API Token**.
4. Set expiration to **1 Month**.
5. Complete SSO re-authentication when prompted.
6. Click **Copy API Token**.
7. Update the `SENTINELONE_API_TOKEN` value wherever it's stored (e.g. AWS Secrets Manager, `.env`).
8. Verify with a quick smoke test:
   ```bash
   curl -s -H "Authorization: ApiToken $SENTINELONE_API_TOKEN" \
     "$SENTINELONE_API_URL/web/api/v2.1/agents?limit=1" | python3 -m json.tool | head -5
   ```

## Notes

- The `cloud_detection_rules` fetcher uses `Bearer` auth for the PowerQuery endpoint and `ApiToken` auth for everything else — both use the same token value.
- Token expiration should be tracked and rotated before it lapses. Consider a calendar reminder or CloudWatch alarm ~1 week before expiry.
