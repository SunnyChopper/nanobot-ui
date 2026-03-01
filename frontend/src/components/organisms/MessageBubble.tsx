import React, { useState, useRef, useEffect } from 'react'
import { Bot, User, Pencil, RotateCcw, Check, X, GitBranch, FileText } from 'lucide-react'
import type { ApprovalOutcome, ChatMessage, MessageBlock } from '../../api/types'
import { MarkdownRenderer } from '../molecules/MarkdownRenderer'
import { ToolCallCard } from '../molecules/ToolCallCard'
import { ToolApprovalCard } from '../molecules/ToolApprovalCard'

interface Props {
  message: ChatMessage
  messageIndex: number
  precedingUserContent?: string
  editMessage: (messageIndex: number, newContent: string) => Promise<void>
  branchFromMessage: (messageIndex: number) => Promise<void>
  onRetry?: () => void
  onApproveToolCall?: (toolId: string, outcome: ApprovalOutcome, reason?: string) => void
  onOpenPdfPreview?: (path: string) => void
  workspace?: string | null
}

function BlockContent({
  block,
  onApproveToolCall,
  workspace,
  contextLabel,
  messageStreaming,
}: {
  block: MessageBlock
  onApproveToolCall?: (toolId: string, outcome: ApprovalOutcome, reason?: string) => void
  workspace?: string | null
  contextLabel?: string
  messageStreaming?: boolean
}) {
  if (block.type === 'content') {
    return <MarkdownRenderer content={block.text} workspace={workspace} />
  }
  if (block.type === 'tool_call') {
    return <ToolCallCard toolCall={block.toolCall} inProgress={messageStreaming} />
  }
  if (block.type === 'approval_request') {
    return (
      <div className="mt-2 mb-2">
        <ToolApprovalCard
          approval={block.request}
          resolved={block.resolved}
          contextLabel={contextLabel}
          onResolve={(id, outcome, reason) => onApproveToolCall?.(id, outcome, reason)}
        />
      </div>
    )
  }
  if (block.type === 'thinking') {
    return (
      <details className="mt-1 mb-1" open={!block.collapsed}>
        <summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-400 select-none">
          Thinking
        </summary>
        <pre className="mt-1 text-xs text-zinc-400 whitespace-pre-wrap font-sans border-l-2 border-zinc-600 pl-2">
          {block.text}
        </pre>
      </details>
    )
  }
  return null
}

function MessageBubbleInner({ message, messageIndex, precedingUserContent, editMessage, branchFromMessage, onRetry, onApproveToolCall, onOpenPdfPreview, workspace }: Props) {
  const isUser = message.role === 'user'
  const isStreaming = message.streaming === true
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(message.content)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus()
      textareaRef.current.selectionStart = textareaRef.current.value.length
    }
  }, [isEditing])

  function handleEditSubmit() {
    const trimmed = editValue.trim()
    if (trimmed && trimmed !== message.content) {
      editMessage(messageIndex, trimmed)
    }
    setIsEditing(false)
  }

  function handleEditCancel() {
    setEditValue(message.content)
    setIsEditing(false)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleEditSubmit()
    }
    if (e.key === 'Escape') {
      handleEditCancel()
    }
  }

  return (
    <div className={`flex gap-3 group ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div
        className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 ${
          isUser
            ? 'bg-blue-600'
            : 'bg-zinc-700 ring-1 ring-zinc-600'
        }`}
      >
        {isUser ? (
          <User size={14} className="text-white" />
        ) : (
          <Bot size={14} className="text-zinc-300" />
        )}
      </div>

      <div className={`flex-1 min-w-0 max-w-[85%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        {isUser ? (
          isEditing ? (
            <div className="self-end w-full max-w-[85%] bg-zinc-800 border border-zinc-600 rounded-2xl rounded-tr-sm px-3 py-2">
              <textarea
                ref={textareaRef}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={Math.min(8, editValue.split('\n').length + 1)}
                className="w-full bg-transparent text-sm text-zinc-200 resize-none outline-none leading-relaxed"
              />
              <div className="flex justify-end gap-1.5 mt-1.5">
                <button
                  onClick={handleEditCancel}
                  className="flex items-center gap-1 px-2 py-1 rounded-md text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
                >
                  <X size={11} /> Cancel
                </button>
                <button
                  onClick={handleEditSubmit}
                  className="flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-blue-600 text-white hover:bg-blue-500 transition-colors"
                >
                  <Check size={11} /> Send
                </button>
              </div>
            </div>
          ) : (
            <div className="relative self-end group/bubble flex flex-col items-end gap-2">
              {message.attachments && message.attachments.length > 0 && (
                <div className="flex flex-wrap gap-1.5 justify-end">
                  {message.attachments.map((path) => {
                    const isPdf = path.toLowerCase().endsWith('.pdf')
                    const mediaUrl = `/api/media?path=${encodeURIComponent(path)}`
                    const fileName = path.split('/').pop() ?? path
                    if (isPdf) {
                      return (
                        <div
                          key={path}
                          className="rounded-xl border border-zinc-600 bg-zinc-800/60 overflow-hidden hover:border-zinc-500 hover:bg-zinc-800/80 transition-colors max-w-[220px]"
                        >
                          <div className="flex items-center gap-2 px-3 py-2.5">
                            <div className="w-9 h-9 rounded-lg bg-zinc-700 flex items-center justify-center shrink-0 text-red-400">
                              <FileText size={18} />
                            </div>
                            <span className="text-xs text-zinc-300 truncate flex-1 min-w-0" title={fileName}>
                              {fileName}
                            </span>
                            {onOpenPdfPreview && (
                              <button
                                type="button"
                                onClick={() => onOpenPdfPreview(path)}
                                className="shrink-0 text-[11px] font-medium text-blue-400 hover:text-blue-300"
                              >
                                Preview
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    }
                    return (
                      <a
                        key={path}
                        href={mediaUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-lg overflow-hidden border border-zinc-600 hover:border-zinc-500 max-w-[200px] max-h-[200px]"
                      >
                        <img
                          src={mediaUrl}
                          alt=""
                          className="w-full h-full object-cover max-h-[200px]"
                        />
                      </a>
                    )
                  })}
                </div>
              )}
              <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed break-words whitespace-pre-wrap">
                {message.content}
              </div>
              <div className="absolute -left-14 top-1/2 -translate-y-1/2 flex gap-0.5 opacity-0 group-hover/bubble:opacity-100 transition-opacity">
                <button
                  onClick={() => branchFromMessage(messageIndex)}
                  className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                  title="Branch from here"
                >
                  <GitBranch size={12} />
                </button>
                {isUser && (
                  <button
                    onClick={() => { setEditValue(message.content); setIsEditing(true) }}
                    className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                    title="Edit message"
                  >
                    <Pencil size={12} />
                  </button>
                )}
              </div>
            </div>
          )
        ) : (
          <div className="relative w-full group/bubble">
            <div className="bg-zinc-800/80 border border-zinc-700/50 rounded-2xl rounded-tl-sm px-4 py-2.5 self-start w-full">
              {message.blocks && message.blocks.length > 0 ? (
                <div className="space-y-2">
                  {message.blocks.map((block, i) => (
                    <div key={i}>
                      <BlockContent
                        block={block}
                        onApproveToolCall={onApproveToolCall}
                        workspace={workspace}
                        contextLabel={precedingUserContent}
                        messageStreaming={isStreaming}
                      />
                    </div>
                  ))}
                  {isStreaming && (
                    <span className="inline-block w-1.5 h-4 bg-zinc-400 rounded-sm animate-pulse ml-0.5 align-middle" />
                  )}
                </div>
              ) : (
                <>
                  {message.tool_calls && message.tool_calls.length > 0 && (
                    <div className="mb-2">
                      {message.tool_calls.map((tc, i) => (
                        <ToolCallCard key={`${tc.name}-${i}`} toolCall={tc} inProgress={isStreaming} />
                      ))}
                    </div>
                  )}
                  <MarkdownRenderer content={message.content} workspace={workspace} />
                  {isStreaming && (
                    <span className="inline-block w-1.5 h-4 bg-zinc-400 rounded-sm animate-pulse ml-0.5 align-middle" />
                  )}
                </>
              )}
            </div>

            <div className="absolute -right-14 top-1/2 -translate-y-1/2 flex gap-0.5 opacity-0 group-hover/bubble:opacity-100 transition-opacity">
              <button
                onClick={() => branchFromMessage(messageIndex)}
                className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                title="Branch from here"
              >
                <GitBranch size={12} />
              </button>
              {onRetry && !isStreaming && (
                <button
                  onClick={onRetry}
                  className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                  title="Retry response"
                >
                  <RotateCcw size={12} />
                </button>
              )}
            </div>
          </div>
        )}

        <span className="text-[10px] text-zinc-600 px-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
    </div>
  )
}

export const MessageBubble = React.memo(MessageBubbleInner, (prev, next) =>
  prev.messageIndex === next.messageIndex &&
  prev.message === next.message &&
  prev.precedingUserContent === next.precedingUserContent &&
  prev.editMessage === next.editMessage &&
  prev.branchFromMessage === next.branchFromMessage &&
  prev.onRetry === next.onRetry &&
  prev.onApproveToolCall === next.onApproveToolCall &&
  prev.onOpenPdfPreview === next.onOpenPdfPreview &&
  prev.workspace === next.workspace
)
