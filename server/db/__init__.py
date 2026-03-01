"""
Persistence for workflow runs and workflow definitions.

SQLite for run history; file-based JSON for workflow definitions (under data_dir).
Postgres can be added later via config for multi-instance.
"""

from server.db.runs import (
    create_run,
    get_last_successful_run_for_workflow_on_date,
    get_run,
    list_runs,
    list_runs_for_workflow,
    update_run_finished,
    update_run_started,
)
from server.db.workflows import (
    delete_workflow_definition,
    list_workflow_ids,
    load_workflow_definition,
    save_workflow_definition,
)

__all__ = [
    "create_run",
    "get_run",
    "get_last_successful_run_for_workflow_on_date",
    "list_runs",
    "list_runs_for_workflow",
    "update_run_finished",
    "update_run_started",
    "save_workflow_definition",
    "load_workflow_definition",
    "list_workflow_ids",
    "delete_workflow_definition",
]
