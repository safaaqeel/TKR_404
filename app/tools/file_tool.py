"""
Purpose:    Local file I/O with path-traversal enforcement. The single
            enforcement point in the codebase (§15) for keeping file
            writes/reads inside data/ or database/ — no other module may
            call raw open() for paths outside its own package-private
            concerns.
Inputs:     write(path, content) — path relative to the project root, plus
            text content. read(path) — path relative to the project root.
Outputs:    write() returns a dict with the resolved relative path and
            byte count. read() returns the file's text content. Both raise
            PermissionError if the resolved path escapes data/ or database/.
Depends on: data/, database/ (the only allowed roots).
Called by:  agents/automation_agent.py (dispatch table, "write_file" /
            "read_file"); tools/calendar_tool.py (persists generated .ics
            files through this module rather than calling open() directly).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ALLOWED_ROOTS = (
    (_PROJECT_ROOT / "data").resolve(),
    (_PROJECT_ROOT / "database").resolve(),
)


def _resolve_safe(path: str) -> Path:
    """Resolves `path` and guarantees it stays inside an allowed root.

    Raises PermissionError on any attempt to escape data/ or database/
    (e.g. via "../" traversal or an absolute path outside the project).
    """
    candidate = (_PROJECT_ROOT / path).resolve()

    for root in _ALLOWED_ROOTS:
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue

    raise PermissionError(f"Refusing to access path outside data/ or database/: {path!r}")


def write(path: str, content: str) -> Dict[str, Any]:
    """Writes `content` to `path`. `path` must resolve inside data/ or database/."""
    resolved = _resolve_safe(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return {
        "path": str(resolved.relative_to(_PROJECT_ROOT)),
        "bytes_written": len(content.encode("utf-8")),
    }


def read(path: str) -> str:
    """Reads and returns the text content at `path`."""
    resolved = _resolve_safe(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No such file: {path}")
    return resolved.read_text(encoding="utf-8")