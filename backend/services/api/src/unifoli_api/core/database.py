from __future__ import annotations

from datetime import datetime, timezone
import logging
import os

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


def _build_engine_kwargs(current_settings) -> dict[str, object]:
    engine_kwargs: dict[str, object] = {
        "echo": current_settings.database_echo,
        "future": True,
        "pool_pre_ping": True,
    }

    if current_settings.database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        return engine_kwargs

    # PostgreSQL specific pool tuning. Serverless pools stay small, but need a
    # little overflow so a long inline parse/diagnosis request does not starve
    # auth or status polling requests in the same warm function instance.
    if current_settings.serverless_runtime:
        engine_kwargs["pool_size"] = max(1, int(current_settings.database_serverless_pool_size))
        engine_kwargs["max_overflow"] = max(0, int(current_settings.database_serverless_max_overflow))
    else:
        engine_kwargs["pool_size"] = current_settings.database_pool_size
        engine_kwargs["max_overflow"] = current_settings.database_max_overflow
    engine_kwargs["pool_timeout"] = float(current_settings.database_pool_timeout_seconds)
    return engine_kwargs


engine_kwargs = _build_engine_kwargs(settings)
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
            logger.error(
                "Database schema revision mismatch in strict runtime. current_revisions=%s head_revisions=%s "
                "has_app_tables=%s script_location=%s",
                sorted(current_revisions),
                sorted(head_revisions),
                has_app_tables,
                str(find_project_root() / "alembic"),
            )
            if not has_app_tables:
                raise RuntimeError(
                    "Database schema has not been initialized. "
                    "Run `backend/scripts/migrate.cmd` or `alembic upgrade head` before starting the service."
                )
            raise RuntimeError(
                "Database schema is not at Alembic head. "
                "Run `backend/scripts/migrate.cmd` or `alembic upgrade head` before starting the service."
            )

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
