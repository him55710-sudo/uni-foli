from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

PYTHONPATH_SEGMENTS = [
    BACKEND_ROOT / "services" / "api" / "src",
    BACKEND_ROOT / "services" / "ingest" / "src",
    BACKEND_ROOT / "services" / "render" / "src",
    BACKEND_ROOT / "services" / "worker" / "src",
    BACKEND_ROOT / "packages" / "domain" / "src",
    BACKEND_ROOT / "packages" / "shared" / "src",
]

for segment in PYTHONPATH_SEGMENTS:
    segment_text = str(segment)
    if segment_text not in sys.path:
        sys.path.insert(0, segment_text)


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "polio-smoke.db"
    os.environ["APP_ENV"] = "local"
    os.environ["APP_DEBUG"] = "false"
    os.environ["AUTH_ALLOW_LOCAL_DEV_BYPASS"] = "true"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["DATABASE_AUTO_CREATE_TABLES"] = "true"
    os.environ["POSTGRES_ENABLE_PGVECTOR"] = "false"
    os.environ["CORS_ORIGINS"] = "http://localhost:3001 http://127.0.0.1:3001"

    from polio_api.core.config import get_settings

    get_settings.cache_clear()

    from polio_api.main import create_app

    return TestClient(create_app())
