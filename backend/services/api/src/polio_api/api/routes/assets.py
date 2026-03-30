from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from polio_shared.paths import get_runtime_root, slugify

router = APIRouter()

LOGO_BASE_DIR = (get_runtime_root() / "university-logos").resolve()
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def _find_logo_path(name: str) -> Path | None:
    raw_name = name.strip()
    if "/" in raw_name or "\\" in raw_name or ".." in raw_name:
        raise HTTPException(status_code=400, detail="University name is invalid.")

    normalized_name = slugify(name)
    if normalized_name in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="University name is invalid.")

    if not LOGO_BASE_DIR.exists():
        return None

    for file_path in LOGO_BASE_DIR.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in ALLOWED_LOGO_EXTENSIONS:
            continue
        if slugify(file_path.stem) != normalized_name:
            continue
        resolved = file_path.resolve()
        if resolved.parent != LOGO_BASE_DIR:
            continue
        return resolved
    return None


@router.get("/univ-logo")
async def get_univ_logo(name: str):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="University name is required.")

    file_path = _find_logo_path(name)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Logo not found.")

    return FileResponse(
        file_path,
        headers={"Cache-Control": "public, max-age=86400"},
    )
