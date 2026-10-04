# envguard

**Catch `.env` drift and hardcoded secrets before they ship.** Zero dependencies, one command, CI-friendly exit codes.

[![CI](https://github.com/ashflamer/envguard/actions/workflows/ci.yml/badge.svg)](https://github.com/ashflamer/envguard/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Dependencies: 0](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)

---

## The problem

Your app reads `REDIS_URL`. Nobody added it to `.env.example`. A new teammate clones the repo, runs it, and gets a `KeyError` at 3am in staging. Meanwhile a Stripe key someone pasted "just to test" is sitting in `server.py`, in git history, forever.

`envguard` finds both in under a second.

## What it does

```console
$ envguard examples/leaky-app

envguard 0.3.0  examples/leaky-app
  reference file: .env.example

✗ 3 variable(s) used but never declared
    API_BASE_URL  examples/leaky-app/client.ts:1
    REDIS_URL  examples/leaky-app/server.py:4
    VITE_ANALYTICS_ID  examples/leaky-app/client.ts:2

✗ 1 possible hardcoded secret(s)
    [HIGH] stripe-secret-key  examples/leaky-app/server.py:5  sk_l************

· 1 declared but unused (dead config)
    LEGACY_FEATURE_FLAG

  4 used · 2 declared · 4 issue(s)

$ echo $?
1
```

Exit code `1` means your CI job fails. That is the whole point.

## Install

```bash
pip install envguard          # once published
pipx install envguard         # or isolated
git clone https://github.com/ashflamer/envguard && cd envguard && pip install -e ".[dev]"
```

## Usage

```bash
envguard                           # scan the current directory
envguard ./services/api            # scan a subdirectory
envguard -e .env.sample            # use a different reference file
envguard --format json             # machine-readable, for dashboards
envguard --format markdown         # paste straight into a PR comment
envguard --init                    # generate .env.example from the code
envguard --strict                  # also fail on dead config
envguard --no-secrets              # drift check only
```

| Flag | What it does |
| --- | --- |
| `-e, --env-file` | Reference file to compare against (auto-detects `.env.example`, `.sample`, `.template`, `.dist`) |
| `-f, --format` | `text` (default), `json`, `markdown` |
| `--init` | Writes a `.env.example` derived from what the code actually reads |
| `--strict` | Unused declarations also fail the run |
| `--no-secrets` | Skip the credential scanner |

Suppress a line that's a known false positive:

```python
SAMPLE_TOKEN = "ghp_documentationexampleonly000000000"  # envguard:allow
```

## What gets detected

**Env var reads**, across languages:

| Language | Patterns |
| --- | --- |
| Python | `os.getenv("X")`, `os.environ["X"]`, `os.environ.get("X")` |
| Node | `process.env.X`, `process.env["X"]` |
| Vite / browser | `import.meta.env.X` |
| Go | `os.Getenv("X")` |
| Shell / compose / Terraform | `${X}`, `${X:-default}` |

**Credentials**, by provider signature and by entropy:

AWS access keys · GitHub tokens (`ghp_`/`gho_`/`ghs_`) · Slack tokens · Stripe keys · OpenAI keys · Google API keys · PEM private key blocks · JWTs · DB connection strings with inline passwords · any `*_SECRET`/`*_TOKEN`/`*_PASSWORD` assignment whose value has high Shannon entropy.

Placeholders (`changeme`, `your-key-here`, `${VAULT}`, `<redacted>`) are deliberately ignored, so a clean repo stays quiet. **Findings are always redacted** — envguard never prints a full credential into a CI log.

## Use it in CI

```yaml
# .github/workflows/env-check.yml
name: env-check
on: [push, pull_request]

jobs:
  envguard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install envguard
      - run: envguard . --format markdown >> $GITHUB_STEP_SUMMARY
      - run: envguard .
```

The first `envguard` call writes a table into the GitHub Actions summary tab; the second one fails the job if anything is wrong.

### pre-commit

```yaml
repos:
  - repo: local
    hooks:
      - id: envguard
        name: envguard
        entry: envguard
        language: system
        pass_filenames: false
```

## How it works

1. **Walk** the tree, skipping `node_modules`, `.venv`, `dist` and friends.
2. **Regex-match** env access patterns per line, recording file + line number. Comment lines are skipped so documented-but-dead vars don't create noise.
3. **Parse** the reference `.env.example` with the same rules python-dotenv uses (`export`, quotes, inline comments) — without the dependency.
4. **Diff** the two sets: `used - declared` = missing, `declared - used` = dead config.
5. **Entropy-score** candidate secrets. Shannon entropy per character separates `"please choose a strong password"` (~3.0 bits, prose) from `"Zx9Qw2Lm8Rt4Vb7Np1Kd6Hs3"` (~4.3 bits, random). Provider-signature matches skip the entropy gate entirely.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean |
| `1` | Issues found |
| `2` | Bad invocation (path doesn't exist) |

## Development

```bash
pip install -e ".[dev]"
pytest -q          # 27 tests
ruff check .
```

## Roadmap

- [ ] `--baseline` file to grandfather in existing findings
- [ ] Scan git history, not just the working tree
- [ ] Rust/Java/PHP access patterns
- [ ] Published GitHub Action (`uses: ashflamer/envguard@v1`)

PRs welcome — adding a new language is one tuple in `PATTERNS` plus a test.

## License

MIT © ashflamer
