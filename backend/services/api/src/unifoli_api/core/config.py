from __future__ import annotations

from functools import lru_cache
import logging
import os
import re
from typing import Annotated
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from unifoli_shared.paths import find_project_root, resolve_runtime_path

logger = logging.getLogger("unifoli.api.config")


class Settings(BaseSettings):
    app_name: str = "Uni Foli Backend"
    app_env: str = "production"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = False
    app_cron_secret: str | None = None
    api_prefix: str = "/api/v1"
    api_docs_enabled: bool = False
    api_root_redirect_enabled: bool = True
    public_app_base_url: str = "https://uni-foli.vercel.app/app"
    database_url: str = "sqlite:///./storage/runtime/unifoli.db?check_same_thread=False&timeout=30"
    database_echo: bool = False
    database_auto_create_tables: bool = True
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: float = 30.0
    database_serverless_pool_size: int = 1
    database_serverless_max_overflow: int = 4
    allow_production_sqlite: bool = False
    postgres_enable_pgvector: bool = True
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "https://uni-foli.vercel.app",
        ]
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
    neis_ensemble_enabled: bool = True
    neis_auto_detect_enabled: bool = True
    neis_auto_detect_min_confidence: float = 0.62
    neis_extractpdf4j_enabled: bool = False
    neis_extractpdf4j_base_url: str | None = None
    neis_extractpdf4j_timeout_seconds: float = 8.0
    neis_dedoc_enabled: bool = True
    neis_provider_min_quality_score: float = 0.58
    neis_merge_policy: str = "conservative_table"
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
    live_web_search_enabled: bool = True
    live_web_search_provider: str = "none"  # none | serpapi
    live_web_search_api_key: str | None = None
    live_web_search_endpoint: str = "https://serpapi.com/search.json"
    live_web_search_timeout_seconds: float = 12.0
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
    auth_session_ttl_minutes: int = 720
    auth_token_leeway_seconds: int = 30
    auth_allow_local_dev_bypass: bool = False
    auth_firebase_fallback_enabled: bool = True
    auth_social_login_enabled: bool = False
    auth_social_state_secret: str | None = None
    auth_social_state_ttl_seconds: int = 600
    admin_emails: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["him55710@gmail.com"],
        validation_alias=AliasChoices("ADMIN_EMAILS", "UNIFOLI_ADMIN_EMAILS"),
    )
    firebase_project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FIREBASE_PROJECT_ID", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"),
    )
    google_application_credentials: str | None = None
    firebase_service_account_json: str | None = None
    firebase_service_account_json_base64: str | None = None
    toss_payments_enabled: bool = False
    toss_payments_client_key: str | None = None
    toss_payments_secret_key: str | None = None
    toss_payments_frontend_base_url: str = "http://localhost:3001"
    toss_plan_plus_amount: int = 5900
    toss_plan_pro_amount: int = 9900
    docling_enabled: bool = True
    gemini_genai_enabled: bool = False

    # Crawl4AI Settings
    crawl4ai_enabled: bool = False
    research_crawl_max_pages: int = 3
    research_crawl_max_chars_per_page: int = 5000
    research_crawl_timeout_seconds: float = 12.0

    # Storage Settings
    unifoli_storage_provider: str = Field(
        default="local",
        validation_alias=AliasChoices("UNIFOLI_STORAGE_PROVIDER", "OBJECT_STORAGE_PROVIDER"),
        description="Storage provider: 'local' or 's3'",
    )
    unifoli_storage_root: str | None = Field(
        default=None,
        validation_alias=AliasChoices("UNIFOLI_STORAGE_ROOT", "LOCAL_OBJECT_STORE_PATH"),
    )
    s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_ENDPOINT_URL", "OBJECT_STORAGE_ENDPOINT"),
    )
    s3_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_ACCESS_KEY_ID", "OBJECT_STORAGE_ACCESS_KEY"),
    )
    s3_secret_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_SECRET_ACCESS_KEY", "OBJECT_STORAGE_SECRET_KEY"),
    )
    s3_bucket_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_BUCKET_NAME", "OBJECT_STORAGE_BUCKET"),
    )
    s3_region_name: str | None = None
    gcs_bucket_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GCS_BUCKET_NAME", "FIREBASE_STORAGE_BUCKET", "VITE_FIREBASE_STORAGE_BUCKET"),
    )
    blob_read_write_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN"),
    )
    vercel_blob_access: str = "private"

    # LLM Settings
    llm_provider: str = Field(default="gemini", description="LLM provider: 'gemini' or 'ollama'")
    llm_provider_fallback_enabled: bool = False
    guided_chat_llm_provider: str | None = None
    diagnosis_llm_provider: str | None = None
    render_llm_provider: str | None = None
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GENAI_API_KEY",
            "GEMINI_KEY",
        ),
    )
    gemini_model: str = "gemini-2.5-flash-lite"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "gemma4"
    ollama_timeout_seconds: float = 90.0
    ollama_keep_alive: str = "30m"
    ollama_num_ctx: int = 2048
    gemini_max_retries: int = 3
    gemini_retry_initial_delay_seconds: float = 1.0
    gemini_retry_max_delay_seconds: float = 8.0
    gemini_retry_jitter_enabled: bool = True
    ollama_num_predict: int = 512
    ollama_num_thread: int | None = None
    ollama_fast_model: str | None = None
    ollama_standard_model: str | None = None
    ollama_render_model: str | None = None
    ollama_fast_timeout_seconds: float | None = None
    ollama_standard_timeout_seconds: float | None = None
    ollama_render_timeout_seconds: float | None = None
    workshop_chat_timeout_seconds: float = 60.0
    diagnosis_generation_timeout_seconds: float = 45.0
    pdf_analysis_llm_enabled: bool = True
    pdf_analysis_llm_provider: str = "gemini"
    pdf_analysis_gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PDF_ANALYSIS_GEMINI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GENAI_API_KEY",
            "GEMINI_KEY",
        ),
    )
    pdf_analysis_gemini_model: str | None = None
    pdf_analysis_ollama_base_url: str | None = None
    pdf_analysis_ollama_model: str = "gemma4"
    pdf_analysis_timeout_seconds: float = 60.0
    pdf_analysis_keep_alive: str = "15m"
    pdf_analysis_num_ctx: int = 3072
    pdf_analysis_num_predict: int = 512
    pdf_analysis_num_thread: int | None = None
    
    # LLM Input Budget Settings
    diagnosis_llm_max_input_chars: int = 120000
    pdf_analysis_max_input_chars: int = 60000
    semantic_extraction_max_input_chars: int = 80000
    gemini_max_output_tokens: int = 4096

    # SMTP Settings
    smtp_enabled: bool = False
    smtp_server: str = "smtp.naver.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_receiver_email: str = "mongben@naver.com"

    model_config = SettingsConfigDict(
        env_file=(
            str(find_project_root().parent / ".env"),
            str(find_project_root() / ".env"),
            str(find_project_root() / "backend" / ".env"),
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

    @field_validator("admin_emails", mode="before")
    @classmethod
    def split_admin_emails(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[,\s;]+", value) if item.strip()]
        return value

    @field_validator("admin_emails", mode="after")
    @classmethod
    def normalize_admin_emails(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            email = item.strip().lower()
            if not email or email in seen:
                continue
            seen.add(email)
            normalized.append(email)
        return normalized

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
    def normalize_database_url(cls, value: str) -> str:
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            relative_path, separator, query = value.removeprefix(prefix).partition("?")
            absolute_path = resolve_runtime_path(relative_path).as_posix()
            suffix = f"{separator}{query}" if separator else ""
            return f"sqlite:///{absolute_path}{suffix}"
        if value.startswith("postgresql://"):
            return f"postgresql+psycopg://{value.removeprefix('postgresql://')}"
        if value.startswith("postgres://"):
            return f"postgresql+psycopg://{value.removeprefix('postgres://')}"
        return value

    @model_validator(mode="after")
    def validate_security_posture(self) -> "Settings":
        normalized_env = (self.app_env or "").strip().lower()
        object.__setattr__(self, "app_env", normalized_env or "production")

        if self.upload_max_bytes <= 0:
            raise ValueError("UPLOAD_MAX_BYTES must be greater than zero.")
        if self.research_fetch_max_bytes <= 0:
            raise ValueError("RESEARCH_FETCH_MAX_BYTES must be greater than zero.")
        if self.live_web_search_timeout_seconds <= 0:
            raise ValueError("LIVE_WEB_SEARCH_TIMEOUT_SECONDS must be greater than zero.")
        
        # Crawl4AI Validation
        if self.research_crawl_max_pages < 1:
            raise ValueError("RESEARCH_CRAWL_MAX_PAGES must be greater than or equal to 1.")
        if self.research_crawl_max_chars_per_page < 500:
            raise ValueError("RESEARCH_CRAWL_MAX_CHARS_PER_PAGE must be greater than or equal to 500.")
        if self.research_crawl_timeout_seconds <= 0:
            raise ValueError("RESEARCH_CRAWL_TIMEOUT_SECONDS must be greater than zero.")

        if self.serverless_runtime and self.crawl4ai_enabled:
            logger.warning(
                "CRAWL4AI_ENABLED is true in a serverless runtime. "
                "Crawl4AI requires a browser environment which may not be available. "
                "Ensure your environment supports Playwright/Puppeteer or disable this feature."
            )

        if not _is_valid_http_url(self.live_web_search_endpoint):
            raise ValueError("LIVE_WEB_SEARCH_ENDPOINT must be a valid http(s) URL.")
        if not 0.0 <= float(self.neis_auto_detect_min_confidence) <= 1.0:
            raise ValueError("NEIS_AUTO_DETECT_MIN_CONFIDENCE must be between 0 and 1.")
        if not 0.0 <= float(self.neis_provider_min_quality_score) <= 1.0:
            raise ValueError("NEIS_PROVIDER_MIN_QUALITY_SCORE must be between 0 and 1.")
        if self.neis_extractpdf4j_timeout_seconds <= 0:
            raise ValueError("NEIS_EXTRACTPDF4J_TIMEOUT_SECONDS must be greater than zero.")
        allowed_merge_policies = {"conservative_table"}
        normalized_merge_policy = (self.neis_merge_policy or "").strip().lower()
        if normalized_merge_policy not in allowed_merge_policies:
            raise ValueError("NEIS_MERGE_POLICY must be 'conservative_table'.")
        object.__setattr__(self, "neis_merge_policy", normalized_merge_policy)

        if self.auth_social_login_enabled and not self.auth_social_state_secret:
            raise ValueError("AUTH_SOCIAL_STATE_SECRET is required when AUTH_SOCIAL_LOGIN_ENABLED=true.")
        if self.auth_session_ttl_minutes <= 0:
            raise ValueError("AUTH_SESSION_TTL_MINUTES must be greater than zero.")
        if self.toss_payments_enabled:
            if not self.toss_payments_client_key:
                raise ValueError("TOSS_PAYMENTS_CLIENT_KEY is required when TOSS_PAYMENTS_ENABLED=true.")
            if not self.toss_payments_secret_key:
                raise ValueError("TOSS_PAYMENTS_SECRET_KEY is required when TOSS_PAYMENTS_ENABLED=true.")
            if self.toss_plan_plus_amount <= 0:
                raise ValueError("TOSS_PLAN_PLUS_AMOUNT must be greater than zero.")
            if self.toss_plan_pro_amount <= 0:
                raise ValueError("TOSS_PLAN_PRO_AMOUNT must be greater than zero.")
            if not _is_valid_http_url(self.toss_payments_frontend_base_url):
                raise ValueError("TOSS_PAYMENTS_FRONTEND_BASE_URL must be a valid http(s) URL.")

        if self.app_env != "local":
            if self.api_root_redirect_enabled and not _is_valid_http_url(self.public_app_base_url):
                raise ValueError("PUBLIC_APP_BASE_URL must be a valid http(s) URL when API_ROOT_REDIRECT_ENABLED=true.")
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

        vercel_env = (os.getenv("VERCEL_ENV") or "").strip().lower()
        strict_runtime = self.serverless_runtime or vercel_env in {"production", "preview"}
        
        # Database Safety Check
        is_sqlite = _is_sqlite_database_url(self.database_url)
        is_production_env = self.app_env not in {"local", "test"}
        
        if strict_runtime and is_sqlite:
            # On Vercel, the only writable path is /tmp.
            # If we are using SQLite, we should at least try to use /tmp.
            # This allows temporary testing with ALLOW_PRODUCTION_SQLITE.
            if "/tmp/" not in self.database_url:
                # Convert ./storage/runtime/unifoli.db -> /tmp/unifoli.db
                new_url = self.database_url.replace("./storage/runtime/", "/tmp/").replace("/storage/runtime/", "/tmp/")
                object.__setattr__(self, "database_url", new_url)
                logger.warning(f"Redirected SQLite to /tmp for serverless write access: {new_url}")

        if strict_runtime and is_production_env and is_sqlite:
            if not self.allow_production_sqlite:
                # We no longer crash here to allow readiness check to report the failure gracefully.
                # But we issue a loud warning.
                logger.error(
                    "CRITICAL: SQLite is being used in a production serverless environment. "
                    "This is UNSAFE and data will be lost. DATABASE_URL must be set to PostgreSQL."
                )
            else:
                logger.warning(
                    "ALLOW_PRODUCTION_SQLITE is enabled in production serverless. "
                    "Data will be ephemeral and will be lost frequently. USE ONLY FOR TEMPORARY TESTING."
                )

        raw_storage_provider = (self.unifoli_storage_provider or "").strip().lower()
        normalized_storage_provider = raw_storage_provider
        if strict_runtime and is_production_env and raw_storage_provider in {"", "local"}:
            inferred_storage_provider: str | None = None
            if self.blob_read_write_token:
                inferred_storage_provider = "vercel_blob"
            elif self.s3_bucket_name:
                inferred_storage_provider = "s3"
            elif self.gcs_bucket_name:
                inferred_storage_provider = "gcs"
            if inferred_storage_provider:
                normalized_storage_provider = inferred_storage_provider
                logger.warning(
                    "UNIFOLI_STORAGE_PROVIDER is unset/local in production serverless. "
                    "Using inferred persistent storage provider: %s.",
                    inferred_storage_provider,
                )
        object.__setattr__(self, "unifoli_storage_provider", normalized_storage_provider or "local")
        
        # Storage Safety Check
        if strict_runtime and is_production_env and self.unifoli_storage_provider == "local":
            logger.warning(
                "LOCAL storage provider is being used in a production serverless environment. "
                "Uploaded files and reports will be LOST when the function instance is recycled. "
                "Use 'vercel_blob', 's3', or 'gcs' for persistent storage."
            )

        if self.unifoli_storage_provider == "s3":
            if not self.s3_bucket_name:
                raise ValueError("S3_BUCKET_NAME is required when UNIFOLI_STORAGE_PROVIDER=s3")
        if self.unifoli_storage_provider in {"gcs", "firebase", "firebase_storage"}:
            if not self.gcs_bucket_name:
                raise ValueError("GCS_BUCKET_NAME is required when UNIFOLI_STORAGE_PROVIDER=gcs")
        if self.unifoli_storage_provider in {"vercel_blob", "blob"}:
            if not self.blob_read_write_token:
                raise ValueError("BLOB_READ_WRITE_TOKEN is required when UNIFOLI_STORAGE_PROVIDER=vercel_blob")
            normalized_blob_access = (self.vercel_blob_access or "").strip().lower() or "private"
            if normalized_blob_access not in {"private", "public"}:
                raise ValueError("VERCEL_BLOB_ACCESS must be 'private' or 'public'.")
            object.__setattr__(self, "vercel_blob_access", normalized_blob_access)

        normalized_live_web_provider = (self.live_web_search_provider or "").strip().lower()
        if normalized_live_web_provider in {"", "disabled"}:
            normalized_live_web_provider = "none"
        allowed_live_web_providers = {"none", "serpapi"}
        if normalized_live_web_provider not in allowed_live_web_providers:
            raise ValueError("LIVE_WEB_SEARCH_PROVIDER must be 'none' or 'serpapi'.")
        object.__setattr__(self, "live_web_search_provider", normalized_live_web_provider)

        allowed_llm_providers = {"gemini", "ollama"}
        normalized_provider = (self.llm_provider or "").strip().lower()
        if normalized_provider and normalized_provider not in allowed_llm_providers:
            raise ValueError("LLM_PROVIDER must be 'gemini' or 'ollama'.")
        object.__setattr__(self, "llm_provider", normalized_provider or "gemini")

        for field_name in ("guided_chat_llm_provider", "diagnosis_llm_provider", "render_llm_provider"):
            raw_value = getattr(self, field_name, None)
            normalized_value = (raw_value or "").strip().lower() or None
            if normalized_value is not None and normalized_value not in allowed_llm_providers:
                raise ValueError(f"{field_name.upper()} must be 'gemini' or 'ollama' when set.")
            object.__setattr__(self, field_name, normalized_value)

        normalized_pdf_provider = (self.pdf_analysis_llm_provider or "").strip().lower() or "gemini"
        if normalized_pdf_provider not in allowed_llm_providers:
            raise ValueError("PDF_ANALYSIS_LLM_PROVIDER must be 'gemini' or 'ollama'.")
        object.__setattr__(self, "pdf_analysis_llm_provider", normalized_pdf_provider)

        if self.gemini_model.strip() == "":
            raise ValueError("GEMINI_MODEL must not be empty.")

        if not _is_valid_http_url(self.ollama_base_url):
            raise ValueError("OLLAMA_BASE_URL must be a valid http(s) URL.")
        if self.app_env != "local" and _is_local_host_url(self.ollama_base_url):
            logger.warning(
                "OLLAMA_BASE_URL points to localhost outside local development. "
                "Startup continues, but deployed runtime will refuse localhost Ollama as a success path."
            )
        if self.ollama_timeout_seconds <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be greater than zero.")
        for name, value in (
            ("OLLAMA_FAST_TIMEOUT_SECONDS", self.ollama_fast_timeout_seconds),
            ("OLLAMA_STANDARD_TIMEOUT_SECONDS", self.ollama_standard_timeout_seconds),
            ("OLLAMA_RENDER_TIMEOUT_SECONDS", self.ollama_render_timeout_seconds),
            ("GEMINI_MAX_RETRIES", self.gemini_max_retries),
            ("GEMINI_RETRY_INITIAL_DELAY_SECONDS", self.gemini_retry_initial_delay_seconds),
            ("GEMINI_RETRY_MAX_DELAY_SECONDS", self.gemini_retry_max_delay_seconds),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be greater than or equal to zero when set.")
        if self.workshop_chat_timeout_seconds <= 0:
            raise ValueError("WORKSHOP_CHAT_TIMEOUT_SECONDS must be greater than zero.")

        pdf_ollama_base_url = self.pdf_analysis_ollama_base_url or self.ollama_base_url
        if not _is_valid_http_url(pdf_ollama_base_url):
            raise ValueError("PDF_ANALYSIS_OLLAMA_BASE_URL must be a valid http(s) URL when set.")
        if self.app_env != "local" and _is_local_host_url(pdf_ollama_base_url):
            logger.warning(
                "PDF_ANALYSIS_OLLAMA_BASE_URL points to localhost outside local development. "
                "Startup continues, but deployed runtime will fall back instead of using localhost Ollama."
            )
        if self.pdf_analysis_timeout_seconds <= 0:
            raise ValueError("PDF_ANALYSIS_TIMEOUT_SECONDS must be greater than zero.")

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


def _is_local_host_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _is_valid_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_sqlite_database_url(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return normalized.startswith("sqlite:")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
