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

    def test_invalid_mode_raises(self, memory_root: Path) -> None:
        action = WriteAction(ActionParam({"path": "a.txt", "content": "x", "mode": "overwrite"}))
        with pytest.raises(ActionValidationError, match="invalid write params"):
            action.execute()

    def test_end_line_less_than_start_line_raises(self, memory_root: Path) -> None:
        action = WriteAction(
            ActionParam({"path": "a.txt", "content": "x", "mode": "replace_lines", "start_line": 5, "end_line": 2})
        )
        with pytest.raises(ActionValidationError, match="invalid write params"):
            action.execute()


class TestWriteActionExecution:
    def test_writes_file_successfully(self, memory_root: Path) -> None:
        action = WriteAction(
            ActionParam({"path": "output.txt", "content": "hello", "mode": "replace_lines"})
        )
        result = action.execute()

        assert result == "hello"
        assert (memory_root / "output.txt").read_text(encoding="utf-8") == "hello"
        assert action.last_error is None

    def test_overwrites_existing_file(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "output.txt"
        target.write_text("old", encoding="utf-8")

        action = WriteAction(
            ActionParam({"path": "output.txt", "content": "new", "mode": "replace_lines"})
        )
        result = action.execute()

        assert result == "new"
        assert target.read_text(encoding="utf-8") == "new"

    def test_explicit_replace_lines_overwrites_file(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "output.txt"
        target.write_text("old", encoding="utf-8")

        action = WriteAction(
            ActionParam({"path": "output.txt", "content": "new", "mode": "replace_lines"})
        )
        result = action.execute()

        assert result == "new"
        assert target.read_text(encoding="utf-8") == "new"

    def test_append_adds_newline_when_existing_file_has_no_trailing_newline(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "output.txt"
        target.write_text("hello", encoding="utf-8")

        action = WriteAction(
            ActionParam({"path": "output.txt", "content": "world", "mode": "append"})
        )
        result = action.execute()

        assert result == "world"
        assert target.read_text(encoding="utf-8") == "hello\nworld"

    def test_append_does_not_add_extra_newline_when_file_already_has_trailing_newline(
        self, memory_root: Path
    ) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "output.txt"
        target.write_text("hello\n", encoding="utf-8")

        action = WriteAction(
            ActionParam({"path": "output.txt", "content": "world", "mode": "append"})
        )
        result = action.execute()

        assert result == "world"
        assert target.read_text(encoding="utf-8") == "hello\nworld"

    def test_replace_lines_half_open_range(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "output.txt"
        target.write_text("a\nb\nc\nd\n", encoding="utf-8")

        action = WriteAction(
            ActionParam(
                {
                    "path": "output.txt",
                    "content": "x\ny",
                    "mode": "replace_lines",
                    "start_line": 2,
                    "end_line": 4,
                }
            )
        )
        result = action.execute()

        assert result == "x\ny"
        assert target.read_text(encoding="utf-8") == "a\nx\ny\nd\n"

    def test_replace_lines_from_start_to_eof(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "output.txt"
        target.write_text("a\nb\nc\n", encoding="utf-8")

        action = WriteAction(
            ActionParam(
                {
                    "path": "output.txt",
                    "content": "tail",
                    "mode": "replace_lines",
                    "start_line": 2,
                }
            )
        )
        result = action.execute()

        assert result == "tail"
        assert target.read_text(encoding="utf-8") == "a\ntail\n"

    def test_invalid_filename_maps_to_action_error(self, memory_root: Path) -> None:
        action = WriteAction(
            ActionParam({"path": "nested/file.txt", "content": "x", "mode": "replace_lines"})
        )
        with pytest.raises(ActionError, match="the requested write file path is invalid"):
            action.execute()

    def test_directory_target_maps_to_action_error(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "adir").mkdir()
        action = WriteAction(
            ActionParam({"path": "adir", "content": "x", "mode": "replace_lines"})
        )

        with pytest.raises(ActionError, match="write failed: path is a directory"):
            action.execute()
