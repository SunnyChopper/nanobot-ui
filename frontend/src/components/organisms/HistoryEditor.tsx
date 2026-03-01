interface HistoryEditorProps {
  title: string
  value: string
  draft: string
  editing: boolean
  saving: boolean
  onEdit: () => void
  onDraftChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
}

export function HistoryEditor({
  title,
  value,
  draft,
  editing,
  saving,
  onEdit,
  onDraftChange,
  onSave,
  onCancel,
}: HistoryEditorProps) {
  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide">{title}</h2>
        {!editing ? (
          <button
            type="button"
            onClick={onEdit}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Edit
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="text-xs px-2 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="text-xs px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          className="w-full rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-xs text-zinc-300 font-sans min-h-[200px] resize-y"
          spellCheck={false}
        />
      ) : (
        <pre className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-xs text-zinc-300 whitespace-pre-wrap font-sans max-h-[50vh] overflow-y-auto">
          {value || '(empty)'}
        </pre>
      )}
    </section>
  )
}
