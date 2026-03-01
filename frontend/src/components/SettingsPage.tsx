import { useEffect, useState } from 'react'
import {
  Save,
  Plus,
  Trash2,
  Loader2,
  ExternalLink,
  Server,
  Cpu,
  Wrench,
  Info,
  FolderOpen,
  ShieldCheck,
  Key,
  ChevronDown,
  ChevronRight,
  Layers,
  Activity,
  HelpCircle,
} from 'lucide-react'
import { Tooltip } from './atoms/Tooltip'
import { McpServerCard } from './molecules/McpServerCard'
import {
  getConfig,
  getMcpServerStatus,
  getModels,
  getProviders,
  testLlmProfiler,
  testMcpConnection,
  updateConfig,
} from '../api/client'
import type { McpServerStatus } from '../api/mcp'
import type {
  ConfigResponse,
  KgDedupConfigResponse,
  LlmProfilerResult,
  MCPServerPatch,
  ModelOption,
  ProviderConfigPatch,
  ProviderItem,
} from '../api/types'

/** Fallback when /api/providers hasn’t loaded so API key inputs always show. */
const FALLBACK_PROVIDER_LIST: ProviderItem[] = [
  { id: 'gemini', display_name: 'Gemini', has_api_key: false },
  { id: 'anthropic', display_name: 'Anthropic', has_api_key: false },
  { id: 'openai', display_name: 'OpenAI', has_api_key: false },
  { id: 'openrouter', display_name: 'OpenRouter', has_api_key: false },
  { id: 'deepseek', display_name: 'DeepSeek', has_api_key: false },
  { id: 'groq', display_name: 'Groq', has_api_key: false },
  { id: 'moonshot', display_name: 'Moonshot', has_api_key: false },
  { id: 'dashscope', display_name: 'DashScope', has_api_key: false },
  { id: 'minimax', display_name: 'MiniMax', has_api_key: false },
  { id: 'zhipu', display_name: 'Zhipu AI', has_api_key: false },
  { id: 'custom', display_name: 'Custom', has_api_key: false },
  { id: 'vllm', display_name: 'vLLM / Local', has_api_key: false },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function SectionTitle({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-200 mb-4">
      {icon}
      {children}
    </h2>
  )
}

function Field({
  label,
  hint,
  hintAsTooltip,
  children,
}: {
  label: string
  hint?: string
  /** When true, show hint in a tooltip on an info icon instead of below the input. Use for MCP and other repetitive hints. */
  hintAsTooltip?: boolean
  children: React.ReactNode
}) {
  const useTooltip = hintAsTooltip === true && !!hint
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        <label className="block text-xs font-medium text-zinc-400">{label}</label>
        {useTooltip && (
          <Tooltip content={hint}>
            <HelpCircle size={12} className="text-zinc-500 shrink-0 cursor-help" aria-hidden />
          </Tooltip>
        )}
      </div>
      {children}
      {hint && !useTooltip && <p className="text-[10px] text-zinc-600">{hint}</p>}
    </div>
  )
}

const inputCls =
  'w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200 outline-none focus:border-zinc-500 transition-colors'

// ---------------------------------------------------------------------------
// Tool Policy Editor
// ---------------------------------------------------------------------------

const TOOL_LABELS: Record<string, string> = {
  read_file: 'Read file',
  list_dir: 'List directory',
  web_search: 'Web search',
  web_fetch: 'Fetch URL',
  message: 'Send message',
  write_file: 'Write file',
  edit_file: 'Edit file',
  exec: 'Shell command',
  spawn: 'Spawn subagent',
  cron: 'Schedule task',
  screenshot: 'Screenshot',
  screenshot_region: 'Screenshot region',
  mouse_move: 'Move mouse',
  mouse_click: 'Mouse click',
  mouse_position: 'Mouse position',
  keyboard_type: 'Keyboard type',
  locate_on_screen: 'Locate image',
  click_image: 'Click image',
  get_foreground_window: 'Foreground window',
  launch_app: 'Launch app',
}

const TOOL_ORDER = [
  'read_file',
  'list_dir',
  'web_search',
  'web_fetch',
  'message',
  'write_file',
  'edit_file',
  'exec',
  'spawn',
  'cron',
  'screenshot',
  'screenshot_region',
  'mouse_move',
  'mouse_click',
  'mouse_position',
  'keyboard_type',
  'locate_on_screen',
  'click_image',
  'get_foreground_window',
  'launch_app',
]

/** Tools that default to "ask" on the server when not set in config (so UI matches server). */
const TOOL_DEFAULT_ASK = new Set([
  'write_file', 'edit_file', 'exec', 'spawn', 'cron',
  'screenshot', 'screenshot_region', 'mouse_move', 'mouse_click', 'mouse_position', 'keyboard_type',
  'locate_on_screen', 'click_image', 'get_foreground_window', 'launch_app',
])

type PolicyValue = 'auto' | 'ask' | 'deny'

const POLICY_LABELS: Record<PolicyValue, string> = {
  auto: 'Auto',
  ask: 'Ask',
  deny: 'Deny',
}

const POLICY_COLORS: Record<PolicyValue, string> = {
  auto: 'bg-emerald-700 text-emerald-100',
  ask: 'bg-yellow-700 text-yellow-100',
  deny: 'bg-red-800 text-red-100',
}

const POLICY_INACTIVE: Record<PolicyValue, string> = {
  auto: 'text-zinc-500 hover:bg-zinc-700',
  ask: 'text-zinc-500 hover:bg-zinc-700',
  deny: 'text-zinc-500 hover:bg-zinc-700',
}

function ToolPolicyEditor({
  policy,
  onChange,
}: {
  policy: Record<string, string>
  onChange: (p: Record<string, string>) => void
}) {
  function setPolicy(tool: string, val: PolicyValue) {
    onChange({ ...policy, [tool]: val })
  }

  return (
    <div className="space-y-1">
      {TOOL_ORDER.map((tool) => {
        const current = (policy[tool] ?? (TOOL_DEFAULT_ASK.has(tool) ? 'ask' : 'auto')) as PolicyValue
        return (
          <div
            key={tool}
            className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2"
          >
            <span className="text-xs text-zinc-300 font-mono">{TOOL_LABELS[tool] ?? tool}</span>
            <div className="flex gap-1">
              {(['auto', 'ask', 'deny'] as PolicyValue[]).map((val) => (
                <button
                  key={val}
                  onClick={() => setPolicy(tool, val)}
                  className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
                    current === val ? POLICY_COLORS[val] : POLICY_INACTIVE[val]
                  }`}
                >
                  {POLICY_LABELS[val]}
                </button>
              ))}
            </div>
          </div>
        )
      })}
      <p className="text-[10px] text-zinc-600 pt-1">
        <strong className="text-emerald-600">Auto</strong> — runs without prompt.{' '}
        <strong className="text-yellow-600">Ask</strong> — pauses for your approval.{' '}
        <strong className="text-red-700">Deny</strong> — always blocked.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Provider selector and contextual model picker
// ---------------------------------------------------------------------------

function ProviderSelector({
  value,
  onChange,
  providers,
}: {
  value: string
  onChange: (v: string) => void
  providers: ProviderItem[]
}) {
  return (
    <select
      className={inputCls}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="LLM Provider"
    >
      <option value="">All providers</option>
      {providers.map((p) => (
        <option key={p.id} value={p.id} disabled={!p.has_api_key}>
          {p.display_name}
          {!p.has_api_key ? ' (no API key)' : ''}
        </option>
      ))}
    </select>
  )
}

// Model picker with datalist for autocomplete (filtered by provider when provided)
function ModelPicker({
  value,
  onChange,
  models,
  providerFilter,
}: {
  value: string
  onChange: (v: string) => void
  models: ModelOption[]
  providerFilter?: string
}) {
  const listId = 'model-options-list'
  const filtered =
    providerFilter != null && providerFilter !== ''
      ? models.filter((m) => m.provider === providerFilter)
      : models

  return (
    <>
      <input
        list={listId}
        className={inputCls}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. gemini/gemini-3-pro-preview or gpt-4o"
      />
      <datalist id={listId}>
        {filtered.map((m) => (
          <option key={m.id} value={m.id} label={m.label} />
        ))}
      </datalist>
    </>
  )
}

// ---------------------------------------------------------------------------
// MCP Servers — unified card (config + status + tools + skills)
// ---------------------------------------------------------------------------

type EffectiveMcpConfig = {
  command: string
  args: string[]
  env: Record<string, string>
  url: string
}

function effectiveMcpConfig(
  base: { command: string; args: string[]; env: Record<string, string>; url: string } | undefined,
  patch: MCPServerPatch | null | undefined
): EffectiveMcpConfig {
  const b = base ?? { command: '', args: [], env: {}, url: '' }
  const p = patch ?? {}
  return {
    command: p.command ?? b.command ?? '',
    args: p.args ?? b.args ?? [],
    env: { ...b.env, ...p.env },
    url: p.url ?? b.url ?? '',
  }
}

function configToPatch(
  serverKey: string,
  command: string,
  argsStr: string,
  envStr: string,
  url: string
): MCPServerPatch {
  const envObj: Record<string, string> = {}
  envStr.split('\n').forEach((line) => {
    const idx = line.indexOf('=')
    if (idx > 0) envObj[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
  })
  return {
    command,
    args: argsStr.split(/\s+/).map((s) => s.trim()).filter(Boolean),
    env: envObj,
    url,
  }
}

function MCPConfigForm({
  serverKey,
  effective,
  onChange,
}: {
  serverKey: string
  effective: EffectiveMcpConfig
  onChange: (patch: MCPServerPatch) => void
}) {
  const envLines = Object.entries(effective.env || {}).map(([k, v]) => `${k}=${v}`).join('\n')
  const [command, setCommand] = useState(effective.command)
  const [argsStr, setArgsStr] = useState(effective.args.join(' '))
  const [envStr, setEnvStr] = useState(envLines)
  const [url, setUrl] = useState(effective.url)

  useEffect(() => {
    setCommand(effective.command)
    setArgsStr(effective.args.join(' '))
    setEnvStr(Object.entries(effective.env || {}).map(([k, v]) => `${k}=${v}`).join('\n'))
    setUrl(effective.url)
  }, [effective.command, effective.args, effective.env, effective.url])

  const apply = (overrides: { command?: string; argsStr?: string; envStr?: string; url?: string }) =>
    onChange(configToPatch(
      serverKey,
      overrides.command ?? command,
      overrides.argsStr ?? argsStr,
      overrides.envStr ?? envStr,
      overrides.url ?? url
    ))

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Command (stdio)" hint="e.g. npx" hintAsTooltip>
          <input
            className={inputCls}
            value={command}
            onChange={(e) => { setCommand(e.target.value); apply({ command: e.target.value }) }}
            placeholder="npx"
          />
        </Field>
        <Field label="URL (HTTP)" hint="For HTTP MCP servers" hintAsTooltip>
          <input
            className={inputCls}
            value={url}
            onChange={(e) => { setUrl(e.target.value); apply({ url: e.target.value }) }}
            placeholder="https://..."
          />
        </Field>
      </div>
      <Field label="Args" hint="Space-separated arguments" hintAsTooltip>
        <input
          className={inputCls}
          value={argsStr}
          onChange={(e) => { setArgsStr(e.target.value); apply({ argsStr: e.target.value }) }}
          placeholder="-y @modelcontextprotocol/server-filesystem /path"
        />
      </Field>
      <Field label="Env vars" hint="One KEY=VALUE per line" hintAsTooltip>
        <textarea
          className={`${inputCls} resize-none`}
          rows={2}
          value={envStr}
          onChange={(e) => { setEnvStr(e.target.value); apply({ envStr: e.target.value }) }}
          placeholder="API_KEY=abc123"
        />
      </Field>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main SettingsPage
// ---------------------------------------------------------------------------

export function SettingsPage() {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([])
  const [availableProviders, setAvailableProviders] = useState<ProviderItem[]>([])
  const [selectedProvider, setSelectedProvider] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')

  // Editable fields
  const [model, setModel] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [maxTokens, setMaxTokens] = useState(8192)
  const [temperature, setTemperature] = useState(0.7)
  const [maxToolIter, setMaxToolIter] = useState(20)
  const [memoryWindow, setMemoryWindow] = useState(50)
  const [restrictToWorkspace, setRestrictToWorkspace] = useState(false)
  const [execTimeout, setExecTimeout] = useState(60)
  const [webSearchKey, setWebSearchKey] = useState('')
  const [mcpPatch, setMcpPatch] = useState<Record<string, MCPServerPatch | null>>({})
  const [mcpGuidance, setMcpGuidance] = useState<Record<string, string>>({})
  const [toolPolicy, setToolPolicy] = useState<Record<string, string>>({})
  const [cuaAutoApprove, setCuaAutoApprove] = useState(false)
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({})
  const [providerApiBases, setProviderApiBases] = useState<Record<string, string>>({})
  const [expandedApiBase, setExpandedApiBase] = useState<Record<string, boolean>>({})
  const [kgDedupEnabled, setKgDedupEnabled] = useState(false)
  const [kgDedupSchedule, setKgDedupSchedule] = useState('0 3 * * *')
  const [kgDedupModel, setKgDedupModel] = useState('')
  const [kgDedupLlmBatchSize, setKgDedupLlmBatchSize] = useState(20)
  const [kgDedupBatchSize, setKgDedupBatchSize] = useState(256)
  /** Explicit provider override from config (agent.provider): 'auto' or provider id. */
  const [providerOverride, setProviderOverride] = useState('auto')
  /** Thinking mode (agent.reasoning_effort): null = off, 'low' | 'medium' | 'high'. */
  const [reasoningEffort, setReasoningEffort] = useState<string | null>(null)
  /** PATH suffix for shell/exec (tools.exec.path_append). */
  const [pathAppend, setPathAppend] = useState('')
  /** Per-server status: loading | result | null (fetch error). Servers shown immediately; each card updates when its request completes. */
  const [mcpStatusPerServer, setMcpStatusPerServer] = useState<
    Record<string, McpServerStatus | 'loading' | null>
  >({})
  const [mcpTestingKey, setMcpTestingKey] = useState<string | null>(null)
  const [mcpNewKey, setMcpNewKey] = useState('')
  const [profilerResult, setProfilerResult] = useState<LlmProfilerResult | null>(null)
  const [profilerLoading, setProfilerLoading] = useState(false)

  useEffect(() => {
    Promise.all([
      getConfig(),
      getModels().catch(() => ({ models: [] as ModelOption[], current: '' })),
      getProviders().catch(() => ({ providers: [] as ProviderItem[] })),
    ])
      .then(([cfg, modelsResp, providersResp]) => {
        setConfig(cfg)
        setModel(cfg.agent.model)
        setWorkspace(cfg.agent.workspace)
        setMaxTokens(cfg.agent.max_tokens)
        setTemperature(cfg.agent.temperature)
        setMaxToolIter(cfg.agent.max_tool_iterations)
        setMemoryWindow(cfg.agent.memory_window)
        setProviderOverride(cfg.agent.provider ?? 'auto')
        setReasoningEffort(cfg.agent.reasoning_effort ?? null)
        setRestrictToWorkspace(cfg.tools.restrict_to_workspace)
        setExecTimeout(cfg.tools.exec_timeout)
        setPathAppend(cfg.tools.path_append ?? '')
        setToolPolicy(cfg.tools.tool_policy)
        setCuaAutoApprove(cfg.tools.cua_auto_approve ?? false)
        setMcpGuidance(cfg.tools.mcp_guidance ?? {})
        setAvailableModels(modelsResp.models)
        setAvailableProviders(providersResp.providers)
        setProviderApiBases((prev) => {
          const next = { ...prev }
          for (const [id, p] of Object.entries(cfg.providers || {})) {
            next[id] = (p as { api_base?: string | null }).api_base || ''
          }
          return next
        })
        // Set initial provider from current model's provider
        const currentModel = modelsResp.models.find((m) => m.id === cfg.agent.model)
        setSelectedProvider(currentModel?.provider ?? '')
        const kd: KgDedupConfigResponse | undefined = (cfg as { kg_dedup?: KgDedupConfigResponse }).kg_dedup
        if (kd) {
          setKgDedupEnabled(kd.enabled)
          setKgDedupSchedule(kd.schedule || '0 3 * * *')
          setKgDedupModel(kd.kg_dedup_model ?? '')
          setKgDedupLlmBatchSize(kd.llm_batch_size ?? 20)
          setKgDedupBatchSize(kd.batch_size ?? 256)
        }
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const keys = config ? Object.keys(config.mcp_servers || {}) : []
    if (keys.length === 0) {
      setMcpStatusPerServer({})
      return
    }
    setMcpStatusPerServer((prev) => ({
      ...prev,
      ...Object.fromEntries(keys.map((k) => [k, 'loading' as const])),
    }))
    keys.forEach((key) => {
      getMcpServerStatus(key)
        .then((s) => setMcpStatusPerServer((p) => ({ ...p, [key]: s })))
        .catch(() => setMcpStatusPerServer((p) => ({ ...p, [key]: null })))
    })
  }, [config])

  function addMcpServer() {
    const trimmed = mcpNewKey.trim()
    if (!trimmed) return
    setMcpPatch((prev) => ({
      ...prev,
      [trimmed]: { command: '', args: [], env: {}, url: '' },
    }))
    setMcpNewKey('')
  }

  async function handleSave() {
    setSaving(true)
    setSavedMsg('')
    try {
      const providersPatch: Record<string, ProviderConfigPatch> = {}
      const providerIds = new Set([
        ...Object.keys(config?.providers || {}),
        ...(availableProviders.length > 0
          ? availableProviders.map((p) => p.id)
          : FALLBACK_PROVIDER_LIST.map((p) => p.id)),
      ])
      for (const id of providerIds) {
        const keyVal = providerKeys[id]
        const baseVal = providerApiBases[id]
        const currentBase = (config?.providers?.[id] as { api_base?: string | null } | undefined)
          ?.api_base ?? ''
        const keyChanged = keyVal !== undefined
        const baseChanged = baseVal !== undefined && baseVal !== currentBase
        if (keyChanged || baseChanged) {
          providersPatch[id] = {}
          if (keyChanged) providersPatch[id].api_key = keyVal
          if (baseChanged) providersPatch[id].api_base = baseVal || null
        }
      }
      await updateConfig({
        agent: {
          model,
          workspace,
          max_tokens: maxTokens,
          temperature,
          max_tool_iterations: maxToolIter,
          memory_window: memoryWindow,
          provider: providerOverride,
          reasoning_effort: reasoningEffort || null,
        },
        ...(Object.keys(providersPatch).length > 0 ? { providers: providersPatch } : {}),
        kg_dedup: {
          enabled: kgDedupEnabled,
          schedule: kgDedupSchedule.trim() || '0 3 * * *',
          kg_dedup_model: kgDedupModel.trim(),
          llm_batch_size: kgDedupLlmBatchSize,
          batch_size: kgDedupBatchSize,
        },
        restrict_to_workspace: restrictToWorkspace,
        exec_timeout: execTimeout,
        exec_path_append: pathAppend,
        ...(webSearchKey ? { web_search_api_key: webSearchKey } : {}),
        ...(Object.keys(mcpPatch).length > 0 ? { mcp_servers: mcpPatch } : {}),
        mcp_guidance: mcpGuidance,
        tool_policy: toolPolicy,
        cua_auto_approve: cuaAutoApprove,
      })
      setSavedMsg('Settings saved.')
      setProviderKeys({})
      const [cfg, modelsResp, providersResp] = await Promise.all([
        getConfig(),
        getModels().catch(() => ({ models: availableModels, current: model })),
        getProviders().catch(() => ({ providers: availableProviders })),
      ])
      setConfig(cfg)
      setProviderOverride(cfg.agent.provider ?? 'auto')
      setReasoningEffort(cfg.agent.reasoning_effort ?? null)
      setPathAppend(cfg.tools.path_append ?? '')
      setToolPolicy(cfg.tools.tool_policy)
      setCuaAutoApprove(cfg.tools.cua_auto_approve ?? false)
      setMcpGuidance(cfg.tools.mcp_guidance ?? {})
      setAvailableModels(modelsResp.models)
      if (providersResp && providersResp.providers)
        setAvailableProviders(providersResp.providers)
      setProviderApiBases((prev) => {
        const next = { ...prev }
        for (const [id, p] of Object.entries(cfg.providers || {})) {
          const base = (p as { api_base?: string | null }).api_base
          next[id] = base ?? ''
        }
        return next
      })
      const kd = (cfg as { kg_dedup?: KgDedupConfigResponse }).kg_dedup
      if (kd) {
        setKgDedupEnabled(kd.enabled)
        setKgDedupSchedule(kd.schedule || '0 3 * * *')
        setKgDedupModel(kd.kg_dedup_model ?? '')
        setKgDedupLlmBatchSize(kd.llm_batch_size ?? 20)
        setKgDedupBatchSize(kd.batch_size ?? 256)
      }
    } catch (e) {
      setSavedMsg(`Error: ${e}`)
    } finally {
      setSaving(false)
      setTimeout(() => setSavedMsg(''), 4000)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-600">
        <Loader2 size={20} className="animate-spin mr-2" />
        Loading settings…
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-zinc-950 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-zinc-950 border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-base font-semibold text-zinc-100">Settings</h1>
        <div className="flex items-center gap-3">
          {savedMsg && (
            <span
              className={`text-xs ${savedMsg.startsWith('Error') ? 'text-red-400' : 'text-emerald-400'}`}
            >
              {savedMsg}
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-medium transition-colors"
          >
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            Save changes
          </button>
        </div>
      </div>

      <div className="flex-1 px-6 py-6 max-w-4xl mx-auto w-full space-y-10">
        {/* Agent */}
        <section>
          <SectionTitle icon={<Cpu size={15} className="text-zinc-400" />}>Agent</SectionTitle>
          <div className="space-y-4">
            <Field
              label="Provider"
              hint="Select the LLM provider first; then pick a model below (only providers with an API key are listed)."
            >
              <ProviderSelector
                value={selectedProvider}
                onChange={(v) => {
                  setSelectedProvider(v)
                  // Optionally clear or keep model when switching provider
                  const firstForProvider = availableModels.find((m) => m.provider === v)
                  if (v && firstForProvider) setModel(firstForProvider.id)
                }}
                providers={availableProviders}
              />
            </Field>
            <Field
              label="Model"
              hint="Type any model string or pick from the list for the selected provider."
            >
              <ModelPicker
                value={model}
                onChange={(v) => {
                  setModel(v)
                  const m = availableModels.find((x) => x.id === v)
                  if (m) setSelectedProvider(m.provider)
                }}
                models={availableModels}
                providerFilter={selectedProvider || undefined}
              />
            </Field>
            <Field
              label="Provider override"
              hint="Force a specific provider or Auto to detect from model."
            >
              <select
                className={inputCls}
                value={providerOverride}
                onChange={(e) => setProviderOverride(e.target.value)}
                aria-label="Provider override"
              >
                <option value="auto">Auto (from model)</option>
                {(availableProviders.length > 0 ? availableProviders : FALLBACK_PROVIDER_LIST).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Thinking mode"
              hint="Enable extended reasoning for supported models (e.g. Claude, DeepSeek). Off disables."
            >
              <select
                className={inputCls}
                value={reasoningEffort ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  setReasoningEffort(v === '' ? null : v)
                }}
                aria-label="Thinking mode"
              >
                <option value="">Off</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>

            {/* Profiler: test connection and stream metrics */}
            <div className="space-y-2">
              <SectionTitle icon={<Activity size={15} className="text-zinc-400" />}>
                Profiler
              </SectionTitle>
              <p className="text-[10px] text-zinc-600 mb-2">
                Test the current model connection and measure time to first token, token speed, and thinking-stream support.
              </p>
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  type="button"
                  disabled={profilerLoading}
                  onClick={async () => {
                    setProfilerLoading(true)
                    setProfilerResult(null)
                    try {
                      const result = await testLlmProfiler()
                      setProfilerResult(result)
                    } catch (e) {
                      setProfilerResult({
                        ok: false,
                        error: e instanceof Error ? e.message : String(e),
                        time_to_first_token_ms: null,
                        tokens_per_second: null,
                        has_thinking_stream: false,
                      })
                    } finally {
                      setProfilerLoading(false)
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 text-zinc-200 text-xs font-medium transition-colors"
                >
                  {profilerLoading ? <Loader2 size={12} className="animate-spin" /> : <Activity size={12} />}
                  Test connection
                </button>
                {profilerResult && (
                  <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2.5 text-xs space-y-1.5 min-w-[200px]">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-zinc-400">Connection</span>
                      <span
                        className={
                          profilerResult.ok
                            ? 'text-emerald-400'
                            : 'text-red-400'
                        }
                      >
                        {profilerResult.ok ? 'OK' : 'Error'}
                      </span>
                    </div>
                    {!profilerResult.ok && profilerResult.error && (
                      <p className="text-red-400 truncate" title={profilerResult.error}>
                        {profilerResult.error}
                      </p>
                    )}
                    {profilerResult.ok && (
                      <>
                        <div className="flex justify-between gap-4">
                          <span className="text-zinc-500">Time to first token</span>
                          <span className="text-zinc-300 font-mono">
                            {profilerResult.time_to_first_token_ms != null
                              ? `${profilerResult.time_to_first_token_ms} ms`
                              : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-zinc-500">Tokens/sec</span>
                          <span className="text-zinc-300 font-mono">
                            {profilerResult.tokens_per_second != null
                              ? profilerResult.tokens_per_second.toFixed(1)
                              : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-zinc-500">Thinking stream</span>
                          <span className="text-zinc-300">
                            {profilerResult.has_thinking_stream ? 'Supported' : 'No'}
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>

            <Field
              label="Workspace"
              hint="Folder the agent operates in. Changes take effect on next server restart."
            >
              <div className="relative">
                <input
                  className={`${inputCls} pr-8`}
                  value={workspace}
                  onChange={(e) => setWorkspace(e.target.value)}
                  placeholder="~/projects/myapp"
                />
                <FolderOpen
                  size={14}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none"
                />
              </div>
              {config?.workspace && config.workspace !== workspace && (
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Current resolved path: <span className="font-mono text-zinc-400">{config.workspace}</span>
                </p>
              )}
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Max tokens">
                <input
                  type="number"
                  className={inputCls}
                  value={maxTokens}
                  min={1}
                  max={131072}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                />
              </Field>
              <Field label={`Temperature: ${temperature.toFixed(2)}`}>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="w-full accent-blue-500 mt-2"
                />
              </Field>
              <Field label="Max tool iterations" hint="Max LLM loop iterations per message">
                <input
                  type="number"
                  className={inputCls}
                  value={maxToolIter}
                  min={1}
                  max={100}
                  onChange={(e) => setMaxToolIter(Number(e.target.value))}
                />
              </Field>
              <Field label="Memory window" hint="Recent messages kept in context">
                <input
                  type="number"
                  className={inputCls}
                  value={memoryWindow}
                  min={5}
                  max={500}
                  onChange={(e) => setMemoryWindow(Number(e.target.value))}
                />
              </Field>
            </div>
          </div>
        </section>

        {/* Provider API keys */}
        <section>
          <SectionTitle icon={<Key size={15} className="text-zinc-400" />}>
            Provider API keys
          </SectionTitle>
          <p className="text-[10px] text-zinc-600 mb-4">
            Set API keys for each provider below. Keys are saved to config when you click Save—
            no need to edit any file. Leave a key blank to keep the current one; enter a new value to
            replace.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(availableProviders.length > 0 ? availableProviders : FALLBACK_PROVIDER_LIST).map(
              (prov) => {
                const id = prov.id
                const p = config?.providers?.[id] as
                  | { api_key_set?: boolean; api_base?: string | null }
                  | undefined
                const keySet = p?.api_key_set ?? false
                const displayName = prov.display_name || id
                return (
                  <div
                    key={id}
                    className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 space-y-2"
                  >
                    <label className="block text-xs font-medium text-zinc-400">
                      {displayName}
                      {keySet ? (
                        <span className="ml-2 text-emerald-500/90 font-normal">Key set</span>
                      ) : (
                        <span className="ml-2 text-zinc-500 font-normal">(no key set)</span>
                      )}
                    </label>
                    <div className="grid gap-2">
                      <input
                        type="password"
                        className={inputCls}
                        value={providerKeys[id] ?? ''}
                        onChange={(e) =>
                          setProviderKeys((prev) => ({ ...prev, [id]: e.target.value }))
                        }
                        placeholder={
                          keySet ? '•••••••• (enter new value to change)' : 'Enter API key'
                        }
                        autoComplete="off"
                      />
                      {(providerApiBases[id] ?? '') !== '' && !expandedApiBase[id] ? (
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-zinc-500">Base URL set</span>
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedApiBase((prev) => ({ ...prev, [id]: true }))
                            }
                            className="text-[10px] text-zinc-500 hover:text-zinc-400 transition-colors"
                          >
                            Edit
                          </button>
                        </div>
                      ) : expandedApiBase[id] ? (
                        <div className="space-y-1">
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedApiBase((prev) => ({ ...prev, [id]: false }))
                            }
                            className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-400 transition-colors"
                          >
                            <ChevronDown size={10} />
                            Hide API base URL
                          </button>
                          <input
                            type="text"
                            className={inputCls}
                            value={providerApiBases[id] ?? ''}
                            onChange={(e) =>
                              setProviderApiBases((prev) => ({ ...prev, [id]: e.target.value }))
                            }
                            placeholder="Optional: API base URL"
                            autoComplete="off"
                          />
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedApiBase((prev) => ({ ...prev, [id]: true }))
                          }
                          className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-400 transition-colors"
                        >
                          <ChevronRight size={10} />
                          Override API base URL
                        </button>
                      )}
                    </div>
                  </div>
                )
              },
            )}
          </div>
        </section>

        {/* Tools */}
        <section>
          <SectionTitle icon={<Wrench size={15} className="text-zinc-400" />}>Tools</SectionTitle>
          <div className="space-y-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={restrictToWorkspace}
                onChange={(e) => setRestrictToWorkspace(e.target.checked)}
                className="w-4 h-4 rounded accent-blue-500"
              />
              <div>
                <span className="text-sm text-zinc-300">Restrict to workspace</span>
                <p className="text-[10px] text-zinc-600">
                  Limit file system and shell tools to the workspace directory.
                </p>
              </div>
            </label>
            <Field label="Shell exec timeout (seconds)">
              <input
                type="number"
                className={inputCls}
                value={execTimeout}
                min={5}
                max={600}
                onChange={(e) => setExecTimeout(Number(e.target.value))}
              />
            </Field>
            <Field
              label="PATH append (for shell/exec)"
              hint="Optional path suffix for subprocess PATH (e.g. /opt/bin)."
            >
              <input
                type="text"
                className={inputCls}
                value={pathAppend}
                onChange={(e) => setPathAppend(e.target.value)}
                placeholder=""
              />
            </Field>
            <Field
              label="Brave Search API key"
              hint={
                config?.tools.web_search_api_key_set
                  ? 'A key is currently set. Enter a new value to replace it.'
                  : 'No key set. Get one at brave.com/search/api'
              }
            >
              <input
                type="password"
                className={inputCls}
                value={webSearchKey}
                onChange={(e) => setWebSearchKey(e.target.value)}
                placeholder={config?.tools.web_search_api_key_set ? '••••••••' : 'BSA…'}
              />
            </Field>
          </div>
        </section>

        {/* De-duplicator (knowledge graph) */}
        <section>
          <SectionTitle icon={<Layers size={15} className="text-zinc-400" />}>
            De-duplicator (knowledge graph)
          </SectionTitle>
          <p className="text-xs text-zinc-600 mb-4">
            Merges similar nodes in the knowledge graph on a schedule. Set the run time with the
            <strong className="text-zinc-400"> Cron schedule</strong> field below. When enabled, a task appears under
            <strong className="text-zinc-400"> Scheduled tasks</strong> where you can pause, resume, or edit the schedule.
          </p>
          <div className="space-y-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={kgDedupEnabled}
                onChange={(e) => setKgDedupEnabled(e.target.checked)}
                className="w-4 h-4 rounded accent-blue-500"
              />
              <div>
                <span className="text-sm text-zinc-300">Enable de-duplicator</span>
                <p className="text-[10px] text-zinc-600">
                  Run knowledge graph dedup at the time set in Cron schedule below.
                </p>
              </div>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field
                label="Cron schedule (run time)"
                hint="e.g. 0 3 * * * = daily at 3:00"
              >
                <input
                  type="text"
                  className={`${inputCls} font-mono`}
                  value={kgDedupSchedule}
                  onChange={(e) => setKgDedupSchedule(e.target.value)}
                  placeholder="0 3 * * *"
                />
              </Field>
              <Field
                label="Dedup LLM model"
                hint="Optional. Model for merge decisions (e.g. gpt-4o-mini). Leave empty to use memory model."
              >
                <input
                  type="text"
                  className={inputCls}
                  value={kgDedupModel}
                  onChange={(e) => setKgDedupModel(e.target.value)}
                  placeholder="Use memory model"
                />
              </Field>
              <Field label="LLM batch size" hint="Groups per LLM call (e.g. 20)">
                <input
                  type="number"
                  className={inputCls}
                  value={kgDedupLlmBatchSize}
                  min={1}
                  max={200}
                  onChange={(e) => setKgDedupLlmBatchSize(Math.max(1, Number(e.target.value)))}
                />
              </Field>
              <Field label="Embedding batch size" hint="Batch size for embedding triples">
                <input
                  type="number"
                  className={inputCls}
                  value={kgDedupBatchSize}
                  min={1}
                  max={2048}
                  onChange={(e) => setKgDedupBatchSize(Math.max(1, Number(e.target.value)))}
                />
              </Field>
            </div>
          </div>
        </section>

        {/* Tool Approval Policy */}
        <section>
          <SectionTitle icon={<ShieldCheck size={15} className="text-zinc-400" />}>
            Tool Approval Policy
          </SectionTitle>
          <p className="text-xs text-zinc-600 mb-4">
            Control which tools the agent can run automatically and which require your approval before
            executing. MCP tools added via servers default to <strong className="text-yellow-600">Ask</strong>.
            For desktop automation, set <strong className="text-emerald-600">Screenshot</strong> (and optionally
            Move mouse, Mouse click, Keyboard type) to <strong className="text-emerald-600">Auto</strong> so the bot
            can run without you clicking Approve and disrupting the screen.
          </p>
          <div className="flex items-center gap-3 mb-4 p-3 rounded-lg bg-zinc-900 border border-zinc-800">
            <input
              type="checkbox"
              id="cua-auto-approve"
              checked={cuaAutoApprove}
              onChange={(e) => setCuaAutoApprove(e.target.checked)}
              className="rounded border-zinc-600 bg-zinc-800 text-emerald-600 focus:ring-emerald-500"
            />
            <label htmlFor="cua-auto-approve" className="text-sm text-zinc-300 cursor-pointer select-none">
              <strong>Auto-approve CUA / desktop activity</strong>
            </label>
          </div>
          <p className="text-[10px] text-zinc-500 mb-3 -mt-2">
            When on: screenshot, move mouse, mouse click, mouse position, and keyboard type run without prompt; inline Python
            is validated by a fast Groq model and auto-approved only if it uses pyautogui safely (no exec, network, etc.).
            The run_python safety guard is also skipped so pyautogui scripts run without being blocked. Requires a <strong>Groq</strong> API key in Providers for run_python validation. Saving applies immediately (no restart).
          </p>
          <ToolPolicyEditor policy={toolPolicy} onChange={setToolPolicy} />
        </section>

        {/* MCP Servers */}
        <section>
          <SectionTitle icon={<Server size={15} className="text-zinc-400" />}>
            MCP Servers
          </SectionTitle>
          <p className="text-xs text-zinc-600 mb-2">
            Model Context Protocol servers extend nanobot with additional tools.{' '}
            <a
              href="https://modelcontextprotocol.io/examples"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:underline inline-flex items-center gap-0.5"
            >
              Browse examples <ExternalLink size={10} />
            </a>
          </p>
          <p className="text-[10px] text-zinc-600 mb-4">
            Each server shows connection status, config, and optional skills & rules. Save to apply changes.
          </p>
          {config && (() => {
            const allServerKeys = [
              ...new Set([
                ...Object.keys(config.mcp_servers || {}),
                ...Object.keys(mcpPatch).filter((k) => mcpPatch[k] !== null),
              ]),
            ].filter((k) => mcpPatch[k] !== null)
            const usedByWorkflows =
              Object.keys(mcpStatusPerServer).length > 0
                ? Object.fromEntries(
                    Object.entries(mcpStatusPerServer)
                      .filter(
                        (entry): entry is [string, McpServerStatus] =>
                          entry[1] !== null && entry[1] !== 'loading'
                      )
                      .map(([k, v]) => [k, v.used_by ?? []])
                  )
                : undefined
            return (
              <div className="space-y-4">
                <ul className="space-y-3">
                  {allServerKeys.map((key) => {
                    const statusOrLoading = mcpStatusPerServer[key]
                    const status =
                      statusOrLoading === 'loading' || statusOrLoading === null
                        ? undefined
                        : statusOrLoading
                    const statusLoading =
                      statusOrLoading === 'loading' || statusOrLoading === undefined
                    const effective = effectiveMcpConfig(config.mcp_servers?.[key], mcpPatch[key] ?? undefined)
                    return (
                      <li key={key}>
                        <McpServerCard
                          serverKey={key}
                          serverConfig={config.mcp_servers?.[key]}
                          status={status}
                          statusLoading={statusLoading}
                          statusError={statusOrLoading === null}
                          configSlot={
                            <MCPConfigForm
                              serverKey={key}
                              effective={effective}
                              onChange={(patch) =>
                                setMcpPatch((prev) => ({ ...prev, [key]: patch }))
                              }
                            />
                          }
                          onDelete={() => {
                            const workflows = usedByWorkflows?.[key]
                            if (workflows && workflows.length > 0) {
                              if (
                                !window.confirm(
                                  `This server is used by ${workflows.length} workflow(s): ${workflows.join(', ')}. Remove anyway?`
                                )
                              )
                                return
                            }
                            setMcpPatch((prev) => ({ ...prev, [key]: null }))
                          }}
                          toolPolicy={toolPolicy}
                          onToolPolicyChange={(fullName, value) =>
                            setToolPolicy((prev) => ({ ...prev, [fullName]: value }))
                          }
                          guidanceValue={mcpGuidance[key] ?? ''}
                          onGuidanceChange={(value) =>
                            setMcpGuidance((prev) => ({ ...prev, [key]: value }))
                          }
                          onTestConnection={async () => {
                            setMcpTestingKey(key)
                            try {
                              await testMcpConnection(key)
                              const next = await getMcpServerStatus(key)
                              setMcpStatusPerServer((p) => ({ ...p, [key]: next }))
                            } catch (e: unknown) {
                              const msg =
                                e && typeof e === 'object' && 'detail' in e
                                  ? String((e as { detail: unknown }).detail)
                                  : 'Test failed'
                              alert(msg)
                              const next = await getMcpServerStatus(key).catch(() => null)
                              setMcpStatusPerServer((p) => ({ ...p, [key]: next }))
                            } finally {
                              setMcpTestingKey(null)
                            }
                          }}
                          testing={mcpTestingKey === key}
                        />
                      </li>
                    )
                  })}
                </ul>
                <div className="flex gap-2">
                  <input
                    className={`${inputCls} flex-1`}
                    value={mcpNewKey}
                    onChange={(e) => setMcpNewKey(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addMcpServer()}
                    placeholder="New server name (e.g. filesystem)"
                  />
                  <button
                    type="button"
                    onClick={addMcpServer}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-xs transition-colors"
                  >
                    <Plus size={12} /> Add server
                  </button>
                </div>
              </div>
            )
          })()}
        </section>

        {/* About */}
        <section>
          <SectionTitle icon={<Info size={15} className="text-zinc-400" />}>About</SectionTitle>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-2 text-xs font-mono text-zinc-500">
            <div className="flex gap-4">
              <span className="text-zinc-600 w-28">Version</span>
              <span className="text-zinc-300">{config?.version}</span>
            </div>
            <div className="flex gap-4">
              <span className="text-zinc-600 w-28">Workspace path</span>
              <span className="text-zinc-300 break-all">{config?.workspace}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
