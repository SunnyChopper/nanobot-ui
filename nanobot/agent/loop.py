"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import os
import re
import weakref
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryStore
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.desktop import (
    SCREENSHOT_RESULT_PREFIX,
    ClickImageTool,
    GetForegroundWindowTool,
    KeyboardTypeTool,
    LaunchAppTool,
    LocateOnScreenTool,
    MouseClickTool,
    MouseMoveTool,
    MousePositionTool,
    ScreenshotRegionTool,
    ScreenshotTool,
)
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.python_inline import RunPythonTool
from nanobot.agent.tools.rag import RagIngestTool, SemanticSearchTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.system_stats import SystemStatsTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import (
        ChannelsConfig,
        ComputerUseConfig,
        ExecToolConfig,
        PythonInlineConfig,
    )
    from nanobot.cron.service import CronService

# Default text injected after a screenshot tool result (TOOLS.md/CUA).
SCREENSHOT_FOLLOW_UP_TEXT = (
    "Screenshot attached below. For taskbar, window previews, icons, or small/fiddly elements: "
    "use screenshot_region then click_image (do not use overlay coordinates). "
    "For other desktop clicks you may use the coordinate overlay to read (x,y) and mouse_click(x,y). "
    "For in-browser targets prefer browser/UI tools (Playwright, cursor-ide-browser)."
)


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 500

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 100,
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        exec_config: ExecToolConfig | None = None,
        python_inline_config: PythonInlineConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        mcp_guidance: dict[str, str] | None = None,
        tool_timeout_seconds: int = 0,
        cua_auto_approve: bool = False,
        screenshot_follow_up_text: str | None = None,
        system_prompt_max_chars: int = 0,
        memory_section_max_chars: int = 0,
        section_order: list[str] | None = None,
        history_max_chars: int = 0,
        computer_use_config: ComputerUseConfig | None = None,
        computer_use_confirm_callback: Callable[..., Awaitable[bool]] | None = None,
        computer_use_api_key: str | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig, PythonInlineConfig
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.python_inline_config = python_inline_config if python_inline_config is not None else PythonInlineConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self.context = ContextBuilder(
            workspace,
            mcp_guidance=mcp_guidance or {},
            system_prompt_max_chars=system_prompt_max_chars,
            memory_section_max_chars=memory_section_max_chars,
            section_order=section_order if section_order else None,
            history_max_chars=history_max_chars,
        )
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            reasoning_effort=reasoning_effort,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            python_inline_config=self.python_inline_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._tool_timeout_seconds = tool_timeout_seconds if tool_timeout_seconds > 0 else 0
        self._cua_auto_approve = cua_auto_approve
        self._screenshot_follow_up_text = screenshot_follow_up_text.strip() if (screenshot_follow_up_text and screenshot_follow_up_text.strip()) else None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()  # Session keys with consolidation in progress
        self._consolidation_tasks: set[asyncio.Task] = set()  # Strong refs to in-flight tasks
        self._consolidation_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._processing_lock = asyncio.Lock()
        self._computer_use_config = computer_use_config
        self._computer_use_confirm_callback = computer_use_confirm_callback
        self._computer_use_api_key = computer_use_api_key
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
            path_append=getattr(self.exec_config, "path_append", "") or "",
            use_sandbox=getattr(self.exec_config, "use_sandbox", False),
            sandbox_image=getattr(self.exec_config, "sandbox_image", "alpine:latest"),
        ))
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # Inline Python (optional; safety check via ephemeral LLM when enabled)
        if self.python_inline_config.enabled:
            self.tools.register(RunPythonTool(
                provider=self.provider,
                workspace=self.workspace,
                timeout=self.python_inline_config.timeout,
                safety_check=self.python_inline_config.safety_check,
                safety_model=self.python_inline_config.safety_model or "",
                restrict_to_workspace=self.restrict_to_workspace,
                skip_safety_when_cua_auto=self._cua_auto_approve,
            ))

        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())

        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # System diagnostics (read-only)
        self.tools.register(SystemStatsTool())

        # Local RAG (optional: requires chromadb + sentence-transformers)
        rag_dir = self.workspace / "data" / "chroma"
        self.tools.register(SemanticSearchTool(persist_directory=rag_dir))
        self.tools.register(RagIngestTool(persist_directory=rag_dir, allowed_dir=allowed_dir))

        # Desktop automation (optional: requires pyautogui; policy "ask" by default)
        self.tools.register(MouseMoveTool())
        self.tools.register(MouseClickTool())
        self.tools.register(MousePositionTool())
        self.tools.register(KeyboardTypeTool())
        self.tools.register(ScreenshotTool())
        self.tools.register(ScreenshotRegionTool())
        self.tools.register(LocateOnScreenTool())
        self.tools.register(ClickImageTool())
        self.tools.register(GetForegroundWindowTool())
        self.tools.register(LaunchAppTool())

        # Computer use (Gemini 3 Flash computer_use tool; optional)
        if self._computer_use_config and getattr(self._computer_use_config, "enabled", False):
            provider_name = (getattr(self._computer_use_config, "provider", None) or "").strip().lower()
            if provider_name == "gemini":
                api_key = (
                    self._computer_use_api_key
                    or getattr(self._computer_use_config, "api_key", None)
                    or ""
                ).strip() or None
                if api_key:
                    from nanobot.agent.computer_use.executor import ActionExecutor
                    from nanobot.agent.computer_use.gemini_provider import GeminiComputerUseProvider
                    from nanobot.agent.computer_use.outcome_store import ComputerUseOutcomeStore
                    from nanobot.agent.tools.computer_use_tool import ComputerUseTool

                    model = getattr(self._computer_use_config, "model", None) or "gemini-3-flash-preview"
                    max_steps = max(1, getattr(self._computer_use_config, "max_steps_per_task", 15))
                    dry_run = bool(getattr(self._computer_use_config, "dry_run", False))
                    excluded = ["open_web_browser"] if getattr(self._computer_use_config, "exclude_open_web_browser", False) else None
                    prefer_kb = getattr(self._computer_use_config, "prefer_keyboard_shortcuts", True)
                    allow_multi = getattr(self._computer_use_config, "allow_multi_action_turn", True)
                    use_cu_history = bool(getattr(self._computer_use_config, "use_conversation_history", False))
                    cu_provider = GeminiComputerUseProvider(
                        api_key=api_key,
                        model=model,
                        excluded_predefined_functions=excluded,
                        prefer_keyboard_shortcuts=prefer_kb,
                        allow_multi_action_turn=allow_multi,
                        use_conversation_history=use_cu_history,
                    )
                    cu_executor = ActionExecutor(
                        dry_run=dry_run,
                        confirm_callback=self._computer_use_confirm_callback,
                    )
                    post_delay_ms = max(0, getattr(self._computer_use_config, "post_action_delay_ms", 400))
                    learning = getattr(self._computer_use_config, "learning", None)
                    cu_outcome_store = None
                    if learning and getattr(learning, "enabled", False):
                        ep_path = getattr(learning, "episodes_path", None) or "memory/computer_use_episodes.jsonl"
                        max_hints = max(0, getattr(learning, "retrieval_max_hints", 3))
                        cu_outcome_store = ComputerUseOutcomeStore(
                            self.workspace,
                            path=ep_path,
                            retrieval_max_hints=max_hints,
                        )
                    use_internal_run_memory = bool(getattr(self._computer_use_config, "use_internal_run_memory", True))
                    same_kind_exit = max(0, getattr(self._computer_use_config, "repetition_same_kind_exit_threshold", 5))
                    same_kind_hint = max(1, getattr(self._computer_use_config, "repetition_same_kind_hint_threshold", 4))
                    oscillation_window = max(0, getattr(self._computer_use_config, "repetition_oscillation_window", 0))
                    self.tools.register(ComputerUseTool(
                        provider=cu_provider,
                        executor=cu_executor,
                        max_steps=max_steps,
                        post_action_delay_ms=post_delay_ms,
                        use_conversation_history=use_cu_history,
                        workspace=self.workspace,
                        outcome_store=cu_outcome_store,
                        use_internal_run_memory=use_internal_run_memory,
                        repetition_same_kind_exit_threshold=same_kind_exit if same_kind_exit > 0 else 999,
                        repetition_same_kind_hint_threshold=same_kind_hint,
                        repetition_oscillation_window=oscillation_window,
                    ))
                    key_src = "GEMINI_API_KEY (env)" if (os.environ.get("GEMINI_API_KEY") or "").strip() else "config"
                    logger.info(
                        "Registered computer_use tool ({}). API key from {}. For desktop tasks prefer this over screenshot/mouse_click.",
                        model,
                        key_src,
                    )
                    try:
                        if cu_provider.probe_api_key():
                            logger.info("computer_use: API key verified (minimal request succeeded).")
                        else:
                            logger.warning(
                                "computer_use: API key check returned 404. Key is set but the model may be unavailable for this key/region. "
                                "Run from this environment: python scripts/test_gemini_computer_use.py"
                            )
                    except Exception as probe_err:
                        logger.warning("computer_use: API key probe failed: {}", probe_err)
                    self._set_computer_use_guidance()
                else:
                    logger.warning(
                        "computer_use not registered: tools.computerUse.enabled is true but no API key. "
                        "Set providers.gemini.apiKey or tools.computerUse.apiKey in config, or GEMINI_API_KEY."
                    )
            else:
                logger.warning(
                    "computer_use not registered: provider '{}' not supported (only 'gemini' is implemented).",
                    provider_name or "(empty)",
                )

    def _set_computer_use_guidance(self) -> None:
        """Inject system-prompt guidance so the agent prefers computer_use for desktop tasks."""
        exclusive = getattr(self._computer_use_config, "exclusive_desktop", True)
        atomic_rule = (
            "**One computer_use call = one atomic task.** Never pass a numbered list (e.g. \"1. … 2. … 3. …\") or multiple sentences describing different steps in a single `task` string. "
            "Plan the high-level steps in your reasoning, then execute each step with a **separate** computer_use call, using the result of each call to decide the next.\n\n"
            "**Bad:** `computer_use(task=\"1. Switch to the browser and go to analytics.x.com. 2. Analyze Top Posts. 3. Report impressions.\")`\n\n"
            "**Good:** First `computer_use(task=\"Switch to the browser and navigate to analytics.x.com\")`, then after that result `computer_use(task=\"Open or focus the Top Posts section for the last 28 days\")`, then `computer_use(task=\"Read the impressions from the chart and summarize\")` (one call per atomic step)."
        )
        if exclusive:
            self.context.computer_use_guidance = (
                "# Computer use (desktop UI)\n\n"
                "All desktop actions (clicks, typing, scrolling, launching apps, etc.) must be done **only** via the **computer_use** tool. "
                "Do not use any other tools for desktop interaction.\n\n"
                + atomic_rule
                + "\n\n"
                "You can pass an optional **max_steps** for small sub-tasks (e.g. `computer_use(task=\"Click the Content tab\", max_steps=5)`). "
                "computer_use captures the screen, asks a vision model for actions, and executes them until the task is done or the step limit is reached."
            )
        else:
            self.context.computer_use_guidance = (
                "# Computer use (desktop UI)\n\n"
                "When the user asks you to do something on the desktop (e.g. open an app, type in a field, click something on screen), "
                "**use the computer_use tool** with a single natural-language task. "
                "Do **not** compose low-level steps yourself with screenshot, mouse_click, keyboard_type, or launch_app unless the user explicitly asks for that.\n\n"
                + atomic_rule
                + "\n\n"
                "computer_use captures the screen, asks a vision model for actions, and executes them until the task is done or the step limit is reached."
            )

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        for name in ("message", "spawn", "cron"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    tool.set_context(channel, chat_id, *([message_id] if name == "message" else []))

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop. Returns (final_content, tools_used, messages)."""
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
            )

            if response.finish_reason == "error":
                final_content = response.content
                break

            if response.has_tool_calls:
                if on_progress:
                    clean = self._strip_think(response.content)
                    if clean:
                        await on_progress(clean)
                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    try:
                        if self._tool_timeout_seconds > 0:
                            result = await asyncio.wait_for(
                                self.tools.execute(tool_call.name, tool_call.arguments),
                                timeout=self._tool_timeout_seconds,
                            )
                        else:
                            result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    except asyncio.TimeoutError:
                        result = f"Tool execution timed out after {self._tool_timeout_seconds} seconds."
                    if tool_call.name == "screenshot" and result.startswith(SCREENSHOT_RESULT_PREFIX):
                        b64 = result[len(SCREENSHOT_RESULT_PREFIX):]
                        follow_up = self._screenshot_follow_up_text or SCREENSHOT_FOLLOW_UP_TEXT
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, follow_up
                        )
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                                {"type": "text", "text": follow_up},
                            ],
                        })
                    else:
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result
                        )
                messages.append({"role": "user", "content": "Reflect on the results and decide next steps."})
            else:
                clean = self._strip_think(response.content)
                # Don't persist error responses to session history — they can
                # poison the context and cause permanent 400 loops (#1303).
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if msg.content.strip().lower() == "/stop":
                await self._handle_stop(msg)
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"⏹ Stopped {total} task(s)." if total else "No active task to stop."
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=content,
        ))

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the global lock."""
        async with self._processing_lock:
            try:
                response = await self._process_message(msg)
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Sorry, I encountered an error.",
                ))

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[..., Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        if msg.channel == "system":
            return await self._process_system_message(msg)
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # Slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())
            self._consolidating.add(session.key)
            try:
                async with lock:
                    snapshot = session.messages[session.last_consolidated:]
                    if snapshot:
                        temp = Session(key=session.key)
                        temp.messages = list(snapshot)
                        if not await self._consolidate_memory(temp, archive_all=True):
                            return OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id,
                                content="Memory archival failed, session not cleared. Please try again.",
                            )
            except Exception:
                logger.exception("/new archival failed for {}", session.key)
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Memory archival failed, session not cleared. Please try again.",
                )
            finally:
                self._consolidating.discard(session.key)

            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 nanobot commands:\n/new — Start a new conversation\n/stop — Stop the current task\n/help — Show available commands")

        unconsolidated = len(session.messages) - session.last_consolidated
        if (unconsolidated >= self.memory_window and session.key not in self._consolidating):
            self._consolidating.add(session.key)
            lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())

            async def _consolidate_and_unlock():
                try:
                    async with lock:
                        await self._consolidate_memory(session)
                finally:
                    self._consolidating.discard(session.key)
                    _task = asyncio.current_task()
                    if _task is not None:
                        self._consolidation_tasks.discard(_task)

            _task = asyncio.create_task(_consolidate_and_unlock())
            self._consolidation_tasks.add(_task)

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=self.memory_window)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages, on_progress=on_progress or _bus_progress,
        )
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)
        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            return None
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata=msg.metadata or {},
        )

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).

        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info("Processing system message from {}", msg.sender_id)

        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id

        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        self._set_tool_context(origin_channel, origin_chat_id)
        history = session.get_history(max_messages=self.memory_window)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        final_content, _, all_msgs = await self._run_agent_loop(initial_messages)
        if final_content is None:
            final_content = "Background task completed."
        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)

        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session, truncating large tool results."""
        from datetime import datetime
        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue  # skip empty assistant messages — they poison session context
            if role == "tool" and isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            elif role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    continue
                if isinstance(content, list):
                    entry["content"] = [
                        {"type": "text", "text": "[image]"} if (
                            c.get("type") == "image_url"
                            and c.get("image_url", {}).get("url", "").startswith("data:image/")
                        ) else c for c in content
                    ]
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def _consolidate_memory(self, session, archive_all: bool = False) -> bool:
        """Delegate to MemoryStore.consolidate(). Returns True on success."""
        return await MemoryStore(self.workspace).consolidate(
            session, self.provider, self.model,
            archive_all=archive_all, memory_window=self.memory_window,
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage)."""
        await self._connect_mcp()
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
        response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
        return response.content if response else ""
