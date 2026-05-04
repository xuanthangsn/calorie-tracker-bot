"""Tests for agent.replace_action.ReplaceAction."""
from __future__ import annotations

from pathlib import Path

import pytest

import config
from agent.action import ActionError, ActionValidationError
from agent.action_param import ActionParam
from agent.replace_action import ReplaceAction


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def memory_root(isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "MEMORY_ROOT", "memory", raising=False)
    return isolated_cwd / "memory"


class TestReplaceActionValidation:
    def test_missing_path_raises(self, memory_root: Path) -> None:
        action = ReplaceAction(ActionParam({"old_text": "a", "new_text": "b"}))
        with pytest.raises(ActionValidationError, match="invalid replace params"):
            action.execute()

    def test_missing_old_text_raises(self, memory_root: Path) -> None:
        action = ReplaceAction(ActionParam({"path": "a.txt", "new_text": "b"}))
        with pytest.raises(ActionValidationError, match="invalid replace params"):
            action.execute()

    def test_missing_new_text_raises(self, memory_root: Path) -> None:
        action = ReplaceAction(ActionParam({"path": "a.txt", "old_text": "a"}))
        with pytest.raises(ActionValidationError, match="invalid replace params"):
            action.execute()

    def test_empty_path_raises(self, memory_root: Path) -> None:
        action = ReplaceAction(ActionParam({"path": "", "old_text": "a", "new_text": "b"}))
        with pytest.raises(ActionValidationError, match="invalid replace params"):
            action.execute()

    def test_empty_old_text_raises(self, memory_root: Path) -> None:
        action = ReplaceAction(ActionParam({"path": "a.txt", "old_text": "", "new_text": "b"}))
        with pytest.raises(ActionValidationError, match="invalid replace params"):
            action.execute()

    def test_empty_new_text_raises(self, memory_root: Path) -> None:
        action = ReplaceAction(ActionParam({"path": "a.txt", "old_text": "a", "new_text": ""}))
        with pytest.raises(ActionValidationError, match="invalid replace params"):
            action.execute()

    def test_extra_field_raises(self, memory_root: Path) -> None:
        action = ReplaceAction(
            ActionParam({"path": "a.txt", "old_text": "a", "new_text": "b", "extra": 1})
        )
        with pytest.raises(ActionValidationError, match="invalid replace params"):
            action.execute()


class TestReplaceActionExecution:
    def test_replaces_all_occurrences(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("foo bar foo", encoding="utf-8")

        action = ReplaceAction(
            ActionParam({"path": "notes.txt", "old_text": "foo", "new_text": "baz"})
        )
        result = action.execute()

        assert result == "baz"
        assert target.read_text(encoding="utf-8") == "baz bar baz"
        assert action.last_error is None

    def test_replaces_once_and_returns_new_text(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("hello world", encoding="utf-8")

        action = ReplaceAction(
            ActionParam({"path": "notes.txt", "old_text": "world", "new_text": "there"})
        )
        result = action.execute()

        assert result == "there"
        assert target.read_text(encoding="utf-8") == "hello there"

    def test_missing_file_maps_to_action_error(self, memory_root: Path) -> None:
        action = ReplaceAction(
            ActionParam({"path": "missing.txt", "old_text": "a", "new_text": "b"})
        )
        with pytest.raises(ActionError, match="replace failed: file not found"):
            action.execute()

    def test_old_text_not_found_maps_to_action_error(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("hello", encoding="utf-8")

        action = ReplaceAction(
            ActionParam({"path": "notes.txt", "old_text": "missing", "new_text": "x"})
        )
        with pytest.raises(ActionError, match="old_text not found"):
            action.execute()

    def test_invalid_filename_maps_to_action_error(self, memory_root: Path) -> None:
        action = ReplaceAction(
            ActionParam({"path": "nested/file.txt", "old_text": "a", "new_text": "b"})
        )
        with pytest.raises(ActionError, match="the requested replace file path is invalid"):
            action.execute()

    def test_directory_target_maps_to_action_error(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "adir").mkdir()
        action = ReplaceAction(
            ActionParam({"path": "adir", "old_text": "a", "new_text": "b"})
        )

        with pytest.raises(ActionError, match="replace failed: path is a directory"):
            action.execute()
