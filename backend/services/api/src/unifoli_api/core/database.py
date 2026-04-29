from __future__ import annotations

from datetime import datetime, timezone
import logging

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from unifoli_api.core.config import get_settings
from unifoli_shared.paths import find_project_root


def utc_now() -> datetime:
    """Returns a naive UTC datetime for internal database operations."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


settings = get_settings()
logger = logging.getLogger("unifoli.api.database")

# Build engine arguments
engine_kwargs = {
    "echo": settings.database_echo,
    "future": True,
    "pool_pre_ping": True,
}

if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL specific pool tuning
    # In serverless, we keep pools very small to avoid "Too many connections" errors
    # as each lambda instance creates its own pool.
    if settings.serverless_runtime:
        engine_kwargs["pool_size"] = 1
        engine_kwargs["max_overflow"] = 0
    else:
        engine_kwargs["pool_size"] = settings.database_pool_size
        engine_kwargs["max_overflow"] = settings.database_max_overflow

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
_APPLICATION_TABLES: tuple[str, ...] = (
    "projects",
    "upload_assets",
    "parsed_documents",
    "async_jobs",
    "diagnosis_runs",
    "diagnosis_report_artifacts",
)


def initialize_database() -> None:
    _import_models()
    _ensure_postgres_extensions()
    _ensure_schema_is_ready()


def _import_models() -> None:
    from unifoli_api.db import models  # noqa: F401


def _ensure_postgres_extensions() -> None:
    if engine.dialect.name == "postgresql" and settings.postgres_enable_pgvector:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _ensure_schema_is_ready() -> None:
    inspector = inspect(engine)
    current_revisions = _current_alembic_revisions(inspector)
    head_revisions = _alembic_head_revisions()
    if current_revisions == head_revisions:
        return

    has_app_tables = any(inspector.has_table(table_name) for table_name in _APPLICATION_TABLES)
    if settings.database_auto_create_tables:
        # Detect strict runtime (Vercel production/preview)
        vercel_env = (os.getenv("VERCEL_ENV") or "").strip().lower()
        is_strict_runtime = settings.serverless_runtime or vercel_env in {"production", "preview"}

        if is_strict_runtime and settings.app_env != "local":
            logger.warning(
                "Skipping automatic migrations in strict serverless production/preview to avoid race conditions. "
                "Run migrations during deployment or via manual admin trigger."
            )
            return

        logger.info(
            "Auto-applying Alembic migrations at startup. current_revisions=%s head_revisions=%s",
            sorted(current_revisions),
            sorted(head_revisions),
        )
        _upgrade_database_to_head()
        return

    if not has_app_tables and settings.database_auto_create_tables:
        raise RuntimeError(
            "Database schema has not been initialized. "
            "Run `backend/scripts/migrate.cmd` or `alembic upgrade head` before starting the service."
        )

    raise RuntimeError(
        "Database schema is not at Alembic head. "
        "Run `backend/scripts/migrate.cmd` or `alembic upgrade head` before starting the service."
    )


def _alembic_config() -> Config:
    backend_root = find_project_root()
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def _alembic_head_revisions() -> set[str]:
    script = ScriptDirectory.from_config(_alembic_config())
    return {revision for revision in script.get_heads() if revision}


def _current_alembic_revisions(inspector) -> set[str]:
    if not inspector.has_table("alembic_version"):
        return set()

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version"))
        return {str(row[0]).strip() for row in rows if str(row[0]).strip()}


def _upgrade_database_to_head() -> None:
    command.upgrade(_alembic_config(), "head")
