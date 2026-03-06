import os
import re

import aiofiles
from fastapi import APIRouter, HTTPException, Query, Request

from auth import get_user_data_dir

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search_notes(request: Request, q: str = Query(min_length=1)):
    user_id = request.state.user["id"]
    base = get_user_data_dir(user_id)
    results = []

    try:
        pattern = re.compile(re.escape(q), re.IGNORECASE)
    except re.error:
        raise HTTPException(400, "Invalid search query")

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != "_templates"]
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

            matches = list(pattern.finditer(content))
            if not matches:
                continue

            # Build context snippets
            snippets = []
            for match in matches[:5]:  # Max 5 snippets per file
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                snippet = content[start:end].replace("\n", " ").strip()
                snippets.append(snippet)

            results.append({
                "path": rel_path,
                "name": f[:-3],
                "matches": len(matches),
                "snippets": snippets,
            })

    results.sort(key=lambda x: x["matches"], reverse=True)
    return {"results": results, "query": q}
