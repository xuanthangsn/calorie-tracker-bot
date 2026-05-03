"""Tests for agent.append_action.AppendAction."""
from __future__ import annotations

from pathlib import Path

import pytest

import config
from agent.action import ActionError, ActionValidationError
from agent.action_param import ActionParam
from agent.append_action import AppendAction


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def memory_root(isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "MEMORY_ROOT", "memory", raising=False)
    return isolated_cwd / "memory"


class TestAppendActionValidation:
    def test_missing_path_raises(self, memory_root: Path) -> None:
        action = AppendAction(ActionParam({"content": "x"}))
        with pytest.raises(ActionValidationError, match="invalid append params"):
            action.execute()

    def test_missing_content_raises(self, memory_root: Path) -> None:
        action = AppendAction(ActionParam({"path": "a.txt"}))
        with pytest.raises(ActionValidationError, match="invalid append params"):
            action.execute()

    def test_empty_path_raises(self, memory_root: Path) -> None:
        action = AppendAction(ActionParam({"path": "", "content": "x"}))
        with pytest.raises(ActionValidationError, match="invalid append params"):
            action.execute()

    def test_empty_content_raises(self, memory_root: Path) -> None:
        action = AppendAction(ActionParam({"path": "a.txt", "content": ""}))
        with pytest.raises(ActionValidationError, match="invalid append params"):
            action.execute()

    def test_extra_field_raises(self, memory_root: Path) -> None:
        action = AppendAction(ActionParam({"path": "a.txt", "content": "x", "extra": 1}))
        with pytest.raises(ActionValidationError, match="invalid append params"):
            action.execute()


class TestAppendActionExecution:
    def test_creates_file_when_missing(self, memory_root: Path) -> None:
        action = AppendAction(ActionParam({"path": "notes.txt", "content": "first"}))
        result = action.execute()

        assert result == "first"
        assert (memory_root / "notes.txt").read_text(encoding="utf-8") == "first"
        assert action.last_error is None

    def test_inserts_newline_when_existing_has_no_trailing_newline(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("hello", encoding="utf-8")

        action = AppendAction(ActionParam({"path": "notes.txt", "content": "world"}))
        result = action.execute()

        assert result == "world"
        assert target.read_text(encoding="utf-8") == "hello\nworld"

    def test_no_extra_newline_when_file_already_ends_with_newline(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("hello\n", encoding="utf-8")

        action = AppendAction(ActionParam({"path": "notes.txt", "content": "world"}))
        result = action.execute()

        assert result == "world"
        assert target.read_text(encoding="utf-8") == "hello\nworld"

    def test_invalid_filename_maps_to_action_error(self, memory_root: Path) -> None:
        action = AppendAction(ActionParam({"path": "nested/file.txt", "content": "x"}))
        with pytest.raises(ActionError, match="the requested append file path is invalid"):
            action.execute()

    def test_directory_target_maps_to_action_error(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "adir").mkdir()
        action = AppendAction(ActionParam({"path": "adir", "content": "x"}))

        with pytest.raises(ActionError, match="append failed: path is a directory"):
            action.execute()
