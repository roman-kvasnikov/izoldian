import os
import shutil

from fastapi import APIRouter, HTTPException, Request

from auth import get_user_data_dir
from models import FolderCreate, MoveRequest

router = APIRouter(prefix="/api/folders", tags=["folders"])


def get_user_id(request: Request) -> str:
    return request.state.user["id"]


def safe_path(user_id: str, path: str) -> str:
    base = os.path.realpath(get_user_data_dir(user_id))
    full = os.path.realpath(os.path.join(base, path))
    if not full.startswith(base):
        raise HTTPException(403, "Path traversal not allowed")
    return full


@router.post("")
async def create_folder(body: FolderCreate, request: Request):
    user_id = get_user_id(request)
    full_path = safe_path(user_id, body.path)
    os.makedirs(full_path, exist_ok=True)
    return {"ok": True}


@router.delete("/{path:path}")
async def delete_folder(path: str, request: Request):
    user_id = get_user_id(request)
    full_path = safe_path(user_id, path)

    if not os.path.isdir(full_path):
        raise HTTPException(404, "Folder not found")

    shutil.rmtree(full_path)
    return {"ok": True}


@router.post("/move")
async def move_folder(body: MoveRequest, request: Request):
    user_id = get_user_id(request)
    src = safe_path(user_id, body.source)
    dst = safe_path(user_id, body.destination)

    if not os.path.isdir(src):
        raise HTTPException(404, "Source folder not found")

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    return {"ok": True}
