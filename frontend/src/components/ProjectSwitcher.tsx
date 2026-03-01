import { useEffect, useState } from 'react'
import { FolderOpen, ChevronDown } from 'lucide-react'
import { useChatStore } from '../stores/chatStore'
import { getProjects, setSessionProject } from '../api/client'
import type { ProjectItem } from '../api/client'

export function ProjectSwitcher() {
  const activeSessionMetadata = useChatStore((s) => s.activeSessionMetadata)
  const setSessionProjectStore = useChatStore((s) => s.setSessionProject)
  const currentProject = (activeSessionMetadata?.project as string) ?? null

  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open && projects.length === 0) {
      setLoading(true)
      getProjects()
        .then(setProjects)
        .finally(() => setLoading(false))
    }
  }, [open, projects.length])

  async function handleSelect(project: string | null) {
    await setSessionProjectStore(project)
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 text-xs"
        title="Active project (context)"
      >
        <FolderOpen size={14} />
        <span className="max-w-[100px] truncate">{currentProject || 'No project'}</span>
        <ChevronDown size={12} className={open ? 'rotate-180' : ''} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute left-0 top-full mt-1 py-1 rounded-lg border border-zinc-700 bg-zinc-900 shadow-xl z-20 min-w-[160px] max-h-[240px] overflow-y-auto">
            {loading ? (
              <div className="px-3 py-2 text-xs text-zinc-500">Loading…</div>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => handleSelect(null)}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-zinc-800 ${!currentProject ? 'text-zinc-200 bg-zinc-800' : 'text-zinc-400'}`}
                >
                  None
                </button>
                {projects.map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => handleSelect(p.name)}
                    className={`w-full text-left px-3 py-1.5 text-xs hover:bg-zinc-800 truncate ${currentProject === p.name ? 'text-zinc-200 bg-zinc-800' : 'text-zinc-400'}`}
                    title={p.path}
                  >
                    {p.name}
                  </button>
                ))}
                {projects.length === 0 && !loading && (
                  <div className="px-3 py-2 text-xs text-zinc-500">
                    Add ~/.nanobot/projects.json to define projects.
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
