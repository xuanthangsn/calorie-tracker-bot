"""Filesystem permission policy for agent file actions.

Policy enforced by this module:
- only allow read/write under `<cwd>/memory`
- deny everything else by default
- normalize/resolve paths before authorization
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PathPermissionError(PermissionError):
    """Raised when a path is outside of the allowed permission scope."""


@dataclass(frozen=True)
class PathPermissionPolicy:
    """Authorize read/write paths against a strict memory-root policy."""

    cwd: Path
    memory_root: Path

    @classmethod
    def from_cwd(cls, cwd: Path | None = None) -> "PathPermissionPolicy":
        """Build policy rooted at `<cwd>/memory`.

        The memory directory is created if missing so `write` can create files
        without needing extra provisioning steps.
        """
        resolved_cwd = (cwd or Path.cwd()).resolve(strict=False)
        memory_root = (resolved_cwd / "memory").resolve(strict=False)
        memory_root.mkdir(parents=True, exist_ok=True)
        return cls(cwd=resolved_cwd, memory_root=memory_root)

    def authorize_read(self, requested_path: str) -> Path:
        """Return normalized path if readable; otherwise raise."""
        resolved = self._resolve_requested_path(requested_path, for_write=False)
        self._ensure_under_memory_root(resolved, operation="read")
        return resolved

    def authorize_write(self, requested_path: str) -> Path:
        """Return normalized path if writable; otherwise raise.

        The path itself may not exist yet; parent directories are validated
        against `memory_root` and can be created by caller inside that root.
        """
        resolved = self._resolve_requested_path(requested_path, for_write=True)
        self._ensure_under_memory_root(resolved, operation="write")
        return resolved

    def authorize(self, operation: str, requested_path: str) -> Path:
        """Authorize operation for a requested path."""
        if operation == "read":
            return self.authorize_read(requested_path)
        if operation == "write":
            return self.authorize_write(requested_path)
        raise PathPermissionError(f"unsupported operation: {operation}")

    def _resolve_requested_path(self, requested_path: str, *, for_write: bool) -> Path:
        if not isinstance(requested_path, str) or not requested_path.strip():
            raise PathPermissionError("path must be a non-empty string")

        candidate = Path(requested_path.strip()).expanduser()
        if not candidate.is_absolute():
            candidate = self.cwd / candidate

        # For writes, target may not exist yet. Resolve the existing parent.
        if for_write and not candidate.exists():
            resolved_parent = candidate.parent.resolve(strict=False)
            return resolved_parent / candidate.name

        return candidate.resolve(strict=False)

    def _ensure_under_memory_root(self, resolved_path: Path, *, operation: str) -> None:
        try:
            resolved_path.relative_to(self.memory_root)
        except ValueError as exc:
            raise PathPermissionError(
                f"permission denied for {operation} path: '{resolved_path}'"
            ) from exc
