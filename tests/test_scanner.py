from pathlib import Path

from envguard.scanner import parse_env_file, scan_sources, scan_text


def test_detects_python_access_patterns():
    src = '\n'.join([
        'import os',
        'a = os.getenv("DATABASE_URL")',
        "b = os.environ.get('REDIS_URL')",
        'c = os.environ["SECRET_KEY"]',
    ])
    names = {r.name for r in scan_text(src, Path("app.py"))}
    assert names == {"DATABASE_URL", "REDIS_URL", "SECRET_KEY"}


def test_detects_js_access_patterns():
    src = '\n'.join([
        'const a = process.env.API_URL;',
        'const b = process.env["PORT"];',
        'const c = import.meta.env.VITE_PUBLIC_KEY;',
    ])
    names = {r.name for r in scan_text(src, Path("app.ts"))}
    assert names == {"API_URL", "PORT", "VITE_PUBLIC_KEY"}


def test_ignores_commented_lines():
    src = '# os.getenv("GHOST_VAR")\n// process.env.ALSO_GHOST\n'
    assert scan_text(src, Path("x.py")) == []


def test_records_line_numbers():
    src = 'x = 1\ny = 2\nz = os.getenv("TOKEN")\n'
    (ref,) = scan_text(src, Path("a.py"))
    assert ref.line == 3
    assert ref.location == "a.py:3"


def test_parse_env_file_handles_real_world_syntax(tmp_path):
    f = tmp_path / ".env.example"
    f.write_text('\n'.join([
        "# a comment",
        "",
        "export EXPORTED=1",
        'QUOTED="hello world"',
        "SINGLE='x'",
        "INLINE=value # trailing comment",
        "EMPTY=",
        "not a pair",
        "123BAD=nope",
    ]))
    parsed = parse_env_file(f)
    assert parsed["EXPORTED"] == "1"
    assert parsed["QUOTED"] == "hello world"
    assert parsed["SINGLE"] == "x"
    assert parsed["INLINE"] == "value"
    assert parsed["EMPTY"] == ""
    assert "123BAD" not in parsed


def test_parse_missing_file_returns_empty(tmp_path):
    assert parse_env_file(tmp_path / "nope.env") == {}


def test_scan_sources_skips_ignored_dirs(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("process.env.SHOULD_NOT_APPEAR")
    (tmp_path / "app.js").write_text("process.env.SHOULD_APPEAR")
    names = {r.name for r in scan_sources(tmp_path)}
    assert names == {"SHOULD_APPEAR"}
