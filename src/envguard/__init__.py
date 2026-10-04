"""envguard - catch .env drift and hardcoded secrets before they ship."""

__version__ = "0.3.0"

from envguard.scanner import EnvReference, scan_sources, parse_env_file
from envguard.secrets import SecretFinding, scan_for_secrets
from envguard.report import Report, build_report

__all__ = [
    "EnvReference",
    "scan_sources",
    "parse_env_file",
    "SecretFinding",
    "scan_for_secrets",
    "Report",
    "build_report",
    "__version__",
]
