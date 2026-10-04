from envguard.report import build_report


def make_project(tmp_path, *, example="DATABASE_URL=changeme\n"):
    (tmp_path / "app.py").write_text(
        'import os\n'
        'db = os.getenv("DATABASE_URL")\n'
        'cache = os.getenv("REDIS_URL")\n'
    )
    (tmp_path / ".env.example").write_text(example)
    return tmp_path


def test_missing_variables_are_detected(tmp_path):
    report = build_report(make_project(tmp_path))
    assert report.missing == ["REDIS_URL"]
    assert report.issue_count >= 1


def test_unused_declarations_are_detected(tmp_path):
    root = make_project(tmp_path, example="DATABASE_URL=changeme\nREDIS_URL=changeme\nLEGACY_FLAG=1\n")
    report = build_report(root)
    assert report.missing == []
    assert report.unused == ["LEGACY_FLAG"]


def test_clean_project_has_no_issues(tmp_path):
    root = make_project(tmp_path, example="DATABASE_URL=changeme\nREDIS_URL=changeme\n")
    report = build_report(root)
    assert report.issue_count == 0


def test_example_with_real_value_is_flagged(tmp_path):
    root = make_project(
        tmp_path,
        example="DATABASE_URL=postgres://u:p@prod.db.internal/app\nREDIS_URL=changeme\n",
    )
    report = build_report(root)
    assert "DATABASE_URL" in report.filled_example


def test_json_output_is_serialisable(tmp_path):
    import json
    report = build_report(make_project(tmp_path))
    assert json.loads(report.to_json())["summary"]["missing"] == 1
