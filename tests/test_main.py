"""Unit tests for pure helpers in main.py (no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402


def test_template_braces_are_preserved():
    template = 'A {subject} with config {"a": 1}'
    assert main.apply_style_template(template, "cat") == 'A cat with config {"a": 1}'


def test_template_without_placeholder_prepends_subject():
    assert main.apply_style_template("flat style", "cat") == "cat. flat style"


def test_load_style_template(tmp_path):
    style = tmp_path / "s.md"
    style.write_text("## Prompt Template\n\n```\nDraw [SUBJECT] café\n```\n", encoding="utf-8")
    assert main.load_style_template(style) == "Draw {subject} café"


def test_load_style_template_missing_section(tmp_path):
    style = tmp_path / "s.md"
    style.write_text("nothing here", encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_style_template(style)


@pytest.mark.parametrize(
    "code,status,message,expected",
    [
        (429, "RESOURCE_EXHAUSTED", "quota exceeded", True),
        (403, "PERMISSION_DENIED", "billing required", True),
        (400, "INVALID_ARGUMENT", "free tier not available, limit: 0", True),
        (400, "INVALID_ARGUMENT", "bad prompt", False),
        (500, "INTERNAL", "oops", False),
    ],
)
def test_is_quota_error(code, status, message, expected):
    exc = genai_errors.APIError(code, {"error": {"code": code, "status": status, "message": message}})
    assert main._is_quota_error(exc) is expected
