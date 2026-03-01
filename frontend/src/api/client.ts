/**
 * REST API client for the nanobot server.
 *
 * Barrel: re-exports from domain modules. All paths are relative /api/*
 * (dev: Vite proxy, prod: same origin).
 */

export { BASE, apiFetch } from './http'
export {
  getSessions,
  getSession,
  deleteSession,
  renameSession,
  retrySession,
  editSessionMessage,
  newSession,
  branchSession,
  setSessionProject,
} from './sessions'
export {
  getAllowlist,
  addAllowlistEntry,
  removeAllowlistEntry,
} from './allowlist'
export {
  getMemory,
  putMemoryLongTerm,
  putMemoryHistory,
  appendMemoryHistory,
  verifyBullet,
  scanIrrelevantHistory,
  removeHistoryEntries,
  getMemoryChunks,
  getMemoryChunk,
  updateMemoryChunk,
  deleteMemoryChunks,
} from './memory'
export {
  getKnowledgeTriples,
  getKnowledgeTriplesStats,
  deleteKnowledgeTriples,
  getKnowledgeRagChunks,
  getKnowledgeRagSources,
  deleteKnowledgeRagChunks,
} from './knowledge'
export {
  getStatus,
  getChannels,
  getModels,
  getProviders,
  getConfig,
  updateConfig,
  testLlmProfiler,
} from './config'
export {
  getCronJobs,
  createCronJob,
  deleteCronJob,
  updateCronJobEnabled,
  updateCronJobSchedule,
  runCronJob,
} from './cron'
export {
  getMcpStatus,
  getMcpServerStatus,
  testMcpConnection,
  invokeMcpTool,
  type McpStatusResponse,
  type McpServerStatus,
  type McpToolInfo,
  type InvokeMcpToolResponse,
} from './mcp'
export {
  getWorkflows,
  getWorkflow,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  runWorkflow,
  listWorkflowRuns,
  getWorkflowRun,
  type WorkflowListItem,
  type WorkflowDefinition,
  type WorkflowRun,
  type WorkflowRunStep,
  type WorkflowRunErrorDetail,
} from './workflows'
export { uploadAttachment } from './media'
export { getProjects, type ProjectItem } from './projects'
export {
  startKgDedup,
  streamKgDedupProgress,
  listKgDedupAudits,
  getKgDedupAudit,
  restoreKgDedupTriple,
} from './kg_dedup'
