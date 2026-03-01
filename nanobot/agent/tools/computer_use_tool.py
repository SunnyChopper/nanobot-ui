"""
Computer use tool: one agent tool that runs an internal agentic loop.

Capture screen → provider (e.g. Gemini 3 Flash with computer_use) → parse actions → execute via pyautogui → repeat.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.agent.computer_use.base import Action, ComputerUseProvider
from nanobot.agent.computer_use.executor import ActionExecutor
from nanobot.agent.computer_use.formatting import format_action, format_action_list
from nanobot.agent.computer_use.repetition import (
    detect_oscillation,
    last_repeated_action_count,
    last_same_kind_streak,
)
from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.computer_use.outcome_store import ComputerUseOutcomeStore


def _action_summary(action: Action) -> dict[str, Any]:
    """Minimal dict for episode logging and hints. Includes extra for kinds that need it (e.g. drag_and_drop)."""
    d: dict[str, Any] = {"kind": action.kind}
    if action.x is not None:
        d["x"] = action.x
    if action.y is not None:
        d["y"] = action.y
    if action.key:
        d["key"] = action.key
    if action.text:
        d["text"] = (action.text[:50] + "…") if len(action.text) > 50 else action.text
    if action.kind == "drag_and_drop" and action.extra:
        dx = action.extra.get("destination_x")
        dy = action.extra.get("destination_y")
        if dx is not None and dy is not None:
            d["extra"] = {"destination_x": dx, "destination_y": dy}
    return d


class ComputerUseTool(Tool):
    """Single tool that runs the computer use loop (capture → model → execute) until done or step limit."""

    def __init__(
        self,
        provider: ComputerUseProvider,
        executor: ActionExecutor,
        max_steps: int = 50,
        post_action_delay_ms: int = 0,
        use_conversation_history: bool = False,
        *,
        workspace: Path | None = None,
        outcome_store: ComputerUseOutcomeStore | None = None,
        use_internal_run_memory: bool = True,
        repetition_same_kind_exit_threshold: int = 5,
        repetition_same_kind_hint_threshold: int = 4,
        repetition_oscillation_window: int = 0,
    ):
        self._provider = provider
        self._executor = executor
        self._max_steps = max(1, max_steps)
        self._post_action_delay_ms = max(0, post_action_delay_ms)
        self._use_conversation_history = use_conversation_history
        self._workspace = workspace
        self._outcome_store = outcome_store
        self._use_internal_run_memory = use_internal_run_memory
        self._repetition_same_kind_exit = max(1, repetition_same_kind_exit_threshold)
        self._repetition_same_kind_hint = max(1, repetition_same_kind_hint_threshold)
        self._repetition_oscillation_window = max(0, repetition_oscillation_window)

    @property
    def name(self) -> str:
        return "computer_use"

    @property
    def description(self) -> str:
        return (
            "Perform desktop UI actions (click, type, scroll, key) to accomplish a task on screen. "
            "Each call must be one atomic task (one action or one short, focused sequence). "
            "One call = one atomic task; use multiple calls for multi-step workflows. "
            "The tool captures the screen, asks the model for actions, executes them, and repeats until the task is done or step limit is reached."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Single natural-language action to do on the screen (e.g. 'click the Start button', 'navigate to example.com', 'type Hello in the text box'). Do not pass a numbered list or multiple different steps in one task; use separate tool calls for each step.",
                },
                "max_steps": {
                    "type": "integer",
                    "description": "Optional cap on steps for this (atomic) task. If omitted or <= 0, uses the config default.",
                },
            },
            "required": ["task"],
        }

    async def execute(self, task: str, max_steps: int | None = None, **kwargs: Any) -> str:
        if not (task and str(task).strip()):
            return "Error: task is required and must be non-empty."

        progress_cb = kwargs.pop("__progress_callback", None)
        effective_max = self._max_steps
        if max_steps is not None and max_steps > 0:
            effective_max = min(max_steps, self._max_steps)

        steps = 0
        conversation_contents: list[Any] = []  # provider-specific (e.g. SDK Content); only used when use_conversation_history
        unsupported_kinds: set[str] = set()
        actions_executed: list[dict[str, Any]] = []  # for outcome_store
        previous_screenshot_hash: str | None = None
        screenshot_hash_before_previous: str | None = None
        first_screenshot_hash: str | None = None
        self._executor.clear_log()

        result_message = ""
        outcome = "error"

        while steps < effective_max:
            steps += 1
            if progress_cb:
                try:
                    await progress_cb(f"Step {steps}/{effective_max}")
                except Exception as e:
                    logger.debug("Computer use progress callback failed: {}", e)

            try:
                screenshot_bytes = self._provider.capture_screen()
            except Exception as e:
                logger.warning("Computer use capture failed: {}", e)
                result_message = f"Error: failed to capture screen: {e}"
                outcome = "error"
                break

            if not screenshot_bytes or len(screenshot_bytes) < 100:
                logger.warning("Computer use: capture returned no or invalid screenshot ({} bytes)", len(screenshot_bytes or 0))
                result_message = "Error: screen capture returned no image. Ensure a display is available and pyautogui can capture it."
                outcome = "error"
                break

            current_screenshot_hash = hashlib.sha256(screenshot_bytes).hexdigest()[:16]
            if steps == 1:
                first_screenshot_hash = current_screenshot_hash
            screen_unchanged_since_last = (
                previous_screenshot_hash is not None and current_screenshot_hash == previous_screenshot_hash
            )

            # Safety exit: same action 3+ times with no screen change
            repeated_count, last_repeated_summary = last_repeated_action_count(actions_executed)
            if (
                steps > 1
                and screen_unchanged_since_last
                and repeated_count >= 3
                and last_repeated_summary is not None
            ):
                result_message = (
                    "Stopped: same action repeated with no screen change; task may need a different approach. "
                    "You can call computer_use again with a follow-up task."
                )
                outcome = "step_limit"
                break

            # Safety exit: same kind (e.g. scroll_at) many times with screen unchanged for last 2 steps
            same_kind_count, same_kind_name = last_same_kind_streak(actions_executed)
            screen_unchanged_for_two_steps = (
                previous_screenshot_hash is not None
                and screenshot_hash_before_previous is not None
                and current_screenshot_hash == previous_screenshot_hash
                and previous_screenshot_hash == screenshot_hash_before_previous
            )
            if (
                steps >= 3
                and same_kind_count >= self._repetition_same_kind_exit
                and screen_unchanged_for_two_steps
                and same_kind_name
            ):
                result_message = (
                    f"Stopped: many consecutive {same_kind_name} actions with no visible progress. "
                    "Try a different approach or call computer_use again with a follow-up task."
                )
                outcome = "step_limit"
                break

            logger.debug("Computer use step {}: sending screenshot ({} bytes) with task", steps, len(screenshot_bytes))
            try:
                history_for_request = (
                    conversation_contents
                    if (self._use_conversation_history and conversation_contents)
                    else None
                )
                hints: list[str] | None = None
                if self._outcome_store and steps == 1:
                    hints = self._outcome_store.get_hints_for_task(task)
                    cached = self._outcome_store.get_cached_actions_for_screen(task, current_screenshot_hash)
                    if cached is not None:
                        strong_hint = "Exact screen match: last time we succeeded with: " + format_action_list(cached, max_items=10) + ". Prefer this sequence."
                        hints = [strong_hint] + (hints or [])
                response = await self._provider.send_action_request(
                    screenshot_bytes,
                    task=task,
                    history=history_for_request,
                    step_index=steps,
                    step_limit=effective_max,
                    excluded_actions_this_run=list(unsupported_kinds) if unsupported_kinds else None,
                    hints=hints if hints else None,
                    actions_taken_this_run=(
                        list(actions_executed) if (self._use_internal_run_memory and actions_executed) else None
                    ),
                    screen_unchanged_since_last=screen_unchanged_since_last,
                    same_action_repeated_count=repeated_count if repeated_count >= 2 else 0,
                    last_repeated_action_summary=last_repeated_summary if repeated_count >= 2 else None,
                    same_kind_streak=same_kind_count if same_kind_count >= self._repetition_same_kind_hint else 0,
                    same_kind_name=same_kind_name if same_kind_count >= self._repetition_same_kind_hint else None,
                    oscillating=(
                        detect_oscillation(actions_executed, window=self._repetition_oscillation_window)
                        if self._repetition_oscillation_window >= 4
                        else False
                    ),
                )
            except Exception as e:
                logger.warning("Computer use provider request failed: {}", e)
                result_message = f"Error: computer use request failed: {e}"
                outcome = "error"
                break

            if response.done and not response.actions:
                if self._executor.dry_run:
                    result_message = self._executor.get_dry_run_summary()
                else:
                    result_message = "Task completed."
                outcome = "completed"
                break

            action_strs = [format_action(a, style="log") for a in response.actions]
            logger.info(
                "Computer use step {}: model returned {} action(s): {}",
                steps,
                len(response.actions),
                ", ".join(action_strs),
            )

            for action in response.actions:
                executed, unsupported = await self._executor.execute(
                    action,
                    requires_confirmation=response.requires_confirmation,
                )
                if executed and not self._executor.dry_run:
                    actions_executed.append(_action_summary(action))
                if unsupported:
                    logger.debug(
                        "Computer use: unsupported tool event: {} (excluded for subsequent steps)",
                        unsupported,
                    )
                    unsupported_kinds.add(unsupported)

            if self._use_conversation_history and response.contents_for_history:
                conversation_contents[:] = response.contents_for_history

            if self._post_action_delay_ms > 0:
                await asyncio.sleep(self._post_action_delay_ms / 1000.0)

            screenshot_hash_before_previous = previous_screenshot_hash
            previous_screenshot_hash = current_screenshot_hash

            if response.done:
                if self._executor.dry_run:
                    result_message = self._executor.get_dry_run_summary()
                else:
                    result_message = "Task completed."
                outcome = "completed"
                break

        if not result_message:
            if self._executor.dry_run:
                result_message = self._executor.get_dry_run_summary()
            else:
                result_message = (
                    f"Step limit ({effective_max}) reached; task may be incomplete. "
                    "You can call computer_use again with a follow-up task."
                )
            outcome = "step_limit"

        if self._outcome_store:
            try:
                self._outcome_store.append_episode(
                    task=task.strip(),
                    steps_used=steps,
                    outcome=outcome,
                    actions_summary=actions_executed,
                    screenshot_hash=first_screenshot_hash,
                )
            except Exception as e:
                logger.debug("Computer use outcome store append failed: {}", e)

        return result_message
