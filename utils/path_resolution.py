"""Workspace path resolution utility for LLM file actions."""
from __future__ import annotations

from pathlib import Path

import config


class InvalidLLMRequestedPath(ValueError):
    """Raised when an LLM-provided file path is invalid for workspace access."""


def resolve_workspace_path(path_from_llm: str) -> Path:
    """Resolve an LLM-provided path into a canonical path under the LLM workspace.
    Workspace root comes from the ``MEMORY_ROOT`` environment variable. The returned path is guaranteed to be inside that root.
    """
    if not isinstance(path_from_llm, str) or not path_from_llm.strip():
        raise InvalidLLMRequestedPath("path must be a non-empty string")

    if not config.MEMORY_ROOT:
        raise InvalidLLMRequestedPath("memory_root environment variable is not set")

    root = Path(config.MEMORY_ROOT).expanduser()
    workspace_root = root.resolve(strict=False) if root.is_absolute() else (Path.cwd() / root).resolve(strict=False)
    workspace_root.mkdir(parents=True, exist_ok=True)

    requested = Path(path_from_llm.strip()).expanduser()
    if requested.is_absolute():
        candidate = requested
    else:
        candidate = workspace_root / requested

    resolved = candidate.resolve(strict=False)

    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise InvalidLLMRequestedPath(
            f"path is outside workspace: '{path_from_llm}'"
        ) from exc

    return resolved
