/**
 * McpServerGuidanceCard — per-MCP-server "skills & rules" guidance editor.
 * Used in Settings > MCP Servers so users can define when/how the agent should use each server's tools.
 */

import { BookOpen } from 'lucide-react'

const textareaCls =
  'w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 outline-none focus:border-zinc-500 transition-colors resize-y min-h-[80px]'

interface McpServerGuidanceCardProps {
  serverKey: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

const DEFAULT_PLACEHOLDER =
  'e.g. Use headless for documentation and simple fetches. Use remote debugging when logging into accounts (e.g. X/Twitter) or when the site depends on cookies/session.'

export function McpServerGuidanceCard({
  serverKey,
  value,
  onChange,
  placeholder = DEFAULT_PLACEHOLDER,
}: McpServerGuidanceCardProps) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <BookOpen size={12} className="text-zinc-500 shrink-0" />
        <span className="text-xs font-medium text-zinc-500">Skills & rules</span>
        <span className="text-xs font-mono text-zinc-400">{serverKey}</span>
      </div>
      <textarea
        className={textareaCls}
        rows={4}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
      <p className="text-[10px] text-zinc-600">
        Injected into the agent system prompt when this server is configured. Markdown supported.
      </p>
    </div>
  )
}
