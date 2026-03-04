import json
import os

from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/locales", tags=["locales"])

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "locales")


@router.get("")
async def list_locales():
    locales = []
    locales_dir = os.path.realpath(LOCALES_DIR)
    if not os.path.isdir(locales_dir):
        return {"locales": []}

    for fname in sorted(os.listdir(locales_dir)):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(locales_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("_meta", {})
        locales.append({
            "code": meta.get("code", fname[:-5]),
            "name": meta.get("name", fname[:-5]),
            "flag": meta.get("flag", ""),
        })
    return {"locales": locales}


@router.get("/{locale_code}")
async def get_locale(locale_code: str):
    locales_dir = os.path.realpath(LOCALES_DIR)
    filepath = os.path.join(locales_dir, f"{locale_code}.json")
    if not os.path.isfile(filepath):
        raise HTTPException(404, "Locale not found")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)
