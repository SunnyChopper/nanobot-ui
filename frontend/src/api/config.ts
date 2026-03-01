/** Config and status API: status, channels, providers, models, config */

import { apiFetch } from './http'
import type {
  ChannelsResponse,
  ConfigPatch,
  ConfigResponse,
  LlmProfilerResult,
  ModelsResponse,
  ProvidersResponse,
  StatusResponse,
} from './types'

export function getStatus(): Promise<StatusResponse> {
  return apiFetch('/status')
}

export function getChannels(): Promise<ChannelsResponse> {
  return apiFetch('/channels')
}

export function getModels(): Promise<ModelsResponse> {
  return apiFetch('/models')
}

export function getProviders(): Promise<ProvidersResponse> {
  return apiFetch('/providers')
}

export function getConfig(): Promise<ConfigResponse> {
  return apiFetch('/config')
}

export function updateConfig(patch: ConfigPatch): Promise<{ status: string }> {
  return apiFetch('/config', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}

export function testLlmProfiler(): Promise<LlmProfilerResult> {
  return apiFetch('/llm/profiler', { method: 'POST' })
}
