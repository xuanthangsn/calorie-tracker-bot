"""Tests for utils.path_resolution.resolve_workspace_path."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import config
from utils.path_resolution import InvalidLLMRequestedPath, resolve_workspace_path


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def memory_relative(isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "MEMORY_ROOT", "memory", raising=False)
    return isolated_cwd / "memory"


@pytest.fixture
def memory_absolute(isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = isolated_cwd / "agent_memory"
    monkeypatch.setattr(config, "MEMORY_ROOT", str(root), raising=False)
    return root


class TestInvalidInputs:
    def test_non_string_raises(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="path must be a non-empty string"):
            resolve_workspace_path(1)  # type: ignore[arg-type]

    def test_empty_string_raises(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="path must be a non-empty string"):
            resolve_workspace_path("")

    def test_whitespace_only_raises(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="path must be a non-empty string"):
            resolve_workspace_path("   \t ")

    def test_missing_memory_root_raises(self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "MEMORY_ROOT", "", raising=False)
        with pytest.raises(ValueError, match="MEMORY_ROOT environment variable is not set"):
            resolve_workspace_path("foo.txt")


class TestWorkspaceRootResolutionFailures:
    def test_workspace_root_resolution_failure_raises_value_error(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "MEMORY_ROOT", "memory", raising=False)

        def _raise_on_mkdir(*args: object, **kwargs: object) -> None:
            raise OSError("simulated mkdir failure")

        monkeypatch.setattr(Path, "mkdir", _raise_on_mkdir)
        with pytest.raises(ValueError, match="Failed to resolve workspace root"):
            resolve_workspace_path("foo.txt")


class TestFilenameOnlyRule:
    def test_nested_path_with_forward_slash_rejected(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="file name only"):
            resolve_workspace_path("notes/today.md")

    def test_nested_path_with_backslash_rejected(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="file name only"):
            resolve_workspace_path(r"notes\\today.md")

    def test_dot_rejected(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="file name only"):
            resolve_workspace_path(".")

    def test_dotdot_rejected(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="file name only"):
            resolve_workspace_path("..")

    def test_absolute_path_rejected_by_filename_rule(self, memory_relative: Path) -> None:
        with pytest.raises(InvalidLLMRequestedPath, match="file name only"):
            resolve_workspace_path("/tmp/file.txt")


class TestResolutionBehavior:
    def test_resolves_filename_under_relative_workspace(self, memory_relative: Path) -> None:
        result = resolve_workspace_path("todo.md")
        assert result == memory_relative / "todo.md"

    def test_trims_whitespace_around_filename(self, memory_relative: Path) -> None:
        result = resolve_workspace_path("  log.txt  ")
        assert result == memory_relative / "log.txt"

    def test_creates_workspace_directory_if_missing(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "MEMORY_ROOT", "memory", raising=False)
        assert not (isolated_cwd / "memory").exists()
        resolve_workspace_path("a.txt")
        assert (isolated_cwd / "memory").is_dir()

    def test_resolves_under_absolute_workspace_root(self, memory_absolute: Path) -> None:
        result = resolve_workspace_path("data.json")
        assert result == memory_absolute / "data.json"

    @pytest.mark.skipif(os.name == "nt", reason="tilde expansion uses HOME on POSIX")
    def test_expands_tilde_in_memory_root(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_home = isolated_cwd / "home" / "user"
        fake_home.mkdir(parents=True)
        mem = fake_home / "mem"
        mem.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setattr(config, "MEMORY_ROOT", "~/mem", raising=False)
        result = resolve_workspace_path("a.txt")
        assert result == mem / "a.txt"


@pytest.mark.skipif(os.name == "nt", reason="symlink behavior differs on Windows")
class TestSymlinkEscape:
    def test_symlink_filename_that_resolves_outside_workspace_is_rejected(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = isolated_cwd / "memory"
        monkeypatch.setattr(config, "MEMORY_ROOT", str(workspace), raising=False)
        workspace.mkdir(parents=True, exist_ok=True)
        outside = isolated_cwd / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        (workspace / "link.txt").symlink_to(outside)

        with pytest.raises(InvalidLLMRequestedPath, match="outside workspace"):
            resolve_workspace_path("link.txt")
