#!/bin/bash
# =============================================================================
# Shared Environment Loader for Evidence Fetcher Shell Scripts
# =============================================================================
#
# Source this file at the top of any fetcher shell script to:
#   1. Load configuration from .env (if not already loaded by the orchestrator)
#   2. Set PROFILE, REGION, and OUTPUT_DIR from environment variables
#   3. Parse optional named CLI overrides: --output-dir, --profile, --region
#
# Usage in a fetcher script:
#   source "$(dirname "$0")/../common/env_loader.sh" "$@"
#
# After sourcing, the following variables are available:
#   PROFILE    - AWS CLI profile (from AWS_PROFILE env var or --profile)
#   REGION     - AWS region (from AWS_DEFAULT_REGION env var or --region)
#   OUTPUT_DIR - Evidence output directory (from EVIDENCE_DIR env var or --output-dir)
#
# Future: This loader is the extension point for secret store backends
# (AWS Secrets Manager, K8s secrets, etc.). Today it reads from .env.
# =============================================================================

# Resolve the project root relative to the calling script
_FETCHER_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}")" && pwd)"
_FETCHER_PROJECT_ROOT="$(cd "$_FETCHER_SCRIPT_DIR/../.." && pwd)"

# Load .env if not already loaded by the orchestrator
if [ -z "$_FETCHER_ENV_LOADED" ]; then
    if [ -f "$_FETCHER_PROJECT_ROOT/.env" ]; then
        set -a
        # shellcheck disable=SC1091
        source "$_FETCHER_PROJECT_ROOT/.env"
        set +a
    fi
    export _FETCHER_ENV_LOADED=1
fi

# Set defaults from environment variables
PROFILE="${AWS_PROFILE:-}"
REGION="${AWS_DEFAULT_REGION:-}"
OUTPUT_DIR="${EVIDENCE_DIR:-$_FETCHER_PROJECT_ROOT/evidence}"

# Parse optional named CLI overrides
while [[ $# -gt 0 ]]; do
    case $1 in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        -*)
            # Unknown flag - warn and skip
            echo "Warning: unknown argument '$1' (ignored)" >&2
            shift
            ;;
        *)
            # Positional argument - skip silently (may be script-specific)
            shift
            ;;
    esac
done

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"
