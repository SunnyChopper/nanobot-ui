"""
Shared runtime context for a single graph run.

Injected into every node execution and into the nanobot invocation.
Credentials are resolved at runtime (e.g. via Bitwarden MCP) and never
hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuntimeContext:
    """
    Per-run context: MCP connections, session, credentials, logging.

    Built in our layer at workflow run start; passed to the nanobot
    node invoker and optionally to tools that need credentials.
    """

    run_id: str
    workflow_name: str
    node_name: str = ""
    """Current node name (set by invoker for each node)."""
    credentials: dict[str, str] = field(default_factory=dict)
    """Resolved secrets by logical name (e.g. Bitwarden item name -> secret)."""
    session_key: str = ""
    """Session key for nanobot (e.g. workflow:{run_id}). Set from run_id if empty."""
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
    """Extra key-value data for logging or tool context."""

    def __post_init__(self) -> None:
        if not self.session_key and self.run_id:
            self.session_key = f"workflow:{self.run_id}"
