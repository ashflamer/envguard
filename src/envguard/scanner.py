"""Find every environment variable a codebase actually reads."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# Directories that are never worth walking into.
DEFAULT_IGNORES = frozenset({
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "out", ".next", ".nuxt", "coverage", "target", ".cache",
})

SOURCE_SUFFIXES = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".svelte", ".vue",
    ".go", ".rb", ".sh", ".bash", ".yml", ".yaml", ".tf",
})

# Each pattern must expose the variable name as group 1.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python", re.compile(r"""os\.getenv\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]""")),
    ("python", re.compile(r"""os\.environ\.get\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]""")),
    ("python", re.compile(r"""os\.environ\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\]""")),
    ("node", re.compile(r"""process\.env\.([A-Za-z_][A-Za-z0-9_]*)""")),
    ("node", re.compile(r"""process\.env\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\]""")),
    ("vite", re.compile(r"""import\.meta\.env\.([A-Za-z_][A-Za-z0-9_]*)""")),
    ("go", re.compile(r'os\.Getenv\(\s*"([A-Za-z_][A-Za-z0-9_]*)"')),
    ("shell", re.compile(r"""\$\{([A-Z][A-Z0-9_]{2,})(?::[-?=][^}]*)?\}""")),
)

# Vite/Next expose these to the browser; flagging them as "unused" is noise.
FRAMEWORK_BUILTINS = frozenset({"MODE", "BASE_URL", "PROD", "DEV", "SSR", "NODE_ENV"})


@dataclass(frozen=True, slots=True)
class EnvReference:
    """A single place in the code where an env var is read."""

    name: str
    path: Path
    line: int
    flavor: str

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}"


def iter_source_files(
    root: Path,
    *,
    suffixes: Iterable[str] = SOURCE_SUFFIXES,
    ignores: Iterable[str] = DEFAULT_IGNORES,
) -> Iterator[Path]:
    """Walk `root`, yielding source files worth scanning."""
    suffixes = frozenset(suffixes)
    ignores = frozenset(ignores)
    root = Path(root)

    if root.is_file():
        yield root
        return

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except (PermissionError, OSError):
            continue
        for entry in entries:
            if entry.is_dir():
                hidden = entry.name.startswith(".") and entry.name != ".github"
                if entry.name in ignores or hidden:
                    continue
                stack.append(entry)
            elif entry.suffix in suffixes:
                yield entry


def scan_text(text: str, path: Path) -> list[EnvReference]:
    """Extract env references from a blob of source text."""
    found: list[EnvReference] = []
    seen: set[tuple[str, int]] = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        # Cheap comment skip - avoids flagging documented-but-dead vars.
        if stripped.startswith(("#", "//", "*")):
            continue
        for flavor, pattern in PATTERNS:
            for match in pattern.finditer(line):
                name = match.group(1)
                if (name, lineno) in seen:
                    continue
                seen.add((name, lineno))
                found.append(EnvReference(name=name, path=path, line=lineno, flavor=flavor))
    return found


def scan_sources(root: Path, **kwargs) -> list[EnvReference]:
    """Scan an entire tree for env var usage."""
    refs: list[EnvReference] = []
    for file in iter_source_files(Path(root), **kwargs):
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        refs.extend(scan_text(text, file))
    return refs


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env / .env.example file into {KEY: value}.

    Handles `export KEY=v`, quotes, inline comments and blank lines the same
    way python-dotenv does, but without the dependency.
    """
    declared: dict[str, str] = {}
    path = Path(path)
    if not path.exists():
        return declared

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        declared[key] = value
    return declared
