"""Allowlist HTTP handlers: list, add, remove tool approval entries."""

from __future__ import annotations

from server import allowlist as allowlist_module
from server.models import AllowlistAddRequest, AllowlistEntry, AllowlistResponse


async def get_allowlist(auth_user: object) -> AllowlistResponse:
    """List all allowlist entries (tool + pattern)."""
    entries = [
        AllowlistEntry(tool=e["tool"], pattern=e["pattern"])
        for e in allowlist_module.get_entries()
    ]
    return AllowlistResponse(entries=entries)


async def add_allowlist_entry(body: AllowlistAddRequest, auth_user: object) -> dict:
    """Add an entry to the allowlist."""
    allowlist_module.add(body.tool, body.pattern)
    return {"status": "added", "tool": body.tool, "pattern": body.pattern}


async def remove_allowlist_entry(body: AllowlistAddRequest, auth_user: object) -> dict:
    """Remove an allowlist entry."""
    removed = allowlist_module.remove(body.tool, body.pattern)
    return {"status": "removed" if removed else "not_found", "tool": body.tool, "pattern": body.pattern}
