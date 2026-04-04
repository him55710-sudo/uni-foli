from __future__ import annotations

from functools import lru_cache
import os
import re
from typing import Annotated
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from polio_shared.paths import find_project_root, resolve_runtime_path


class Settings(BaseSettings):
    app_name: str = "polio Backend"
    app_env: str = "production"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = False
    api_prefix: str = "/api/v1"
    api_docs_enabled: bool = False
    database_url: str = "sqlite:///./storage/runtime/polio.db?check_same_thread=False&timeout=30"
    database_echo: bool = False
    database_auto_create_tables: bool = True
    postgres_enable_pgvector: bool = True
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3001"]
    )
    cors_origin_regex: str | None = None
    cors_allow_credentials: bool = True
    allow_inline_render: bool = True
    auto_ingest_uploads: bool = True
    upload_max_bytes: int = 50 * 1024 * 1024
    upload_allowed_extensions: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [".pdf", ".txt", ".md"]
    )
    upload_chunk_size_chars: int = 1200
    upload_chunk_overlap_chars: int = 180
    opendataloader_enabled: bool = True
    opendataloader_default_mode: str = "heuristic"
    opendataloader_hybrid_ocr_enabled: bool = True
    opendataloader_annotate_pdf: bool = False
    vector_dimensions: int = 1536
    retrieval_candidate_pool_size: int = 24
    retrieval_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    retrieval_reranker_enabled: bool = True
    retrieval_reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    grounded_answer_top_k: int = 4
    grounded_answer_min_similarity: float = 0.15
    grounded_answer_min_lexical_overlap: float = 0.08
    semantic_scholar_search_url: str = "https://api.semanticscholar.org/graph/v1/paper/search"
    semantic_scholar_timeout_seconds: float = 10.0
    semantic_scholar_api_key: str | None = None
    semantic_scholar_max_limit: int = 10
    kci_api_key: str | None = None
    research_fetch_max_bytes: int = 2 * 1024 * 1024
    llm_cache_enabled: bool = True
    llm_cache_ttl_seconds: int = 21600
    llm_cache_version: str = "2026-03-29"
    prompt_asset_root: str | None = None
    prompt_registry_path: str | None = None
    async_job_max_retries: int = 2
    async_job_retry_delay_seconds: int = 15
    async_job_stale_after_seconds: int = 300
    async_jobs_inline_dispatch: bool = True
    allow_inline_job_processing: bool = True
    serverless_runtime: bool = Field(default_factory=lambda: os.getenv("VERCEL") == "1")
    
    # Social Auth
    kakao_client_id: str = "DUMMY_KAKAO_ID"
    kakao_redirect_uri: str = "http://localhost:3001/auth/callback/kakao"
    naver_client_id: str = "DUMMY_NAVER_ID"
    naver_client_secret: str = "DUMMY_NAVER_SECRET"
    naver_redirect_uri: str = "http://localhost:3001/auth/callback/naver"
    google_client_id: str = "DUMMY_GOOGLE_ID"
    google_client_secret: str = "DUMMY_GOOGLE_SECRET"
    google_redirect_uri: str = "http://localhost:3001/auth/callback/google"
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_secret: str | None = None
    auth_jwt_public_key: str | None = None
    auth_jwt_issuer: str | None = None
    auth_jwt_audience: str | None = None
    auth_token_leeway_seconds: int = 30
    auth_allow_local_dev_bypass: bool = False
    auth_firebase_fallback_enabled: bool = True
    auth_social_login_enabled: bool = False
    auth_social_state_secret: str | None = None
    auth_social_state_ttl_seconds: int = 600

    # LLM Settings
    llm_provider: str = Field(default="gemini", description="LLM provider: 'gemini' or 'ollama'")
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"
    ollama_timeout_seconds: float = 90.0
    ollama_keep_alive: str = "30m"
    ollama_num_ctx: int = 2048
    ollama_num_predict: int = 512
    ollama_num_thread: int | None = None

    model_config = SettingsConfigDict(
        env_file=(
            str(find_project_root() / ".env"),
            str(find_project_root().parent / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            # Accept comma, semicolon, or whitespace separated origin lists.
            return [item.strip() for item in re.split(r"[,\s;]+", value) if item.strip()]
        return value

    @field_validator("upload_allowed_extensions", mode="before")
    @classmethod
    def split_upload_allowed_extensions(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[,\s;]+", value) if item.strip()]
        return value

    @field_validator("upload_allowed_extensions", mode="after")
    @classmethod
    def normalize_upload_allowed_extensions(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            cleaned = item.strip().lower()
            if not cleaned:
                continue
            if not cleaned.startswith("."):
                cleaned = f".{cleaned}"
            if cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)
        return normalized or [".pdf", ".txt", ".md"]

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_sqlite_path(cls, value: str) -> str:
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            relative_path, separator, query = value.removeprefix(prefix).partition("?")
            absolute_path = resolve_runtime_path(relative_path).as_posix()
            suffix = f"{separator}{query}" if separator else ""
            return f"sqlite:///{absolute_path}{suffix}"
        return value

    @model_validator(mode="after")
    def validate_security_posture(self) -> "Settings":
        normalized_env = (self.app_env or "").strip().lower()
        object.__setattr__(self, "app_env", normalized_env or "production")

        if self.upload_max_bytes <= 0:
            raise ValueError("UPLOAD_MAX_BYTES must be greater than zero.")
        if self.research_fetch_max_bytes <= 0:
            raise ValueError("RESEARCH_FETCH_MAX_BYTES must be greater than zero.")

        if self.auth_social_login_enabled and not self.auth_social_state_secret:
            raise ValueError("AUTH_SOCIAL_STATE_SECRET is required when AUTH_SOCIAL_LOGIN_ENABLED=true.")

        if self.app_env != "local":
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false outside local development.")
            if self.auth_allow_local_dev_bypass:
                raise ValueError("AUTH_ALLOW_LOCAL_DEV_BYPASS can only be enabled when APP_ENV=local.")
            if self.cors_allow_credentials and "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origins cannot be combined with credentialed requests.")
            if self.cors_allow_credentials and self.cors_origin_regex:
                normalized_regex = self.cors_origin_regex.strip()
                if normalized_regex in {"*", ".*", "^.*$", "https?://.*", "https?://.*$"}:
                    raise ValueError("Wildcard CORS origin regex is not allowed with credentials outside local development.")
            if self.auth_social_login_enabled:
                redirect_uris: list[tuple[str, str]] = []
                if _oauth_provider_is_configured(self.kakao_client_id):
                    redirect_uris.append(("kakao", self.kakao_redirect_uri))
                if _oauth_provider_is_configured(self.naver_client_id, self.naver_client_secret):
                    redirect_uris.append(("naver", self.naver_redirect_uri))
                if _oauth_provider_is_configured(self.google_client_id, self.google_client_secret):
                    redirect_uris.append(("google", self.google_redirect_uri))
                for provider, redirect_uri in redirect_uris:
                    if _is_local_redirect(redirect_uri):
                        raise ValueError(
                            f"{provider.upper()} redirect URI must not target localhost outside local development."
                        )

        return self


def _oauth_provider_is_configured(client_id: str | None, client_secret: str | None = None) -> bool:
    def _is_real(value: str | None) -> bool:
        normalized = (value or "").strip()
        return bool(normalized) and not normalized.startswith("DUMMY_")

    if not _is_real(client_id):
        return False
    if client_secret is None:
        return True
    return _is_real(client_secret)


def _is_local_redirect(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "::1"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
