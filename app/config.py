from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "prod-docker-app"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = ""
    redis_url: str = ""


settings = Settings()
