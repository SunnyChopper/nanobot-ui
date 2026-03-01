"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class WhatsAppConfig(Base):
    """WhatsApp channel configuration."""

    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    bridge_token: str = ""  # Shared token for bridge auth (optional, recommended)
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(Base):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    reply_to_message: bool = False  # If true, bot replies quote the original message


class FeishuConfig(Base):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids
    react_emoji: str = "THUMBSUP"  # Emoji type for message reactions (e.g. THUMBSUP, OK, DONE, SMILE)


class DingTalkConfig(Base):
    """DingTalk channel configuration using Stream mode."""

    enabled: bool = False
    client_id: str = ""  # AppKey
    client_secret: str = ""  # AppSecret
    allow_from: list[str] = Field(default_factory=list)  # Allowed staff_ids


class DiscordConfig(Base):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class MatrixConfig(Base):
    """Matrix (Element) channel configuration."""

    enabled: bool = False
    homeserver: str = "https://matrix.org"
    access_token: str = ""
    user_id: str = ""  # @bot:matrix.org
    device_id: str = ""
    e2ee_enabled: bool = True # Enable Matrix E2EE support (encryption + encrypted room handling).
    sync_stop_grace_seconds: int = 2 # Max seconds to wait for sync_forever to stop gracefully before cancellation fallback.
    max_media_bytes: int = 20 * 1024 * 1024 # Max attachment size accepted for Matrix media handling (inbound + outbound).
    allow_from: list[str] = Field(default_factory=list)
    group_policy: Literal["open", "mention", "allowlist"] = "open"
    group_allow_from: list[str] = Field(default_factory=list)
    allow_room_mentions: bool = False


class EmailConfig(Base):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""

    enabled: bool = False
    consent_granted: bool = False  # Explicit owner permission to access mailbox data

    # IMAP (receive)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # SMTP (send)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    # Behavior
    auto_reply_enabled: bool = True  # If false, inbound email is read but no automatic reply is sent
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)  # Allowed sender email addresses


class MochatMentionConfig(Base):
    """Mochat mention behavior configuration."""

    require_in_groups: bool = False


class MochatGroupRule(Base):
    """Mochat per-group mention requirement."""

    require_mention: bool = False


class MochatConfig(Base):
    """Mochat channel configuration."""

    enabled: bool = False
    base_url: str = "https://mochat.io"
    socket_url: str = ""
    socket_path: str = "/socket.io"
    socket_disable_msgpack: bool = False
    socket_reconnect_delay_ms: int = 1000
    socket_max_reconnect_delay_ms: int = 10000
    socket_connect_timeout_ms: int = 10000
    refresh_interval_ms: int = 30000
    watch_timeout_ms: int = 25000
    watch_limit: int = 100
    retry_delay_ms: int = 500
    max_retry_attempts: int = 0  # 0 means unlimited retries
    claw_token: str = ""
    agent_user_id: str = ""
    sessions: list[str] = Field(default_factory=list)
    panels: list[str] = Field(default_factory=list)
    allow_from: list[str] = Field(default_factory=list)
    mention: MochatMentionConfig = Field(default_factory=MochatMentionConfig)
    groups: dict[str, MochatGroupRule] = Field(default_factory=dict)
    reply_delay_mode: str = "non-mention"  # off | non-mention
    reply_delay_ms: int = 120000


class SlackDMConfig(Base):
    """Slack DM policy configuration."""

    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackConfig(Base):
    """Slack channel configuration."""

    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    reply_in_thread: bool = True
    react_emoji: str = "eyes"
    group_policy: str = "mention"  # "mention", "open", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class QQConfig(Base):
    """QQ channel configuration using botpy SDK."""

    enabled: bool = False
    app_id: str = ""  # 机器人 ID (AppID) from q.qq.com
    secret: str = ""  # 机器人密钥 (AppSecret) from q.qq.com
    allow_from: list[str] = Field(default_factory=list)  # Allowed user openids (empty = public access)

class MatrixConfig(Base):
    """Matrix (Element) channel configuration."""
    enabled: bool = False
    homeserver: str = "https://matrix.org"
    access_token: str = ""
    user_id: str = ""                       # e.g. @bot:matrix.org
    device_id: str = ""
    e2ee_enabled: bool = True               # end-to-end encryption support
    sync_stop_grace_seconds: int = 2        # graceful sync_forever shutdown timeout
    max_media_bytes: int = 20 * 1024 * 1024 # inbound + outbound attachment limit
    allow_from: list[str] = Field(default_factory=list)
    group_policy: Literal["open", "mention", "allowlist"] = "open"
    group_allow_from: list[str] = Field(default_factory=list)
    allow_room_mentions: bool = False

class ChannelsConfig(Base):
    """Configuration for chat channels."""

    send_progress: bool = True    # stream agent's text progress to the channel
    send_tool_hints: bool = False  # stream tool-call hints (e.g. read_file("…"))
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    mochat: MochatConfig = Field(default_factory=MochatConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    qq: QQConfig = Field(default_factory=QQConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    provider: str = "auto"  # Provider name (e.g. "anthropic", "openrouter") or "auto" for auto-detection
    max_tokens: int = 8192
    temperature: float = 0.1
    max_tool_iterations: int = 40
    memory_window: int = 100
    memory_model: str = "gpt-oss-120b"  # Model for web-triggered memory writes; set "" to disable
    max_llm_retries: int = 3  # Retries for LLM stream/completion on transient errors
    retry_backoff_base_seconds: int = 2  # Exponential backoff base (2^attempt * this)
    system_prompt_max_chars: int = 0  # Cap assembled system prompt (0 = no limit)
    memory_section_max_chars: int = 0  # Cap the Memory section when injected
    system_prompt_section_order: list[str] = Field(default_factory=list)  # Section ids order; empty = default
    history_max_chars: int = 0  # Cap total history content length (0 = no limit)


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(Base):
    """Configuration for LLM providers."""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)  # Any OpenAI-compatible endpoint
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway
    siliconflow: ProviderConfig = Field(default_factory=ProviderConfig)  # SiliconFlow (硅基流动) API gateway
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)  # VolcEngine (火山引擎) API gateway
    openai_codex: ProviderConfig = Field(default_factory=ProviderConfig)  # OpenAI Codex (OAuth)
    github_copilot: ProviderConfig = Field(default_factory=ProviderConfig)  # Github Copilot (OAuth)


class HeartbeatConfig(Base):
    """Heartbeat service configuration."""

    enabled: bool = True
    interval_s: int = 30 * 60  # 30 minutes


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    log_format: str = "text"  # "text" | "json" – JSON for ELK/Datadog aggregation
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 60.0
    webhook_secret: str = ""
    auth_enabled: bool = False
    jwt_secret: str = ""


class WebSearchConfig(Base):
    """Web search tool configuration."""

    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""

    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    timeout: int = 60
    path_append: str = ""
    use_sandbox: bool = False
    sandbox_image: str = "alpine:latest"


class PythonInlineConfig(BaseModel):
    """Inline Python execution tool (run_python): run code via python -c with optional LLM safety check."""
    enabled: bool = True
    timeout: int = 30
    safety_check: bool = True
    safety_model: str = ""


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""

    command: str = ""  # Stdio: command to run (e.g. "npx")
    args: list[str] = Field(default_factory=list)  # Stdio: command arguments
    env: dict[str, str] = Field(default_factory=dict)  # Stdio: extra env vars
    url: str = ""  # HTTP: streamable HTTP endpoint URL
    headers: dict[str, str] = Field(default_factory=dict)  # HTTP: Custom HTTP Headers
    tool_timeout: int = 30  # Seconds before a tool call is cancelled


class MemorySleepConfig(BaseModel):
    """Memory sleep (scheduled consolidation into vector DB and knowledge graph)."""
    enabled: bool = True
    schedule: str = "0 2 * * *"
    archive_threshold_bytes: int = 200_000


class KgDedupConfig(BaseModel):
    """Knowledge graph deduplication."""
    enabled: bool = False
    schedule: str = "0 3 * * *"
    kg_dedup_model: str = ""
    llm_batch_size: int = 20
    batch_size: int = 256


class ComputerUseLearningConfig(Base):
    """Self-improvement for computer use: log outcomes and optionally retrieve similar past tasks as hints."""

    enabled: bool = False
    """When True, log each run to episodes file and enable similar-task retrieval for hints."""
    episodes_path: str | None = None
    """Workspace-relative path for JSONL episodes (e.g. memory/computer_use_episodes.jsonl). If None, use memory/computer_use_episodes.jsonl."""
    retrieval_max_hints: int = 3
    """Max number of similar past episodes to inject as hints (0 = no retrieval)."""
    retrieval_min_similarity: float = 0.0
    """Reserved for future embedding threshold; token-overlap retrieval ignores this."""


class ComputerUseConfig(Base):
    """Computer use tool (Gemini 2.5 computer use, etc.): screenshot → model → actions → execute."""

    enabled: bool = False
    provider: str = "gemini"
    model: str | None = None  # Default for Gemini: gemini-3-flash-preview
    max_steps_per_task: int = 15
    dry_run: bool = False
    confirm_destructive: bool = True
    api_key: str = ""  # Override; if empty, use providers.gemini.api_key
    exclude_open_web_browser: bool = True
    """When True (default), model uses click/type for desktop tasks (e.g. Open Notepad). Set False to allow open_web_browser for browser tasks."""
    prefer_keyboard_shortcuts: bool = True
    """When True (default), instruct the model to prefer keyboard shortcuts and key presses; use mouse clicks only when necessary."""
    allow_multi_action_turn: bool = True
    """When True (default), allow the model to return a short sequence of actions in one turn (e.g. click then type) when the next steps are clear."""
    post_action_delay_ms: int = 400
    """Delay in ms after executing actions before capturing the next screenshot (0 = no delay). Lets the UI update before the next step."""
    use_conversation_history: bool = False
    """When True, pass prior turns (user + model) to the API so the model sees what it suggested and the new screenshot. Reduces redundant steps; increases request size."""
    use_internal_run_memory: bool = True
    """When True (default), pass actions already taken this run to the provider so the model does not repeat them (reduces loops and cost)."""
    exclusive_desktop: bool = True
    """When True (default), only computer_use is registered for desktop; legacy tools (screenshot, mouse_click, etc.) are not registered. When False, both computer_use and legacy desktop tools are available."""
    learning: ComputerUseLearningConfig | None = None
    """Optional self-improvement: outcome logging and similar-task retrieval. When None, learning is disabled."""
    repetition_same_kind_exit_threshold: int = 5
    """Exit when this many consecutive same-kind actions (e.g. scroll_at) and screen unchanged for last 2 steps. 0 = disable same-kind exit."""
    repetition_same_kind_hint_threshold: int = 4
    """When same-kind streak >= this, add a hint to the model (e.g. 'The last N actions were all scroll_at...')."""
    repetition_oscillation_window: int = 0
    """If > 0, enable oscillation detection over this many recent actions; when alternating A-B-A-B is detected, add a hint. 0 = disabled."""


class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    python_inline: PythonInlineConfig = Field(default_factory=PythonInlineConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    mcp_guidance: dict[str, str] = Field(default_factory=dict)
    """Optional per-MCP-server guidance (server name → markdown). Injected into system prompt as "MCP tool guidance" section."""
    tool_policy: dict[str, str] = Field(default_factory=dict)
    """Per-tool execution policy. Values: "auto" | "ask" | "deny".
    Tools not listed use built-in defaults (read-only → auto, write/exec → ask, mcp_* → ask)."""
    tool_timeout_seconds: int = 0
    """Max seconds per tool execution (0 = no timeout). Prevents long-running MCP tools from hanging the UI."""
    cua_auto_approve: bool = False
    """When True, screenshot/mouse/keyboard run without approval; run_python is validated by a fast Groq model and auto-approved if safe (pyautogui-only)."""
    cua_safety_model: str = "llama-3.1-8b-instant"
    """Model id for CUA inline-Python safety check (Groq). Used only when cua_auto_approve is True."""
    screenshot_follow_up_text: str | None = None
    """Optional text injected after a screenshot tool result. When set, overrides the default (TOOLS.md-aligned) guidance. Use to customize desktop workflow per deployment."""
    computer_use: ComputerUseConfig = Field(default_factory=ComputerUseConfig)


class Config(BaseSettings):
    """Root configuration for nanobot."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory_sleep: MemorySleepConfig = Field(default_factory=MemorySleepConfig)
    kg_dedup: KgDedupConfig = Field(default_factory=KgDedupConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path. Uses NANOBOT_HOME when default workspace is set."""
        raw = self.agents.defaults.workspace
        if raw == "~/.nanobot/workspace":
            from nanobot.utils.helpers import get_workspace_path
            return get_workspace_path()
        return Path(raw).expanduser()

    def _match_provider(self, model: str | None = None) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from nanobot.providers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return (p, forced) if p else (None, None)

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        # Explicit provider prefix wins — prevents `github-copilot/...codex` matching openai_codex.
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and model_prefix and normalized_prefix == spec.name:
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        # OAuth providers are NOT valid fallbacks — they require explicit model selection
        for spec in PROVIDERS:
            if spec.is_oauth:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider (e.g. "deepseek", "openrouter")."""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Falls back to first available key."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        from nanobot.providers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        # Only gateways get a default api_base here. Standard providers
        # (like Moonshot) set their base URL via env vars in _setup_env
        # to avoid polluting the global litellm.api_base.
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    model_config = ConfigDict(env_prefix="NANOBOT_", env_nested_delimiter="__")
