"""
Project list for the Project Context Switcher.

Reads ~/.nanobot/projects.json (or $NANOBOT_HOME/projects.json) which maps
project names to paths. Paths can be absolute or relative to the workspace.
No nanobot config or schema is modified.
"""

from __future__ import annotations

import json
from pathlib import Path

from nanobot.utils.helpers import get_data_path, get_workspace_path


def get_projects_path() -> Path:
    """Path to the projects config file."""
    return get_data_path() / "projects.json"


def load_projects(workspace_path: Path | None = None) -> dict[str, str]:
    """
    Load project name -> path from projects.json.
    Returns a dict mapping project name to resolved absolute path.
    """
    path = get_projects_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    raw = data if isinstance(data, dict) else data.get("projects", {})
    if not isinstance(raw, dict):
        return {}
    workspace = workspace_path or get_workspace_path()
    result: dict[str, str] = {}
    for name, p in raw.items():
        if not isinstance(p, str) or not name:
            continue
        expanded = Path(p).expanduser()
        if not expanded.is_absolute():
            expanded = workspace / p
        result[str(name).strip()] = str(expanded.resolve())
    return result


def get_project_context_path(project_path: str) -> Path | None:
    """
    Return path to PROJECT_CONTEXT.md or memory/MEMORY.md under the project path.
    Prefers PROJECT_CONTEXT.md, then memory/MEMORY.md.
    """
    root = Path(project_path)
    if not root.is_dir():
        return None
    for candidate in ("PROJECT_CONTEXT.md", "memory/MEMORY.md"):
        p = root / candidate
        if p.is_file():
            return p
    return None
