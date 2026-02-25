"""
Shared Environment Loader for Evidence Fetcher Python Scripts
=============================================================

Import and call parse_fetcher_args() at the top of any fetcher script to:
  1. Load configuration from .env (if not already loaded by the orchestrator)
  2. Parse optional named CLI overrides: --output-dir, --profile, --region
  3. Return (output_dir, profile, region) with sensible defaults

Usage in a fetcher script:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common.env_loader import parse_fetcher_args

    output_dir, profile, region = parse_fetcher_args()

Future: This loader is the extension point for secret store backends
(AWS Secrets Manager, K8s secrets, etc.). Today it reads from .env.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _find_project_root(start: Path = None) -> Path:
    """Find the project root by looking for .env file walking up from start."""
    if start is None:
        start = Path.cwd()
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".env").exists():
            return parent
    # Fallback: assume fetchers/common/ is two levels below root
    return Path(__file__).resolve().parent.parent.parent


def init_fetcher_env() -> tuple:
    """Load .env and return (output_dir, profile, region) from environment.

    Uses override=False so that environment variables set by the orchestrator
    (or any parent process) take precedence over .env file values.
    """
    project_root = _find_project_root()
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)

    output_dir = os.environ.get("EVIDENCE_DIR", str(project_root / "evidence"))
    profile = os.environ.get("AWS_PROFILE", "")
    region = os.environ.get("AWS_DEFAULT_REGION", "")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return output_dir, profile, region


def parse_fetcher_args() -> tuple:
    """Parse CLI args and environment, returning (output_dir, profile, region).

    Supports named CLI overrides:
        --output-dir <path>
        --profile <name>
        --region <name>

    Falls back to environment variables / .env for any value not provided
    on the command line.
    """
    args = sys.argv[1:]

    output_dir = None
    profile = None
    region = None

    i = 0
    while i < len(args):
        if args[i] == "--output-dir" and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] == "--profile" and i + 1 < len(args):
            profile = args[i + 1]
            i += 2
        elif args[i] == "--region" and i + 1 < len(args):
            region = args[i + 1]
            i += 2
        else:
            i += 1

    # Load defaults from .env / environment
    env_dir, env_profile, env_region = init_fetcher_env()

    output_dir = output_dir or env_dir
    profile = profile or env_profile
    region = region or env_region

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return output_dir, profile, region
