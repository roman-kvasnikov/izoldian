import os

import aiofiles
from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from auth import get_user_data_dir

router = APIRouter(prefix="/api/media", tags=["media"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".mp3", ".wav", ".ogg", ".mp4", ".webm",
    ".pdf", ".zip",
}


def safe_path(user_id: str, path: str) -> str:
    base = os.path.realpath(get_user_data_dir(user_id))
    full = os.path.realpath(os.path.join(base, path))
    if not full.startswith(base):
        raise HTTPException(403, "Path traversal not allowed")
    return full


@router.post("/upload")
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    folder: str = "",
):
    user_id = request.state.user["id"]

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed")

    # Default to _attachments folder
    if not folder:
        folder = "_attachments"

    dest_dir = safe_path(user_id, folder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file.filename)

    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 50MB)")

    async with aiofiles.open(dest_path, "wb") as f:
        await f.write(content)

    rel_path = os.path.join(folder, file.filename)
    return {"path": rel_path, "ok": True}


@router.delete("/{path:path}")
async def delete_media(path: str, request: Request):
    user_id = request.state.user["id"]
    full_path = safe_path(user_id, path)

    if not os.path.isfile(full_path):
        raise HTTPException(404, "File not found")

    os.remove(full_path)
    return {"ok": True}


@router.get("/{path:path}")
async def get_media(path: str, request: Request):
    user_id = request.state.user["id"]
    full_path = safe_path(user_id, path)

    if not os.path.isfile(full_path):
        raise HTTPException(404, "File not found")

    from starlette.responses import FileResponse
    return FileResponse(full_path)
