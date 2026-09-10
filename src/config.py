"""
Configuration for the MCP Legal Assistant.

Changes over the previous revision:

* Adds ``api_key`` and ``environment``. Every ``/api/v1`` route depends on the
  key; production refuses to start while it is the placeholder.
* Adds ``cors_allow_origins``. The API allowed every origin with credentials, a
  combination browsers reject and a misconfiguration for anything but a demo.
* Removes settings nothing read: Stripe, Twilio, Google Calendar, CourtListener,
  ``secret_key`` (it signed the JWTs of an in-memory user store that protected
  no route) and ``encryption_key`` (never referenced).
* Drops the ``env=`` keyword on every field. It is pydantic v1 syntax that
  pydantic v2 ignores; the field name is the environment variable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_API_KEY = "changeme-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # ---- LLM providers -------------------------------------------------------
    # Placeholders are recognised by src.llm and treated as "not configured".
    openai_api_key: str = "sk-placeholder"
    anthropic_api_key: str = "sk-ant-placeholder"

    # ---- Pinecone (case research, optional) -----------------------------------
    pinecone_api_key: str = "placeholder-pinecone-key"
    pinecone_environment: str = "us-west-2"
    pinecone_index_name: str = "legal-assistant-index"

    # ---- Database (optional; nothing in the API uses it yet) ------------------
    database_url: str = "postgresql://localhost:5432/legal_assistant"
    database_async_url: str | None = None

    # ---- Server ---------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

    # ---- Security -------------------------------------------------------------
    api_key: str = INSECURE_API_KEY
    environment: Literal["development", "testing", "staging", "production"] = "development"
    # Comma-separated browser origins. Empty means: the dev origins in
    # development, nothing in production.
    cors_allow_origins: str = ""

    # ---- Firm defaults ---------------------------------------------------------
    default_jurisdiction: str = "Texas"
    default_billing_increment: float = 0.1
    conflict_check_required: bool = True

    # ---- Model configuration ---------------------------------------------------
    # Model defaults were pinned to claude-3-5-sonnet-20241022, superseded by
    # the Claude 5 family. Every one is overridable by environment variable.
    orchestrator_model: str = "claude-sonnet-5"
    contract_reviewer_model: str = "claude-sonnet-5"
    case_researcher_model: str = "gpt-4o"
    document_drafter_model: str = "claude-sonnet-5"
    deadline_tracker_model: str = "gpt-4o"
    billing_calculator_model: str = "gpt-4o"

    # ---- Derived ---------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def has_insecure_api_key(self) -> bool:
        return self.api_key == INSECURE_API_KEY

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    # ---- Fail closed -------------------------------------------------------------
    @model_validator(mode="after")
    def _guard_production(self) -> Settings:
        if self.is_production:
            self.validate_production_settings()
        return self

    def validate_production_settings(self) -> None:
        problems: list[str] = []
        if self.has_insecure_api_key:
            problems.append(
                "API_KEY is still the default placeholder. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        if problems:
            raise ValueError("Invalid production configuration:\n  - " + "\n  - ".join(problems))


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
