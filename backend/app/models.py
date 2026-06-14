from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SyncMode(str, Enum):
    hybrid = "hybrid"
    interval = "interval"
    watch = "watch"


class Settings(SQLModel, table=True):
    """Singleton settings row (id == 1)."""

    id: int | None = Field(default=1, primary_key=True)

    services_dir: str = "/services"
    repo_url: str = ""
    branch: str = "main"
    # Token stored here overrides the GITHUB_TOKEN env var. Never committed.
    github_token: str | None = None

    git_author_name: str = "Homelab Keeper"
    git_author_email: str = "backup@homelab.local"

    sync_mode: SyncMode = SyncMode.hybrid
    interval_seconds: int = 3600
    debounce_seconds: int = 30
    auto_push: bool = True

    stop_containers_on_restore: bool = True

    notify_webhook_url: str | None = None
    notify_on_success: bool = False
    notify_on_failure: bool = True

    initialized: bool = False
    updated_at: datetime = Field(default_factory=_utcnow)


class ServiceSetting(SQLModel, table=True):
    """Per-service inclusion toggle. `name` is the directory name under services_dir."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    enabled: bool = True


class ExcludeRule(SQLModel, table=True):
    """A path (relative to services_dir) to exclude from backups when enabled."""

    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)
    enabled: bool = True
