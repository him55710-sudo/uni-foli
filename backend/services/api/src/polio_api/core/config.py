from __future__ import annotations

from functools import lru_cache
import re
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from polio_shared.paths import find_project_root


class Settings(BaseSettings):
    app_name: str = "polio Backend"
    app_env: str = "local"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./storage/runtime/polio.db?check_same_thread=False&timeout=30"
    database_echo: bool = False
    database_auto_create_tables: bool = True
    postgres_enable_pgvector: bool = True
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3001"]
    )
    cors_origin_regex: str | None = None
    allow_inline_render: bool = True
    auto_ingest_uploads: bool = True
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
    auth_allow_local_dev_bypass: bool = True
    auth_firebase_fallback_enabled: bool = True

    # LLM Settings
    llm_provider: str = Field(default="gemini", description="LLM provider: 'gemini' or 'ollama'")
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"

    model_config = SettingsConfigDict(
        env_file=".env",
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

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_sqlite_path(cls, value: str) -> str:
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            relative_path = value.removeprefix(prefix)
            absolute_path = (find_project_root() / relative_path).as_posix()
            return f"sqlite:///{absolute_path}"
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
