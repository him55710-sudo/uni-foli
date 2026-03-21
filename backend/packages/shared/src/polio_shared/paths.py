from __future__ import annotations

from pathlib import Path
import re


def find_project_root() -> Path:
    search_points = [Path.cwd(), Path(__file__).resolve()]

    for start in search_points:
        for candidate in [start, *start.parents]:
            if (candidate / "pyproject.toml").exists():
                return candidate

    raise RuntimeError("Could not find the polio-backend project root.")


def get_storage_root() -> Path:
    return find_project_root() / "storage"


def get_upload_root() -> Path:
    return get_storage_root() / "uploads"


def get_export_root() -> Path:
    return get_storage_root() / "exports"


def get_runtime_root() -> Path:
    return get_storage_root() / "runtime"


def get_tmp_root() -> Path:
    return find_project_root() / "tmp"


def ensure_app_directories() -> None:
    for path in [get_storage_root(), get_upload_root(), get_export_root(), get_runtime_root(), get_tmp_root()]:
        path.mkdir(parents=True, exist_ok=True)


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return find_project_root() / path


def resolve_stored_path(stored_path: str) -> Path:
    path = Path(stored_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "storage":
        return find_project_root() / path
    return get_storage_root() / path


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^\w\s-]", "", lowered)
    lowered = re.sub(r"[-\s]+", "-", lowered)
    return lowered or "item"
