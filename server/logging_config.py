"""
Structured logging configuration for the nanobot server.

When log_format is "json", each log record is written as a single JSON line
to stderr for easy aggregation in ELK, Datadog, etc. Exception and extra
context (e.g. session_id, request_id) are included in the JSON.

Set LOG_FORMAT=json in the environment to enable without config change.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from loguru import logger


def configure_logging(log_format: str = "text") -> None:
    """
    Configure loguru to use either human-readable (text) or JSON output.

    Args:
        log_format: "text" for dev-friendly output; "json" for one JSON object
            per line (level, time, message, exception, extra).
    """
    # Remove default handler (id 0)
    logger.remove(0)

    if log_format.lower() == "json":
        def json_sink(message: Any) -> None:
            record = message.record
            payload = {
                "level": record["level"].name,
                "time": record["time"].isoformat(),
                "message": record["message"],
            }
            if record["exception"] is not None:
                payload["exception"] = {
                    "type": record["exception"].type.__name__ if record["exception"].type else None,
                    "value": str(record["exception"].value) if record["exception"].value else None,
                }
            if record["extra"]:
                payload["extra"] = {k: v for k, v in record["extra"].items()}
            sys.stderr.write(json.dumps(payload, default=str) + "\n")

        logger.add(json_sink, level="DEBUG", serialize=False)
    else:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            level="DEBUG",
        )
