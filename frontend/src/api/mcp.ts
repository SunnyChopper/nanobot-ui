/** MCP connection status and test */

import { apiFetch } from './http'

export interface McpToolInfo {
  name: string
  full_name: string
  description: string
}

export interface McpServerStatus {
  server: string
  status: 'connected' | 'error' | 'misconfigured'
  error?: string
  tools_count?: number
  tools?: McpToolInfo[]
  used_by?: string[]
}

export interface McpStatusResponse {
  servers: Record<string, McpServerStatus>
}

export function getMcpStatus(): Promise<McpStatusResponse> {
  return apiFetch('/mcp/status')
}

export function getMcpServerStatus(serverKey: string): Promise<McpServerStatus> {
  return apiFetch(`/mcp/status/${encodeURIComponent(serverKey)}`)
}

export function testMcpConnection(serverKey: string): Promise<{ ok: boolean; server: string; tools_count: number }> {
  return apiFetch(`/mcp/test/${encodeURIComponent(serverKey)}`, { method: 'POST' })
}

export interface InvokeMcpToolResponse {
  ok: boolean
  server: string
  tool: string
  result: string
}

export function invokeMcpTool(
  serverKey: string,
  toolName: string,
  arguments_: Record<string, unknown> = {}
): Promise<InvokeMcpToolResponse> {
  return apiFetch(`/mcp/servers/${encodeURIComponent(serverKey)}/tools/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_name: toolName, arguments: arguments_ }),
  })
}
