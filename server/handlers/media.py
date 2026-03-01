"""Media HTTP handlers: serve uploaded files, upload new files."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import FileResponse


async def serve_media(request: Request, path: str = "") -> FileResponse:
    """Serve an uploaded file by path (e.g. path=media/abc.png). Only under data dir."""
    if not path or ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    from nanobot.utils.helpers import get_data_path

    data_dir = get_data_path().resolve()
    full = (data_dir / path).resolve()
    if not full.is_file() or not str(full).startswith(str(data_dir)):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(full)


async def upload_file(file: UploadFile) -> dict:
    """Upload a file for message attachment. Saves under data_dir/media/{uuid}.{ext}."""
    from nanobot.utils.helpers import ensure_dir, get_data_path

    data_dir = get_data_path()
    media_dir = ensure_dir(data_dir / "media")
    ext = Path(file.filename or "bin").suffix.lstrip(".") or "bin"
    name = f"{uuid.uuid4().hex}.{ext}"
    path = media_dir / name
    content = await file.read()
    path.write_bytes(content)
    return {"path": f"media/{name}"}
