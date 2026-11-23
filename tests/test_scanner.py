import pytest
from pathlib import Path
import tempfile
import os

def test_extended_project_targets():
    from scanner import project_target
    assert project_target(Path("/tmp/proj/.venv"), {"pyproject.toml"}) == "Python virtual environment"
    assert project_target(Path("/tmp/proj/venv"), {"requirements.txt"}) == "Python virtual environment"
    assert project_target(Path("/tmp/proj/node_modules"), {"package.json"}) == "Installed Node dependencies"
    assert project_target(Path("/tmp/proj/target"), {"Cargo.toml"}) == "Project build output"

def test_assessment_extended_targets():
    from scanner import assessment
    app, advice, reason = assessment("/tmp/proj/.venv", "Python virtual environment")
    assert "Python venv" in app
    assert "Review first" in advice

def test_size_formatting():
    from scanner import size
    assert size(500) == "500.0 B"
    assert size(1024) == "1.0 KiB"
    assert size(1024 * 1024 * 5) == "5.0 MiB"
    assert size(1024 * 1024 * 1024 * 2) == "2.0 GiB"

def test_trash_info_and_empty():
    from scanner import get_trash_info, empty_trash
    # Just verify get_trash_info returns valid tuple without crashing
    count, total_bytes = get_trash_info()
    assert isinstance(count, int)
    assert isinstance(total_bytes, int)
    assert count >= 0
    assert total_bytes >= 0
