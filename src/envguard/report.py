"""Turn raw scan results into something a human (or CI) can act on."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from envguard.scanner import EnvReference, FRAMEWORK_BUILTINS, parse_env_file, scan_sources
from envguard.secrets import SecretFinding, scan_for_secrets


@dataclass
class Report:
    root: Path
    declared: dict[str, str] = field(default_factory=dict)
    references: list[EnvReference] = field(default_factory=list)
    secrets: list[SecretFinding] = field(default_factory=list)
    env_file: Path | None = None
    committed_env_files: list[Path] = field(default_factory=list)

    @property
    def used(self) -> set[str]:
        return {ref.name for ref in self.references}

    @property
    def missing(self) -> list[str]:
        """Read by the code, but never declared. These cause 3am outages."""
        return sorted(self.used - set(self.declared) - FRAMEWORK_BUILTINS)

    @property
    def unused(self) -> list[str]:
        """Declared but nothing reads it. Dead config, safe to delete."""
        return sorted(set(self.declared) - self.used)

    @property
    def filled_example(self) -> list[str]:
        """A .env.example should ship placeholders, not real values."""
        suspicious = []
        for key, value in self.declared.items():
            if not value or len(value) < 8:
                continue
            lowered = value.lower()
            if any(t in lowered for t in ("your", "change", "example", "xxx", "placeholder", "<", "{")):
                continue
            suspicious.append(key)
        return sorted(suspicious)

    def references_for(self, name: str) -> list[EnvReference]:
        return [r for r in self.references if r.name == name]

    @property
    def issue_count(self) -> int:
        return (
            len(self.missing)
            + len(self.secrets)
            + len(self.committed_env_files)
            + len(self.filled_example)
        )

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "env_file": str(self.env_file) if self.env_file else None,
            "summary": {
                "variables_used": len(self.used),
                "variables_declared": len(self.declared),
                "missing": len(self.missing),
                "unused": len(self.unused),
                "secrets": len(self.secrets),
                "issues": self.issue_count,
            },
            "missing": [
                {"name": name, "used_at": [r.location for r in self.references_for(name)]}
                for name in self.missing
            ],
            "unused": self.unused,
            "example_contains_real_values": self.filled_example,
            "committed_env_files": [str(p) for p in self.committed_env_files],
            "secrets": [
                {
                    "rule": s.rule,
                    "confidence": s.confidence,
                    "location": s.location,
                    "preview": s.preview,
                }
                for s in self.secrets
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def find_env_files(root: Path) -> list[Path]:
    """Real .env files sitting in the tree (not the .example ones)."""
    out: list[Path] = []
    for path in sorted(Path(root).rglob(".env*")):
        if any(part in {".git", "node_modules", ".venv"} for part in path.parts):
            continue
        if path.is_file() and not path.name.endswith((".example", ".sample", ".template", ".dist")):
            out.append(path)
    return out


def build_report(
    root: Path,
    *,
    env_file: Path | None = None,
    check_secrets: bool = True,
) -> Report:
    root = Path(root)
    if env_file is None:
        for candidate in (".env.example", ".env.sample", ".env.template", ".env.dist"):
            if (root / candidate).exists():
                env_file = root / candidate
                break

    report = Report(root=root, env_file=env_file)
    report.declared = parse_env_file(env_file) if env_file else {}
    report.references = scan_sources(root)
    if check_secrets:
        report.secrets = scan_for_secrets(root)
    report.committed_env_files = find_env_files(root)
    return report
