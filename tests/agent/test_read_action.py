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

    def test_empty_contains_raises(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": "a.txt", "contains": ""}))
        with pytest.raises(ActionValidationError, match="invalid read params"):
            action.execute()

    def test_start_line_zero_raises(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": "a.txt", "start_line": 0}))
        with pytest.raises(ActionValidationError, match="invalid read params"):
            action.execute()

    def test_end_line_less_than_start_line_raises(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": "a.txt", "start_line": 5, "end_line": 3}))
        with pytest.raises(ActionValidationError, match="invalid read params"):
            action.execute()


class TestReadActionExecution:
    def test_reads_existing_file_successfully(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("hello", encoding="utf-8")

        action = ReadAction(ActionParam({"path": "notes.txt"}))
        result = action.execute()

        assert result == "1 | hello"
        assert action.result == "1 | hello"
        assert action.last_error is None

    def test_reads_multiline_markdown_file_successfully(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "summary.md"
        markdown_content = "# Daily Summary\n\n- Breakfast: eggs\n- Lunch: salad\n\nTotal: 1200 kcal\n"
        target.write_text(markdown_content, encoding="utf-8")

        action = ReadAction(ActionParam({"path": "summary.md"}))
        result = action.execute()

        assert result == (
            "1 | # Daily Summary\n"
            "2 | \n"
            "3 | - Breakfast: eggs\n"
            "4 | - Lunch: salad\n"
            "5 | \n"
            "6 | Total: 1200 kcal"
        )
        assert action.result == result
        assert action.last_error is None

    def test_missing_file_maps_to_action_error(self, memory_root: Path) -> None:
        action = ReadAction(ActionParam({"path": "missing.txt"}))
        with pytest.raises(ActionError, match="read failed: file not found"):
            action.execute()

    def test_contains_returns_all_matching_lines(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("breakfast: eggs\nlunch: salad\nlunch: soup\n", encoding="utf-8")

        action = ReadAction(ActionParam({"path": "notes.txt", "contains": "lunch"}))
        result = action.execute()

        assert result == "2 | lunch: salad\n3 | lunch: soup"
        assert action.result == "2 | lunch: salad\n3 | lunch: soup"
        assert action.last_error is None

    def test_contains_returns_empty_when_no_match(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("breakfast: eggs\nlunch: salad\n", encoding="utf-8")

        action = ReadAction(ActionParam({"path": "notes.txt", "contains": "dinner"}))
        result = action.execute()

        assert result == ""
        assert action.result == ""
        assert action.last_error is None

    def test_start_line_and_end_line_apply_half_open_range(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("a\nb\nc\nd\n", encoding="utf-8")

        action = ReadAction(ActionParam({"path": "notes.txt", "start_line": 2, "end_line": 4}))
        result = action.execute()

        assert result == "2 | b\n3 | c"
        assert action.result == "2 | b\n3 | c"
        assert action.last_error is None

    def test_start_line_without_end_line_reads_to_file_end(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("a\nb\nc\n", encoding="utf-8")

        action = ReadAction(ActionParam({"path": "notes.txt", "start_line": 2}))
        result = action.execute()

        assert result == "2 | b\n3 | c"
        assert action.result == "2 | b\n3 | c"
        assert action.last_error is None

    def test_contains_and_line_range_are_combined(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("apple\nbanana\napricot\navocado\n", encoding="utf-8")

        action = ReadAction(
            ActionParam({"path": "notes.txt", "contains": "a", "start_line": 2, "end_line": 4})
        )
        result = action.execute()

        assert result == "2 | banana\n3 | apricot"
        assert action.result == "2 | banana\n3 | apricot"
        assert action.last_error is None

    def test_line_numbers_are_left_padded_to_max_width(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text("\n".join(f"line-{idx}" for idx in range(1, 12)) + "\n", encoding="utf-8")

        action = ReadAction(ActionParam({"path": "notes.txt", "start_line": 9, "end_line": 12}))
        result = action.execute()

        assert result == " 9 | line-9\n10 | line-10\n11 | line-11"
        assert action.result == " 9 | line-9\n10 | line-10\n11 | line-11"
        assert action.last_error is None

    def test_padding_uses_filtered_result_max_line_width(self, memory_root: Path) -> None:
        memory_root.mkdir(parents=True, exist_ok=True)
        target = memory_root / "notes.txt"
        target.write_text(
            "line-1\nline-2\nline-3\nline-4\nline-5\nline-6\nline-7\nline-8\nline-9\nline-10\nline-11\n",
            encoding="utf-8",
        )

        action = ReadAction(ActionParam({"path": "notes.txt", "contains": "line-1"}))
        result = action.execute()

        # matching lines are 1, 10, 11 so width is 2 in filtered output.
        assert result == " 1 | line-1\n10 | line-10\n11 | line-11"
        assert action.result == " 1 | line-1\n10 | line-10\n11 | line-11"
        assert action.last_error is None

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
