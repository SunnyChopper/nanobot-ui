"""Computer use: screenshot → model (computer_use tool) → actions → execute via pyautogui."""

from nanobot.agent.computer_use.base import (
    Action,
    ActionResponse,
    ComputerUseProvider,
)
from nanobot.agent.computer_use.formatting import format_action, format_action_list
from nanobot.agent.computer_use.repetition import (
    DEFAULT_REPEAT_PIXEL_TOLERANCE,
    action_summaries_identical,
    action_summaries_nearly_identical,
    detect_oscillation,
    last_repeated_action_count,
    last_same_kind_streak,
)

__all__ = [
    "Action",
    "ActionResponse",
    "ComputerUseProvider",
    "DEFAULT_REPEAT_PIXEL_TOLERANCE",
    "action_summaries_identical",
    "action_summaries_nearly_identical",
    "detect_oscillation",
    "format_action",
    "format_action_list",
    "last_repeated_action_count",
    "last_same_kind_streak",
]
