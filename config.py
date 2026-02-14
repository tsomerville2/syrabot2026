"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot_service"
    gemini_api_key: str = ""
    admin_api_key: str = ""

    embedding_model: str = "models/gemini-embedding-001"
    embedding_dim: int = 3072
    embedding_max_chars: int = 2000

    # Chat defaults
    default_similarity_threshold: float = 0.3
    default_top_k: int = 1

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def async_database_url(self) -> str:
        """Convert any postgres(ql):// URL to postgresql+asyncpg:// for async support."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
