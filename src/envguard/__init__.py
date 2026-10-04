"""envguard - catch .env drift and hardcoded secrets before they ship."""

__version__ = "0.3.0"

from envguard.report import Report, build_report
from envguard.scanner import EnvReference, parse_env_file, scan_sources
from envguard.secrets import SecretFinding, scan_for_secrets

__all__ = [
    "EnvReference",
    "Report",
    "SecretFinding",
    "__version__",
    "build_report",
    "parse_env_file",
    "scan_for_secrets",
    "scan_sources",
]
