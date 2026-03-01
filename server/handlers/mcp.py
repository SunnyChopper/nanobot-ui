"""MCP connection status and test endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException, Request

from nanobot.config.loader import get_data_dir
from server.agents.registry import get_mcp_usage_by_workflows


async def _check_mcp_server(name: str, cfg: Any) -> dict[str, Any]:
    """Try to connect to one MCP server and list tools. Returns status dict."""
    if not getattr(cfg, "command", None) and not getattr(cfg, "url", None):
        return {"server": name, "status": "misconfigured", "error": "No command or URL configured"}
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        return {"server": name, "status": "error", "error": "MCP client not installed"}

    @asynccontextmanager
    async def _connect():
        if getattr(cfg, "command", None):
            params = StdioServerParameters(
                command=cfg.command,
                args=getattr(cfg, "args", []) or [],
                env=getattr(cfg, "env", None),
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        elif getattr(cfg, "url", None):
            from mcp.client.streamable_http import streamable_http_client
            async with streamable_http_client(cfg.url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            raise ValueError("No command or URL")

    try:
        async with _connect() as session:
            tools_resp = await session.list_tools()
        tools_list = [
            {
                "name": t.name,
                "full_name": f"mcp_{name}_{t.name}",
                "description": (t.description or "")[:200] if t.description else "",
            }
            for t in tools_resp.tools
        ]
        return {
            "server": name,
            "status": "connected",
            "tools_count": len(tools_resp.tools),
            "tools": tools_list,
        }
    except Exception as e:
        return {"server": name, "status": "error", "error": str(e)}


async def get_mcp_status(request: Request) -> dict[str, Any]:
    """Return status for each configured MCP server and which workflows use them."""
    config = getattr(request.app.state, "config", None)
    if not config or not getattr(config, "tools", None):
        return {"servers": {}, "usage": {}}
    mcp_servers = getattr(config.tools, "mcp_servers", None) or {}
    data_dir = get_data_dir()
    usage = get_mcp_usage_by_workflows(data_dir)
    servers: dict[str, dict[str, Any]] = {}
    for name, cfg in mcp_servers.items():
        result = await _check_mcp_server(name, cfg)
        result["used_by"] = usage.get(name, [])
        servers[name] = result
    return {"servers": servers}


async def get_mcp_server_status(server_key: str, request: Request) -> dict[str, Any]:
    """Return status for a single MCP server (same shape as one entry in get_mcp_status servers)."""
    config = getattr(request.app.state, "config", None)
    if not config or not getattr(config.tools, "mcp_servers", None):
        raise HTTPException(status_code=400, detail="No MCP servers configured")
    mcp_servers = config.tools.mcp_servers
    if server_key not in mcp_servers:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_key}' not found")
    data_dir = get_data_dir()
    usage = get_mcp_usage_by_workflows(data_dir)
    result = await _check_mcp_server(server_key, mcp_servers[server_key])
    result["used_by"] = usage.get(server_key, [])
    return result


async def test_mcp_connection(server_key: str, request: Request) -> dict[str, Any]:
    """Test one MCP server by key. Returns success or error message."""
    config = getattr(request.app.state, "config", None)
    if not config or not getattr(config.tools, "mcp_servers", None):
        raise HTTPException(status_code=400, detail="No MCP servers configured")
    mcp_servers = config.tools.mcp_servers
    if server_key not in mcp_servers:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_key}' not found")
    result = await _check_mcp_server(server_key, mcp_servers[server_key])
    if result.get("status") == "connected":
        return {"ok": True, "server": server_key, "tools_count": result.get("tools_count", 0)}
    raise HTTPException(
        status_code=502,
        detail=result.get("error", "Connection failed"),
    )


async def _connect_mcp_session(server_key: str, request: Request):
    """Context manager: connect to one MCP server and yield session."""
    config = getattr(request.app.state, "config", None)
    if not config or not getattr(config.tools, "mcp_servers", None):
        raise HTTPException(status_code=400, detail="No MCP servers configured")
    mcp_servers = config.tools.mcp_servers
    if server_key not in mcp_servers:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_key}' not found")
    cfg = mcp_servers[server_key]
    if not getattr(cfg, "command", None) and not getattr(cfg, "url", None):
        raise HTTPException(status_code=400, detail="No command or URL configured")
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        raise HTTPException(status_code=503, detail="MCP client not installed")

    @asynccontextmanager
    async def _connect():
        if getattr(cfg, "command", None):
            params = StdioServerParameters(
                command=cfg.command,
                args=getattr(cfg, "args", []) or [],
                env=getattr(cfg, "env", None),
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            from mcp.client.streamable_http import streamable_http_client
            async with streamable_http_client(cfg.url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

    return _connect()


async def invoke_mcp_tool(server_key: str, request: Request) -> dict[str, Any]:
    """Invoke one MCP tool by server key and tool name (sandbox: runs for real, no chat session)."""
    body = await request.json()
    tool_name = body.get("tool_name")
    arguments = body.get("arguments") or {}
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name required")
    try:
        from mcp import types
    except ImportError:
        raise HTTPException(status_code=503, detail="MCP client not installed")

    async with (await _connect_mcp_session(server_key, request)) as session:
        result = await session.call_tool(tool_name, arguments=arguments)
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
        else:
            parts.append(str(block))
    text = "\n".join(parts) if parts else "(no output)"
    return {"ok": True, "server": server_key, "tool": tool_name, "result": text}
