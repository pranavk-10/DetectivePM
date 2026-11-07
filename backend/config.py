"""Environment-driven settings. Secrets come only from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def normalise_db_url(url: str) -> str:
    """Hosts hand out postgres:// URLs; SQLAlchemy needs the psycopg driver name."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@dataclass(frozen=True)
class Settings:
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    database_url: str = field(
        default_factory=lambda: normalise_db_url(
            os.getenv("DATABASE_URL", f"sqlite:///{(ROOT / 'backend' / 'local.db').as_posix()}")
        )
    )
    frontend_url: str = field(default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:3000"))
    backend_url: str = field(default_factory=lambda: os.getenv("BACKEND_URL", "http://localhost:8000"))
    admin_api_key: str = field(default_factory=lambda: os.getenv("ADMIN_API_KEY", ""))
    google_sheets_id: str = field(default_factory=lambda: os.getenv("GOOGLE_SHEETS_ID", ""))
    google_service_account_json: str = field(
        default_factory=lambda: os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    )
    adzuna_app_id: str = field(default_factory=lambda: os.getenv("ADZUNA_APP_ID", ""))
    adzuna_app_key: str = field(default_factory=lambda: os.getenv("ADZUNA_APP_KEY", ""))
    run_scheduler_in_api: bool = field(default_factory=lambda: _bool("RUN_SCHEDULER_IN_API"))
    show_demo_data: bool = field(default_factory=lambda: _bool("SHOW_DEMO_DATA"))
    manual_run_cooldown_seconds: int = field(
        default_factory=lambda: _int("MANUAL_RUN_COOLDOWN_SECONDS", 300)
    )
    discovery_interval_seconds: int = 18_000  # the five-hour requirement
    http_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "HTTP_USER_AGENT", "DetectivePM/2.0 (India PM job intelligence; public job board reader)"
        )
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cors_origins(self) -> list[str]:
        if self.is_production:
            return [self.frontend_url]
        return [self.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"]

    def validate(self) -> None:
        """Fail at boot rather than run production in an unsafe configuration."""
        if not self.is_production:
            return
        problems = []
        if self.is_sqlite:
            problems.append("DATABASE_URL must be PostgreSQL in production")
        if not self.admin_api_key:
            problems.append("ADMIN_API_KEY is required in production")
        if self.show_demo_data:
            problems.append("SHOW_DEMO_DATA must be off in production")
        if problems:
            raise RuntimeError("Invalid production configuration: " + "; ".join(problems))


settings = Settings()
