from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    redis_host: str = "redis"
    redis_port: int = 6379

    kafka_bootstrap_servers: str = "kafka:9092"

    openai_api_key: str

    app_env: str = "development"
    log_level: str = "INFO"

    tenant_api_keys: str = ""

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def tenant_key_map(self) -> dict:
        """Parses TENANT_API_KEYS env var into a dict.
        Input:  "amazon-key-123:amazon,flipkart-key-456:flipkart"
        Output: {"amazon-key-123": "amazon", "flipkart-key-456": "flipkart"}"""
        
        result = {}
        if not self.tenant_api_keys:
            return result
        for pair in self.tenant_api_keys.split(","):
            key, tenant = pair.strip().split(":")
            result[key.strip()] = tenant.strip()
        return result

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()