import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # PostgreSQL settings
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_DB: str = Field(default="hub_osint")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    
    # Custom DB URL if provided
    DATABASE_URL: str | None = Field(default=None)

    # Redis settings
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    
    # Custom Celery settings
    CELERY_BROKER_URL: str | None = Field(default=None)
    CELERY_RESULT_BACKEND: str | None = Field(default=None)

    # Feed scraper options
    RSS_REFRESH_INTERVAL_SECONDS: int = Field(default=3600)  # default 1 hour

    # Application settings
    APP_NAME: str = Field(default="OSINT & Private Intelligence Hub")
    DEBUG: bool = Field(default=True)
    
    # Gemini API Configuration
    GEMINI_API_KEY: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def celery_broker(self) -> str:
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def celery_backend(self) -> str:
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

settings = Settings()
