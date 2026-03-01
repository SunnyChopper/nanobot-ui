/**
 * Shared human-readable display names for tool names.
 * Used by ToolApprovalCard and ToolCallCard.
 */
export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  exec: 'Shell command',
  write_file: 'Write file',
  edit_file: 'Edit file',
  spawn: 'Spawn subagent',
  cron: 'Schedule task',
  read_file: 'Read file',
  list_dir: 'List directory',
  web_search: 'Web search',
  web_fetch: 'Fetch URL',
  message: 'Send message',
  system_stats: 'System stats',
  semantic_search: 'Semantic search',
  rag_ingest: 'RAG ingest',
  mouse_move: 'Move mouse',
  mouse_click: 'Click',
  mouse_position: 'Mouse position',
  keyboard_type: 'Type',
  screenshot: 'Screenshot',
  screenshot_region: 'Screenshot region',
  locate_on_screen: 'Locate image',
  click_image: 'Click image',
  get_foreground_window: 'Foreground window',
  launch_app: 'Launch app',
}

export function getToolDisplayName(name: string): string {
  return TOOL_DISPLAY_NAMES[name] ?? name
}
