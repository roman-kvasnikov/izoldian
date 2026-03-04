import os
import re

import aiofiles
from fastapi import APIRouter, Request

from auth import get_user_data_dir

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
async def get_graph(request: Request):
    user_id = request.state.user["id"]
    base = get_user_data_dir(user_id)

    nodes = []
    edges = []
    note_paths = {}  # name -> path mapping for link resolution

    # Collect all notes
    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".md"):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base)
            name = f[:-3]
            note_paths[name.lower()] = rel_path
            nodes.append({"id": rel_path, "label": name})

    # Build edges from wikilinks
    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".md"):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base)

            try:
                async with aiofiles.open(full_path, "r", encoding="utf-8") as fh:
                    content = await fh.read()
            except Exception:
                continue

            # Extract wikilinks
            wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
            for link in wikilinks:
                target = link.strip().lower()
                if target in note_paths:
                    edges.append({
                        "from": rel_path,
                        "to": note_paths[target],
                        "type": "wikilink",
                    })

            # Extract markdown links to local .md files
            md_links = re.findall(r"\[([^\]]+)\]\(([^)]+\.md)\)", content)
            for _, href in md_links:
                if not href.startswith("http"):
                    # Resolve relative to current note's directory
                    note_dir = os.path.dirname(rel_path)
                    resolved = os.path.normpath(os.path.join(note_dir, href))
                    if resolved in [n["id"] for n in nodes]:
                        edges.append({
                            "from": rel_path,
                            "to": resolved,
                            "type": "markdown",
                        })

    return {"nodes": nodes, "edges": edges}
