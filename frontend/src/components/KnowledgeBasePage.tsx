import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import {
  getKnowledgeTriples,
  getKnowledgeTriplesStats,
  deleteKnowledgeTriples,
  getKnowledgeRagChunks,
  getKnowledgeRagSources,
  deleteKnowledgeRagChunks,
} from '../api/client'
import type {
  TripleItem,
  TriplesStatsResponse,
  RagChunkItemKnowledge,
} from '../api/types'

export type KnowledgeSubTab = 'triples' | 'graph' | 'rag'

const TRIPLES_PAGE_SIZE = 100
const RAG_PAGE_SIZE = 20

type KnowledgeBasePageProps = {
  subTab: KnowledgeSubTab
  onSubTabChange: (t: KnowledgeSubTab) => void
}

export function KnowledgeBasePage({ subTab, onSubTabChange }: KnowledgeBasePageProps) {
  const queryClient = useQueryClient()
  const [triplesPage, setTriplesPage] = useState(0)
  const [filterSubject, setFilterSubject] = useState('')
  const [filterPredicate, setFilterPredicate] = useState('')
  const [filterObject, setFilterObject] = useState('')
  const [appliedFilterSubject, setAppliedFilterSubject] = useState('')
  const [appliedFilterPredicate, setAppliedFilterPredicate] = useState('')
  const [appliedFilterObject, setAppliedFilterObject] = useState('')
  const [selectedTripleIds, setSelectedTripleIds] = useState<Set<number>>(new Set())
  const [deletingTriples, setDeletingTriples] = useState(false)

  const { data: triplesData, isLoading: triplesLoading } = useQuery({
    queryKey: ['knowledge', 'triples', triplesPage, appliedFilterSubject, appliedFilterPredicate, appliedFilterObject],
    queryFn: () => getKnowledgeTriples({
      limit: TRIPLES_PAGE_SIZE,
      offset: triplesPage * TRIPLES_PAGE_SIZE,
      subject: appliedFilterSubject || undefined,
      predicate: appliedFilterPredicate || undefined,
      object: appliedFilterObject || undefined,
    }),
    enabled: subTab === 'triples',
  })
  const triples = triplesData?.triples ?? []
  const triplesTotal = triplesData?.total ?? 0

  const { data: triplesStats } = useQuery({
    queryKey: ['knowledge', 'triplesStats'],
    queryFn: getKnowledgeTriplesStats,
    enabled: subTab === 'triples',
  })

  const [focusNode, setFocusNode] = useState('')
  const [appliedFocusNode, setAppliedFocusNode] = useState('')

  const {
    data: focusTriplesData,
    isLoading: focusLoading,
    isError: focusError,
    error: focusErrorDetail,
  } = useQuery({
    queryKey: ['knowledge', 'focusTriples', appliedFocusNode],
    queryFn: async () => {
      const node = appliedFocusNode.trim()
      const [bySub, byObj] = await Promise.all([
        getKnowledgeTriples({ subject: node, limit: 150 }),
        getKnowledgeTriples({ object: node, limit: 150 }),
      ])
      const seen = new Set<number>()
      const merged: TripleItem[] = []
      for (const t of bySub.triples) {
        if (!seen.has(t.id)) {
          seen.add(t.id)
          merged.push(t)
        }
      }
      for (const t of byObj.triples) {
        if (!seen.has(t.id)) {
          seen.add(t.id)
          merged.push(t)
        }
      }
      return merged
    },
    enabled: subTab === 'graph' && !!appliedFocusNode.trim(),
  })
  const focusTriples = focusTriplesData ?? []

  const [ragPage, setRagPage] = useState(0)
  const [ragSourceFilter, setRagSourceFilter] = useState('')
  const [ragSearchQ, setRagSearchQ] = useState('')
  const [appliedRagSourceFilter, setAppliedRagSourceFilter] = useState('')
  const [appliedRagSearchQ, setAppliedRagSearchQ] = useState('')
  const [selectedRagIds, setSelectedRagIds] = useState<Set<string>>(new Set())
  const [deletingRag, setDeletingRag] = useState(false)

  const { data: ragData, isLoading: ragLoading } = useQuery({
    queryKey: ['knowledge', 'rag', ragPage, appliedRagSourceFilter, appliedRagSearchQ],
    queryFn: () => getKnowledgeRagChunks({
      limit: RAG_PAGE_SIZE,
      offset: ragPage * RAG_PAGE_SIZE,
      source: appliedRagSourceFilter || undefined,
      q: appliedRagSearchQ.trim() || undefined,
    }),
    enabled: subTab === 'rag',
  })
  const ragChunks = ragData?.chunks ?? []
  const ragTotal = ragData?.total ?? 0

  const { data: ragSourcesData } = useQuery({
    queryKey: ['knowledge', 'ragSources'],
    queryFn: () => getKnowledgeRagSources().then((r) => r.sources ?? []),
    enabled: subTab === 'rag',
  })
  const ragSources = ragSourcesData ?? []

  const [error, setError] = useState<string | null>(null)

  const [highlightedNodeId, setHighlightedNodeId] = useState<string | null>(null)
  const [highlightedLink, setHighlightedLink] = useState<{ source: string; target: string } | null>(null)
  const graphRef = useRef<ForceGraphMethods | undefined>(undefined)

  const graphData = useMemo(() => {
    const nodeIds = new Set<string>()
    const nodes: { id: string; label: string }[] = []
    const links: { source: string; target: string; label: string }[] = []
    for (const t of focusTriples) {
      if (!nodeIds.has(t.subject)) {
        nodeIds.add(t.subject)
        nodes.push({ id: t.subject, label: t.subject })
      }
      if (!nodeIds.has(t.object)) {
        nodeIds.add(t.object)
        nodes.push({ id: t.object, label: t.object })
      }
      links.push({ source: t.subject, target: t.object, label: t.predicate })
    }
    return { nodes, links }
  }, [focusTriples])

  useEffect(() => {
    if (focusError && focusErrorDetail) setError(String((focusErrorDetail as Error)?.message ?? focusErrorDetail))
  }, [focusError, focusErrorDetail])

  const handleDeleteTriples = async () => {
    const ids = Array.from(selectedTripleIds)
    if (ids.length === 0 || deletingTriples) return
    if (!window.confirm(`Delete ${ids.length} triple(s)?`)) return
    setDeletingTriples(true)
    try {
      await deleteKnowledgeTriples(ids)
      setSelectedTripleIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['knowledge', 'triples'] })
      queryClient.invalidateQueries({ queryKey: ['knowledge', 'triplesStats'] })
    } catch (e) {
      setError(String((e as Error)?.message ?? e))
    } finally {
      setDeletingTriples(false)
    }
  }

  const handleDeleteRag = async () => {
    const ids = Array.from(selectedRagIds)
    if (ids.length === 0 || deletingRag) return
    if (!window.confirm(`Delete ${ids.length} RAG chunk(s)?`)) return
    setDeletingRag(true)
    try {
      await deleteKnowledgeRagChunks(ids)
      setSelectedRagIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['knowledge', 'rag'] })
    } catch (e) {
      setError(String((e as Error)?.message ?? e))
    } finally {
      setDeletingRag(false)
    }
  }

  const toggleTriple = (id: number) => {
    setSelectedTripleIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleRag = (id: string) => {
    setSelectedRagIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-zinc-950">
      <div className="flex gap-1 border-b border-zinc-800 px-4">
        <button
          type="button"
          onClick={() => onSubTabChange('triples')}
          className={`px-3 py-2 text-sm border-b-2 -mb-px ${
            subTab === 'triples'
              ? 'text-zinc-200 border-zinc-400'
              : 'text-zinc-500 hover:text-zinc-300 border-transparent'
          }`}
        >
          Triples (table)
        </button>
        <button
          type="button"
          onClick={() => onSubTabChange('graph')}
          className={`px-3 py-2 text-sm border-b-2 -mb-px ${
            subTab === 'graph'
              ? 'text-zinc-200 border-zinc-400'
              : 'text-zinc-500 hover:text-zinc-300 border-transparent'
          }`}
        >
          Graph
        </button>
        <button
          type="button"
          onClick={() => onSubTabChange('rag')}
          className={`px-3 py-2 text-sm border-b-2 -mb-px ${
            subTab === 'rag'
              ? 'text-zinc-200 border-zinc-400'
              : 'text-zinc-500 hover:text-zinc-300 border-transparent'
          }`}
        >
          RAG chunks
        </button>
      </div>

      {error && (
        <div className="mx-4 mt-2 rounded-lg border border-red-800 bg-red-950/50 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {subTab === 'triples' && (
        <div className="flex-1 overflow-auto px-4 py-4">
          <div className="flex flex-wrap gap-2 mb-4 items-center">
            <input
              type="text"
              placeholder="Filter subject"
              value={filterSubject}
              onChange={(e) => setFilterSubject(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-200 w-40"
            />
            <input
              type="text"
              placeholder="Filter predicate"
              value={filterPredicate}
              onChange={(e) => setFilterPredicate(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-200 w-40"
            />
            <input
              type="text"
              placeholder="Filter object"
              value={filterObject}
              onChange={(e) => setFilterObject(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-200 w-40"
            />
            <button
              type="button"
              onClick={() => {
                setAppliedFilterSubject(filterSubject)
                setAppliedFilterPredicate(filterPredicate)
                setAppliedFilterObject(filterObject)
                setTriplesPage(0)
              }}
              className="px-2 py-1 rounded bg-zinc-700 text-zinc-200 text-sm"
            >
              Apply
            </button>
            {selectedTripleIds.size > 0 && (
              <button
                type="button"
                onClick={handleDeleteTriples}
                disabled={deletingTriples}
                className="px-2 py-1 rounded bg-red-900/60 text-red-200 text-sm disabled:opacity-50"
              >
                Delete {selectedTripleIds.size} selected
              </button>
            )}
          </div>
          {triplesStats && (
            <p className="text-xs text-zinc-500 mb-2">
              Total triples: {triplesStats.total}
              {Object.keys(triplesStats.by_predicate).length > 0 && (
                <> · By predicate: {Object.entries(triplesStats.by_predicate).slice(0, 5).map(([p, c]) => `${p}: ${c}`).join(', ')}</>
              )}
            </p>
          )}
          {triplesLoading ? (
            <p className="text-zinc-500 text-sm animate-pulse">Loading…</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-zinc-500 border-b border-zinc-700">
                      <th className="p-2 w-8" />
                      <th className="p-2">Subject</th>
                      <th className="p-2">Predicate</th>
                      <th className="p-2">Object</th>
                      <th className="p-2">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {triples.map((t) => (
                      <tr key={t.id} className="border-b border-zinc-800">
                        <td className="p-2">
                          <input
                            type="checkbox"
                            checked={selectedTripleIds.has(t.id)}
                            onChange={() => toggleTriple(t.id)}
                            className="rounded border-zinc-600"
                          />
                        </td>
                        <td className="p-2 text-zinc-300">{t.subject}</td>
                        <td className="p-2 text-zinc-400">{t.predicate}</td>
                        <td className="p-2 text-zinc-300">{t.object}</td>
                        <td className="p-2 text-zinc-500 text-xs">{t.created_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {triplesTotal > TRIPLES_PAGE_SIZE && (
                <div className="flex gap-2 mt-2">
                  <button
                    type="button"
                    onClick={() => setTriplesPage((p) => Math.max(0, p - 1))}
                    disabled={triplesPage === 0}
                    className="px-2 py-1 rounded bg-zinc-800 text-zinc-300 text-xs disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-zinc-500 py-1">
                    {triplesPage * TRIPLES_PAGE_SIZE + 1}–{Math.min((triplesPage + 1) * TRIPLES_PAGE_SIZE, triplesTotal)} of {triplesTotal}
                  </span>
                  <button
                    type="button"
                    onClick={() => setTriplesPage((p) => p + 1)}
                    disabled={(triplesPage + 1) * TRIPLES_PAGE_SIZE >= triplesTotal}
                    className="px-2 py-1 rounded bg-zinc-800 text-zinc-300 text-xs disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {subTab === 'graph' && (
        <div className="flex-1 overflow-auto px-4 py-4 flex flex-col">
          <div className="flex gap-2 mb-4 items-center">
            <input
              type="text"
              placeholder="Focus on node (subject or object)"
              value={focusNode}
              onChange={(e) => setFocusNode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && setAppliedFocusNode(focusNode.trim())}
              className="rounded border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 flex-1 max-w-md"
            />
            <button
              type="button"
              onClick={() => setAppliedFocusNode(focusNode.trim())}
              disabled={focusLoading}
              className="px-3 py-2 rounded bg-zinc-700 text-zinc-200 text-sm disabled:opacity-50"
            >
              {focusLoading ? 'Loading…' : 'Load'}
            </button>
          </div>
          <p className="text-xs text-zinc-500 mb-2">
            Triples where this node is subject or object (1-hop neighborhood). Enter a node label and click Load.
          </p>
          {focusTriples.length === 0 ? (
            <p className="text-zinc-500 text-sm py-4">
              {appliedFocusNode && !focusLoading
                ? 'No triples found for this node.'
                : 'Enter a node and click Load to see its neighborhood.'}
            </p>
          ) : (
            <>
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden shrink-0 w-full" style={{ height: 450 }}>
                <ForceGraph2D
                  ref={graphRef}
                  graphData={graphData}
                  nodeLabel={(n) => (n as { label?: string }).label ?? String((n as { id?: string }).id)}
                  linkLabel={(l) => (l as { label?: string }).label ?? ''}
                  nodeCanvasObjectMode="after"
                  nodeCanvasObject={(node, ctx, globalScale) => {
                    const label = (node as { label?: string }).label ?? String((node as { id?: string }).id)
                    const x = (node as { x?: number }).x ?? 0
                    const y = (node as { y?: number }).y ?? 0
                    const fontSize = 12 / Math.min(globalScale, 2)
                    ctx.font = `${fontSize}px Sans-Serif`
                    ctx.textAlign = 'left'
                    ctx.textBaseline = 'middle'
                    ctx.fillStyle = '#e4e4e7'
                    ctx.fillText(label, x + 6, y)
                  }}
                  nodeColor={(n) => {
                    const id = String((n as { id?: string }).id)
                    return id === highlightedNodeId ? '#fbbf24' : '#a1a1aa'
                  }}
                  linkColor={(l) => {
                    const src = typeof (l as { source?: { id?: string } }).source === 'object' ? (l as { source: { id: string } }).source?.id : (l as { source: string }).source
                    const tgt = typeof (l as { target?: { id?: string } }).target === 'object' ? (l as { target: { id: string } }).target?.id : (l as { target: string }).target
                    const match = highlightedLink && String(src) === highlightedLink.source && String(tgt) === highlightedLink.target
                    return match ? '#fbbf24' : '#52525b'
                  }}
                  onNodeHover={(n) => setHighlightedNodeId(n ? String((n as { id?: string }).id) : null)}
                  onLinkHover={(l) => {
                    if (!l) {
                      setHighlightedLink(null)
                      return
                    }
                    const src = (l as { source: string | { id?: string } }).source
                    const tgt = (l as { target: string | { id?: string } }).target
                    setHighlightedLink({
                      source: typeof src === 'object' && src?.id != null ? String(src.id) : String(src),
                      target: typeof tgt === 'object' && tgt?.id != null ? String(tgt.id) : String(tgt),
                    })
                  }}
                  onEngineStop={() => {
                    const g = graphRef.current as { d3Force?: (n: string) => { distance?: (d: number) => void; strength?: (s: number) => void } } | null | undefined
                    const linkForce = g?.d3Force?.('link')
                    const chargeForce = g?.d3Force?.('charge')
                    if (linkForce?.distance) linkForce.distance(80)
                    if (chargeForce?.strength) chargeForce.strength(-100)
                  }}
                  enablePointerInteraction={true}
                  showPointerCursor={true}
                  nodeRelSize={8}
                  backgroundColor="#18181b"
                />
              </div>
              <div className="mt-4 space-y-2">
                {focusTriples.map((t) => {
                  const rowHighlight = highlightedNodeId === t.subject || highlightedNodeId === t.object || (highlightedLink && highlightedLink.source === t.subject && highlightedLink.target === t.object)
                  return (
                    <div
                      key={t.id}
                      className={`rounded border px-3 py-2 text-sm ${rowHighlight ? 'border-amber-500/60 bg-amber-950/30' : 'border-zinc-700 bg-zinc-900/80'}`}
                      onMouseEnter={() => setHighlightedNodeId(t.subject)}
                      onMouseLeave={() => setHighlightedNodeId(null)}
                    >
                      <span className="text-zinc-300 font-medium">{t.subject}</span>
                      <span className="text-zinc-500 mx-2">—{t.predicate}→</span>
                      <span className="text-zinc-300">{t.object}</span>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}

      {subTab === 'rag' && (
        <div className="flex-1 overflow-auto px-4 py-4">
          <div className="flex flex-wrap gap-2 mb-4 items-center">
            <input
              type="text"
              placeholder="Semantic search (optional)"
              value={ragSearchQ}
              onChange={(e) => setRagSearchQ(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-200 w-48"
            />
            <select
              value={ragSourceFilter}
              onChange={(e) => setRagSourceFilter(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-200"
            >
              <option value="">All sources</option>
              {ragSources.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => {
                setAppliedRagSearchQ(ragSearchQ)
                setAppliedRagSourceFilter(ragSourceFilter)
                setRagPage(0)
              }}
              className="px-2 py-1 rounded bg-zinc-700 text-zinc-200 text-sm"
            >
              Apply
            </button>
            {selectedRagIds.size > 0 && (
              <button
                type="button"
                onClick={handleDeleteRag}
                disabled={deletingRag}
                className="px-2 py-1 rounded bg-red-900/60 text-red-200 text-sm disabled:opacity-50"
              >
                Delete {selectedRagIds.size} selected
              </button>
            )}
          </div>
          {ragLoading ? (
            <p className="text-zinc-500 text-sm animate-pulse">Loading…</p>
          ) : ragChunks.length === 0 ? (
            <p className="text-zinc-500 text-sm">
              {appliedRagSearchQ || appliedRagSourceFilter
                ? 'No chunks match your search or filter.'
                : 'No RAG chunks yet. Use rag_ingest to add documents.'}
            </p>
          ) : (
            <>
              <div className="space-y-3">
                {ragChunks.map((c) => (
                  <div
                    key={c.id}
                    className="rounded-lg border border-zinc-800 bg-zinc-900/80 p-4"
                  >
                    <div className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked={selectedRagIds.has(c.id)}
                        onChange={() => toggleRag(c.id)}
                        className="mt-1 rounded border-zinc-600"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-zinc-500 mb-1">
                          {c.id}
                          {c.metadata?.source != null && (
                            <span className="ml-2">source: {String(c.metadata.source)}</span>
                          )}
                        </div>
                        <p className="text-sm text-zinc-300 whitespace-pre-wrap">
                          {c.document.slice(0, 400)}
                          {c.document.length > 400 ? '…' : ''}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {ragTotal > RAG_PAGE_SIZE && (
                <div className="flex gap-2 mt-4">
                  <button
                    type="button"
                    onClick={() => setRagPage((p) => Math.max(0, p - 1))}
                    disabled={ragPage === 0}
                    className="px-2 py-1 rounded bg-zinc-800 text-zinc-300 text-xs disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-zinc-500 py-1">
                    {ragPage * RAG_PAGE_SIZE + 1}–{Math.min((ragPage + 1) * RAG_PAGE_SIZE, ragTotal)} of {ragTotal}
                  </span>
                  <button
                    type="button"
                    onClick={() => setRagPage((p) => p + 1)}
                    disabled={(ragPage + 1) * RAG_PAGE_SIZE >= ragTotal}
                    className="px-2 py-1 rounded bg-zinc-800 text-zinc-300 text-xs disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
