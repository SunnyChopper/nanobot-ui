interface StatusBadgeProps {
  status: string | null
  /** Use compact variant for cron/ok only. Default: workflow (success, error, running, etc.) */
  variant?: 'workflow' | 'cron'
}

export function StatusBadge({ status, variant = 'workflow' }: StatusBadgeProps) {
  if (!status) return <span className="text-zinc-500">—</span>
  const cls =
    variant === 'cron'
      ? status === 'ok'
        ? 'bg-emerald-900/50 text-emerald-400'
        : status === 'error'
          ? 'bg-red-900/50 text-red-400'
          : 'bg-zinc-700 text-zinc-400'
      : status === 'success' || status === 'ok'
        ? 'bg-emerald-900/50 text-emerald-400'
        : status === 'error'
          ? 'bg-red-900/50 text-red-400'
          : status === 'running'
            ? 'bg-blue-900/50 text-blue-400'
            : 'bg-zinc-700 text-zinc-400'
  return (
    <span className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}
