from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router
from .config import get_config
from .core.git_service import git_service
from .core.logbus import log_bus
from .core.orchestrator import run_backup, state
from .core.scheduler import scheduler_manager
from .core.watcher import watcher_manager
from .db import get_settings, init_db, session_scope

# Resolve VERSION file: check next to the package root (works in Docker where
# backend/ is copied to /app/) and then one level higher (local repo root).
def _read_version() -> str:
    for candidate in [
        Path(__file__).parent.parent / "VERSION",
        Path(__file__).parent.parent.parent / "VERSION",
    ]:
        if candidate.is_file():
            return candidate.read_text().strip()
    return "unknown"


APP_VERSION = _read_version()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def _backup_cb(reason: str = "auto") -> None:
    run_backup(reason=reason)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    init_db()

    with session_scope() as session:
        settings = get_settings(session)
        if settings.initialized and settings.repo_url.strip():
            try:
                git_service.init_repo(settings)
            except Exception as exc:  # noqa: BLE001
                log_bus.error(f"Failed to reattach git repo on startup: {exc}")

    scheduler_manager.configure(_backup_cb)
    watcher_manager.configure(_backup_cb)
    scheduler_manager.start()
    watcher_manager.restart()
    log_bus.info("Homelab Service Backup started.")
    yield
    watcher_manager.stop()
    scheduler_manager.shutdown()


app = FastAPI(title="Homelab Service Backup", lifespan=lifespan)
app.include_router(api_router)


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"


@app.get("/version")
def version():
    return {"version": APP_VERSION}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    with session_scope() as session:
        settings = get_settings(session)
        repo = git_service.status(settings)
    lines = [
        "# HELP backup_repo_pending_changes Number of uncommitted changes.",
        "# TYPE backup_repo_pending_changes gauge",
        f"backup_repo_pending_changes {repo.pending_changes}",
        "# HELP backup_repo_ahead Commits ahead of remote.",
        "# TYPE backup_repo_ahead gauge",
        f"backup_repo_ahead {repo.ahead}",
        "# HELP backup_repo_size_bytes Size of the git directory in bytes.",
        "# TYPE backup_repo_size_bytes gauge",
        f"backup_repo_size_bytes {repo.repo_size_bytes}",
        "# HELP backup_error Whether the last operation errored (1) or not (0).",
        "# TYPE backup_error gauge",
        f"backup_error {1 if state['status'] == 'error' else 0}",
    ]
    return "\n".join(lines) + "\n"


# ----- static frontend ------------------------------------------------------
_cfg = get_config()
_static = Path(_cfg.static_dir) if _cfg.static_dir else Path(__file__).parent / "static"
if _static.is_dir():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(_static / "index.html")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = _static / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
