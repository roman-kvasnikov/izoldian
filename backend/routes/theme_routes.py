import os
import re

from fastapi import APIRouter, HTTPException
from starlette.responses import Response

router = APIRouter(prefix="/api/themes", tags=["themes"])

THEMES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "themes")


def parse_theme_meta(filepath: str) -> dict:
    """Parse theme metadata from CSS comments."""
    meta = {"type": "dark", "hljs": "github-dark"}
    with open(filepath, "r", encoding="utf-8") as f:
        head = f.read(500)
    m = re.search(r"@theme-type:\s*(\w+)", head)
    if m:
        meta["type"] = m.group(1)
    m = re.search(r"@hljs:\s*([\w-]+)", head)
    if m:
        meta["hljs"] = m.group(1)
    return meta


@router.get("")
async def list_themes():
    themes = []
    themes_dir = os.path.realpath(THEMES_DIR)
    if not os.path.isdir(themes_dir):
        return {"themes": []}

    for fname in sorted(os.listdir(themes_dir)):
        if not fname.endswith(".css"):
            continue
        theme_id = fname[:-4]
        meta = parse_theme_meta(os.path.join(themes_dir, fname))
        # Human-readable name from id
        name = theme_id.replace("-", " ").title()
        themes.append({
            "id": theme_id,
            "name": name,
            "type": meta["type"],
            "hljs": meta["hljs"],
        })
    return {"themes": themes}


@router.get("/{theme_id}")
async def get_theme_css(theme_id: str):
    themes_dir = os.path.realpath(THEMES_DIR)
    filepath = os.path.join(themes_dir, f"{theme_id}.css")
    if not os.path.isfile(filepath):
        raise HTTPException(404, "Theme not found")

    with open(filepath, "r", encoding="utf-8") as f:
        css = f.read()
    return Response(content=css, media_type="text/css")
