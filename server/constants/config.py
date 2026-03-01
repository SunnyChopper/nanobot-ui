"""
Constants used by config and other handlers.

Moved from routes.py so routes stay thin (registration only).
"""

# Tools NOT listed here inherit: "auto" for known read-only, "ask" for write/exec, "ask" for MCP.
DEFAULT_TOOL_POLICY: dict[str, str] = {
    "read_file": "auto",
    "list_dir": "auto",
    "web_search": "auto",
    "web_fetch": "auto",
    "message": "auto",
    "write_file": "ask",
    "edit_file": "ask",
    "exec": "ask",
    "run_python": "ask",
    "spawn": "ask",
    "cron": "ask",
}

# Curated model list per provider (only returned when provider has an API key).
PROVIDER_MODELS: dict[str, list[tuple[str, str]]] = {
    "anthropic": [
        ("anthropic/claude-opus-4-6", "Claude Opus 4.6"),
        ("anthropic/claude-opus-4-5", "Claude Opus 4.5"),
        ("anthropic/claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ("anthropic/claude-sonnet-4-5", "Claude Sonnet 4.5"),
        ("anthropic/claude-haiku-4-5", "Claude Haiku 4.5"),
    ],
    "openai": [
        ("gpt-5.2-codex", "GPT-5.2 Codex"),
        ("gpt-5.2", "GPT-5.2"),
        ("gpt-5.1-codex", "GPT-5.1 Codex"),
        ("gpt-5.1", "GPT-5.1"),
        ("gpt-5-mini", "GPT-5 Mini"),
        ("gpt-5-nano", "GPT-5 Nano")
    ],
    "gemini": [
        ("gemini-3.1-pro-preview", "Gemini 3.1 Pro"),
        ("gemini-3-pro-preview", "Gemini 3 Pro"),
        ("gemini-3-flash-preview", "Gemini 3 Flash")
    ],
    "deepseek": [
        ("deepseek/deepseek-chat", "DeepSeek V3.2 (Non-reasoning)"),
        ("deepseek/deepseek-reasoner", "DeepSeek V3.2 (Reasoning)"),
    ],
    "openrouter": [
        ("minimax/minimax-m2.5", "MiniMax M2.5"),
        ("moonshotai/kimi-k2.5", "Kimi K2.5"),
        ("z-ai/glm-5", "GLM-5"),
        ("x-ai/grok-4.1-fast", "Grok 4.1 Fast")
    ],
    "groq": [
        ("openai/gpt-oss-120b", "GPT-OSS 120B"),
        ("openai/gpt-oss-20b", "GPT-OSS 20B"),
        ("moonshotai/kimi-k2-instruct-0905", "Kimi K2"),
        ("meta-llama/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick"),
        ("llama-3.3-70b-versatile", "Llama 3.3 70B"),
        ("llama-3.1-8b-instant", "Llama 3.1 8B"),
        ("qwen/qwen3-32b", "Qwen3 32B")
    ],
    "moonshot": [
        ("moonshot/kimi-k2-5", "Kimi K2.5"),
    ],
    "zhipu": [
        ("zai/glm-4", "GLM-4"),
        ("zai/glm-4-flash", "GLM-4 Flash"),
    ],
    "dashscope": [
        ("dashscope/qwen-max", "Qwen Max"),
        ("dashscope/qwen-plus", "Qwen Plus"),
        ("dashscope/qwen-turbo", "Qwen Turbo"),
    ],
    "minimax": [
        ("minimax/MiniMax-M2.1", "MiniMax M2.1"),
    ],
    "vllm": [],
    "aihubmix": [],
    "custom": [],
}
