import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, Loader2, Paperclip, X, FileText, Square, Play, Trash2 } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { uploadAttachment } from '../../api/client'
import { ChatMessageList } from '../organisms/ChatMessageList'

type PendingAttachment = { path: string; file: File }

function AttachmentThumbnail({ file }: { file: File }) {
  const [url] = useState(() => (file.type.startsWith('image/') ? URL.createObjectURL(file) : null))
  useEffect(() => () => { if (url) URL.revokeObjectURL(url) }, [url])
  if (!url) return <Paperclip size={12} className="text-zinc-400" />
  return <img src={url} alt="" className="h-full w-full object-cover pointer-events-none" />
}

export function ChatPage() {
  const connectionStatus = useChatStore((s) => s.connectionStatus)
  const streamingMessageId = useChatStore((s) => s.streamingMessageId)
  const waitingForResponse = useChatStore((s) => s.waitingForResponse)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const interruptStream = useChatStore((s) => s.interruptStream)
  const activeSessionId = useChatStore((s) => s.activeSessionId)
  const loadSession = useChatStore((s) => s.loadSession)

  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<PendingAttachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  type PreviewState = { url: string; type: 'image' | 'pdf'; isBlob?: boolean } | null
  const [preview, setPreview] = useState<PreviewState>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevSessionRef = useRef<string>('')

  const handleOpenPdfPreview = useCallback((path: string) => {
    setPreview({ url: `/api/media?path=${encodeURIComponent(path)}`, type: 'pdf', isBlob: false })
  }, [])

  useEffect(() => {
    return () => {
      if (preview?.isBlob && preview.url.startsWith('blob:')) URL.revokeObjectURL(preview.url)
    }
  }, [preview])

  useEffect(() => {
    if (activeSessionId && activeSessionId !== prevSessionRef.current) {
      prevSessionRef.current = activeSessionId
      loadSession(activeSessionId)
    }
  }, [activeSessionId, loadSession])

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [input])

  const isStreaming = streamingMessageId !== null
  const messageQueue = useChatStore((s) => s.messageQueue)
  const retractFromQueue = useChatStore((s) => s.retractFromQueue)
  const runImmediately = useChatStore((s) => s.runImmediately)
  const hasContent = input.trim().length > 0 || attachments.length > 0
  const canSend = connectionStatus === 'connected' && hasContent

  async function addFilesAsAttachments(files: FileList | File[]) {
    const list = Array.from(files)
    if (!list.length) return
    setUploading(true)
    try {
      for (const file of list) {
        const { path } = await uploadAttachment(file)
        setAttachments((prev) => [...prev, { path, file }])
      }
    } finally {
      setUploading(false)
    }
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files?.length) return
    await addFilesAsAttachments(files)
    e.target.value = ''
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
    const files = e.dataTransfer.files
    if (!files?.length) return
    await addFilesAsAttachments(files)
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  function handleSend() {
    const text = input.trim()
    if (!canSend) return
    const paths = attachments.map((a) => a.path)
    sendMessage(text || '(attachment)', paths.length ? paths : undefined)
    setInput('')
    setAttachments([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      className="flex flex-col h-full bg-zinc-950 relative"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {dragOver && (
        <div
          className="absolute inset-0 z-40 flex items-center justify-center bg-zinc-900/90 border-2 border-dashed border-zinc-500 rounded-lg pointer-events-none"
          aria-hidden
        >
          <span className="text-zinc-300 text-sm font-medium">Drop files to add to context</span>
        </div>
      )}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6 space-y-4">
        <ChatMessageList onOpenPdfPreview={handleOpenPdfPreview} />
      </div>

      {messageQueue.length > 0 && (
        <div className="border-t border-zinc-800 px-4 py-2 bg-zinc-900/50">
          <p className="text-[11px] font-medium text-zinc-500 mb-1.5">Queue ({messageQueue.length})</p>
          <ul className="space-y-1.5 max-h-32 overflow-y-auto">
            {messageQueue.map((item) => (
              <li
                key={item.queue_id}
                className="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800/80 px-2.5 py-1.5 text-xs"
              >
                <span className="flex-1 min-w-0 truncate text-zinc-300" title={item.content}>
                  {item.content || '…'}
                </span>
                <button
                  type="button"
                  onClick={() => runImmediately(item.queue_id)}
                  className="shrink-0 p-1 rounded text-emerald-400 hover:bg-emerald-500/20"
                  title="Run immediately"
                >
                  <Play size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => retractFromQueue(item.queue_id)}
                  className="shrink-0 p-1 rounded text-zinc-400 hover:bg-zinc-600"
                  title="Retract"
                >
                  <Trash2 size={12} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="border-t border-zinc-800 px-4 py-3">
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {attachments.map((a, i) => (
              <div
                key={a.path}
                className="relative inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800/80 px-2 py-1.5 text-xs"
              >
                {a.file.type.startsWith('image/') ? (
                  <button
                    type="button"
                    onClick={() => {
                      setPreview((prev) => {
                        if (prev?.isBlob && prev.url.startsWith('blob:')) URL.revokeObjectURL(prev.url)
                        return { url: URL.createObjectURL(a.file), type: 'image', isBlob: true }
                      })
                    }}
                    className="h-8 w-8 rounded object-cover overflow-hidden shrink-0 hover:ring-2 ring-zinc-500 transition-shadow"
                    title="View larger"
                  >
                    <AttachmentThumbnail file={a.file} />
                  </button>
                ) : a.file.type === 'application/pdf' ? (
                  <button
                    type="button"
                    onClick={() => {
                      setPreview((prev) => {
                        if (prev?.isBlob && prev.url.startsWith('blob:')) URL.revokeObjectURL(prev.url)
                        return { url: URL.createObjectURL(a.file), type: 'pdf', isBlob: true }
                      })
                    }}
                    className="h-8 w-8 rounded flex items-center justify-center bg-zinc-700 hover:bg-zinc-600 shrink-0 text-red-400"
                    title="Preview PDF"
                  >
                    <FileText size={14} />
                  </button>
                ) : (
                  <Paperclip size={12} className="text-zinc-400 shrink-0" />
                )}
                <span className="text-zinc-300 max-w-[120px] truncate">{a.file.name}</span>
                <button
                  type="button"
                  onClick={() => removeAttachment(i)}
                  className="p-0.5 rounded hover:bg-zinc-600 text-zinc-400 hover:text-zinc-200 shrink-0"
                  title="Remove"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        {preview && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
            onClick={() => setPreview(null)}
            onKeyDown={(e) => e.key === 'Escape' && setPreview(null)}
            role="dialog"
            aria-modal="true"
          >
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="absolute top-4 right-4 p-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 z-10"
              title="Close"
            >
              <X size={20} />
            </button>
            {preview.type === 'pdf' ? (
              <iframe
                src={preview.url}
                title="PDF preview"
                className="w-full h-full max-h-[90vh] rounded-lg bg-white"
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <img
                src={preview.url}
                alt="Preview"
                className="max-h-full max-w-full object-contain rounded-lg"
                onClick={(e) => e.stopPropagation()}
              />
            )}
          </div>
        )}
        <div
          className={`flex items-end gap-2 rounded-xl border px-3 py-2 transition-colors ${
            connectionStatus === 'connected'
              ? 'border-zinc-700 bg-zinc-900 focus-within:border-zinc-500'
              : 'border-zinc-800 bg-zinc-900/50'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.png,.jpg,.jpeg,.gif,.webp,.pdf"
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={connectionStatus !== 'connected' || uploading}
            className="shrink-0 p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
            title="Attach image or PDF"
          >
            {uploading ? <Loader2 size={15} className="animate-spin" /> : <Paperclip size={15} />}
          </button>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              connectionStatus === 'connected'
                ? 'Message nanobot… (Enter to send, Shift+Enter for newline)'
                : 'Connecting to server…'
            }
            disabled={connectionStatus !== 'connected'}
            rows={1}
            className="flex-1 bg-transparent text-sm text-zinc-200 placeholder-zinc-600 resize-none outline-none max-h-[200px] leading-relaxed disabled:opacity-50"
          />

          {(isStreaming || waitingForResponse) ? (
            <button
              type="button"
              onClick={interruptStream}
              className="shrink-0 p-1.5 rounded-lg bg-red-600/80 text-white hover:bg-red-600 transition-colors"
              title="Stop"
            >
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!canSend}
              className={`shrink-0 p-1.5 rounded-lg transition-all ${
                canSend
                  ? 'bg-blue-600 text-white hover:bg-blue-500'
                  : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
              }`}
              title="Send message"
            >
              <Send size={15} />
            </button>
          )}
        </div>

        <p className="text-[10px] text-zinc-700 mt-1.5 text-center">
          nanobot can make mistakes. Review important information.
        </p>
      </div>
    </div>
  )
}
