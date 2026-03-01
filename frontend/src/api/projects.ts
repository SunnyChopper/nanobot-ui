/** Projects API (context switcher) */

import { apiFetch } from './http'

export interface ProjectItem {
  name: string
  path: string
}

export function getProjects(): Promise<ProjectItem[]> {
  return apiFetch('/projects')
}
