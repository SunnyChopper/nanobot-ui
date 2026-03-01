/** Knowledge base API: KG triples + RAG chunks */

import { apiFetch } from './http'
import type {
  RagChunksListResponseKnowledge,
  RagSourcesResponse,
  TriplesListResponse,
  TriplesStatsResponse,
} from './types'

export function getKnowledgeTriples(params?: {
  subject?: string
  predicate?: string
  object?: string
  limit?: number
  offset?: number
}): Promise<TriplesListResponse> {
  const sp = new URLSearchParams()
  if (params?.subject != null) sp.set('subject', params.subject)
  if (params?.predicate != null) sp.set('predicate', params.predicate)
  if (params?.object != null) sp.set('object', params.object)
  if (params?.limit != null) sp.set('limit', String(params.limit))
  if (params?.offset != null) sp.set('offset', String(params.offset))
  const q = sp.toString()
  return apiFetch(`/knowledge/triples${q ? `?${q}` : ''}`)
}

export function getKnowledgeTriplesStats(): Promise<TriplesStatsResponse> {
  return apiFetch('/knowledge/triples/stats')
}

export function deleteKnowledgeTriples(
  ids: number[],
): Promise<{ status: string; deleted: number }> {
  return apiFetch('/knowledge/triples', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  })
}

export function getKnowledgeRagChunks(params?: {
  limit?: number
  offset?: number
  source?: string
  q?: string
}): Promise<RagChunksListResponseKnowledge> {
  const sp = new URLSearchParams()
  if (params?.limit != null) sp.set('limit', String(params.limit))
  if (params?.offset != null) sp.set('offset', String(params.offset))
  if (params?.source != null) sp.set('source', params.source)
  if (params?.q != null) sp.set('q', params.q)
  const q = sp.toString()
  return apiFetch(`/knowledge/rag/chunks${q ? `?${q}` : ''}`)
}

export function getKnowledgeRagSources(): Promise<RagSourcesResponse> {
  return apiFetch('/knowledge/rag/sources')
}

export function deleteKnowledgeRagChunks(
  ids: string[],
): Promise<{ status: string; deleted: number }> {
  return apiFetch('/knowledge/rag/chunks', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  })
}
