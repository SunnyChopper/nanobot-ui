"""Inline Python execution tool: run code via python -c with optional LLM safety check.

Default tool policy: ask (user approves before execution). Documented in docs/reference/mcp-and-tools.md.
"""

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider

_SAFETY_SYSTEM_PROMPT = """You are a code safety checker. For the user-provided Python code, reply with exactly one line: either 'SAFE' or 'UNSAFE' and a brief reason.
Consider UNSAFE: exec/eval/compile of untrusted input, deleting or overwriting files outside a temp dir, formatting disks, network exfiltration, privilege escalation, fork bombs, excessive resource use, or bypassing sandbox."""

_MAX_OUTPUT_LEN = 10000


class RunPythonTool(Tool):
    """Tool to run Python code inline (no file). Optional ephemeral LLM call verifies code is not malicious before execution."""

    def __init__(
        self,
        provider: "LLMProvider",
        workspace: Path,
        timeout: int = 30,
        safety_check: bool = True,
        safety_model: str = "",
        restrict_to_workspace: bool = False,
        skip_safety_when_cua_auto: bool = False,
    ):
        self._provider = provider
        self._workspace = Path(workspace)
        self._timeout = timeout
        self._safety_check = safety_check
        self._safety_model = safety_model or None  # None = use provider default
        self._restrict_to_workspace = restrict_to_workspace
        self._skip_safety_when_cua_auto = skip_safety_when_cua_auto

    @property
    def name(self) -> str:
        return "run_python"

    @property
    def description(self) -> str:
        return "Run Python code inline (no file created). Code is executed via python -c. Use for one-off computations or scripts. Optional safety check runs first when enabled in config."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute (can be multi-line)",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for execution (default: workspace)",
                },
            },
            "required": ["code"],
        }

    async def execute(
        self,
        code: str,
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> str:
        code = code.strip()
        if not code:
            return "Error: No code provided."

        cwd = self._resolve_cwd(working_dir)
        if cwd is None:
            return "Error: Working directory is outside the allowed workspace (restrict_to_workspace is enabled)."

        if self._safety_check and not self._skip_safety_when_cua_auto:
            block_reason = await self._safety_check_code(code)
            if block_reason is not None:
                return f"Blocked by safety check: {block_reason}"

        return await self._run_code(code, cwd)

    def _resolve_cwd(self, working_dir: str | None) -> Path | None:
        base = self._workspace.resolve()
        if not working_dir:
            return base
        try:
            cwd = Path(working_dir).resolve()
        except Exception:
            return base
        if not cwd.is_dir():
            return base
        if self._restrict_to_workspace:
            try:
                cwd.relative_to(base)
            except ValueError:
                return None
        return cwd

    async def _safety_check_code(self, code: str) -> str | None:
        """Run ephemeral LLM call; return block reason if UNSAFE, else None."""
        messages = [
            {"role": "system", "content": _SAFETY_SYSTEM_PROMPT},
            {"role": "user", "content": code},
        ]
        try:
            response = await self._provider.chat(
                messages=messages,
                tools=None,
                model=self._safety_model,
                max_tokens=150,
                temperature=0,
            )
        except Exception as e:
            return f"Safety check failed ({e}); refusing to run code."

        content = (response.content or "").strip().upper()
        if "UNSAFE" in content:
            # Use the rest of the response as reason, or default
            reason = (response.content or "UNSAFE").strip()
            if reason.upper().startswith("UNSAFE"):
                reason = reason[6:].strip() or "Code classified as unsafe."
            return reason
        return None

    async def _run_code(self, code: str, cwd: Path) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._timeout,
                )
            except asyncio.CancelledError:
                process.kill()
                try:
                    await process.wait()
                except Exception:
                    pass
                raise
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Execution timed out after {self._timeout} seconds."
            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            result = "\n".join(output_parts) if output_parts else "(no output)"
            if len(result) > _MAX_OUTPUT_LEN:
                result = result[:_MAX_OUTPUT_LEN] + f"\n... (truncated, {len(result) - _MAX_OUTPUT_LEN} more chars)"
            return result
        except Exception as e:
            return f"Error executing code: {str(e)}"
