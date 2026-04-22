"""Workspace path resolution utility for LLM file actions."""
from __future__ import annotations

from pathlib import Path

import config


class InvalidLLMRequestedPath(ValueError):
    """Raised when an LLM-provided file path is invalid for workspace access."""


def resolve_workspace_path(file_path_from_llm: str) -> Path:
    """Resolve an LLM-provided path into a canonical path under the LLM workspace.
    Workspace root comes from the ``MEMORY_ROOT`` environment variable. The returned path is guaranteed to be inside that root.
    """
    if not isinstance(file_path_from_llm, str):
        raise InvalidLLMRequestedPath("path must be a non-empty string")

    requested_name = file_path_from_llm.strip()
    if not requested_name:
        raise InvalidLLMRequestedPath("path must be a non-empty string")

    if not config.MEMORY_ROOT:
        raise ValueError("MEMORY_ROOT environment variable is not set")

    # LLM may request file name only; nested paths and traversal markers are forbidden.
    if "/" in requested_name or "\\" in requested_name:
        raise InvalidLLMRequestedPath(
            "path must be a file name only (nested paths are not allowed)"
        )
    if requested_name in {".", ".."}:
        raise InvalidLLMRequestedPath(
            "path must be a file name only ('.' and '..' are not allowed)"
        )

    root = Path(config.MEMORY_ROOT).expanduser()
    try:
        workspace_root = root.resolve(strict=False) if root.is_absolute() else (Path.cwd() / root).resolve(strict=False)
        workspace_root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise ValueError(f"Failed to resolve workspace root: {exc}") from exc

    # Always treat LLM input as relative to workspace root.
    candidate = workspace_root / requested_name

    resolved = candidate.resolve(strict=False)

    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise InvalidLLMRequestedPath(
            f"path is outside workspace: '{file_path_from_llm}'"
        ) from exc

    return resolved
