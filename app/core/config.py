from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    ANTHROPIC_API_KEY: str = ""
    ENABLE_SCHEDULER: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()

client_id = settings.NAVER_CLIENT_ID
client_secret = settings.NAVER_CLIENT_SECRET
