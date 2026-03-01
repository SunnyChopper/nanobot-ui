"""Context builder for assembling agent prompts."""

from __future__ import annotations

import base64
import mimetypes
import platform
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader

if TYPE_CHECKING:
    from collections.abc import Callable


# Default order of system prompt sections. When config provides system_prompt_section_order,
# only sections in that list are included, in that order; unknown names are ignored.
DEFAULT_SECTION_ORDER = [
    "identity",
    "bootstrap",
    "memory",
    "always_skills",
    "requested_skills",
    "skills_summary",
    "workflow",
    "mcp_guidance",
    "computer_use_guidance",
]


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    Assembles bootstrap files, memory, skills, and conversation history.
    Section order and inclusion can be overridden via section_order.
    """
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"

    def __init__(
        self,
        workspace: Path,
        mcp_guidance: dict[str, str] | None = None,
        *,
        system_prompt_max_chars: int = 0,
        memory_section_max_chars: int = 0,
        section_order: list[str] | None = None,
        history_max_chars: int = 0,
    ):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
        self.workflow_summary_callback: Callable[[], str] | None = None
        self.mcp_guidance: dict[str, str] = mcp_guidance or {}
        self.computer_use_guidance: str | None = None
        self.system_prompt_max_chars = system_prompt_max_chars
        self.memory_section_max_chars = memory_section_max_chars
        self.section_order = section_order if section_order else None
        self.history_max_chars = history_max_chars

    def _build_section_contents(self, skill_names: list[str] | None) -> dict[str, str]:
        """Build all section contents keyed by section id."""
        sections: dict[str, str] = {}
        sections["identity"] = self._get_identity()
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            sections["bootstrap"] = bootstrap
        memory = self.memory.get_memory_context()
        if memory:
            if self.memory_section_max_chars > 0 and len(memory) > self.memory_section_max_chars:
                suffix = "\n\n... [truncated]"
                memory = memory[: self.memory_section_max_chars - len(suffix)] + suffix
            sections["memory"] = f"# Memory\n\n{memory}"

        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                sections["always_skills"] = f"# Active Skills\n\n{always_content}"
        if skill_names:
            requested_content = self.skills.load_skills_for_context(skill_names)
            if requested_content:
                sections["requested_skills"] = f"# Requested Skills\n\n{requested_content}"

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            sections["skills_summary"] = f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}"""

        if self.workflow_summary_callback:
            try:
                workflow_summary = self.workflow_summary_callback()
                if workflow_summary:
                    sections["workflow"] = f"# Registered Workflows\n\n{workflow_summary}"
            except Exception:
                pass
        if self.mcp_guidance:
            guidance_parts = []
            for server_name, text in self.mcp_guidance.items():
                if text and text.strip():
                    guidance_parts.append(f"### {server_name}\n\n{text.strip()}")
            if guidance_parts:
                sections["mcp_guidance"] = "# MCP tool guidance\n\n" + "\n\n".join(guidance_parts)
        if self.computer_use_guidance and self.computer_use_guidance.strip():
            sections["computer_use_guidance"] = self.computer_use_guidance.strip()
        return sections

    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """Build the system prompt. Section order follows section_order if set, else DEFAULT_SECTION_ORDER."""
        order = self.section_order if self.section_order else DEFAULT_SECTION_ORDER
        sections = self._build_section_contents(skill_names)
        parts = [sections[name] for name in order if name in sections]
        sep = "\n\n---\n\n"
        result = sep.join(parts)
        if self.system_prompt_max_chars > 0 and len(result) > self.system_prompt_max_chars:
            while len(parts) > 1 and len(result) > self.system_prompt_max_chars:
                parts.pop()
                result = sep.join(parts)
        return result

    def get_system_blocks(self, skill_names: list[str] | None = None) -> list[dict[str, str]]:
        """Return the system prompt as a list of blocks for providers that support multiple system messages."""
        order = self.section_order if self.section_order else DEFAULT_SECTION_ORDER
        sections = self._build_section_contents(skill_names)
        return [{"role": "system", "content": sections[name]} for name in order if name in sections]

    def _get_identity(self) -> str:
        """Get the core identity section."""
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        return f"""# nanobot 🐈

You are nanobot, a helpful AI assistant.

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Long-term memory: {workspace_path}/memory/MEMORY.md (write important facts here)
- History log: {workspace_path}/memory/HISTORY.md (grep-searchable). Each entry starts with [YYYY-MM-DD HH:MM].
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

## nanobot Guidelines
- State intent before tool calls, but NEVER predict or claim results before receiving them.
- Before modifying a file, read it first. Do not assume files or directories exist.
- After writing or editing a file, re-read it if accuracy matters.
- If a tool call fails, analyze the error before retrying with a different approach.
- Ask for clarification when the request is ambiguous.

Reply directly with text for conversations. Only use the 'message' tool to send to a specific chat channel."""

    @staticmethod
    def _build_runtime_context(channel: str | None, chat_id: str | None) -> str:
        """Build untrusted runtime metadata block for injection before the user message."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        lines = [f"Current Time: {now} ({tz})"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call."""
        messages = []
        system_prompt = self.build_system_prompt(skill_names)
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        messages.append({"role": "system", "content": system_prompt})
        if self.history_max_chars > 0 and history:
            total = 0
            keep: list[dict[str, Any]] = []
            for m in reversed(history):
                total += len(str(m.get("content", "")))
                if total > self.history_max_chars:
                    break
                keep.append(m)
            history = list(reversed(keep))
        messages.extend(history)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})
        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self, messages: list[dict[str, Any]],
        tool_call_id: str, tool_name: str, result: str,
    ) -> list[dict[str, Any]]:
        """Add a tool result to the message list."""
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages

    def add_assistant_message(
        self, messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
        thinking_blocks: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the message list."""
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content is not None:
            msg["reasoning_content"] = reasoning_content
        if thinking_blocks:
            msg["thinking_blocks"] = thinking_blocks
        messages.append(msg)
        return messages
