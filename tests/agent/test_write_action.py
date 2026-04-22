"""Tests for agent.write_action.WriteAction."""
from __future__ import annotations

from pathlib import Path

import pytest

import config
from agent.action import ActionError, ActionValidationError
from agent.action_param import ActionParam
from agent.write_action import WriteAction


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def memory_root(isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "MEMORY_ROOT", "memory", raising=False)
    return isolated_cwd / "memory"


class TestWriteActionValidation:
    def test_missing_path_raises(self, memory_root: Path) -> None:
        action = WriteAction(ActionParam({"content": "x"}))
        with pytest.raises(ActionValidationError, match="invalid write params"):
            action.execute()

    def test_missing_content_raises(self, memory_root: Path) -> None:
        action = WriteAction(ActionParam({"path": "a.txt"}))
        with pytest.raises(ActionValidationError, match="invalid write params"):
            action.execute()

    def test_empty_path_raises(self, memory_root: Path) -> None:
        action = WriteAction(ActionParam({"path": "", "content": "x"}))
        with pytest.raises(ActionValidationError, match="invalid write params"):
            action.execute()

    def test_extra_field_raises(self, memory_root: Path) -> None:
        action = WriteAction(ActionParam({"path": "a.txt", "content": "x", "extra": 1}))
        with pytest.raises(ActionValidationError, match="invalid write params"):
            action.execute()


class TestWriteActionExecution:
    def test_writes_file_successfully(self, memory_root: Path) -> None:
        action = WriteAction(ActionParam({"path": "output.txt", "content": "hello"}))
        result = action.execute()

        assert result == "hello"
        assert (memory_root / "output.txt").read_text(encoding="utf-8") == "hello"
        assert action.last_error is None

    def test_overwrites_existing_file(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "output.txt"
        target.write_text("old", encoding="utf-8")

        action = WriteAction(ActionParam({"path": "output.txt", "content": "new"}))
        result = action.execute()

        assert result == "new"
        assert target.read_text(encoding="utf-8") == "new"

    def test_invalid_filename_maps_to_action_error(self, memory_root: Path) -> None:
        action = WriteAction(ActionParam({"path": "nested/file.txt", "content": "x"}))
        with pytest.raises(ActionError, match="the requested write file path is invalid"):
            action.execute()

    def test_directory_target_maps_to_action_error(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "adir").mkdir()
        action = WriteAction(ActionParam({"path": "adir", "content": "x"}))

        with pytest.raises(ActionError, match="write failed: path is a directory"):
            action.execute()
