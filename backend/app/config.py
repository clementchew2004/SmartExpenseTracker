from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    OPENAI_API_KEY: SecretStr
    OPENAI_MODEL: str = "gpt-4o-mini"
    # Websites whose JavaScript may call this API from a browser.
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Auth
    JWT_SECRET_KEY: SecretStr  # signs access tokens; changing it logs everyone out
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 30  # counted from login, not extended by refreshing
    # Secure cookies are only sent over HTTPS: off for http:// dev, on in production.
    COOKIE_SECURE: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
