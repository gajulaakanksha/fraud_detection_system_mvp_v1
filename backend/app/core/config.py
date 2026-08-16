from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://valli:valli_dev_password@localhost:5432/valli_securepay"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-to-a-random-secret-in-every-environment"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Comma-separated -- e.g. the deployed frontend's own origin in production,
    # localhost:5173 for local dev. A plain string (not list[str]) so it
    # round-trips through a .env file / docker-compose environment var
    # without needing JSON-array syntax.
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
