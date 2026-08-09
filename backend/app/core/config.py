"""Centralized application configuration, loaded from environment / .env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All tunables live here so no module reads os.environ directly."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # LLM (Groq, behind the LLMProvider abstraction)
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # Neo4j (Aura or local)
    neo4j_uri: str = "neo4j+s://localhost"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""

    # Ingestion
    workspace_dir: Path = Path("./workspace")
    max_repo_size_mb: int = 500
    max_repo_files: int = 5000

    # Vector store
    vector_index_dir: Path = Path("./workspace/_vector_index")


settings = Settings()
