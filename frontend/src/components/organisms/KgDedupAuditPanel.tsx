import { ChevronDown, ChevronRight, Loader2, RotateCcw } from 'lucide-react'
import type { KgDedupAuditDetail, KgDedupRemovedTriple } from '../../api/types'

interface KgDedupAuditPanelProps {
  open: boolean
  onToggle: () => void
  audit: KgDedupAuditDetail | null
  auditLoading: boolean
  onRestore: (t: KgDedupRemovedTriple) => void
}

export function KgDedupAuditPanel({ open, onToggle, audit, auditLoading, onRestore }: KgDedupAuditPanelProps) {
  return (
    <>
      <button
        onClick={onToggle}
        className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
      >
        {open ? (
          <ChevronDown size={14} />
        ) : (
          <ChevronRight size={14} />
        )}
        View what was deleted
      </button>
      {open && (
        <div className="mt-3 pt-3 border-t border-zinc-700">
          {auditLoading ? (
            <p className="text-xs text-zinc-500 flex items-center gap-2">
              <Loader2 size={12} className="animate-spin" />
              Loading audit…
            </p>
          ) : audit ? (
            <div className="space-y-4 max-h-80 overflow-y-auto">
              {audit.merged_nodes.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-zinc-400 mb-2">Merged nodes</p>
                  <ul className="text-xs text-zinc-500 space-y-1">
                    {audit.merged_nodes.map((m, i) => (
                      <li key={i}>
                        &quot;{m.old_label}&quot; → &quot;{m.canonical_label}&quot;
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {audit.removed_triples.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-zinc-400 mb-2">Removed triples</p>
                  <ul className="text-xs text-zinc-500 space-y-2 font-mono">
                    {audit.removed_triples.map((t, i) => (
                      <li
                        key={i}
                        className="flex flex-wrap items-start gap-2 py-1 border-b border-zinc-700/50 last:border-0"
                      >
                        <span className="flex-1 min-w-0">
                          <span className="text-zinc-400">
                            {t.subject} —{t.predicate}— {t.object}
                          </span>
                          {t.merged_into &&
                            (t.merged_into.subject !== t.subject ||
                              t.merged_into.predicate !== t.predicate ||
                              t.merged_into.object !== t.object) && (
                              <span className="block mt-0.5 text-zinc-600">
                                → merged into: {t.merged_into.subject} —{t.merged_into.predicate}—{' '}
                                {t.merged_into.object}
                              </span>
                            )}
                        </span>
                        <button
                          type="button"
                          onClick={() => onRestore(t)}
                          className="flex items-center gap-1 shrink-0 px-2 py-0.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-[10px] font-medium transition-colors"
                          title="Restore this triple into the knowledge graph"
                        >
                          <RotateCcw size={10} />
                          Restore
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {audit.merged_nodes.length === 0 && audit.removed_triples.length === 0 && (
                <p className="text-xs text-zinc-500">No merges or removals in this run.</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-zinc-500">Could not load audit for this run.</p>
          )}
        </div>
      )}
    </>
  )
}
