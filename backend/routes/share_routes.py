import os
import re

import aiofiles
import yaml
import markdown
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import HTMLResponse

from auth import get_user_data_dir
from config import settings
from share import (
    create_share_token,
    get_all_shared_paths,
    get_note_by_token,
    get_share_info,
    revoke_share_token,
)

router = APIRouter(tags=["share"])


def get_user_id(request: Request) -> str:
    return request.state.user["id"]


# --- Authenticated endpoints ---

@router.post("/api/share/{note_path:path}")
async def share_note(note_path: str, request: Request):
    user_id = get_user_id(request)
    data_dir = get_user_data_dir(user_id)
    full_path = os.path.join(data_dir, note_path)
    if not os.path.exists(full_path):
        raise HTTPException(404, "Note not found")

    token = create_share_token(data_dir, note_path)
    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}/share/{token}"
    return {"success": True, "token": token, "url": url, "path": note_path}


@router.get("/api/share/info/{note_path:path}")
async def share_info(note_path: str, request: Request):
    user_id = get_user_id(request)
    data_dir = get_user_data_dir(user_id)
    info = get_share_info(data_dir, note_path)
    if info:
        base_url = str(request.base_url).rstrip("/")
        return {
            "shared": True,
            "token": info["token"],
            "url": f"{base_url}/share/{info['token']}",
            "created": info.get("created"),
        }
    return {"shared": False}


@router.get("/api/shared-notes")
async def list_shared_notes(request: Request):
    user_id = get_user_id(request)
    data_dir = get_user_data_dir(user_id)
    paths = get_all_shared_paths(data_dir)
    return {"paths": paths}


@router.delete("/api/share/{note_path:path}")
async def unshare_note(note_path: str, request: Request):
    user_id = get_user_id(request)
    data_dir = get_user_data_dir(user_id)
    ok = revoke_share_token(data_dir, note_path)
    if not ok:
        raise HTTPException(404, "Share not found")
    return {"success": True}


# --- Public endpoint (no auth) ---

@router.get("/share/{token}")
async def view_shared_note(token: str):
    result = get_note_by_token(token, settings.data_dir)
    if not result:
        raise HTTPException(404, "Shared note not found")

    data_dir, note_path = result
    full_path = os.path.join(data_dir, note_path)

    async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
        content = await f.read()

    # Strip frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()

    # Convert wikilinks to plain text links
    content = re.sub(
        r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
        lambda m: m.group(2) or m.group(1),
        content,
    )

    # Extract title from first heading or filename
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1) if title_match else note_path.replace(".md", "").split("/")[-1]

    # Render markdown to HTML
    md = markdown.Markdown(extensions=["fenced_code", "tables", "codehilite", "toc", "nl2br"])
    html_body = md.convert(content)

    # Build full page
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(title)} — Izoldian</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github-dark.min.css">
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/highlight.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #111827;
            color: #e5e7eb;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            font-size: 16px;
            line-height: 1.7;
            padding: 2rem;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: #1a1d23;
            border-radius: 12px;
            border: 1px solid #1f2937;
            padding: 2.5rem;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #1f2937;
        }}
        .header .brand {{
            font-size: 0.85rem;
            color: #6b7280;
        }}
        .header .brand a {{
            color: #3b82f6;
            text-decoration: none;
        }}
        h1 {{ font-size: 2em; font-weight: 700; margin: 0.8em 0 0.5em; color: #e5e7eb; border-bottom: 1px solid #1f2937; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; font-weight: 600; margin: 0.8em 0 0.4em; color: #e5e7eb; border-bottom: 1px solid #1f2937; padding-bottom: 0.2em; }}
        h3 {{ font-size: 1.25em; font-weight: 600; margin: 0.6em 0 0.3em; color: #e5e7eb; }}
        h4, h5, h6 {{ font-weight: 600; margin: 0.5em 0 0.25em; color: #9ca3af; }}
        p {{ margin: 0.5em 0; }}
        a {{ color: #3b82f6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        code {{
            background: #1f2937;
            padding: 0.15em 0.4em;
            border-radius: 4px;
            font-size: 0.9em;
            color: #f472b6;
        }}
        pre {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 8px;
            padding: 1em;
            overflow-x: auto;
            margin: 0.8em 0;
        }}
        pre code {{
            background: none;
            padding: 0;
            color: #e5e7eb;
            font-size: 0.875em;
        }}
        blockquote {{
            border-left: 3px solid #3b82f6;
            padding-left: 1em;
            margin: 0.5em 0;
            color: #9ca3af;
        }}
        ul, ol {{ padding-left: 1.5em; margin: 0.5em 0; }}
        ul {{ list-style-type: disc; }}
        ol {{ list-style-type: decimal; }}
        li {{ margin: 0.2em 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 0.8em 0; }}
        th, td {{ border: 1px solid #1f2937; padding: 0.5em 0.75em; text-align: left; }}
        th {{ background: #1f2937; font-weight: 600; }}
        img {{ max-width: 100%; border-radius: 8px; margin: 0.5em 0; }}
        hr {{ border: none; border-top: 1px solid #1f2937; margin: 1.5em 0; }}
        input[type="checkbox"] {{ margin-right: 0.5em; accent-color: #3b82f6; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">Shared via <a href="/">Izoldian</a></div>
        </div>
        {html_body}
    </div>
    <script>hljs.highlightAll();</script>
</body>
</html>"""
    return HTMLResponse(html)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
