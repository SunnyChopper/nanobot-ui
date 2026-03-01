"""
HTTP handlers for the nanobot web API.

Each module exposes async functions that take Request (and body/path/query).
Handlers call services from request.app.state and return Pydantic models.
"""
