"""
Workflow run history: SQLite persistence for result envelopes and run metadata.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL,
    finished_at_ms INTEGER,
    input_snapshot TEXT,
    result_envelope TEXT,
    error_message TEXT,
    langsmith_run_id TEXT,
    error_node TEXT,
    error_detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_name ON workflow_runs(workflow_name);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_started_at ON workflow_runs(started_at_ms);
"""


def _migrate_add_error_columns(conn: sqlite3.Connection) -> None:
    """Add error_node and error_detail columns if missing (existing DBs)."""
    for col in ("error_node", "error_detail"):
        try:
            conn.execute(f"ALTER TABLE workflow_runs ADD COLUMN {col} TEXT")
            conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise


def _db_path(data_dir: Path) -> Path:
    agents_dir = data_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    return agents_dir / "runs.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    _migrate_add_error_columns(conn)


def _get_conn(data_dir: Path) -> sqlite3.Connection:
    path = _db_path(data_dir)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def create_run(
    data_dir: Path,
    workflow_name: str,
    input_snapshot: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> str:
    """Create a new run record; returns run_id."""
    run_id = run_id or str(uuid.uuid4())
    now_ms = int(time.time() * 1000)
    input_json = json.dumps(input_snapshot or {}, default=str) if input_snapshot else None
    conn = _get_conn(data_dir)
    try:
        conn.execute(
            "INSERT INTO workflow_runs (run_id, workflow_name, status, started_at_ms, input_snapshot) VALUES (?, ?, ?, ?, ?)",
            (run_id, workflow_name, "running", now_ms, input_json),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info(f"Workflow run created: {run_id} ({workflow_name})")
    return run_id


def update_run_started(
    data_dir: Path,
    run_id: str,
    langsmith_run_id: str | None = None,
) -> None:
    """Record that the run has started (optional LangSmith link)."""
    conn = _get_conn(data_dir)
    try:
        if langsmith_run_id:
            conn.execute(
                "UPDATE workflow_runs SET langsmith_run_id = ? WHERE run_id = ?",
                (langsmith_run_id, run_id),
            )
        conn.commit()
    finally:
        conn.close()


def update_run_finished(
    data_dir: Path,
    run_id: str,
    status: str,
    result_envelope: dict[str, Any] | None = None,
    error_message: str | None = None,
    error_node: str | None = None,
    error_detail: dict[str, Any] | None = None,
) -> None:
    """Mark run as finished with status (success | error | skipped) and optional result/error.
    error_detail may contain stack_trace, node_input_snapshot for drill-down."""
    now_ms = int(time.time() * 1000)
    result_json = json.dumps(result_envelope or {}, default=str) if result_envelope else None
    detail_json = json.dumps(error_detail or {}, default=str) if error_detail else None
    conn = _get_conn(data_dir)
    try:
        conn.execute(
            "UPDATE workflow_runs SET status = ?, finished_at_ms = ?, result_envelope = ?, error_message = ?, error_node = ?, error_detail = ? WHERE run_id = ?",
            (status, now_ms, result_json, error_message, error_node, detail_json, run_id),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info(f"Workflow run finished: {run_id} status={status}")


def get_run(data_dir: Path, run_id: str) -> dict[str, Any] | None:
    """Get a single run by run_id."""
    conn = _get_conn(data_dir)
    try:
        row = conn.execute("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        conn.close()


def list_runs_for_workflow(
    data_dir: Path,
    workflow_name: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List runs for a workflow, newest first."""
    conn = _get_conn(data_dir)
    try:
        rows = conn.execute(
            "SELECT * FROM workflow_runs WHERE workflow_name = ? ORDER BY started_at_ms DESC LIMIT ? OFFSET ?",
            (workflow_name, limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_runs(
    data_dir: Path,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List all runs, newest first."""
    conn = _get_conn(data_dir)
    try:
        rows = conn.execute(
            "SELECT * FROM workflow_runs ORDER BY started_at_ms DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_last_successful_run_for_workflow_on_date(
    data_dir: Path,
    workflow_name: str,
    date_iso: str,
) -> dict[str, Any] | None:
    """Return the last successful run for the given workflow on the given date (YYYY-MM-DD). Used for idempotency."""
    conn = _get_conn(data_dir)
    try:
        row = conn.execute(
            """
            SELECT * FROM workflow_runs
            WHERE workflow_name = ? AND status = 'success'
            AND strftime('%Y-%m-%d', started_at_ms / 1000.0, 'unixepoch', 'localtime') = ?
            ORDER BY started_at_ms DESC LIMIT 1
            """,
            (workflow_name, date_iso),
        ).fetchone()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for key in ("input_snapshot", "result_envelope", "error_detail"):
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                pass
    return d
