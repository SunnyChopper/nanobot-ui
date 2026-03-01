"""
Constants for the streaming agent loop (event types, block types, policy values).

Used by server/services/streaming.py so string literals are centralized and typo-safe.
"""

# ---------------------------------------------------------------------------
# Event types (payloads sent to on_event / event_sink)
# ---------------------------------------------------------------------------
EVENT_TOKEN = "token"
EVENT_THINKING = "thinking"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_TOOL_PROGRESS = "tool_progress"
EVENT_TOOL_APPROVAL_REQUEST = "tool_approval_request"
EVENT_ERROR = "error"

# ---------------------------------------------------------------------------
# Block types (for collected_blocks)
# ---------------------------------------------------------------------------
BLOCK_THINKING = "thinking"
BLOCK_TOOL_CALL = "tool_call"
BLOCK_CONTENT = "content"
BLOCK_APPROVAL_REQUEST = "approval_request"

# ---------------------------------------------------------------------------
# Policy values (tool_policy)
# ---------------------------------------------------------------------------
POLICY_AUTO = "auto"
POLICY_ASK = "ask"
POLICY_DENY = "deny"

# ---------------------------------------------------------------------------
# Dict keys used in event/block payloads
# ---------------------------------------------------------------------------
KEY_TYPE = "type"
KEY_CONTENT = "content"
KEY_TEXT = "text"
KEY_NAME = "name"
KEY_ARGUMENTS = "arguments"
KEY_TOOL_ID = "tool_id"
KEY_RESULT = "result"
KEY_TITLE = "title"
KEY_RESOLVED = "resolved"
KEY_TOOL_CALL = "toolCall"
KEY_REQUEST = "request"
KEY_DENIED = "denied"

# ---------------------------------------------------------------------------
# Other literals
# ---------------------------------------------------------------------------
TOOL_CHUNK_ID_PREFIX = "tc_"
TOOL_CALL_TYPE_FUNCTION = "function"
REFLECT_USER_MESSAGE = "Reflect on the results and decide next steps."
CIRCUIT_BREAKER_MESSAGE = (
    "Service temporarily unavailable (circuit breaker open). Try again later."
)
