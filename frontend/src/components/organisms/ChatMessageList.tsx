import React, { useEffect, useMemo, useRef } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { MessageBubble } from './MessageBubble'
import { ThinkingIndicator } from '../molecules/ThinkingIndicator'

export interface ChatMessageListProps {
  onOpenPdfPreview?: (path: string) => void
}

function ChatMessageListInner({ onOpenPdfPreview }: ChatMessageListProps) {
  const messages = useChatStore((s) => s.messages)
  const streamingMessageId = useChatStore((s) => s.streamingMessageId)
  const pendingToolCalls = useChatStore((s) => s.pendingToolCalls)
  const pendingApprovals = useChatStore((s) => s.pendingApprovals)
  const waitingForResponse = useChatStore((s) => s.waitingForResponse)
  const workspace = useChatStore((s) => s.status?.workspace ?? null)
  const editMessage = useChatStore((s) => s.editMessage)
  const branchFromMessage = useChatStore((s) => s.branchFromMessage)
  const retryLastMessage = useChatStore((s) => s.retryLastMessage)
  const approveToolCall = useChatStore((s) => s.approveToolCall)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const precedingUserContentByIndex = useMemo(() => {
    const arr: (string | undefined)[] = []
    let last: string | undefined
    for (const m of messages) {
      arr.push(last)
      if (m.role === 'user') last = m.content
    }
    return arr
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pendingToolCalls, pendingApprovals, waitingForResponse])

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-zinc-600 select-none">
        <span className="text-5xl mb-4">🐈</span>
        <p className="text-sm">Start a conversation with nanobot</p>
        <p className="text-xs mt-1">Press Enter to send</p>
      </div>
    )
  }

  return (
    <>
      {messages.map((msg, idx) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          messageIndex={idx}
          precedingUserContent={precedingUserContentByIndex[idx]}
          editMessage={editMessage}
          branchFromMessage={branchFromMessage}
          onRetry={msg.role === 'assistant' ? retryLastMessage : undefined}
          onApproveToolCall={msg.role === 'assistant' ? approveToolCall : undefined}
          onOpenPdfPreview={onOpenPdfPreview}
          workspace={workspace}
        />
      ))}

      {waitingForResponse && !streamingMessageId && <ThinkingIndicator />}

      <div ref={messagesEndRef} />
    </>
  )
}

export const ChatMessageList = React.memo(ChatMessageListInner)
