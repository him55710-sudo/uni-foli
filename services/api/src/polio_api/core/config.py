from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    allow_inline_render: bool = True
    auto_ingest_uploads: bool = True
    upload_chunk_size_chars: int = 1200
    upload_chunk_overlap_chars: int = 180
    vector_dimensions: int = 1536

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
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
