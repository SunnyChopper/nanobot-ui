export function formatTimestamp(ms: number | null): string {
  if (ms == null) return '—'
  return new Date(ms).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

interface TimestampProps {
  ms: number | null
}

export function Timestamp({ ms }: TimestampProps) {
  return <span>{formatTimestamp(ms)}</span>
}
