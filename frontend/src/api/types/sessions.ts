/** Session API types */

import type { MessageBlock } from './ws'

export interface SessionListItem {
  key: string
  created_at: string | null
  updated_at: string | null
  message_count: number
  channel: string
  chat_id: string
  title?: string | null
}

export interface MessageRecord {
  role: 'user' | 'assistant'
  content: string
  timestamp: string | null
  tools_used: string[] | null
  blocks?: MessageBlock[]
}

export interface SessionDetail {
  key: string
  created_at: string | null
  updated_at: string | null
  messages: MessageRecord[]
  metadata: Record<string, unknown>
}
