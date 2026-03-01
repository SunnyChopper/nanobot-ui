import { useEffect } from 'react'
import { Layout } from './components/Layout'
import { useChatStore } from './stores/chatStore'

export default function App() {
  const connect = useChatStore((s) => s.connect)
  const disconnect = useChatStore((s) => s.disconnect)

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return (
    <div className="h-full">
      <Layout />
    </div>
  )
}
