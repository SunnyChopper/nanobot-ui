/**
 * Global chat state managed with Zustand.
 *
 * This store is the single source of truth for:
 * - The thread/session list (from REST API)
 * - The active session and its messages
 * - The live streaming state (tokens accumulating)
 * - Pending tool calls being executed
 * - WebSocket connection status
 */

import { create } from 'zustand'
import {
  branchSession as apiBranchSession,
  deleteSession,
  editSessionMessage,
  getSession,
  getSessions,
  getStatus,
  renameSession as apiRenameSession,
  retrySession,
  setSessionProject as apiSetSessionProject,
} from '../api/client'

const uuidv4 = () => crypto.randomUUID()
import type {
  ApprovalRequest,
  ApprovalOutcome,
  ChatMessage,
  MessageBlock,
  QueuedMessage,
  SessionListItem,
  StatusResponse,
  ToolCallEvent,
  WsConnectionStatus,
  WsServerFrame,
} from '../api/types'
import { NanobotWebSocket } from '../api/websocket'

// ---------------------------------------------------------------------------
// Persist a stable session ID in localStorage so refreshes reconnect the
// same conversation.
// ---------------------------------------------------------------------------

/** Normalize toolCall payload so UI always gets name, arguments, result, tool_id (API may send e.g. toolId). */
function normalizeToolCallPayload(payload: Record<string, unknown>): ToolCallEvent {
  return {
    name: (payload.name as string) ?? '',
    arguments: (payload.arguments as Record<string, unknown>) ?? {},
    result: payload.result as string | undefined,
    tool_id: (payload.tool_id as string | undefined) ?? (payload as Record<string, unknown>).toolId as string | undefined,
  }
}

/** Normalize a block from the API so the UI always receives canonical shape (e.g. toolCall not tool_call). */
function normalizeBlock(block: Record<string, unknown>): MessageBlock {
  const type = block.type as string
  if (type === 'tool_call') {
    const rawPayload = (block.toolCall ?? block.tool_call) as Record<string, unknown> | undefined
    if (rawPayload && typeof rawPayload === 'object') {
      return { type: 'tool_call', toolCall: normalizeToolCallPayload(rawPayload) }
    }
  }
  if (type === 'content' && typeof block.text === 'string') {
    return { type: 'content', text: block.text }
  }
  if (type === 'thinking' && typeof block.text === 'string') {
    return {
      type: 'thinking',
      text: block.text,
      collapsed: block.collapsed as boolean | undefined,
    }
  }
  if (type === 'approval_request' && block.request) {
    return {
      type: 'approval_request',
      request: block.request as ApprovalRequest,
      resolved: block.resolved as ApprovalOutcome | undefined,
    }
  }
  return block as MessageBlock
}

/**
 * Returns a session key always in the form "web:{uuid}".
 * Handles both old bare-UUID storage and new prefixed format.
 * Same key is used for GET /sessions/:key and WebSocket session; consistency ensures tool calls persist after reload.
 */
function getOrCreateSessionId(): string {
  const STORAGE_KEY = 'nanobot_session_id'
  let stored = localStorage.getItem(STORAGE_KEY)
  if (!stored) {
    const key = `web:${uuidv4()}`
    localStorage.setItem(STORAGE_KEY, key)
    return key
  }
  // Migrate old bare-UUID values to prefixed format
  if (!stored.includes(':')) {
    const key = `web:${stored}`
    localStorage.setItem(STORAGE_KEY, key)
    return key
  }
  return stored
}

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------

interface ChatStore {
  // ---- Connection ----
  connectionStatus: WsConnectionStatus
  wsClient: NanobotWebSocket | null

  // ---- Sessions ----
  sessions: SessionListItem[]
  activeSessionId: string
  /** Metadata for the active session (from last loadSession), e.g. title, project. */
  activeSessionMetadata: Record<string, unknown>
  status: StatusResponse | null

  // ---- Messages ----
  messages: ChatMessage[]
  streamingMessageId: string | null
  pendingToolCalls: Map<string, ToolCallEvent>
  /** True after sendMessage() until first token/error arrives */
  waitingForResponse: boolean
  /** Tools awaiting user approval before the agent can execute them. */
  pendingApprovals: ApprovalRequest[]
  /** Messages queued while the bot is running (server echoes via queue_updated). */
  messageQueue: QueuedMessage[]

  // ---- Actions ----
  /** Connect to the WebSocket and start listening. */
  connect: () => void
  /** Disconnect and clean up. */
  disconnect: () => void

  /** Refresh the session list from the REST API. */
  loadSessions: () => Promise<void>
  /** Load full history for a session. */
  loadSession: (key: string) => Promise<void>
  /** Switch to a different session (loads history). */
  selectSession: (key: string) => Promise<void>
  /** Delete (hard-delete) a session. */
  deleteSession: (key: string) => Promise<void>
  /** Start a new conversation (clear + switch). */
  startNewSession: () => Promise<void>
  /** Rename a session title. */
  renameSession: (key: string, title: string) => Promise<void>
  /** Set active project for the current session (for context injection). */
  setSessionProject: (project: string | null) => Promise<void>
  /** Retry the last assistant message (re-run last user message). */
  retryLastMessage: () => Promise<void>
  /** Edit a user message at index, truncating downstream messages. */
  editMessage: (messageIndex: number, newContent: string) => Promise<void>
  /** Branch from a message: create a new session with history up to messageIndex, then switch to it. */
  branchFromMessage: (messageIndex: number) => Promise<void>

  /** Send a chat message via WebSocket. Optional attachments are paths from upload API (e.g. "media/uuid.png"). */
  sendMessage: (content: string, attachments?: string[]) => void

  /** Resolve a pending tool approval (approve, deny, or add to allowlist). When outcome is 'denied', optional reason is sent for course-correction. */
  approveToolCall: (toolId: string, outcome: 'approved' | 'denied' | 'allowlisted', reason?: string) => void

  /** Stop the current streaming run (interrupt). */
  interruptStream: () => void

  /** Remove a message from the queue (retract). */
  retractFromQueue: (queueId: string) => void
  /** Run a queued message immediately (interrupts current run). */
  runImmediately: (queueId: string) => void

  /** Load backend status. */
  loadStatus: () => Promise<void>

  // Internal handlers (called from WS event router)
  _handleFrame: (frame: WsServerFrame) => void
  _setConnectionStatus: (status: WsConnectionStatus) => void
}

// ---------------------------------------------------------------------------
// Store implementation
// ---------------------------------------------------------------------------

export const useChatStore = create<ChatStore>((set, get) => {
  return {
    connectionStatus: 'disconnected',
    wsClient: null,
    sessions: [],
    activeSessionId: getOrCreateSessionId(),
    activeSessionMetadata: {},
    status: null,
    messages: [],
    streamingMessageId: null,
    pendingToolCalls: new Map(),
    waitingForResponse: false,
    pendingApprovals: [],
    messageQueue: [],

    // ---- Connection ----

    connect() {
      const existing = get().wsClient
      if (existing) return

      // The WS client only needs the bare UUID (the server will prefix with "web:")
      const activeKey = get().activeSessionId
      const bareId = activeKey.startsWith('web:') ? activeKey.slice(4) : activeKey

      const client = new NanobotWebSocket({
        sessionId: bareId,
        onFrame: (frame) => get()._handleFrame(frame),
        onStatus: (status) => get()._setConnectionStatus(status),
      })
      client.connect()

      set({ wsClient: client })

      // Also load initial data
      get().loadSessions()
      get().loadStatus()
    },

    disconnect() {
      get().wsClient?.close()
      set({ wsClient: null, connectionStatus: 'disconnected' })
    },

    // ---- Sessions ----

    async loadSessions() {
      try {
        const sessions = await getSessions()
        set({ sessions })
      } catch (e) {
        console.warn('Failed to load sessions:', e)
      }
    },

    async loadSession(key) {
      try {
        const detail = await getSession(key)
        const messages: ChatMessage[] = detail.messages.map((m, i) => {
          const msg: ChatMessage = {
            id: `${key}-${i}`,
            role: m.role,
            content: m.content,
            timestamp: m.timestamp ? Date.parse(m.timestamp) : Date.now(),
            tools_used: m.tools_used ?? undefined,
          }
          if (m.role === 'assistant') {
            if (m.blocks && m.blocks.length > 0) {
              msg.blocks = (m.blocks as Record<string, unknown>[]).map(normalizeBlock)
            } else if (m.tools_used && m.tools_used.length > 0) {
              msg.blocks = [
                ...m.tools_used.map(
                  (name): MessageBlock => ({
                    type: 'tool_call',
                    toolCall: { name, arguments: {} },
                  })
                ),
                ...(m.content
                  ? [{ type: 'content' as const, text: m.content }]
                  : []),
              ]
            } else if (m.content) {
              msg.blocks = [{ type: 'content', text: m.content }]
            }
          }
          return msg
        })
        set({
          messages,
          streamingMessageId: null,
          pendingToolCalls: new Map(),
          pendingApprovals: [],
          activeSessionMetadata: detail.metadata ?? {},
        })
      } catch (e) {
        console.warn('Failed to load session:', e)
      }
    },

    async selectSession(key) {
      // key is always "channel:id", e.g. "web:abc-123"
      set({ activeSessionId: key })
      localStorage.setItem('nanobot_session_id', key)
      await get().loadSession(key)
    },

    async deleteSession(key) {
      await deleteSession(key)
      const { activeSessionId } = get()
      await get().loadSessions()
      if (activeSessionId === key) {
        // Switch to next available session or start fresh
        const remaining = get().sessions.filter((s) => s.key !== key)
        if (remaining.length > 0) {
          await get().selectSession(remaining[0].key)
        } else {
          await get().startNewSession()
        }
      }
    },

    async startNewSession() {
      const newKey = `web:${uuidv4()}`
      localStorage.setItem('nanobot_session_id', newKey)
      const bareId = newKey.slice(4)

      set({
        activeSessionId: newKey,
        activeSessionMetadata: {},
        messages: [],
        streamingMessageId: null,
        pendingToolCalls: new Map(),
        waitingForResponse: false,
      })

      // Tell the server about the new session (bare UUID, server prefixes "web:")
      get().wsClient?.send({ type: 'new_session', session_id: bareId })

      // Reload session list
      await get().loadSessions()
    },

    async renameSession(key, title) {
      await apiRenameSession(key, title)
      await get().loadSessions()
    },

    async setSessionProject(project) {
      const { activeSessionId } = get()
      await apiSetSessionProject(activeSessionId, project)
      set((s) => ({
        activeSessionMetadata: {
          ...s.activeSessionMetadata,
          project: project ?? undefined,
        },
      }))
    },

    async retryLastMessage() {
      const { activeSessionId, messages } = get()
      const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')
      if (!lastUserMsg) return

      const result = await retrySession(activeSessionId)
      if (result.status === 'no_user_message') return

      // Switch to the new branch (server created it with messages up to last user)
      await get().selectSession(result.key)
      get().sendMessage(lastUserMsg.content)
    },

    async editMessage(messageIndex, newContent) {
      const { activeSessionId, messages } = get()

      // Truncate on the server (removes messages at index and beyond)
      await editSessionMessage(activeSessionId, messageIndex, newContent)

      // Truncate locally
      set({ messages: messages.slice(0, messageIndex), streamingMessageId: null })

      // Send the new content
      get().sendMessage(newContent)
    },

    async branchFromMessage(messageIndex) {
      const { activeSessionId } = get()
      const result = await apiBranchSession(activeSessionId, messageIndex)
      if (result.status !== 'branched') return
      await get().selectSession(result.key)
      await get().loadSessions()
    },

    // ---- Messaging ----

    sendMessage(content, attachments) {
      const { wsClient, activeSessionId, connectionStatus, streamingMessageId, waitingForResponse } = get()
      if (connectionStatus !== 'connected' || !wsClient) return

      const isStreaming = streamingMessageId !== null || waitingForResponse
      const queueId = uuidv4()

      const userMsg: ChatMessage = {
        id: uuidv4(),
        role: 'user',
        content,
        timestamp: Date.now(),
        ...(attachments?.length ? { attachments } : {}),
      }
      set((s) => ({
        messages: [...s.messages, userMsg],
        waitingForResponse: true,
        ...(isStreaming
          ? { messageQueue: [...s.messageQueue, { queue_id: queueId, content, attachments }] }
          : {}),
      }))

      const sessionIdForWs = activeSessionId.startsWith('web:')
        ? activeSessionId.slice(4)
        : activeSessionId

      const frame: { type: 'message'; content: string; session_id: string; attachments?: string[]; queue_id?: string } = {
        type: 'message',
        content,
        session_id: sessionIdForWs,
      }
      if (attachments?.length) frame.attachments = attachments
      if (isStreaming) frame.queue_id = queueId
      wsClient.send(frame)
    },

    // ---- Status ----

    async loadStatus() {
      try {
        const status = await getStatus()
        set({ status })
      } catch (e) {
        console.warn('Failed to load status:', e)
      }
    },

    // ---- Internal WebSocket frame handler ----

    _handleFrame(frame) {
      switch (frame.type) {
        case 'session_ready': {
          // Server confirmed session -- nothing special needed
          break
        }

        case 'token': {
          const { streamingMessageId } = get()

          if (streamingMessageId) {
            // Append token to existing streaming bubble (content and last content block)
            set((s) => {
              const messages = s.messages.map((m) => {
                if (m.id !== streamingMessageId) return m
                const blocks = m.blocks ?? [{ type: 'content' as const, text: m.content }]
                const last = blocks[blocks.length - 1]
                const nextBlocks =
                  last?.type === 'content'
                    ? [...blocks.slice(0, -1), { type: 'content' as const, text: last.text + frame.content }]
                    : [...blocks, { type: 'content' as const, text: frame.content }]
                return {
                  ...m,
                  content: m.content + frame.content,
                  blocks: nextBlocks,
                }
              })
              return { messages, waitingForResponse: false }
            })
          } else {
            // Create a new assistant bubble with timeline blocks
            const msgId = uuidv4()
            const assistantMsg: ChatMessage = {
              id: msgId,
              role: 'assistant',
              content: frame.content,
              timestamp: Date.now(),
              streaming: true,
              blocks: [{ type: 'content', text: frame.content }],
            }
            set((s) => ({
              messages: [...s.messages, assistantMsg],
              streamingMessageId: msgId,
              waitingForResponse: false,
            }))
          }
          break
        }

        case 'thinking': {
          set((s) => {
            if (!s.streamingMessageId) return s
            const messages = s.messages.map((m) => {
              if (m.id !== s.streamingMessageId) return m
              const blocks = m.blocks ?? []
              const last = blocks[blocks.length - 1]
              const nextBlocks =
                last?.type === 'thinking'
                  ? [...blocks.slice(0, -1), { type: 'thinking' as const, text: last.text + frame.content, collapsed: last.collapsed ?? true }]
                  : [...blocks, { type: 'thinking' as const, text: frame.content, collapsed: true }]
              return { ...m, blocks: nextBlocks }
            })
            return { messages }
          })
          break
        }

        case 'tool_approval_request': {
          const approval: ApprovalRequest = {
            tool_id: frame.tool_id,
            name: frame.name,
            arguments: frame.arguments,
            ...(frame.title != null && { title: frame.title }),
          }
          set((s) => {
            const approvalBlock = { type: 'approval_request' as const, request: approval }
            if (!s.streamingMessageId) {
              const msgId = uuidv4()
              const assistantMsg: ChatMessage = {
                id: msgId,
                role: 'assistant',
                content: '',
                timestamp: Date.now(),
                streaming: true,
                blocks: [approvalBlock],
              }
              return {
                messages: [...s.messages, assistantMsg],
                streamingMessageId: msgId,
                pendingApprovals: [...s.pendingApprovals, approval],
                waitingForResponse: false,
              }
            }
            return {
              pendingApprovals: [...s.pendingApprovals, approval],
              waitingForResponse: false,
              messages: s.messages.map((m) => {
                if (m.id !== s.streamingMessageId) return m
                const blocks = m.blocks ?? []
                return { ...m, blocks: [...blocks, approvalBlock] }
              }),
            }
          })
          break
        }

        case 'tool_call': {
          const toolEvent: ToolCallEvent = {
            name: frame.name,
            arguments: frame.arguments,
            tool_id: frame.tool_id,
          }
          set((s) => {
            const next = new Map(s.pendingToolCalls)
            next.set(frame.tool_id ?? frame.name, toolEvent)
            const toolCallBlock = { type: 'tool_call' as const, toolCall: toolEvent }
            if (!s.streamingMessageId) {
              const msgId = uuidv4()
              const assistantMsg: ChatMessage = {
                id: msgId,
                role: 'assistant',
                content: '',
                timestamp: Date.now(),
                streaming: true,
                blocks: [toolCallBlock],
              }
              return {
                messages: [...s.messages, assistantMsg],
                streamingMessageId: msgId,
                pendingToolCalls: next,
                waitingForResponse: false,
              }
            }
            const messages: ChatMessage[] = s.messages.map((m) => {
              if (m.id !== s.streamingMessageId) return m
              const blocks = m.blocks ?? []
              return { ...m, blocks: [...blocks, toolCallBlock] }
            })
            return { pendingToolCalls: next, messages, waitingForResponse: false }
          })
          break
        }

        case 'tool_progress': {
          const { tool_id: tid, content } = frame
          set((s) => {
            if (!s.streamingMessageId) return s
            const messages: ChatMessage[] = s.messages.map((m) => {
              if (m.id !== s.streamingMessageId || !m.blocks) return m
              const blocks: MessageBlock[] = m.blocks.slice()
              for (let i = blocks.length - 1; i >= 0; i--) {
                const b = blocks[i]
                if (b.type === 'tool_call' && (tid == null || b.toolCall.tool_id === tid)) {
                  blocks[i] = { type: 'tool_call', toolCall: { ...b.toolCall, progress: content ?? '' } }
                  break
                }
              }
              return { ...m, blocks }
            })
            return { messages }
          })
          break
        }

        case 'tool_result': {
          const key = frame.tool_id ?? frame.name
          set((s) => {
            const next = new Map(s.pendingToolCalls)
            const existing = next.get(key) ?? next.get(frame.name)
            if (existing) {
              next.set(key, { ...existing, result: frame.result })
            }
            const toolWithResult: ToolCallEvent = {
              name: frame.name,
              arguments: {},
              tool_id: frame.tool_id,
              result: frame.result,
            }
            if (!s.streamingMessageId) {
              const msgId = uuidv4()
              const assistantMsg: ChatMessage = {
                id: msgId,
                role: 'assistant',
                content: '',
                timestamp: Date.now(),
                streaming: true,
                blocks: [{ type: 'tool_call' as const, toolCall: toolWithResult }],
              }
              next.set(key, toolWithResult)
              return {
                messages: [...s.messages, assistantMsg],
                streamingMessageId: msgId,
                pendingToolCalls: next,
              }
            }
            const messages: ChatMessage[] = s.messages.map((m) => {
              if (m.id !== s.streamingMessageId || !m.blocks) return m
              const blocks: MessageBlock[] = m.blocks.slice()
              for (let i = blocks.length - 1; i >= 0; i--) {
                const b = blocks[i]
                if (b.type === 'tool_call' && (b.toolCall.tool_id === frame.tool_id || b.toolCall.name === frame.name)) {
                  blocks[i] = { type: 'tool_call', toolCall: { ...b.toolCall, result: frame.result } }
                  break
                }
              }
              return { ...m, blocks }
            })
            return { pendingToolCalls: next, messages }
          })
          break
        }

        case 'message_complete': {
          const { streamingMessageId } = get()
          const toolCalls = Array.from(get().pendingToolCalls.values())

          set((s) => ({
            messages: s.messages.map((m) =>
              m.id === streamingMessageId
                ? {
                    ...m,
                    content: frame.content,
                    streaming: false,
                    tools_used: frame.tools_used,
                    tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
                    blocks: m.blocks?.length ? m.blocks : undefined,
                  }
                : m,
            ),
            streamingMessageId: null,
            pendingToolCalls: new Map(),
            pendingApprovals: [],
            waitingForResponse: false,
          }))

          get().loadSessions()
          break
        }

        case 'error': {
          const errMsg: ChatMessage = {
            id: uuidv4(),
            role: 'assistant',
            content: `⚠️ ${frame.content}`,
            timestamp: Date.now(),
          }
          set((s) => ({
            messages: [...s.messages, errMsg],
            streamingMessageId: null,
            pendingApprovals: [],
            waitingForResponse: false,
          }))
          break
        }

        case 'interrupt_ack': {
          set({
            streamingMessageId: null,
            pendingToolCalls: new Map(),
            pendingApprovals: [],
            waitingForResponse: false,
          })
          break
        }

        case 'assistant_message': {
          const sessionId = (frame as { session_id: string }).session_id
          const content = (frame as { content: string }).content ?? ''
          const { activeSessionId } = get()
          if (sessionId !== activeSessionId) break
          const assistantMsg: ChatMessage = {
            id: uuidv4(),
            role: 'assistant',
            content,
            timestamp: Date.now(),
          }
          set((s) => ({ messages: [...s.messages, assistantMsg] }))
          break
        }

        case 'queue_updated': {
          const ids = (frame as { queue_ids: string[] }).queue_ids ?? []
          set((s) => ({
            messageQueue: ids.map(
              (id) => s.messageQueue.find((m) => m.queue_id === id) ?? { queue_id: id, content: '…' }
            ),
          }))
          break
        }

        default:
          break
      }
    },

    interruptStream() {
      const { wsClient } = get()
      if (wsClient) wsClient.send({ type: 'interrupt' })
    },

    retractFromQueue(queueId: string) {
      const { wsClient } = get()
      if (wsClient) wsClient.send({ type: 'retract', queue_id: queueId })
      set((s) => ({ messageQueue: s.messageQueue.filter((m) => m.queue_id !== queueId) }))
    },

    runImmediately(queueId: string) {
      const { wsClient } = get()
      if (wsClient) wsClient.send({ type: 'run_immediately', queue_id: queueId })
      set((s) => ({ messageQueue: s.messageQueue.filter((m) => m.queue_id !== queueId) }))
    },

    approveToolCall(toolId: string, outcome: ApprovalOutcome, reason?: string) {
      const { wsClient } = get()
      if (wsClient) {
        const frame: { type: 'tool_approval_response'; tool_id: string; approved: boolean; reason?: string } = {
          type: 'tool_approval_response',
          tool_id: toolId,
          approved: outcome !== 'denied',
        }
        if (outcome === 'denied' && reason?.trim()) frame.reason = reason.trim()
        wsClient.send(frame)
      }
      set((s) => {
        const pendingApprovals = s.pendingApprovals.filter((a) => a.tool_id !== toolId)
        const messages: ChatMessage[] = s.messages.map((m) => {
          if (!m.blocks) return m
          const blocks: MessageBlock[] = m.blocks.map((b) => {
            if (b.type !== 'approval_request' || b.request.tool_id !== toolId) return b
            return { ...b, resolved: outcome }
          })
          return { ...m, blocks }
        })
        return { pendingApprovals, messages }
      })
    },

    _setConnectionStatus(status) {
      set({ connectionStatus: status })
      if (status === 'connected') {
        // Refresh data on reconnect
        get().loadSessions()
        get().loadStatus()
      }
    },
  }
})
