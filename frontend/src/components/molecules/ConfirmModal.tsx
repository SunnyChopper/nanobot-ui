import { Loader2 } from 'lucide-react'

export type ConfirmModalVariant = 'danger' | 'primary'

interface ConfirmModalProps {
  title: string
  message: string
  confirmLabel: string
  variant?: ConfirmModalVariant
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  title,
  message,
  confirmLabel,
  variant = 'primary',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const confirmClass =
    variant === 'danger'
      ? 'rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-500 disabled:opacity-50 inline-flex items-center gap-1.5'
      : 'rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500 disabled:opacity-50 inline-flex items-center gap-1.5'
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
    >
      <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 shadow-xl max-w-sm w-full mx-4">
        <h2 id="confirm-modal-title" className="text-sm font-medium text-zinc-200 mb-2">
          {title}
        </h2>
        <p className="text-xs text-zinc-500 mb-4">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-zinc-600 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={confirmClass}
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {loading && ' '}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
