from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Process-level configuration sourced from the environment.

    Per-user/runtime preferences (repo URL, sync mode, exclusions, ...) live in
    the SQLite settings table instead; this class only holds things that are
    fixed for the lifetime of the container.
    """

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Directory holding the service folders to back up (mounted into the container).
    services_dir: str = "/services"
    # Persistent volume for the git dir, SQLite state and logs.
    data_dir: str = "/data"
    # Fallback GitHub token if one is not stored via the UI.
    github_token: str | None = None

    host: str = "0.0.0.0"
    port: int = 8000

    # Path to the built frontend assets (set in the Docker image).
    static_dir: str | None = None

    @property
    def git_dir(self) -> Path:
        return Path(self.data_dir) / "repo.git"

    @property
    def db_path(self) -> Path:
        return Path(self.data_dir) / "state.db"

    @property
    def log_dir(self) -> Path:
        return Path(self.data_dir) / "logs"


@lru_cache
def get_config() -> AppConfig:
    cfg = AppConfig()
    Path(cfg.data_dir).mkdir(parents=True, exist_ok=True)
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    return cfg
