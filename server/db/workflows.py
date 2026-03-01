"""
Workflow definition storage (file-based under data_dir).

Each workflow is stored as a JSON file in data_dir/agents/workflows/{id}.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _workflows_dir(data_dir: Path) -> Path:
    d = data_dir / "agents" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_workflow_definition(
    data_dir: Path,
    workflow_id: str,
    definition: dict[str, Any],
) -> None:
    """Persist a workflow definition as JSON."""
    path = _workflows_dir(data_dir) / f"{workflow_id}.json"
    with open(path, "w") as f:
        json.dump(definition, f, indent=2, default=str)


def load_workflow_definition(data_dir: Path, workflow_id: str) -> dict[str, Any] | None:
    """Load a workflow definition by id. Returns None if not found."""
    path = _workflows_dir(data_dir) / f"{workflow_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def list_workflow_ids(data_dir: Path) -> list[str]:
    """List all workflow ids (from filenames without .json)."""
    d = _workflows_dir(data_dir)
    return [p.stem for p in d.glob("*.json")]


def delete_workflow_definition(data_dir: Path, workflow_id: str) -> bool:
    """Remove a workflow definition file. Returns True if deleted."""
    path = _workflows_dir(data_dir) / f"{workflow_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
