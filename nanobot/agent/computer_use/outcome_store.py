"""Append-only outcome store for computer use self-improvement (logging + similar-task retrieval)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from nanobot.agent.computer_use.formatting import format_action_list

_DEFAULT_EPISODES_FILENAME = "memory/computer_use_episodes.jsonl"


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens for overlap scoring."""
    return set(re.findall(r"\w+", (text or "").lower()))


def _overlap_score(query_tokens: set[str], task_tokens: set[str]) -> float:
    """Jaccard-like score: |intersection| / |query| so current task drives relevance."""
    if not query_tokens:
        return 0.0
    inter = len(query_tokens & task_tokens)
    return inter / len(query_tokens)


class ComputerUseOutcomeStore:
    """Append-only JSONL store of computer use episodes; supports similar-task retrieval by token overlap."""

    def __init__(
        self,
        workspace: Path,
        *,
        path: str | Path | None = None,
        retrieval_max_hints: int = 3,
    ):
        self._workspace = Path(workspace)
        if path is None:
            path = _DEFAULT_EPISODES_FILENAME
        self._path = self._workspace / path if isinstance(path, str) else Path(path)
        self._retrieval_max_hints = max(0, retrieval_max_hints)

    def _ensure_file(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        return self._path

    def append_episode(
        self,
        task: str,
        steps_used: int,
        outcome: str,
        actions_summary: list[dict[str, Any]],
        *,
        screenshot_hash: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Append one episode (one line of JSON) to the log."""
        record = {
            "task": (task or "").strip(),
            "steps_used": steps_used,
            "outcome": outcome,
            "actions_summary": actions_summary,
            "timestamp": time.time(),
        }
        if screenshot_hash:
            record["screenshot_hash"] = screenshot_hash
        if session_id:
            record["session_id"] = session_id
        p = self._ensure_file()
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def find_similar(self, task: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Return past episodes most similar to task by token overlap (newest first in file = last N)."""
        cap = limit if limit is not None else self._retrieval_max_hints
        if cap <= 0:
            return []
        path = self._path
        if not path.exists():
            return []
        query_tokens = _tokenize(task)
        if not query_tokens:
            return []
        # Read last N lines to bound work (e.g. last 500 episodes)
        max_lines = 500
        lines: list[str] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    lines.append(line)
                    if len(lines) > max_lines:
                        lines.pop(0)
        except (OSError, UnicodeDecodeError):
            return []
        scored: list[tuple[float, dict[str, Any]]] = []
        for raw in reversed(lines):
            raw = raw.strip()
            if not raw:
                continue
            try:
                ep = json.loads(raw)
            except json.JSONDecodeError:
                continue
            task_text = (ep.get("task") or "")
            score = _overlap_score(query_tokens, _tokenize(task_text))
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: (-x[0], -(x[1].get("timestamp") or 0)))
        return [ep for _, ep in scored[:cap]]

    def _format_hint(self, ep: dict[str, Any]) -> str:
        """One-line hint for injection into the prompt."""
        task = (ep.get("task") or "").strip()[:80]
        steps = ep.get("steps_used", 0)
        outcome = ep.get("outcome", "unknown")
        actions = ep.get("actions_summary") or []
        actions_str = format_action_list(actions, max_items=6) if actions else "—"
        return f"Past task: \"{task}\"; steps: {steps}; outcome: {outcome}; actions: {actions_str}."

    def get_hints_for_task(self, task: str) -> list[str]:
        """Retrieve similar episodes and return formatted hint strings (capped by retrieval_max_hints)."""
        similar = self.find_similar(task, limit=self._retrieval_max_hints)
        return [self._format_hint(ep) for ep in similar]

    def get_cached_actions_for_screen(self, task: str, screenshot_hash: str) -> list[dict[str, Any]] | None:
        """Return actions_summary from the most recent successful episode with the same screenshot hash and similar task.
        Used to inject a strong hint (action-sequence cache) when the screen matches a past success."""
        if not screenshot_hash or not self._path.exists():
            return None
        query_tokens = _tokenize(task)
        max_lines = 500
        lines: list[str] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    lines.append(line)
                    if len(lines) > max_lines:
                        lines.pop(0)
        except (OSError, UnicodeDecodeError):
            return None
        for raw in reversed(lines):
            raw = raw.strip()
            if not raw:
                continue
            try:
                ep = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if ep.get("outcome") != "completed":
                continue
            if ep.get("screenshot_hash") != screenshot_hash:
                continue
            task_text = ep.get("task") or ""
            score = _overlap_score(query_tokens, _tokenize(task_text)) if query_tokens else 1.0
            if score <= 0:
                continue
            actions = ep.get("actions_summary")
            if actions:
                return actions
        return None
