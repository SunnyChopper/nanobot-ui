/**
 * McpServerCard — one card per MCP server with connection status and skills/rules.
 * Used in Settings > MCP Servers so each server shows status and guidance in one place.
 */

import { useState } from 'react'
import { BookOpen, ChevronDown, ChevronRight, Loader2, Play, Trash2, Wrench } from 'lucide-react'
import { invokeMcpTool } from '../../api/mcp'
import type { McpServerStatus } from '../../api/mcp'
import type { MCPServerConfigResponse } from '../../api/types'

type PolicyValue = 'auto' | 'ask' | 'deny'
const POLICY_LABELS: Record<PolicyValue, string> = { auto: 'Auto', ask: 'Ask', deny: 'Deny' }
const POLICY_COLORS: Record<PolicyValue, string> = {
  auto: 'bg-emerald-700 text-emerald-100',
  ask: 'bg-yellow-700 text-yellow-100',
  deny: 'bg-red-800 text-red-100',
}
const POLICY_INACTIVE = 'text-zinc-500 hover:bg-zinc-700'

const textareaCls =
  'w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 outline-none focus:border-zinc-500 transition-colors resize-y min-h-[80px]'

const DEFAULT_GUIDANCE_PLACEHOLDER =
  'e.g. Use headless for documentation and simple fetches. Use remote debugging when logging into accounts (e.g. X/Twitter) or when the site depends on cookies/session.'

function maskConfigValue(val: string): string {
  if (!val || val.length < 8) return '***'
  if (/^https?:\/\//i.test(val)) return val.replace(/\/\/[^@/]+@/, '//***@')
  return val.slice(0, 4) + '…' + val.slice(-4)
}

function configSummary(serverConfig: MCPServerConfigResponse | null | undefined): string {
  if (!serverConfig) return ''
  if (serverConfig.url) return `URL: ${maskConfigValue(serverConfig.url)}`
  if (serverConfig.command)
    return `stdio: ${serverConfig.command} ${(serverConfig.args ?? []).slice(0, 2).join(' ')}`
  return ''
}

export interface McpServerCardProps {
  serverKey: string
  serverConfig: MCPServerConfigResponse | null | undefined
  status: McpServerStatus | undefined
  /** True while fetching status for this server (show "Checking…"). */
  statusLoading?: boolean
  /** True when fetch failed (show error state). */
  statusError?: boolean
  /** Optional config form block (command, args, url, env) rendered inside the card. */
  configSlot?: React.ReactNode
  /** When set, show delete button in header. */
  onDelete?: () => void
  /** Tool policy (full_name -> 'auto'|'ask'|'deny'). Used for MCP tools list. */
  toolPolicy?: Record<string, string>
  /** Called when user changes policy for one MCP tool. */
  onToolPolicyChange?: (fullName: string, value: PolicyValue) => void
  guidanceValue: string
  onGuidanceChange: (value: string) => void
  onTestConnection: () => Promise<void>
  testing: boolean
}

export function McpServerCard({
  serverKey,
  serverConfig,
  status,
  statusLoading = false,
  statusError = false,
  configSlot,
  onDelete,
  toolPolicy = {},
  onToolPolicyChange,
  guidanceValue,
  onGuidanceChange,
  onTestConnection,
  testing,
}: McpServerCardProps) {
  const [skillsOpen, setSkillsOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [toolTestTarget, setToolTestTarget] = useState<{ name: string; full_name: string; description: string } | null>(null)
  const [toolTestArgs, setToolTestArgs] = useState('{}')
  const [toolTestResult, setToolTestResult] = useState<string | null>(null)
  const [toolTestError, setToolTestError] = useState<string | null>(null)
  const [toolTestLoading, setToolTestLoading] = useState(false)
  const tools = status?.tools ?? []
  const statusVal = status?.status ?? (statusError ? 'error' : 'unknown')
  const statusLabel =
    statusLoading ? 'checking…' : statusError && !status ? 'failed to load' : statusVal === 'error' ? 'unreachable' : statusVal
  const usedBy = status?.used_by ?? []
  const summary = configSummary(serverConfig)

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden">
      {/* Connection status block */}
      <div className="px-3 py-2.5 text-xs space-y-1.5 border-b border-zinc-800/80">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono font-medium text-zinc-300">{serverKey}</span>
          <span
            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium ${
              statusLoading
                ? 'bg-zinc-700 text-zinc-400'
                : statusVal === 'connected'
                  ? 'bg-emerald-900/50 text-emerald-400'
                  : statusVal === 'misconfigured'
                    ? 'bg-amber-900/50 text-amber-400'
                    : 'bg-red-900/50 text-red-400'
            }`}
          >
            {statusLoading && <Loader2 size={10} className="animate-spin shrink-0" />}
            {statusLabel}
          </span>
          {statusVal === 'connected' && status?.tools_count != null && (
            <span className="text-zinc-500">{status.tools_count} tools</span>
          )}
          <button
            type="button"
            disabled={testing}
            onClick={onTestConnection}
            className="ml-auto flex items-center gap-1 rounded px-2 py-1 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 disabled:opacity-50"
          >
            {testing ? <Loader2 size={10} className="animate-spin" /> : null}
            Test connection
          </button>
          {onDelete && (
            <button
              type="button"
              onClick={onDelete}
              className="p-1 rounded text-zinc-600 hover:text-red-400 hover:bg-zinc-800 transition-colors"
              title="Remove server"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
        {summary && (
          <p className="text-zinc-500 font-mono truncate" title={summary}>
            {summary}
          </p>
        )}
        {status?.error && (
          <p className="text-red-400" title={status.error}>
            {status.error.slice(0, 80)}
            {status.error.length > 80 ? '…' : ''}
          </p>
        )}
        {usedBy.length > 0 && (
          <p className="text-zinc-500">
            Used by workflows: {usedBy.join(', ')}
          </p>
        )}
      </div>
      {configSlot && <div className="p-3 border-b border-zinc-800/80 space-y-2">{configSlot}</div>}
      {/* Tools — list with Auto/Ask/Deny per tool */}
      {tools.length > 0 && (
        <div className="border-b border-zinc-800/80">
          <button
            type="button"
            onClick={() => setToolsOpen((o) => !o)}
            className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs font-medium text-zinc-500 hover:bg-zinc-800/50 transition-colors"
          >
            {toolsOpen ? (
              <ChevronDown size={12} className="shrink-0" />
            ) : (
              <ChevronRight size={12} className="shrink-0" />
            )}
            <Wrench size={12} className="shrink-0" />
            Tools ({tools.length})
          </button>
          {toolsOpen && (
            <div className="px-3 pb-3 pt-0 space-y-1">
              {tools.map((t) => {
                const current = (toolPolicy[t.full_name] ?? 'ask') as PolicyValue
                return (
                  <div
                    key={t.full_name}
                    className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 gap-2"
                  >
                    <span
                      className="text-xs text-zinc-300 font-mono truncate min-w-0"
                      title={t.description || t.name}
                    >
                      {t.name}
                    </span>
                    <div className="flex gap-1 shrink-0 items-center">
                      {onToolPolicyChange &&
                        (['auto', 'ask', 'deny'] as PolicyValue[]).map((val) => (
                          <button
                            key={val}
                            type="button"
                            onClick={() => onToolPolicyChange(t.full_name, val)}
                            className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
                              current === val ? POLICY_COLORS[val] : POLICY_INACTIVE
                            }`}
                          >
                            {POLICY_LABELS[val]}
                          </button>
                        ))}
                      <button
                        type="button"
                        onClick={() => {
                          setToolTestTarget(t)
                          setToolTestArgs('{}')
                          setToolTestResult(null)
                          setToolTestError(null)
                        }}
                        className="flex items-center gap-0.5 px-2 py-0.5 rounded text-[11px] text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-colors"
                        title="Test this tool (runs for real, no chat session)"
                      >
                        <Play size={10} />
                        Test
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
      {/* Skills & rules — collapsible, collapsed by default */}
      <div className="border-b border-zinc-800/80">
        <button
          type="button"
          onClick={() => setSkillsOpen((o) => !o)}
          className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs font-medium text-zinc-500 hover:bg-zinc-800/50 transition-colors"
        >
          {skillsOpen ? (
            <ChevronDown size={12} className="shrink-0" />
          ) : (
            <ChevronRight size={12} className="shrink-0" />
          )}
          <BookOpen size={12} className="shrink-0" />
          Skills & rules (optional)
        </button>
        {skillsOpen && (
          <div className="px-3 pb-3 pt-0 space-y-2">
            <textarea
              className={textareaCls}
              rows={4}
              value={guidanceValue}
              onChange={(e) => onGuidanceChange(e.target.value)}
              placeholder={DEFAULT_GUIDANCE_PLACEHOLDER}
              spellCheck={false}
            />
            <p className="text-[10px] text-zinc-600">
              Injected into the agent system prompt when this server is configured. Markdown supported.
            </p>
          </div>
        )}
      </div>

      {/* Sandbox modal: test one MCP tool */}
      {toolTestTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setToolTestTarget(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 py-3 border-b border-zinc-700">
              <h3 className="text-sm font-semibold text-zinc-200">
                Test: {toolTestTarget.name}
              </h3>
              <p className="text-[10px] text-zinc-500 mt-0.5">
                Runs the tool for real (no chat session). Side effects will occur.
              </p>
            </div>
            <div className="p-4 space-y-2 flex-1 overflow-auto">
              <label className="block text-xs font-medium text-zinc-400">Arguments (JSON)</label>
              <textarea
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-xs font-mono text-zinc-200 min-h-[80px] resize-y"
                value={toolTestArgs}
                onChange={(e) => setToolTestArgs(e.target.value)}
                placeholder='{"url": "https://example.com"}'
                spellCheck={false}
              />
              {toolTestError && (
                <p className="text-xs text-red-400">{toolTestError}</p>
              )}
              {toolTestResult !== null && (
                <div>
                  <p className="text-xs font-medium text-zinc-400 mb-1">Result</p>
                  <pre className="text-xs text-zinc-300 bg-zinc-800 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap break-words">
                    {toolTestResult}
                  </pre>
                </div>
              )}
            </div>
            <div className="px-4 py-3 border-t border-zinc-700 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setToolTestTarget(null)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              >
                Close
              </button>
              <button
                type="button"
                disabled={toolTestLoading}
                onClick={async () => {
                  setToolTestError(null)
                  setToolTestResult(null)
                  let args: Record<string, unknown> = {}
                  try {
                    args = JSON.parse(toolTestArgs || '{}')
                  } catch {
                    setToolTestError('Invalid JSON')
                    return
                  }
                  setToolTestLoading(true)
                  try {
                    const res = await invokeMcpTool(serverKey, toolTestTarget.name, args)
                    setToolTestResult(res.result)
                  } catch (e: unknown) {
                    const msg =
                      e && typeof e === 'object' && 'detail' in e
                        ? String((e as { detail: unknown }).detail)
                        : 'Invoke failed'
                    setToolTestError(msg)
                  } finally {
                    setToolTestLoading(false)
                  }
                }}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors disabled:opacity-50"
              >
                {toolTestLoading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                Run
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
