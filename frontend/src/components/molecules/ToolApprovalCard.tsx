/**
 * ToolApprovalCard — shown when the agent wants to run a tool that requires
 * user approval. The user can Approve, Deny, or Add to Allowlist.
 */

import { useState } from 'react'
import { Check, ChevronDown, ChevronUp, ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { addAllowlistEntry } from '../../api/client'
import type { ApprovalRequest, ApprovalOutcome } from '../../api/types'
import { getToolDisplayName } from '../../lib/toolLabels'

const PREVIEW_LINES = 3
const CONTEXT_TITLE_MAX = 40

interface Props {
  approval: ApprovalRequest
  resolved?: ApprovalOutcome
  contextLabel?: string
  /** outcome; when outcome is 'denied', optional reason can be passed for course-correction */
  onResolve: (toolId: string, outcome: ApprovalOutcome, reason?: string) => void
}

function formatArgValue(val: unknown): string {
  if (typeof val === 'string') return val
  return JSON.stringify(val, null, 2)
}

function getPreviewSnippet(approval: ApprovalRequest): string {
  const entries = Object.entries(approval.arguments)
  if (entries.length === 0) return ''
  const [, val] = entries[0]
  const str = formatArgValue(val)
  const lines = str.split('\n')
  return lines.slice(0, PREVIEW_LINES).join('\n')
}

function getAllowlistPattern(approval: ApprovalRequest): string {
  if (approval.name === 'exec') {
    const cmd = approval.arguments.command ?? approval.arguments.cmd
    if (typeof cmd === 'string') return cmd.trim()
    if (Array.isArray(cmd)) return cmd.map(String).join(' ').trim()
    for (const v of Object.values(approval.arguments)) {
      if (typeof v === 'string' && v.trim()) return v.trim()
    }
  }
  return JSON.stringify(approval.arguments)
}

const RESOLVED_LABELS: Record<ApprovalOutcome, string> = {
  approved: 'Approved',
  denied: 'Denied',
  allowlisted: 'Added to allowlist',
}

function truncateContext(s: string, max: number): string {
  const t = s.trim()
  if (t.length <= max) return t
  return t.slice(0, max).trim() + '…'
}

export function ToolApprovalCard({ approval, resolved, contextLabel, onResolve }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [showAllowlistModal, setShowAllowlistModal] = useState(false)
  const [showDenyReasonModal, setShowDenyReasonModal] = useState(false)
  const [denyReason, setDenyReason] = useState('')
  const [allowlistLoading, setAllowlistLoading] = useState(false)
  const label = getToolDisplayName(approval.name)
  const argEntries = Object.entries(approval.arguments)
  const pattern = getAllowlistPattern(approval)
  const previewSnippet = getPreviewSnippet(approval)
  const title =
    approval.title?.trim() ||
    (contextLabel && contextLabel.trim()
      ? `Approval: ${truncateContext(contextLabel, CONTEXT_TITLE_MAX)}`
      : `Approval required — ${label}`)

  async function handleAddToAllowlist() {
    if (!pattern) return
    setAllowlistLoading(true)
    try {
      await addAllowlistEntry(approval.name, pattern)
      setShowAllowlistModal(false)
      onResolve(approval.tool_id, 'allowlisted')
    } catch (e) {
      console.warn('Failed to add to allowlist:', e)
    } finally {
      setAllowlistLoading(false)
    }
  }

  const actionButtons = resolved ? null : (
    <div className="flex flex-wrap items-center gap-1.5 shrink-0">
      <button
        onClick={(e) => {
          e.stopPropagation()
          onResolve(approval.tool_id, 'approved')
        }}
        className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white text-[11px] font-semibold transition-colors"
      >
        <Check size={12} />
        Approve
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation()
          setDenyReason('')
          setShowDenyReasonModal(true)
        }}
        className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-800 text-zinc-200 text-[11px] font-semibold transition-colors"
      >
        <X size={12} />
        Deny
      </button>
      {pattern && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            setShowAllowlistModal(true)
          }}
          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-amber-600/80 hover:bg-amber-600 active:bg-amber-700 text-white text-[11px] font-semibold transition-colors"
          title="Add this command to the allowlist so it runs without asking next time"
        >
          <ShieldCheck size={12} />
          Allowlist
        </button>
      )}
    </div>
  )

  return (
    <>
      <div className="w-full mb-3">
        <div className="rounded-xl border border-zinc-600/80 bg-zinc-800/40 overflow-hidden">
          <div
            className="flex flex-col gap-2 px-3 py-2.5 cursor-pointer select-none hover:bg-zinc-700/30 transition-colors"
            onClick={() => setExpanded((e) => !e)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                setExpanded((v) => !v)
              }
            }}
            aria-expanded={expanded}
          >
            <div className="flex items-center gap-2 flex-wrap">
              {expanded ? (
                <ChevronUp className="w-4 h-4 text-zinc-400 shrink-0" aria-hidden />
              ) : (
                <ChevronDown className="w-4 h-4 text-zinc-400 shrink-0" aria-hidden />
              )}
              <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
              <span className="text-xs font-semibold text-zinc-200">{title}</span>
              {resolved && (
                <span className="text-xs text-zinc-500 ml-1">
                  — {RESOLVED_LABELS[resolved]}
                </span>
              )}
              <div className="ml-auto flex items-center gap-2">{actionButtons}</div>
            </div>
            {!expanded && previewSnippet && (
              <div className="relative pl-6 pr-2 py-1.5 rounded bg-zinc-900/50 border border-zinc-700/50 overflow-hidden">
                <pre
                  className="text-[11px] text-zinc-500 font-mono whitespace-pre-wrap break-words leading-relaxed max-h-[4.5rem] overflow-hidden select-none pointer-events-none"
                  style={resolved ? undefined : { filter: 'blur(3px)' }}
                >
                  {previewSnippet}
                </pre>
              </div>
            )}
          </div>

          {expanded && (
            <div className="border-t border-zinc-700/50">
              {resolved && (
                <div className="px-4 pt-2 pb-1 text-xs text-zinc-500">
                  {RESOLVED_LABELS[resolved]}
                </div>
              )}
              {argEntries.length > 0 && (
                <div className="px-4 py-3 space-y-2">
                  {argEntries.map(([key, val]) => (
                    <div key={key}>
                      <p className="text-xs text-zinc-500 mb-0.5">{key}</p>
                      <pre className="text-xs text-zinc-200 bg-zinc-900/60 rounded px-3 py-2 overflow-x-auto whitespace-pre-wrap break-words font-mono max-h-48 overflow-y-auto">
                        {formatArgValue(val)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {showDenyReasonModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowDenyReasonModal(false)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl max-w-lg w-full p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm font-medium text-zinc-200 mb-2">
              Deny this action. Optionally add feedback so the bot can course-correct:
            </p>
            <textarea
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
              placeholder="e.g. Use a different approach, or don't run that command."
              className="w-full min-h-[80px] px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-500 resize-y mb-4"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDenyReasonModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowDenyReasonModal(false)
                  onResolve(approval.tool_id, 'denied', denyReason.trim() || undefined)
                }}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-zinc-600 hover:bg-zinc-500 text-white text-xs font-semibold transition-colors"
              >
                Deny
              </button>
            </div>
          </div>
        </div>
      )}

      {showAllowlistModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => !allowlistLoading && setShowAllowlistModal(false)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl max-w-lg w-full p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm font-medium text-zinc-200 mb-2">
              The following will be allowlisted (future runs won’t ask for approval):
            </p>
            <pre className="text-xs text-zinc-300 bg-zinc-800 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words font-mono mb-4">
              {pattern}
            </pre>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => !allowlistLoading && setShowAllowlistModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddToAllowlist}
                disabled={allowlistLoading}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold transition-colors disabled:opacity-50"
              >
                {allowlistLoading ? 'Adding…' : 'Confirm and approve'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
