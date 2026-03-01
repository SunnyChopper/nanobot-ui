import { useEffect, useState } from 'react'
import { Clock, PanelLeftClose, PanelLeftOpen, Settings, Brain, Shield, GitBranch } from 'lucide-react'
import { ThreadList } from './ThreadList'
import { ChatView } from './ChatView'
import { StatusBar } from './StatusBar'
import { SettingsPage } from './SettingsPage'
import { JobsPage } from './JobsPage'
import { MemoryPage } from './MemoryPage'
import { AdminPage } from './AdminPage'
import { WorkflowsPage } from './WorkflowsPage'
import { ProjectSwitcher } from './ProjectSwitcher'
import { useChatStore } from '../stores/chatStore'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [view, setView] = useState<'chat' | 'settings' | 'jobs' | 'memory' | 'admin' | 'workflows'>('chat')
  const [scheduleWorkflowId, setScheduleWorkflowId] = useState<string | null>(null)

  const sessions = useChatStore((s) => s.sessions)
  const activeSessionId = useChatStore((s) => s.activeSessionId)

  const activeSession = sessions.find((s) => s.key === activeSessionId)
  const chatTitle = activeSession?.title || 'Untitled chat'

  // Collapse sidebar on small screens
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 640px)')
    if (mq.matches) setSidebarOpen(false)
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-800 bg-zinc-950">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
          title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
        >
          {sidebarOpen ? (
            <PanelLeftClose size={16} />
          ) : (
            <PanelLeftOpen size={16} />
          )}
        </button>

        {/* Chat title + project (only visible in chat view) */}
        {view === 'chat' && (
          <div className="flex-1 flex items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-zinc-400 truncate" title={chatTitle}>
              {chatTitle}
            </span>
            <ProjectSwitcher />
          </div>
        )}
        {view === 'settings' && (
          <span className="flex-1 text-sm font-medium text-zinc-400">Settings</span>
        )}
        {view === 'jobs' && (
          <span className="flex-1 text-sm font-medium text-zinc-400">Scheduled tasks</span>
        )}
        {view === 'memory' && (
          <span className="flex-1 text-sm font-medium text-zinc-400">Memory</span>
        )}
        {view === 'admin' && (
          <span className="flex-1 text-sm font-medium text-zinc-400">Admin</span>
        )}
        {view === 'workflows' && (
          <span className="flex-1 text-sm font-medium text-zinc-400">Workflows</span>
        )}

        {/* Memory */}
        <button
          onClick={() => setView((v) => (v === 'memory' ? 'chat' : 'memory'))}
          className={`p-1.5 rounded-lg transition-colors ${
            view === 'memory'
              ? 'bg-zinc-700 text-zinc-200'
              : 'hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300'
          }`}
          title={view === 'memory' ? 'Back to chat' : 'Memory (MEMORY.md / HISTORY.md)'}
        >
          <Brain size={15} />
        </button>

        {/* Workflows */}
        <button
          onClick={() => setView((v) => (v === 'workflows' ? 'chat' : 'workflows'))}
          className={`p-1.5 rounded-lg transition-colors ${
            view === 'workflows'
              ? 'bg-zinc-700 text-zinc-200'
              : 'hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300'
          }`}
          title={view === 'workflows' ? 'Back to chat' : 'Workflows'}
        >
          <GitBranch size={15} />
        </button>

        {/* Jobs (scheduled tasks) */}
        <button
          onClick={() => setView((v) => (v === 'jobs' ? 'chat' : 'jobs'))}
          className={`p-1.5 rounded-lg transition-colors ${
            view === 'jobs'
              ? 'bg-zinc-700 text-zinc-200'
              : 'hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300'
          }`}
          title={view === 'jobs' ? 'Back to chat' : 'Scheduled tasks'}
        >
          <Clock size={15} />
        </button>

        {/* Admin */}
        <button
          onClick={() => setView((v) => (v === 'admin' ? 'chat' : 'admin'))}
          className={`p-1.5 rounded-lg transition-colors ${
            view === 'admin'
              ? 'bg-zinc-700 text-zinc-200'
              : 'hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300'
          }`}
          title={view === 'admin' ? 'Back to chat' : 'Admin'}
        >
          <Shield size={15} />
        </button>

        {/* Settings */}
        <button
          onClick={() => setView((v) => (v === 'settings' ? 'chat' : 'settings'))}
          className={`p-1.5 rounded-lg transition-colors ${
            view === 'settings'
              ? 'bg-zinc-700 text-zinc-200'
              : 'hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300'
          }`}
          title={view === 'settings' ? 'Back to chat' : 'Open settings'}
        >
          <Settings size={15} />
        </button>
      </div>

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Sidebar (always shown; hidden in settings to keep context) */}
        {sidebarOpen && (view === 'chat' || view === 'jobs' || view === 'memory' || view === 'admin' || view === 'workflows') && (
          <div className="w-64 shrink-0 flex flex-col min-h-0">
            <ThreadList />
          </div>
        )}

        {/* Main view */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">
          {view === 'chat' && <ChatView />}
          {view === 'settings' && <SettingsPage />}
          {view === 'jobs' && (
            <JobsPage
              initialScheduleWorkflowId={scheduleWorkflowId}
              onConsumedScheduleWorkflowId={() => setScheduleWorkflowId(null)}
            />
          )}
          {view === 'memory' && <MemoryPage />}
          {view === 'admin' && <AdminPage />}
          {view === 'workflows' && (
            <WorkflowsPage
              onOpenScheduleForWorkflow={(id: string) => {
                setScheduleWorkflowId(id)
                setView('jobs')
              }}
            />
          )}
        </div>
      </div>

      {/* Footer status bar */}
      <StatusBar />
    </div>
  )
}
