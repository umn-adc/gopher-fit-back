from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: SecretStr = Field(min_length=32)
    database_url: str = "sqlite:///./gopherfit.db"
    jwt_ttl_seconds: int = Field(default=900, gt=0, le=3600)
    refresh_ttl_seconds: int = Field(default=2592000, gt=0)
    recovery_ttl_seconds: int = Field(default=1800, gt=0, le=86400)
    recovery_enabled: bool = False
    recovery_frontend_url: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=587, gt=0, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: EmailStr | None = None
    smtp_tls: Literal["starttls", "implicit"] = "starttls"
    smtp_timeout_seconds: int = Field(default=10, gt=0, le=60)
    auth_rate_limit: int = Field(default=20, gt=0)
    recovery_rate_limit: int = Field(default=5, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    metrics_token: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    backup_directory: str = "./backups"
    backup_retention: int = Field(default=7, ge=1)

    @model_validator(mode="after")
    def configured_services(self) -> Self:
        if self.recovery_enabled:
            url = urlsplit(self.recovery_frontend_url)
            if (
                not self.smtp_host
                or self.smtp_from is None
                or url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("Recovery requires SMTP and an HTTPS frontend URL without a query")
        for origin in self.cors_origins:
            url = urlsplit(origin)
            if (
                url.scheme not in {"http", "https"}
                or not url.netloc
                or url.path
                or url.query
                or url.fragment
                or url.username
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths")
        if self.metrics_token is not None and len(self.metrics_token.get_secret_value()) < 32:
            raise ValueError("METRICS_TOKEN must contain at least 32 characters")
        return self
