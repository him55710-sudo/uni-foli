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
    database_url: str = "sqlite:///./storage/runtime/polio.db"
    database_echo: bool = False
    database_auto_create_tables: bool = True
    postgres_enable_pgvector: bool = True
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3001"]
    )
    allow_inline_render: bool = True
    auto_ingest_uploads: bool = True
    upload_chunk_size_chars: int = 1200
    upload_chunk_overlap_chars: int = 180
    vector_dimensions: int = 1536
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
