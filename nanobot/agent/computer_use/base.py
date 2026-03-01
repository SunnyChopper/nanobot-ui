"""Computer use provider interface and shared types (Action, ActionResponse)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict, runtime_checkable


class ActionSummary(TypedDict, total=False):
    """Action summary dict: required 'kind'; optional x, y, key, text, extra.
    Producers (e.g. tool's _action_summary) should set 'extra' for kinds that need it
    (e.g. drag_and_drop with destination_x, destination_y)."""
    kind: str
    x: int
    y: int
    key: str
    text: str
    extra: dict[str, Any]


@dataclass(frozen=True)
class Action:
    """A single UI action from the computer use model (click, type, scroll, key, wait, etc.)."""

    kind: str  # "click" | "type" | "scroll" | "key" | "wait" | ...
    # Kind-specific fields (use get() or getattr for optional fields)
    x: int | None = None
    y: int | None = None
    button: str | None = None  # left, right, middle
    text: str | None = None
    delta_x: int | None = None
    delta_y: int | None = None
    key: str | None = None
    duration_ms: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("Action.kind must be non-empty")


@dataclass
class ActionResponse:
    """Response from a computer use provider (model output for one turn)."""

    actions: list[Action] = field(default_factory=list)
    done: bool = False
    message: str | None = None
    requires_confirmation: bool = False
    """When use_conversation_history is True, provider sets this so the tool can pass it as history on the next request. List of Content-like items (user + model turns)."""
    contents_for_history: list[Any] = field(default_factory=list)


@runtime_checkable
class ComputerUseProvider(Protocol):
    """Protocol for computer use backends (Gemini 3 Flash, future Claude/OpenAI)."""

    def capture_screen(self) -> bytes:
        """Return raw PNG bytes of the current screen (or primary monitor)."""
        ...

    async def send_action_request(
        self,
        screenshot_bytes: bytes,
        task: str,
        history: list[dict[str, Any]] | None = None,
        step_index: int | None = None,
        step_limit: int | None = None,
        excluded_actions_this_run: list[str] | None = None,
        hints: list[str] | None = None,
        actions_taken_this_run: list[dict[str, Any]] | None = None,
        screen_unchanged_since_last: bool = False,
        same_action_repeated_count: int = 0,
        last_repeated_action_summary: dict[str, Any] | None = None,
        same_kind_streak: int = 0,
        same_kind_name: str | None = None,
        oscillating: bool = False,
    ) -> ActionResponse:
        """Send screenshot + task to the model; return structured actions and done flag.
        step_index: when > 1, provider may add step-aware instructions (do only next action; do not repeat).
        step_limit: max steps for this run; provider may add "Step N of M" to the prompt.
        excluded_actions_this_run: action names to exclude for this request (e.g. previously unsupported).
        hints: optional similar-past-run lines to prepend so the model can reuse strategies.
        actions_taken_this_run: list of action summaries already executed this run (kind, key, text, x, y, …).
        Provider should inject a short 'do not repeat' summary when non-empty so the model has internal run memory.
        screen_unchanged_since_last: when True, the screen hash did not change after the previous action; provider should tell the model to try a different action.
        same_action_repeated_count: when >= 2, the last N actions were identical; provider should add a stronger hint.
        last_repeated_action_summary: one action summary dict for the repeated action (so provider can format it in the hint).
        same_kind_streak: number of consecutive actions of the same kind (e.g. scroll_at); provider may add a hint when >= threshold.
        same_kind_name: the kind name for the streak (e.g. scroll_at).
        oscillating: when True, last actions alternate between two similar actions; provider may add a hint."""
        ...
