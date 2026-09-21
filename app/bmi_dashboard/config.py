from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class BmiSettings(BaseSettings):
    """All BMI-dashboard configuration. Every value comes from the environment.

    The feature is *disabled* (routes answer 503, no migrations run) unless the
    database, the password hash and a long session secret are all configured, so
    deploying this code before the server is prepared cannot break the app.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Either a full URL (used by tests) or the parts below (used by Compose).
    bmi_database_url: str = ""
    bmi_db_user: str = ""
    bmi_db_password: str = ""
    bmi_db_host: str = "postgres"
    bmi_db_port: int = 5432
    bmi_db_name: str = ""

    dashboard_password_hash: str = ""
    session_secret: str = ""
    session_ttl_hours: int = 12
    cookie_secure: bool = True

    login_max_attempts: int = 5
    login_window_seconds: int = 900

    def database_url(self) -> str:
        if self.bmi_database_url:
            return self.bmi_database_url
        if self.bmi_db_user and self.bmi_db_password and self.bmi_db_name:
            return URL.create(
                "postgresql+psycopg",
                username=self.bmi_db_user,
                password=self.bmi_db_password,
                host=self.bmi_db_host,
                port=self.bmi_db_port,
                database=self.bmi_db_name,
            ).render_as_string(hide_password=False)
        return ""

    def missing(self) -> list[str]:
        """Names (never values) of settings that keep the feature disabled."""
        gaps = []
        if not self.database_url():
            gaps.append("BMI_DB_USER/BMI_DB_PASSWORD/BMI_DB_NAME")
        if not self.dashboard_password_hash:
            gaps.append("DASHBOARD_PASSWORD_HASH")
        if len(self.session_secret) < 32:
            gaps.append("SESSION_SECRET (min 32 chars)")
        return gaps

    @property
    def enabled(self) -> bool:
        return not self.missing()


bmi_settings = BmiSettings()
