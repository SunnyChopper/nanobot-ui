#!/bin/sh
# Ensure NANOBOT_HOME is set so the app finds config/workspace at the mount point.
# Docker -e on Windows may not pass env vars reliably; default to /workspace.
export NANOBOT_HOME="${NANOBOT_HOME:-/workspace}"
exec nanobot "$@"
