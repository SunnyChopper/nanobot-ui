import { useRef, useEffect, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { TransformWrapper, TransformComponent, useTransformContext } from 'react-zoom-pan-pinch'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check, Maximize2, X } from 'lucide-react'

/** When fullscreen, fits diagram to viewport after SVG is rendered. */
function MermaidFitOnLoad({
  containerRef,
  fullscreen,
  svgReady,
  children,
}: {
  containerRef: React.RefObject<HTMLDivElement | null>
  fullscreen: boolean
  svgReady: boolean
  children: React.ReactNode
}) {
  const ctx = useTransformContext()
  useEffect(() => {
    if (!fullscreen || !svgReady || !containerRef.current) return
    const svg = containerRef.current.querySelector('svg')
    if (!svg) return
    const wrapper = ctx.wrapperComponent
    if (!wrapper) return
    const pad = 0.85
    const wr = wrapper.getBoundingClientRect()
    const sr = svg.getBoundingClientRect()
    if (sr.width <= 0 || sr.height <= 0) return
    const scale = Math.min((wr.width / sr.width) * pad, (wr.height / sr.height) * pad, 4)
    ctx.getContext().centerView(scale, 0)
  }, [fullscreen, svgReady, ctx, containerRef])
  return <>{children}</>
}

interface Props {
  content: string
  className?: string
  /** Workspace root path for resolving relative folder names (e.g. personal-os -> workspace/personal-os) */
  workspace?: string | null
}

/** Simple djb2 hash for stable Mermaid block ids. */
function simpleHash(str: string): string {
  let h = 5381
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h) + str.charCodeAt(i)
  return (h >>> 0).toString(36)
}

/** Renders a Mermaid diagram from source string with pan/zoom and full-screen. */
function MermaidBlock({ code, id, fullscreen = false }: { code: string; id: string; fullscreen?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [svgReady, setSvgReady] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const renderId = fullscreen ? `${id}-fullscreen` : id

  useEffect(() => {
    if (!ref.current || !code.trim()) return
    setSvgReady(false)
    let cancelled = false
    setError(null)
    import('mermaid')
      .then((mod) => {
        const mermaid = mod.default
        if (cancelled) return
        mermaid.initialize({ startOnLoad: false, theme: 'dark' })
        return mermaid.render(renderId, code).then(({ svg }: { svg: string }) => {
          if (cancelled) return
          if (ref.current) {
            ref.current.innerHTML = svg
            setSvgReady(true)
          }
        })
      })
      .catch((err) => {
        if (!cancelled) setError(String(err?.message || err))
      })
    return () => { cancelled = true }
  }, [code, renderId])

  const closeFullscreen = useCallback(() => setIsFullscreen(false), [])
  useEffect(() => {
    if (!isFullscreen) return
    const onEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') closeFullscreen() }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [isFullscreen, closeFullscreen])

  if (error) {
    return (
      <pre className="my-2 min-h-[60px] p-3 rounded-lg bg-zinc-800 text-red-400 text-xs overflow-x-auto">
        Mermaid error: {error}
      </pre>
    )
  }

  const diagramContent = (
    <div
      ref={ref}
      className="flex justify-center rounded-lg bg-zinc-800/80 p-3 mermaid-container w-full inline-block"
      style={{ minHeight: fullscreen ? 200 : 280 }}
    />
  )

  const wrappedDiagram = (
    <TransformWrapper
      initialScale={1}
      minScale={0.2}
      maxScale={4}
      centerOnInit
      doubleClick={{ mode: 'reset' }}
    >
      <TransformComponent
        wrapperClass={fullscreen ? '!w-full !overflow-hidden' : '!w-full !overflow-auto'}
        contentClass="!flex !justify-center !items-start"
        wrapperStyle={{
          minHeight: fullscreen ? '80vh' : 420,
          width: '100%',
          height: fullscreen ? '80vh' : 'auto',
          maxHeight: fullscreen ? undefined : '70vh',
        }}
      >
        {fullscreen ? (
          <MermaidFitOnLoad containerRef={ref} fullscreen={fullscreen} svgReady={svgReady}>
            {diagramContent}
          </MermaidFitOnLoad>
        ) : (
          diagramContent
        )}
      </TransformComponent>
    </TransformWrapper>
  )

  if (fullscreen) {
    return <div className="w-full h-full flex items-center justify-center">{wrappedDiagram}</div>
  }

  return (
    <div className="my-2 relative group/mermaid rounded-lg bg-zinc-800/80 min-h-[420px] overflow-auto">
      <div className="absolute right-2 top-2 z-10 opacity-0 group-hover/mermaid:opacity-100 transition-opacity flex gap-1">
        <button
          type="button"
          onClick={() => setIsFullscreen(true)}
          className="p-1.5 rounded-md bg-zinc-700 hover:bg-zinc-600 text-zinc-300"
          title="Open full screen"
          aria-label="Open diagram in full screen"
        >
          <Maximize2 size={14} />
        </button>
      </div>
      {wrappedDiagram}
      {isFullscreen && createPortal(
        <div
          className="fixed inset-0 z-50 flex flex-col bg-black/90"
          role="dialog"
          aria-modal="true"
          aria-label="Diagram full screen"
        >
          <div className="flex items-center justify-end gap-2 p-2 border-b border-zinc-700 shrink-0">
            <button
              type="button"
              onClick={closeFullscreen}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm"
              aria-label="Close full screen"
            >
              <X size={16} /> Close
            </button>
          </div>
          <div className="flex-1 min-h-0 p-4">
            <MermaidBlock code={code} id={id} fullscreen />
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

/** Sandboxed HTML preview (artifact-style) for code blocks with language html. */
function HtmlPreviewBlock({ codeString, children }: { codeString: string; children: React.ReactNode }) {
  const [showPreview, setShowPreview] = useState(false)
  return (
    <div className="my-2 rounded-lg border border-zinc-700 bg-zinc-800/80 overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-2 py-1.5 border-b border-zinc-700">
        <span className="text-xs text-zinc-500">HTML</span>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="px-2 py-1 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-300"
          >
            {showPreview ? 'Hide preview' : 'Preview'}
          </button>
        </div>
      </div>
      {children}
      {showPreview && (
        <div className="border-t border-zinc-700 p-2 bg-zinc-900 min-h-[120px]">
          <iframe
            title="HTML preview"
            sandbox=""
            srcDoc={codeString}
            className="w-full min-h-[200px] rounded bg-white border-0"
            style={{ height: 'min(400px, 50vh)' }}
          />
        </div>
      )}
    </div>
  )
}

/** Code block with Copy button. */
function CodeBlockWithCopy({
  codeString,
  language,
  children,
}: {
  codeString: string
  language: string
  children: React.ReactNode
}) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(codeString).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="relative group/code my-2">
      <div className="absolute right-2 top-2 z-10 opacity-0 group-hover/code:opacity-100 transition-opacity">
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs"
          title="Copy"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {children}
    </div>
  )
}

/** Heuristic: does code look like Mermaid (for untagged or mis-tagged blocks). */
function looksLikeMermaid(code: string): boolean {
  const first = code.trim().split(/\n/)[0]?.trim().toLowerCase() ?? ''
  return /^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|requirement)\b/.test(first)
}

/** Heuristic: does this look like a path we can link to? */
function looksLikePath(text: string): boolean {
  const t = text.trim()
  if (!t || t.length > 260) return false
  if (/^[A-Z]:[\\/]/.test(t)) return true
  if (t.startsWith('/') || t.startsWith('~/')) return true
  if (/^[\w.-]+$/.test(t) && !t.includes('..')) return true
  return false
}

/** Build file:// URL for a path. workspace is used for single-segment names like 'nanobot'. */
function fileUrlForPath(path: string, workspace?: string | null): string {
  const p = path.trim()
  if (/^[A-Z]:[\\/]/.test(p)) return 'file:///' + p.replace(/\\/g, '/')
  if (p.startsWith('/')) return 'file://' + p
  if (p.startsWith('~/')) return 'file://' + p
  if (workspace && /^[\w.-]+$/.test(p)) {
    const full = (workspace.replace(/\\/g, '/') + '/' + p).replace(/\/+/g, '/')
    return 'file:///' + (full.startsWith('/') ? full.slice(1) : full)
  }
  return 'file:///' + p.replace(/\\/g, '/')
}

/** Ensure content has trailing newline so block elements (code, lists) parse correctly. */
function normalizeContent(s: string): string {
  if (!s) return s
  return s.endsWith('\n') ? s : s + '\n'
}

const mermaidIndexRef = { current: 0 }

export function MarkdownRenderer({ content, className = '', workspace }: Props) {
  const normalized = normalizeContent(content)
  mermaidIndexRef.current = 0
  return (
    <div className={`prose prose-invert prose-sm max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '')
            const lang = (match ? match[1] : '').toLowerCase().trim()
            const codeString = String(children).replace(/\n$/, '')

            const isMermaid =
              lang === 'mermaid' ||
              ((!lang || lang === 'text') && looksLikeMermaid(codeString))

            if (!inline && isMermaid) {
              const index = mermaidIndexRef.current++
              const id = `mermaid-${simpleHash(codeString)}-${index}`
              return <MermaidBlock key={id} id={id} code={codeString} />
            }

            if (!inline && lang) {
              const isHtml = lang === 'html' || lang === 'htm' || lang === 'text/html'
              const block = (
                <CodeBlockWithCopy codeString={codeString} language={lang}>
                  <SyntaxHighlighter
                    style={oneDark}
                    language={lang}
                    PreTag="div"
                    className="!rounded-lg !text-xs !my-2"
                    {...props}
                  >
                    {codeString}
                  </SyntaxHighlighter>
                </CodeBlockWithCopy>
              )
              if (isHtml) {
                return (
                  <HtmlPreviewBlock key={lang + codeString.slice(0, 20)} codeString={codeString}>
                    {block}
                  </HtmlPreviewBlock>
                )
              }
              return block
            }

            if (inline && looksLikePath(codeString)) {
              const fileUrl = fileUrlForPath(codeString, workspace)
              return (
                <a
                  href={fileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-zinc-800 text-blue-400 hover:text-blue-300 rounded px-1 py-0.5 text-xs font-mono underline cursor-pointer"
                  title="Open path (or copy)"
                  onClick={(e) => {
                    try {
                      const path = fileUrl.replace(/^file:\/\/\/?/, '').replace(/\//g, '\\')
                      navigator.clipboard?.writeText(path)
                    } catch (_) {}
                  }}
                >
                  {children}
                </a>
              )
            }

            return (
              <code
                className="bg-zinc-800 text-zinc-200 rounded px-1 py-0.5 text-xs font-mono"
                {...props}
              >
                {children}
              </code>
            )
          },
          pre({ children }) {
            return <>{children}</>
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 underline"
              >
                {children}
              </a>
            )
          },
          table({ children }) {
            return (
              <div className="overflow-x-auto my-2">
                <table className="border-collapse text-xs">{children}</table>
              </div>
            )
          },
          th({ children }) {
            return (
              <th className="border border-zinc-700 px-2 py-1 bg-zinc-800 text-left font-semibold">
                {children}
              </th>
            )
          },
          td({ children }) {
            return (
              <td className="border border-zinc-700 px-2 py-1">{children}</td>
            )
          },
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  )
}
