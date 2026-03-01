"""
Nanobot web server entry point.

Usage:
    python -m server

Starts the FastAPI server on config.gateway.port (default: 18790) with all
nanobot services (agent loop, channels, cron, heartbeat) running as background
tasks inside the FastAPI lifespan.

Prerequisites:
    pip install -e .                    # installs nanobot package in editable mode
    pip install -r server/requirements.txt  # installs fastapi + uvicorn

Environment:
    LOG_FORMAT=json  Enable structured JSON logging (one JSON object per line).
"""

import os
import uvicorn

from server.bootstrap import bootstrap
from server.app import create_app
from server.logging_config import configure_logging


def main() -> None:
    config, bus, agent, session_manager, channels, cron, heartbeat = bootstrap()
    log_format = os.environ.get("LOG_FORMAT") or getattr(config.gateway, "log_format", "text")
    configure_logging(log_format=log_format)
    app = create_app(config, bus, agent, session_manager, channels, cron, heartbeat)

    uvicorn.run(
        app,
        host=config.gateway.host,
        port=config.gateway.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
