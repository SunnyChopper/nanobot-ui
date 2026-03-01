/** WebSocket and frontend message types */

export type WsConnectionStatus = 'connecting' | 'connected' | 'disconnected'

/** Frames sent from client to server */
export type WsClientFrame =
  | { type: 'session_init'; session_id: string }
  | { type: 'message'; content: string; session_id: string; attachments?: string[]; queue_id?: string }
  | { type: 'new_session'; session_id: string }
  | { type: 'tool_approval_response'; tool_id: string; approved: boolean; reason?: string }
  | { type: 'interrupt' }
  | { type: 'retract'; queue_id: string }
  | { type: 'run_immediately'; queue_id: string }
  | { type: 'ping' }

/** Frames received from server */
export type WsServerFrame =
  | { type: 'session_ready'; session_id: string }
  | { type: 'token'; content: string; session_id: string }
  | { type: 'thinking'; content: string; session_id?: string }
  | { type: 'tool_call'; name: string; arguments: Record<string, unknown>; session_id: string; tool_id?: string }
  | { type: 'tool_approval_request'; name: string; arguments: Record<string, unknown>; session_id: string; tool_id: string; title?: string }
  | { type: 'tool_result'; name: string; result: string; session_id: string; tool_id?: string }
  | { type: 'tool_progress'; tool_id?: string; content: string; session_id?: string }
  | { type: 'message_complete'; content: string; session_id: string; tools_used: string[] }
  | { type: 'error'; content: string; session_id?: string }
  | { type: 'interrupt_ack'; session_id: string }
  | { type: 'queue_updated'; session_id: string; queue_ids: string[]; count: number }
  | { type: 'pong' }
  | { type: 'assistant_message'; session_id: string; content: string }

export interface ToolCallEvent {
  name: string
  arguments: Record<string, unknown>
  result?: string
  tool_id?: string
  /** Progress message while the tool is running (e.g. "Step 2/50"). */
  progress?: string
}

export interface ApprovalRequest {
  tool_id: string
  name: string
  arguments: Record<string, unknown>
  title?: string
}

export type ApprovalOutcome = 'approved' | 'denied' | 'allowlisted'

/** A message in the send queue (while bot is running). */
export interface QueuedMessage {
  queue_id: string
  content: string
  attachments?: string[]
}

export type MessageBlock =
  | { type: 'content'; text: string }
  | { type: 'tool_call'; toolCall: ToolCallEvent }
  | { type: 'approval_request'; request: ApprovalRequest; resolved?: ApprovalOutcome }
  | { type: 'thinking'; text: string; collapsed?: boolean }

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  tools_used?: string[]
  attachments?: string[]
  tool_calls?: ToolCallEvent[]
  blocks?: MessageBlock[]
  streaming?: boolean
}
