"""System resource diagnostics tool for CPU, RAM, disk, and network."""

from typing import Any

from nanobot.agent.tools.base import Tool


def _format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


class SystemStatsTool(Tool):
    """Tool to report host CPU, memory, disk, and network usage for self-diagnostics or optimization."""

    @property
    def name(self) -> str:
        return "system_stats"

    @property
    def description(self) -> str:
        return (
            "Get current host system resource usage: CPU percent, memory (RAM) usage, "
            "disk usage, and network I/O. Use for self-diagnostics or system optimization tasks."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        try:
            import psutil
        except ImportError:
            return "Error: psutil is not installed. Run: pip install psutil"

        lines = []
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        lines.append(f"CPU: {cpu_percent}% used ({cpu_count} logical cores)")

        # Memory
        mem = psutil.virtual_memory()
        lines.append(
            f"Memory: {mem.percent}% used — "
            f"{_format_bytes(mem.used)} / {_format_bytes(mem.total)} "
            f"(available: {_format_bytes(mem.available)})"
        )

        # Disk (root or main mount)
        try:
            disk = psutil.disk_usage("/")
        except Exception:
            disk = None
        if disk:
            lines.append(
                f"Disk: {disk.percent}% used — "
                f"{_format_bytes(disk.used)} / {_format_bytes(disk.total)} "
                f"(free: {_format_bytes(disk.free)})"
            )

        # Network (aggregate I/O since boot)
        try:
            net = psutil.net_io_counters()
            if net:
                lines.append(
                    f"Network (since boot): bytes_sent={_format_bytes(net.bytes_sent)}, "
                    f"bytes_recv={_format_bytes(net.bytes_recv)}"
                )
        except Exception:
            pass

        return "\n".join(lines)
