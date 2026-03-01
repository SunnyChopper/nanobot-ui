---
name: add-frontend-api-and-ui
description: Add a new API client function or UI component in the frontend following domain API and Atomic Design. Use when adding endpoints to the client, new types, or new components in frontend/src.
---

# Add frontend API and UI

Use this when adding new API calls or UI in the nanobot frontend.

## API (frontend/src/api/)

1. **Domain**: Put the function in the right domain module (e.g. `getStatus` → `config.ts`, memory calls → `memory.ts`, sessions → `sessions.ts`). Do **not** re-export from the wrong module (e.g. `getStatus` belongs in `config.ts`, not `memory.ts`).
2. **Implementation**: Use `apiFetch` from `./http`; use types from `./types` or `./types/<domain>.ts`.
3. **Barrel**: Re-export the new function (and types if public) from `client.ts` so existing `import { … } from '../api/client'` keep working.

## Types (frontend/src/api/)

- Add or extend types in `api/types.ts`. For larger domains, use `api/types/<name>.ts` and re-export from `api/types.ts` or `api/types/index.ts`.

## Components (frontend/src/components/)

- **Atoms**: Small, presentational (e.g. `StatusBar`, button, label). No or minimal state.
- **Molecules**: Compositions of atoms (e.g. `ToolCallCard`, `MarkdownRenderer`).
- **Organisms**: Larger blocks (e.g. `MessageBubble`, `ThreadList`, `KgDedupRunPanel`). Compose molecules/atoms.
- **Pages**: Top-level route views (e.g. `ChatPage`). Own state and data fetching; compose organisms.

Put new components in the **smallest layer** that fits. Root-level re-exports (e.g. `MessageBubble.tsx` → `export { MessageBubble } from './organisms/MessageBubble'`) keep existing imports working.

## Checklist

- [ ] New API function in correct domain module; re-exported from `client.ts`
- [ ] Types in `api/types.ts` or `api/types/<domain>.ts`
- [ ] New component in correct Atomic layer; re-export from root or index if needed for existing imports
