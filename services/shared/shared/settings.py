from functools import lru_cache
from typing import List, Optional
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


class DatabaseSettings(BaseAppSettings):
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "liara_chatbot"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_STATEMENT_TIMEOUT_MS: int = 5000

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            # ensure asyncpg scheme
            url = self.DATABASE_URL
            if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql+asyncpg://"):
                return url.replace("postgresql+asyncpg://", "postgresql://", 1)
            return url
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


class RedisSettings(BaseAppSettings):
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None

    @property
    def url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


class AIProviderSettings(BaseAppSettings):
    """Configuration for OpenAI-compatible LLM and embedding providers.

    LLM and embedding traffic can use the same provider or two different
    providers.  The legacy OpenRouter environment variables are accepted as
    aliases so existing deployments continue to work during migration.
    """

    LLM_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "LIARA_API_KEY", "OPENROUTER_API_KEY"),
    )
    LLM_BASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LLM_BASE_URL", "BASE_URL", "OPENROUTER_BASE_URL"),
    )
    LLM_PROXY_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LLM_PROXY_URL", "OPENROUTER_PROXY_URL"),
    )

    # If embedding-specific values are omitted, the LLM provider is used.
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_BASE_URL: Optional[str] = None
    EMBEDDING_PROXY_URL: Optional[str] = None

    # Models
    # Defaults are available in Liara's OpenAI-compatible catalog and are
    # also valid for other providers that expose these model IDs.
    ROUTER_MODEL: str = "openai/gpt-4.1-mini"
    SYNTHESIS_MODEL: str = "openai/gpt-4.1"
    SYNTHESIS_FALLBACK_MODEL: str = "openai/gpt-4o-mini"
    EMBEDDING_MODEL: str = "openai/text-embedding-3-large"
    EMBEDDING_FALLBACK_MODEL: str = "openai/text-embedding-3-small"

    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_SEND_DIMENSIONS: bool = True
    EMBEDDING_BATCH_SIZE: int = 16
    MAX_TOKENS_PER_TURN: int = 12000

    @property
    def llm_api_key(self) -> Optional[str]:
        return self.LLM_API_KEY or "sk-dummy-key"

    @property
    def llm_base_url(self) -> str:
        return (self.LLM_BASE_URL or "https://openrouter.ai/api/v1").rstrip("/")

    @property
    def llm_proxy_url(self) -> Optional[str]:
        return self.LLM_PROXY_URL or None

    @property
    def embedding_api_key(self) -> Optional[str]:
        return self.EMBEDDING_API_KEY or self.llm_api_key

    @property
    def embedding_base_url(self) -> str:
        return (self.EMBEDDING_BASE_URL or self.llm_base_url).rstrip("/")

    @property
    def embedding_proxy_url(self) -> Optional[str]:
        return self.EMBEDDING_PROXY_URL if self.EMBEDDING_PROXY_URL is not None else self.llm_proxy_url


class SecuritySettings(BaseAppSettings):
    INTERNAL_TOKEN: str = "internal-secret-token-change-in-production"
    ADMIN_OPERATOR_TOKEN: str = "admin-operator-token-change-in-production"
    ALLOWED_SITE_KEYS: List[str] = [
        "pk_live_docs_liara_ir",
        "pk_test_liara_ir",
        "pk_console_liara_ir",
    ]
    HMAC_SALT: str = "liara-daily-hmac-salt-secure"
    CORS_ORIGINS: List[str] = [
        "https://docs.liara.ir",
        "https://console.liara.ir",
        "https://liara.ir",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
    ]
    RATE_LIMIT_IP_BURST: int = 6
    RATE_LIMIT_IP_HOURLY: int = 30
    RATE_LIMIT_CONV_HOURLY: int = 40


class IndexerSettings(BaseAppSettings):
    INDEXER_HOST: str = "0.0.0.0"
    INDEXER_PORT: int = 8001
    INDEXER_WORKER_CONCURRENCY: int = 4
    DOCS_REPO_URL: str = "https://github.com/liara-cloud/docs.git"
    DOCS_REPO_BRANCH: str = "master"
    DOCS_LOCAL_CLONE_DIR: str = "/tmp/liara_docs_repo"
    INDEXER_API_BASE_URL: str = "http://localhost:8001"


class ChatApiSettings(BaseAppSettings):
    CHAT_API_HOST: str = "0.0.0.0"
    CHAT_API_PORT: int = 8000
    INDEXER_BASE_URL: str = "http://indexer:8001"
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIME_SECS: int = 60
    CIRCUIT_BREAKER_TIMEOUT_SECS: float = 15.0


class Settings(BaseAppSettings):
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    ai: AIProviderSettings = Field(default_factory=AIProviderSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    indexer: IndexerSettings = Field(default_factory=IndexerSettings)
    chat_api: ChatApiSettings = Field(default_factory=ChatApiSettings)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
