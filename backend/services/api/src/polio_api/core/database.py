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
    from polio_api.db.models import (  # noqa: F401
        async_job,
        blueprint,
        citation,
        diagnosis_run,
        document_chunk,
        draft,
        inquiry,
        llm_cache_entry,
        parsed_document,
        payment_order,
        policy_flag,
        project,
        quest,
        research_chunk,
        research_document,
        render_job,
        response_trace,
        review_task,
        upload_asset,
        user,
        workshop,
    )

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
            "interest_universities": "interest_universities JSON",
        },
        "projects": {
            "owner_user_id": "owner_user_id VARCHAR(36)",
            "discussion_log": "discussion_log TEXT",
        },
        "blueprints": {
            "headline": "headline VARCHAR(500)",
            "recommended_focus": "recommended_focus TEXT",
        },
        "parsed_documents": {
            "status": "status VARCHAR(32) DEFAULT 'uploaded' NOT NULL",
            "masking_status": "masking_status VARCHAR(32) DEFAULT 'pending' NOT NULL",
            "parse_attempts": "parse_attempts INTEGER DEFAULT 0 NOT NULL",
            "last_error": "last_error TEXT",
            "parse_started_at": "parse_started_at DATETIME",
            "parse_completed_at": "parse_completed_at DATETIME",
        },
        "workshop_sessions": {
            "quality_level": "quality_level VARCHAR(8) DEFAULT 'mid' NOT NULL",
            "stream_token": "stream_token VARCHAR(128)",
            "stream_token_expires_at": "stream_token_expires_at DATETIME",
        },
        "workshop_turns": {
            "speaker_role": "speaker_role VARCHAR(32) DEFAULT 'user' NOT NULL",
            "action_payload": "action_payload JSON",
        },
        "draft_artifacts": {
            "quality_level_applied": "quality_level_applied VARCHAR(8)",
            "safety_score": "safety_score INTEGER",
            "safety_flags": "safety_flags JSON",
            "quality_downgraded": "quality_downgraded BOOLEAN DEFAULT 0 NOT NULL",
            "quality_control_meta": "quality_control_meta JSON",
            "visual_specs": "visual_specs JSON DEFAULT '[]' NOT NULL",
            "math_expressions": "math_expressions JSON DEFAULT '[]' NOT NULL",
        },
        "research_documents": {
            "source_classification": "source_classification VARCHAR(32) DEFAULT 'EXPERT_COMMENTARY' NOT NULL",
            "trust_rank": "trust_rank INTEGER DEFAULT 0 NOT NULL",
            "usage_note": "usage_note TEXT",
            "copyright_note": "copyright_note TEXT",
        },
        "render_jobs": {
            "template_id": "template_id VARCHAR(80)",
            "include_provenance_appendix": "include_provenance_appendix BOOLEAN DEFAULT 0 NOT NULL",
            "hide_internal_provenance_on_final_export": "hide_internal_provenance_on_final_export BOOLEAN DEFAULT 1 NOT NULL",
        },
        "async_jobs": {
            "progress_stage": "progress_stage VARCHAR(64)",
            "progress_message": "progress_message TEXT",
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
