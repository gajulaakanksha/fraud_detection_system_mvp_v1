from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://valli:valli_dev_password@localhost:5432/valli_securepay"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-to-a-random-secret-in-every-environment"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
