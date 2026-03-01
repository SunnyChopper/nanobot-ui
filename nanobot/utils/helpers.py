"""Utility functions for nanobot."""

import os
import re
import sys
from pathlib import Path
from datetime import datetime

_windows_dpi_aware_done = False


def ensure_windows_dpi_aware() -> None:
    """Set process DPI awareness on Windows so screenshot and click use the same coordinate system.
    Idempotent and safe to call from multiple modules (executor, capture, desktop). No-op on non-Windows."""
    global _windows_dpi_aware_done
    if _windows_dpi_aware_done or sys.platform != "win32":
        return
    try:
        ctypes = __import__("ctypes")
        shcore = getattr(ctypes.windll, "shcore", None)
        if shcore is not None:
            shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        _windows_dpi_aware_done = True
    except Exception:
        _windows_dpi_aware_done = True


def get_nanobot_home() -> Path:
    """
    Get the nanobot home directory (config, data, workspace parent).
    Uses NANOBOT_HOME if set, otherwise ~/.nanobot.
    """
    raw = os.environ.get("NANOBOT_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".nanobot"


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_path() -> Path:
    """Get the nanobot data directory (~/.nanobot or $NANOBOT_HOME)."""
    return ensure_dir(get_nanobot_home())


def get_workspace_path(workspace: str | None = None) -> Path:
    """
    Get the workspace path.
    Defaults to ~/.nanobot/workspace or $NANOBOT_HOME/workspace.
    """
    if workspace:
        path = Path(workspace).expanduser()
    else:
        path = get_nanobot_home() / "workspace"
    return ensure_dir(path)


def get_sessions_path() -> Path:
    """Sessions directory under nanobot home."""
    return ensure_dir(get_nanobot_home() / "sessions")


def timestamp() -> str:
    """Current ISO timestamp."""
    return datetime.now().isoformat()


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')

def safe_filename(name: str) -> str:
    """Replace unsafe path characters with underscores."""
    return _UNSAFE_CHARS.sub("_", name).strip()


def sync_workspace_templates(workspace: Path, silent: bool = False) -> list[str]:
    """Sync bundled templates to workspace. Only creates missing files."""
    from importlib.resources import files as pkg_files
    try:
        tpl = pkg_files("nanobot") / "templates"
    except Exception:
        return []
    if not tpl.is_dir():
        return []

    added: list[str] = []

    def _write(src, dest: Path):
        if dest.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8") if src else "", encoding="utf-8")
        added.append(str(dest.relative_to(workspace)))

    for item in tpl.iterdir():
        if item.name.endswith(".md"):
            _write(item, workspace / item.name)
    _write(tpl / "memory" / "MEMORY.md", workspace / "memory" / "MEMORY.md")
    _write(None, workspace / "memory" / "HISTORY.md")
    (workspace / "skills").mkdir(exist_ok=True)

    if added and not silent:
        from rich.console import Console
        for name in added:
            Console().print(f"  [dim]Created {name}[/dim]")
    return added
