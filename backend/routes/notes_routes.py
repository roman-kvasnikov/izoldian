import os
import re
import shutil

import aiofiles
import yaml
from fastapi import APIRouter, HTTPException, Request

from auth import get_user_data_dir
from models import MoveRequest, NoteContent
from share import delete_token_for_note, update_token_path

router = APIRouter(prefix="/api/notes", tags=["notes"])


def get_user_id(request: Request) -> str:
    return request.state.user["id"]


def safe_path(user_id: str, path: str) -> str:
    """Resolve path safely within user's data directory."""
    base = os.path.realpath(get_user_data_dir(user_id))
    full = os.path.realpath(os.path.join(base, path))
    if not full.startswith(base):
        raise HTTPException(403, "Path traversal not allowed")
    return full


def build_file_tree(base_dir: str, rel_prefix: str = "") -> list[dict]:
    """Build hierarchical file tree for sidebar."""
    items = []
    try:
        entries = sorted(os.listdir(base_dir), key=lambda x: (not os.path.isdir(os.path.join(base_dir, x)), x.lower()))
    except FileNotFoundError:
        return items

    for entry in entries:
        if entry.startswith("."):
            continue
        full_path = os.path.join(base_dir, entry)
        rel_path = os.path.join(rel_prefix, entry) if rel_prefix else entry

        if os.path.isdir(full_path):
            children = build_file_tree(full_path, rel_path)
            items.append({
                "name": entry,
                "path": rel_path,
                "type": "folder",
                "children": children,
            })
        elif entry.endswith(".md"):
            items.append({
                "name": entry[:-3],  # Remove .md extension
                "path": rel_path,
                "type": "file",
            })
        else:
            ext = os.path.splitext(entry)[1].lower()
            MEDIA_EXTENSIONS = {
                ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
                ".pdf",
                ".mp3", ".wav", ".ogg", ".mp4", ".webm",
            }
            if ext in MEDIA_EXTENSIONS:
                items.append({
                    "name": entry,
                    "path": rel_path,
                    "type": "media",
                    "ext": ext,
                })
    return items


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                return meta, parts[2].lstrip("\n")
            except yaml.YAMLError:
                pass
    return {}, content


def extract_tags(content: str) -> list[str]:
    """Extract tags from frontmatter."""
    meta, _ = extract_frontmatter(content)
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    return [str(t) for t in tags if t]


def extract_wikilinks(content: str) -> list[str]:
    """Extract wikilink targets from content."""
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


@router.get("")
async def list_notes(request: Request):
    user_id = get_user_id(request)
    base = get_user_data_dir(user_id)
    os.makedirs(base, exist_ok=True)
    tree = build_file_tree(base)
    return {"tree": tree}


@router.get("/tags")
async def list_tags(request: Request):
    """Get all tags across user's notes."""
    user_id = get_user_id(request)
    base = get_user_data_dir(user_id)
    all_tags: dict[str, int] = {}

    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".md"):
                continue
            full = os.path.join(root, f)
            try:
                async with aiofiles.open(full, "r", encoding="utf-8") as fh:
                    content = await fh.read()
                for tag in extract_tags(content):
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            except Exception:
                continue

    return {"tags": [{"name": k, "count": v} for k, v in sorted(all_tags.items())]}


@router.get("/by-path/{path:path}")
async def get_note(path: str, request: Request):
    user_id = get_user_id(request)
    full_path = safe_path(user_id, path)

    if not os.path.isfile(full_path):
        raise HTTPException(404, "Note not found")

    async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
        content = await f.read()

    meta, body = extract_frontmatter(content)
    tags = extract_tags(content)
    wikilinks = extract_wikilinks(content)

    return {
        "path": path,
        "name": os.path.basename(path).replace(".md", ""),
        "content": content,
        "tags": tags,
        "wikilinks": wikilinks,
        "meta": meta,
    }


@router.post("/by-path/{path:path}")
async def save_note(path: str, body: NoteContent, request: Request):
    user_id = get_user_id(request)

    if not path.endswith(".md"):
        path += ".md"

    full_path = safe_path(user_id, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
        await f.write(body.content)

    return {"path": path, "ok": True}


@router.delete("/by-path/{path:path}")
async def delete_note(path: str, request: Request):
    user_id = get_user_id(request)
    full_path = safe_path(user_id, path)

    if not os.path.isfile(full_path):
        raise HTTPException(404, "Note not found")

    os.remove(full_path)
    delete_token_for_note(get_user_data_dir(user_id), path)
    return {"ok": True}


@router.post("/move")
async def move_note(body: MoveRequest, request: Request):
    user_id = get_user_id(request)
    src = safe_path(user_id, body.source)
    dst = safe_path(user_id, body.destination)

    if not os.path.exists(src):
        raise HTTPException(404, "Source not found")

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    update_token_path(get_user_data_dir(user_id), body.source, body.destination)
    return {"ok": True}
