from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from polio_api.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    future=True,
    echo=settings.database_echo,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def initialize_database() -> None:
    from polio_api.db.models import document_chunk, draft, parsed_document, project, render_job, upload_asset, user  # noqa: F401

    if engine.dialect.name == "postgresql" and settings.postgres_enable_pgvector:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    _apply_schema_evolution()


def _apply_schema_evolution() -> None:
    inspector = inspect(engine)
    table_columns = {
        "users": {
            "target_university": "target_university VARCHAR(200)",
            "target_major": "target_major VARCHAR(200)",
        },
        "projects": {
            "discussion_log": "discussion_log TEXT",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in table_columns.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
