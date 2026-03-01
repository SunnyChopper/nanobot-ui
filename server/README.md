# nanobot web server

A FastAPI web server that wraps the `nanobot` package to expose a REST API
and WebSocket interface for the React frontend.

## Architecture

All code in `server/` imports from nanobot's public package API.
**Zero nanobot source files are modified.**

```
server/
  __main__.py     Entry point (python -m server)
  bootstrap.py    Composes nanobot classes (mirrors gateway command)
  app.py          FastAPI application factory + lifespan
  routes.py       REST endpoints (/api/*)
  websocket.py    WebSocket handler (/ws/chat)
  services/streaming.py  Streaming agent loop (litellm stream=True)
  models.py              Pydantic response models
  requirements.txt  fastapi + uvicorn
```

## Quick start

```powershell
# 1. Activate the repo venv
.\venv\Scripts\Activate.ps1

# 2. Install server dependencies (nanobot itself is already installed in the venv)
#    This includes chromadb + sentence-transformers for memory sleep and RAG.
pip install -r server\requirements.txt

# 3. Run the server (port from ~/.nanobot/config.json, default 18790)
python -m server
```

## API endpoints

| Method    | Path                              | Description                    |
|-----------|-----------------------------------|--------------------------------|
| GET       | `/api/sessions`                   | List all chat sessions         |
| GET       | `/api/sessions/{key}`             | Full session with messages     |
| DELETE    | `/api/sessions/{key}`             | Clear session messages         |
| POST      | `/api/sessions/{key}/new`         | Start new conversation         |
| GET       | `/api/status`                     | Backend health + config        |
| GET       | `/api/channels`                   | Channel status                 |
| WebSocket | `/ws/chat`                        | Bidirectional streaming chat   |

## WebSocket protocol

**Client → Server:**
```json
{"type": "session_init", "session_id": "<uuid>"}
{"type": "message",      "content": "hello",  "session_id": "<uuid>"}
{"type": "new_session",  "session_id": "<uuid>"}
{"type": "ping"}
```

**Server → Client:**
```json
{"type": "session_ready",    "session_id": "..."}
{"type": "token",            "content": "...", "session_id": "..."}
{"type": "thinking",         "content": "..."}
{"type": "tool_call",        "name": "...", "arguments": {...}, "session_id": "..."}
{"type": "tool_approval_request", "name": "...", "arguments": {...}, "session_id": "...", "tool_id": "...", "title": "..."}
{"type": "tool_result",      "name": "...", "result": "...",    "session_id": "..."}
{"type": "message_complete", "content": "...", "session_id": "...", "tools_used": [...]}
{"type": "error",            "content": "...", "session_id": "..."}
{"type": "pong"}
```

- **thinking**: Reasoning tokens from models that support it (e.g. Claude extended thinking, DeepSeek-R1). The frontend shows them as collapsible blocks between tool calls. If the model does not send `reasoning_content` in the stream, no thinking blocks appear.
- **tool_approval_request**: Optional **title** is an LLM-generated short phrase describing the request (e.g. "Run shell command: bw status"). When absent, the frontend falls back to the preceding user message or a generic label.

## Adding new endpoints (runbook)

1. Add Pydantic models to `server/models.py`
2. Add route function to `server/routes.py`
3. Router is already included in `server/app.py` -- no change needed
4. Add TypeScript interface to `frontend/src/api/types.ts`
5. Add client function to `frontend/src/api/client.ts`
6. Wire to UI component or Zustand action
