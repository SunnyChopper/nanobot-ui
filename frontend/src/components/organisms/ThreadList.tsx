import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Plus, Trash2, Pencil, Check, X, Search } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import type { SessionListItem } from '../../api/types'

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = Date.now()
  const diffMs = now - date.getTime()
  const diffMin = Math.floor(diffMs / 60_000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

function channelBadge(channel: string): { label: string; color: string } {
  const map: Record<string, { label: string; color: string }> = {
    web: { label: 'web', color: 'bg-blue-900/60 text-blue-300' },
    telegram: { label: 'tg', color: 'bg-sky-900/60 text-sky-300' },
    discord: { label: 'dc', color: 'bg-indigo-900/60 text-indigo-300' },
    slack: { label: 'sl', color: 'bg-purple-900/60 text-purple-300' },
    whatsapp: { label: 'wa', color: 'bg-emerald-900/60 text-emerald-300' },
    cli: { label: 'cli', color: 'bg-zinc-700 text-zinc-400' },
  }
  return map[channel] ?? { label: channel, color: 'bg-zinc-700 text-zinc-400' }
}

interface SessionRowProps {
  session: SessionListItem
  active: boolean
  onSelect: (key: string) => void
  onDelete: (key: string) => void
  onRename: (key: string, title: string) => void
}

function SessionRow({ session, active, onSelect, onDelete, onRename }: SessionRowProps) {
  const badge = channelBadge(session.channel)
  const displayName = session.title || 'Untitled chat'
  const [isRenaming, setIsRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState(displayName)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isRenaming && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isRenaming])

  function startRename(e: React.MouseEvent) {
    e.stopPropagation()
    setRenameValue(displayName)
    setIsRenaming(true)
  }

  function commitRename() {
    const trimmed = renameValue.trim()
    if (trimmed && trimmed !== displayName) {
      onRename(session.key, trimmed)
    }
    setIsRenaming(false)
  }

  function cancelRename() {
    setRenameValue(displayName)
    setIsRenaming(false)
  }

  function handleRenameKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') commitRename()
    if (e.key === 'Escape') cancelRename()
    e.stopPropagation()
  }

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation()
    if (window.confirm(`Delete "${displayName}"? This cannot be undone.`)) {
      onDelete(session.key)
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => !isRenaming && onSelect(session.key)}
      onKeyDown={(e) => !isRenaming && e.key === 'Enter' && onSelect(session.key)}
      className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
        active
          ? 'bg-zinc-700 text-zinc-100'
          : 'hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200'
      }`}
    >
      <MessageSquare size={13} className="shrink-0 opacity-70" />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span
            className={`rounded text-[9px] px-1 py-0.5 font-mono font-medium shrink-0 ${badge.color}`}
          >
            {badge.label}
          </span>

          {isRenaming ? (
            <input
              ref={inputRef}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={handleRenameKey}
              onBlur={commitRename}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 min-w-0 bg-zinc-700 text-zinc-100 text-xs rounded px-1 py-0.5 outline-none border border-zinc-500"
            />
          ) : (
            <span className="text-xs truncate font-medium">{displayName}</span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] text-zinc-600">
            {session.message_count} msg
          </span>
          <span className="text-[10px] text-zinc-600">
            {formatRelativeTime(session.updated_at)}
          </span>
        </div>
      </div>

      {isRenaming ? (
        <div className="flex gap-0.5 shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); commitRename() }}
            className="p-1 rounded hover:bg-zinc-600 text-zinc-400 hover:text-zinc-200"
            title="Confirm rename"
          >
            <Check size={11} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); cancelRename() }}
            className="p-1 rounded hover:bg-zinc-600 text-zinc-400 hover:text-zinc-200"
            title="Cancel rename"
          >
            <X size={11} />
          </button>
        </div>
      ) : (
        <div className="flex gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={startRename}
            className="p-1 rounded hover:bg-zinc-600 text-zinc-500 hover:text-zinc-300"
            title="Rename conversation"
          >
            <Pencil size={11} />
          </button>
          <button
            onClick={handleDelete}
            className="p-1 rounded hover:bg-zinc-600 text-zinc-500 hover:text-red-400"
            title="Delete conversation"
          >
            <Trash2 size={11} />
          </button>
        </div>
      )}
    </div>
  )
}

export function ThreadList() {
  const sessions = useChatStore((s) => s.sessions)
  const activeSessionId = useChatStore((s) => s.activeSessionId)
  const loadSessions = useChatStore((s) => s.loadSessions)
  const selectSession = useChatStore((s) => s.selectSession)
  const deleteSession = useChatStore((s) => s.deleteSession)
  const startNewSession = useChatStore((s) => s.startNewSession)
  const renameSession = useChatStore((s) => s.renameSession)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  const filteredSessions = searchQuery.trim()
    ? sessions.filter(
        (s) =>
          (s.title ?? '')
            .toLowerCase()
            .includes(searchQuery.trim().toLowerCase()) ||
          (s.chat_id ?? '')
            .toLowerCase()
            .includes(searchQuery.trim().toLowerCase()) ||
          (s.key ?? '')
            .toLowerCase()
            .includes(searchQuery.trim().toLowerCase())
      )
    : sessions

  return (
    <div className="flex flex-col h-full bg-zinc-900 border-r border-zinc-800">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-lg">🐈</span>
          <span className="text-sm font-semibold text-zinc-200">nanobot</span>
        </div>
        <button
          onClick={startNewSession}
          className="p-1.5 rounded-lg hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
          title="New conversation"
        >
          <Plus size={15} />
        </button>
      </div>

      <div className="px-2 py-2 border-b border-zinc-800">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations…"
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 py-2 space-y-0.5">
        {filteredSessions.length === 0 ? (
          <div className="text-center py-8 text-zinc-600 text-xs">
            {sessions.length === 0
              ? 'No conversations yet. Start chatting below.'
              : 'No matches for your search.'}
          </div>
        ) : (
          filteredSessions.map((session) => (
            <SessionRow
              key={session.key}
              session={session}
              active={session.key === activeSessionId}
              onSelect={selectSession}
              onDelete={deleteSession}
              onRename={renameSession}
            />
          ))
        )}
      </div>
    </div>
  )
}
