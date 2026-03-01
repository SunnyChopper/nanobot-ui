"""
Tool approval allowlist: when a tool+pattern is allowlisted, the server
auto-approves without prompting. Used to make it clear which commands
(e.g. Get-ChildItem) are trusted.
"""

from __future__ import annotations

import fnmatch
from typing import Any

# In-memory store: list of { "tool": str, "pattern": str }
# For "exec", pattern is the exact command or a glob (e.g. "Get-ChildItem*").
_entries: list[dict[str, str]] = []


def get_entries() -> list[dict[str, str]]:
    """Return a copy of the allowlist entries."""
    return list(_entries)


def add(tool: str, pattern: str) -> None:
    """Add an allowlist entry. Pattern is the command or glob for that tool."""
    entry = {"tool": tool, "pattern": pattern}
    if entry not in _entries:
        _entries.append(entry)


def remove(tool: str, pattern: str) -> bool:
    """Remove an allowlist entry. Returns True if one was removed."""
    for i, e in enumerate(_entries):
        if e["tool"] == tool and e["pattern"] == pattern:
            _entries.pop(i)
            return True
    return False


def is_allowlisted(tool_name: str, tool_args: dict[str, Any]) -> bool:
    """
    Return True if this tool call matches any allowlisted entry.
    For "exec", the pattern is matched against the command string (e.g. arguments["command"]).
    """
    cmd_preview = get_command_preview(tool_name, tool_args)
    for entry in _entries:
        if entry["tool"] != tool_name:
            continue
        pattern = entry["pattern"]
        if tool_name == "exec":
            if not cmd_preview:
                continue
            if cmd_preview == pattern:
                return True
            if fnmatch.fnmatch(cmd_preview, pattern):
                return True
        elif tool_name == "run_python" and cmd_preview:
            if cmd_preview == pattern or fnmatch.fnmatch(cmd_preview, pattern):
                return True
        else:
            import json
            args_str = json.dumps(tool_args, sort_keys=True)
            if pattern in args_str or fnmatch.fnmatch(args_str, pattern):
                return True
    return False


def get_command_preview(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Return a human-readable command string for display (e.g. for exec, run_python)."""
    if tool_name == "exec":
        cmd = tool_args.get("command") or tool_args.get("cmd")
        if isinstance(cmd, list):
            return " ".join(str(c) for c in cmd)
        if cmd is not None:
            return str(cmd).strip()
        for v in tool_args.values():
            if isinstance(v, str) and v.strip():
                return str(v).strip()
    if tool_name == "run_python":
        code = tool_args.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()[:500] + ("..." if len(code) > 500 else "")
    return ""


def pattern_for_tool(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Return the pattern string that would be stored for this tool call (for allowlist add)."""
    if tool_name in ("exec", "run_python"):
        return get_command_preview(tool_name, tool_args)
    import json
    return json.dumps(tool_args, sort_keys=True)
