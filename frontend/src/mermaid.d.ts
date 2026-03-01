/**
 * Type declaration for mermaid (dynamic import in MarkdownRenderer).
 * Mermaid v11 render API: mermaid.render(id, code) returns Promise<{ svg: string; bindFunctions?: (element: Element) => void }>.
 */
declare module 'mermaid' {
  interface MermaidConfig {
    startOnLoad?: boolean
    theme?: string
  }

  interface RenderResult {
    svg: string
    bindFunctions?: (element: Element) => void
  }

  interface MermaidAPI {
    initialize(config: MermaidConfig): void
    render(id: string, code: string): Promise<RenderResult>
  }

  const mermaid: MermaidAPI
  export default mermaid
}
