from pathlib import Path

from envguard.secrets import redact, scan_line_for_secrets, shannon_entropy


def find(line: str):
    return scan_line_for_secrets(line, Path("f.py"), 1)


def test_detects_aws_key():
    (f,) = find('key = "AKIAIOSFODNN7EXAMPLE"')
    assert f.rule == "aws-access-key-id"
    assert f.confidence == "high"


def test_detects_github_token():
    hits = find('TOKEN = "ghp_' + "a" * 36 + '"')
    assert any(h.rule == "github-token" for h in hits)


def test_detects_connection_string_with_password():
    (f,) = find('DB = "postgres://admin:hunter2pass@db.internal:5432/app"')
    assert f.rule == "connection-string"


def test_ignores_placeholders():
    assert find('API_KEY = "your-api-key-here"') == []
    assert find('PASSWORD = "changeme"') == []
    assert find('SECRET = "${VAULT_SECRET}"') == []
    assert find('TOKEN = "process.env.TOKEN"') == []


def test_ignores_low_entropy_prose():
    assert find('PASSWORD_HELP_TEXT = "please choose a strong password"') == []


def test_flags_high_entropy_assignment():
    (f,) = find("API_SECRET = 'Zx9Qw2Lm8Rt4Vb7Np1Kd6Hs3'")
    assert f.confidence == "high"


def test_allowlist_comment_is_respected_by_line_filter():
    # the inline marker is handled in scan_for_secrets; verify the token itself matches
    assert find('key = "AKIAIOSFODNN7EXAMPLE"')


def test_redact_never_leaks_full_value():
    assert redact("supersecretvalue") == "supe************"
    assert "secretvalue" not in redact("supersecretvalue")


def test_entropy_ordering():
    assert shannon_entropy("aaaaaaaa") < shannon_entropy("password") < shannon_entropy("Zx9Qw2Lm8Rt4")
