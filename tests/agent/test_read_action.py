"""Tests for agent.read_action.ReadAction."""
from __future__ import annotations

from pathlib import Path

import pytest

import config
from agent.action import ActionError, ActionValidationError
from agent.action_param import ActionParam
from agent.read_action import ReadAction


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def memory_root(isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "MEMORY_ROOT", "memory", raising=False)
    return isolated_cwd / "memory"


class TestReadActionValidation:
    def test_missing_path_raises(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({}))
        with pytest.raises(ActionValidationError, match="invalid read params"):
            action.execute()

    def test_empty_path_raises(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": ""}))
        with pytest.raises(ActionValidationError, match="invalid read params"):
            action.execute()

    def test_extra_field_raises(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": "a.txt", "extra": 1}))
        with pytest.raises(ActionValidationError, match="invalid read params"):
            action.execute()


class TestReadActionExecution:
    def test_reads_existing_file_successfully(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("hello", encoding="utf-8")

        action = ReadAction(ActionParam({"path": "notes.txt"}))
        result = action.execute()

        assert result == "hello"
        assert action.result == "hello"
        assert action.last_error is None

    def test_reads_multiline_markdown_file_successfully(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "summary.md"
        markdown_content = "# Daily Summary\n\n- Breakfast: eggs\n- Lunch: salad\n\nTotal: 1200 kcal\n"
        target.write_text(markdown_content, encoding="utf-8")

        action = ReadAction(ActionParam({"path": "summary.md"}))
        result = action.execute()

        assert result == markdown_content
        assert action.result == markdown_content
        assert action.last_error is None

    def test_missing_file_maps_to_action_error(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": "missing.txt"}))
        with pytest.raises(ActionError, match="read failed: file not found"):
            action.execute()

    def test_invalid_filename_maps_to_action_error(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": "nested/file.txt"}))
        with pytest.raises(ActionError, match="the requested read file path is invalid"):
            action.execute()

    def test_directory_target_maps_to_action_error(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "adir").mkdir()

        action = ReadAction(ActionParam({"path": "adir"}))
        with pytest.raises(ActionError, match="read failed: path is a directory"):
            action.execute()
