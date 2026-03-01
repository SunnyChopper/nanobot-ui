---
name: add-backend-endpoint
description: Add a new REST endpoint to the nanobot server following routes → handlers → services. Use when adding an API route, new handler, or new service in server/.
---

# Add backend endpoint

Use this when adding a new REST endpoint or server-side behavior.

## 1. Add or reuse a handler

- **File**: `server/handlers/<domain>.py` (e.g. `sessions.py`, `memory.py`) or create a new module if the domain is new.
- **Handler**: Async function that takes `Request` and any path/query/body params. Get services from `request.app.state`, call them, return a Pydantic model or raise `HTTPException`.
- **Models**: Use or extend `server/models.py` for request/response shapes.

## 2. Register the route

- **File**: `server/routes.py`.
- Add the route and point it at the handler (e.g. `@router.get("/something")` → `get_something` from the handler module). No business logic in routes.

## 3. Service (if needed)

- **Interface**: In `server/services/` define a protocol or ABC (e.g. `SomeService`) if handlers should depend on an abstraction.
- **Implementation**: Name by backing, e.g. `NanobotSessionService`, **not** `SessionServiceImpl`. Put it in a module under `server/services/`, wire it in `server/app.py` (e.g. `app.state.some_service = NanobotSomeService(...)`).

## 4. Re-export

- If you add a new service module, export from `server/services/__init__.py` so `app.py` can import cleanly.

## Checklist

- [ ] Handler in `handlers/<domain>.py`, HTTP-only
- [ ] Route registered in `routes.py`
- [ ] Service (if any) named like `NanobotXxxService`, wired in `app.py`
- [ ] No business logic in `routes.py`
