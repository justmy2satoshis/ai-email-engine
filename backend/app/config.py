"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """AI Email Engine settings."""

    # IMAP (Proton Mail Bridge)
    imap_host: str = "127.0.0.1"
    imap_port: int = 1143
    imap_user: str = ""
    imap_password: str = ""
    imap_use_ssl: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_email_engine"

    # Sync database URL (for alembic / sync operations)
    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "")

    # Redis
    redis_url: str = "redis://localhost:6379/2"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # Sync
    sync_interval_minutes: int = 5
    sync_folders: str = "INBOX"
    initial_sync_limit: int = 5000

    @property
    def sync_folder_list(self) -> list[str]:
        return [f.strip() for f in self.sync_folders.split(",")]

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8400

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
