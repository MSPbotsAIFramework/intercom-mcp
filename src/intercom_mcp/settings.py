"""Non-credential configuration. Credentials never live here (PRD-21309, SOP S3.1)."""

from pydantic_settings import BaseSettings, SettingsConfigDict

# Pinned protocol version, not a per-tenant credential. See PRD-21309.md
# "Decisions made by DEV01" for why this is a constant rather than an
# agent-supplied header.
INTERCOM_API_VERSION = "2.11"

INTERCOM_REGION_HOSTS = {
    "us": "https://api.intercom.io",
    "eu": "https://api.eu.intercom.io",
    "au": "https://api.au.intercom.io",
}
DEFAULT_REGION = "us"

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0


class Settings(BaseSettings):
    """Process-level configuration, sourced from the environment.

    `extra="ignore"` is required: the runtime injects environment variables
    this project never declared, and a strict model would crash on startup.
    """

    model_config = SettingsConfigDict(extra="ignore")

    mcp_http_host: str = "0.0.0.0"
    mcp_http_port: int = 8080


def get_settings() -> Settings:
    return Settings()
