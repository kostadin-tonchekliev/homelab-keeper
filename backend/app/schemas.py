from __future__ import annotations

from pydantic import BaseModel

from .models import SyncMode


class SettingsUpdate(BaseModel):
    services_dir: str | None = None
    repo_url: str | None = None
    branch: str | None = None
    github_token: str | None = None  # write-only; "" leaves unchanged
    git_author_name: str | None = None
    git_author_email: str | None = None
    sync_mode: SyncMode | None = None
    interval_seconds: int | None = None
    debounce_seconds: int | None = None
    auto_push: bool | None = None
    stop_containers_on_restore: bool | None = None
    notify_webhook_url: str | None = None
    notify_on_success: bool | None = None
    notify_on_failure: bool | None = None


class SettingsOut(BaseModel):
    services_dir: str
    repo_url: str
    branch: str
    has_token: bool
    git_author_name: str
    git_author_email: str
    sync_mode: SyncMode
    interval_seconds: int
    debounce_seconds: int
    auto_push: bool
    stop_containers_on_restore: bool
    notify_webhook_url: str | None
    notify_on_success: bool
    notify_on_failure: bool
    initialized: bool


class ServiceToggle(BaseModel):
    name: str
    enabled: bool


class ExcludeToggle(BaseModel):
    path: str
    enabled: bool


class RestoreRequest(BaseModel):
    sha: str
    paths: list[str] = []


class BackupRequest(BaseModel):
    message: str | None = None
