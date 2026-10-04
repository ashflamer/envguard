"""Heuristic detection of credentials that were hardcoded into source."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from envguard.scanner import DEFAULT_IGNORES, iter_source_files

# High-confidence provider tokens. These are near zero false-positive.
PROVIDER_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("aws-access-key-id", "high", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", "high", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack-token", "high", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b")),
    ("stripe-secret-key", "high", re.compile(r"\b[sr]k_(?:live|test)_[0-9A-Za-z]{20,}\b")),
    ("openai-key", "high", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("google-api-key", "high", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private-key-block", "high", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("jwt", "medium", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("connection-string", "medium", re.compile(
        r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:@/]+:[^\s:@/]+@[^\s/\"']+"
    )),
)

# Generic "SECRET = '...'" assignments, judged by entropy.
ASSIGNMENT_RE = re.compile(
    r"""(?P<key>[A-Za-z_][A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|APIKEY|API_KEY|ACCESS_KEY|PRIVATE_KEY|CREDENTIAL)[A-Za-z0-9_]*)"""
    r"""\s*[:=]\s*(?P<quote>['"])(?P<value>[^'"\n]{8,})(?P=quote)""",
    re.IGNORECASE,
)

# Values that look secret-ish but obviously are not.
PLACEHOLDER_RE = re.compile(
    r"^(?:|x{3,}|\*{3,}|\.{3,}|changeme|change_me|your[_-]?\w*|replace[_-]?\w*|todo|tbd|none|null|"
    r"example\w*|dummy\w*|sample\w*|test\w*|fake\w*|placeholder\w*|secret|password|token|"
    r"\$\{[^}]*\}|<[^>]*>|\{\{[^}]*\}\}|process\.env\.\w+|os\.environ\w*)$",
    re.IGNORECASE,
)

SKIP_SUFFIXES = frozenset({".lock", ".min.js", ".map", ".snap"})


@dataclass(frozen=True, slots=True)
class SecretFinding:
    rule: str
    confidence: str
    path: Path
    line: int
    preview: str

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}"


def shannon_entropy(value: str) -> float:
    """Bits of entropy per character. Random tokens score > 3.5, words < 3.0."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    length = len(value)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def redact(value: str, keep: int = 4) -> str:
    """Never print a full credential - even into a CI log."""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{value[:keep]}{'*' * min(len(value) - keep, 12)}"


def _is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.match(value.strip()))


def scan_line_for_secrets(line: str, path: Path, lineno: int) -> list[SecretFinding]:
    findings: list[SecretFinding] = []

    for rule, confidence, pattern in PROVIDER_RULES:
        match = pattern.search(line)
        if match:
            findings.append(SecretFinding(
                rule=rule, confidence=confidence, path=path, line=lineno,
                preview=redact(match.group(0)),
            ))

    for match in ASSIGNMENT_RE.finditer(line):
        value = match.group("value")
        if _is_placeholder(value):
            continue
        entropy = shannon_entropy(value)
        # Long + random enough to be a real credential rather than a sentence.
        if entropy < 3.0 or " " in value:
            continue
        confidence = "high" if entropy >= 4.0 and len(value) >= 16 else "medium"
        findings.append(SecretFinding(
            rule=f"hardcoded-{match.group('key').lower()}",
            confidence=confidence, path=path, line=lineno, preview=redact(value),
        ))

    return findings


def scan_for_secrets(root: Path, *, ignores=DEFAULT_IGNORES) -> list[SecretFinding]:
    """Walk a tree looking for committed credentials."""
    findings: list[SecretFinding] = []
    suffixes = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rb", ".java",
        ".sh", ".bash", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".tf",
        ".env", ".properties", ".xml", ".md",
    }
    for file in iter_source_files(Path(root), suffixes=suffixes, ignores=ignores):
        if any(file.name.endswith(s) for s in SKIP_SUFFIXES):
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if len(line) > 4000:  # minified blob
                continue
            if "envguard:allow" in line:
                continue
            findings.extend(scan_line_for_secrets(line, file, lineno))
    return findings
