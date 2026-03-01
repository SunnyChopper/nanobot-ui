import { Cpu, Wifi, WifiOff, Loader2 } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

export function StatusBar() {
  const connectionStatus = useChatStore((s) => s.connectionStatus)
  const status = useChatStore((s) => s.status)

  const statusConfig = {
    connected: {
      icon: <Wifi size={12} className="text-emerald-400" />,
      label: 'Connected',
      color: 'text-emerald-400',
    },
    connecting: {
      icon: <Loader2 size={12} className="text-amber-400 animate-spin" />,
      label: 'Connecting…',
      color: 'text-amber-400',
    },
    disconnected: {
      icon: <WifiOff size={12} className="text-zinc-500" />,
      label: 'Disconnected',
      color: 'text-zinc-500',
    },
  }[connectionStatus]

  return (
    <div className="flex items-center gap-4 px-4 py-1.5 border-t border-zinc-800 bg-zinc-950 text-[11px]">
      <div className="flex items-center gap-1.5">
        {statusConfig.icon}
        <span className={statusConfig.color}>{statusConfig.label}</span>
      </div>

      {status && (
        <>
          <div className="flex items-center gap-1.5 text-zinc-500">
            <Cpu size={11} />
            <span className="font-mono truncate max-w-[200px]">{status.model}</span>
          </div>
          <div className="ml-auto text-zinc-600">v{status.version}</div>
        </>
      )}
    </div>
  )
}
