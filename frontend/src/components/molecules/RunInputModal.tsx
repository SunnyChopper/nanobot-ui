interface RunInputModalProps {
  title: string
  value: string
  onChange: (value: string) => void
  onConfirm: () => void
  onCancel: () => void
  placeholder?: string
}

export function RunInputModal({
  title,
  value,
  onChange,
  onConfirm,
  onCancel,
  placeholder = '{"key": "value"}',
}: RunInputModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-labelledby="run-input-title"
    >
      <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 shadow-xl max-w-md w-full mx-4">
        <h2 id="run-input-title" className="text-sm font-medium text-zinc-200 mb-2">
          {title}
        </h2>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={6}
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm font-mono text-zinc-300 resize-none mb-4"
          placeholder={placeholder}
        />
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-zinc-600 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500"
          >
            Run
          </button>
        </div>
      </div>
    </div>
  )
}
