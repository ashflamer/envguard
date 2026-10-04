import json

from envguard.cli import main


def write_project(tmp_path, example):
    (tmp_path / "app.py").write_text('import os\nx = os.getenv("API_URL")\n')
    (tmp_path / ".env.example").write_text(example)


def test_exit_code_zero_when_clean(tmp_path, capsys):
    write_project(tmp_path, "API_URL=changeme\n")
    assert main([str(tmp_path), "--no-color"]) == 0
    assert "no issues found" in capsys.readouterr().out


def test_exit_code_one_when_drifted(tmp_path, capsys):
    write_project(tmp_path, "")
    assert main([str(tmp_path), "--no-color"]) == 1
    assert "API_URL" in capsys.readouterr().out


def test_json_format(tmp_path, capsys):
    write_project(tmp_path, "")
    main([str(tmp_path), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["missing"][0]["name"] == "API_URL"


def test_markdown_format(tmp_path, capsys):
    write_project(tmp_path, "")
    main([str(tmp_path), "--format", "markdown"])
    assert "## envguard report" in capsys.readouterr().out


def test_init_generates_example(tmp_path, capsys):
    (tmp_path / "app.py").write_text('import os\nx = os.getenv("NEW_VAR")\n')
    assert main([str(tmp_path), "--init"]) == 0
    assert "NEW_VAR=changeme" in (tmp_path / ".env.example").read_text()


def test_missing_path_returns_two(tmp_path, capsys):
    assert main([str(tmp_path / "ghost")]) == 2
