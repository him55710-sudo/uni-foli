from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.enums import PrivacyMaskingMode


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Polio Admissions Intelligence Backend"
    app_env: str = "local"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    auth_enabled: bool = True
    auth_bootstrap_default_accounts: bool = True
    auth_default_tenant_slug: str = "local-lab"
    auth_default_tenant_name: str = "Local Lab"
    auth_default_admin_email: str = "admin@local.polio"
    auth_default_admin_password: str = "ChangeMe123!"
    auth_default_reviewer_email: str = "reviewer@local.polio"
    auth_default_reviewer_password: str = "ChangeMe123!"
    auth_default_member_email: str = "member@local.polio"
    auth_default_member_password: str = "ChangeMe123!"
    auth_session_ttl_minutes: int = 720

    database_url: str = "sqlite:///./storage/runtime/polio_admissions.db"
    database_echo: bool = False
    database_auto_create_tables: bool = True
    postgres_enable_pgvector: bool = True

    redis_url: str = "redis://127.0.0.1:6379/0"
    object_storage_provider: str = "local"
    object_storage_bucket: str = "polio"
    object_storage_endpoint: str = "http://127.0.0.1:9000"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    local_object_store_path: str = "./storage/object-store"

    ollama_base_url: str = "http://127.0.0.1:11434"
    extraction_model_provider: str = "ollama"
    extraction_model_name: str = "llama3.1:8b"
    extraction_model_api_base: str | None = None
    extraction_model_api_key: str | None = None
    extraction_timeout_seconds: int = 90
    extraction_max_retries: int = 2
    extraction_retry_backoff_seconds: float = 1.5
    extraction_batch_size: int = 4
    extraction_prompt_key: str = "claim_extraction_v2"
    vector_dimensions: int = 1536
    retrieval_candidate_pool_size: int = 40
    retrieval_lexical_weight: float = 0.34
    retrieval_vector_weight: float = 0.26
    retrieval_trust_weight: float = 0.14
    retrieval_quality_weight: float = 0.10
    retrieval_freshness_weight: float = 0.08
    retrieval_official_document_boost: float = 0.08
    retrieval_current_cycle_boost: float = 0.08
    retrieval_approved_claim_boost: float = 0.08
    retrieval_direct_rule_boost: float = 0.04
    retrieval_conflict_penalty_weight: float = 0.18
    retrieval_stale_penalty_weight: float = 0.08
    retrieval_low_trust_penalty_weight: float = 0.10
    retrieval_freshness_threshold: float = 0.55
    retrieval_embedding_provider: str = "hashing"
    retrieval_embedding_model: str = "hashing-1536"
    retrieval_embedding_api_base: str | None = None
    retrieval_embedding_api_key: str | None = None
    retrieval_reranker_enabled: bool = False
    retrieval_reranker_provider: str = "none"
    retrieval_reranker_model: str | None = None
    stale_after_days: int = 180
    default_owner_key: str = "local-dev"
    crawler_user_agent: str = "PolioAdmissionsCrawler/0.1 (+https://github.com/him55710-sudo/polio)"
    crawler_timeout_seconds: int = 20
    crawler_max_pages_per_job: int = 25
    crawler_respect_robots_by_default: bool = True
    docling_enabled: bool = True
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str | None = None
    langfuse_environment: str = "local"
    langfuse_release: str | None = None
    privacy_default_masking_mode: PrivacyMaskingMode = PrivacyMaskingMode.MASK_FOR_INDEX
    privacy_log_masking_enabled: bool = True
    student_data_retention_days: int = 365
    presidio_enabled: bool = True
    presidio_helper_python: str | None = None
    presidio_helper_timeout_seconds: int = 12
    presidio_allow_regex_fallback: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url", "local_object_store_path", mode="after")
    @classmethod
    def normalize_relative_paths(cls, value: str, info: object) -> str:
        if not isinstance(value, str):
            return value
        if info.field_name == "database_url" and value.startswith("sqlite:///./"):
            relative_path = value.removeprefix("sqlite:///./")
            return f"sqlite:///{(PROJECT_ROOT / relative_path).as_posix()}"
        if info.field_name == "local_object_store_path" and value.startswith("./"):
            return str((PROJECT_ROOT / value[2:]).resolve())
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
