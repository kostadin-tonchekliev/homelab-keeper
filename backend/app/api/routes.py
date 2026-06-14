from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..config import get_config
from ..core import docker_client
from ..core.discovery import discover_services
from ..core.excludes import apply_excludes
from ..core.git_service import GitError, git_service
from ..core.logbus import log_bus
from ..core.orchestrator import run_backup, run_push, run_restore, state
from ..db import get_session, get_settings
from ..models import ExcludeRule, ServiceSetting
from ..schemas import (
    BackupRequest,
    ExcludeToggle,
    RestoreRequest,
    ServiceToggle,
    SettingsOut,
    SettingsUpdate,
)

router = APIRouter(prefix="/api")


def _settings_out(session: Session) -> SettingsOut:
    s = get_settings(session)
    cfg = get_config()
    return SettingsOut(
        services_dir=s.services_dir,
        repo_url=s.repo_url,
        branch=s.branch,
        has_token=bool(s.github_token or cfg.github_token),
        git_author_name=s.git_author_name,
        git_author_email=s.git_author_email,
        sync_mode=s.sync_mode,
        interval_seconds=s.interval_seconds,
        debounce_seconds=s.debounce_seconds,
        auto_push=s.auto_push,
        stop_containers_on_restore=s.stop_containers_on_restore,
        notify_webhook_url=s.notify_webhook_url,
        notify_on_success=s.notify_on_success,
        notify_on_failure=s.notify_on_failure,
        initialized=s.initialized,
    )


# ----- status / dashboard ---------------------------------------------------
@router.get("/status")
def get_status(session: Session = Depends(get_session)):
    settings = get_settings(session)
    repo = git_service.status(settings)
    payload = asdict(repo)
    if repo.last_commit:
        payload["last_commit"] = asdict(repo.last_commit)
    payload.update(
        {
            "activity": state["status"],
            "last_error": state["last_error"],
            "docker_available": docker_client.available(),
            "configured": settings.initialized and bool(settings.repo_url.strip()),
        }
    )
    return payload


@router.post("/backup")
def trigger_backup(req: BackupRequest):
    result = run_backup(message=req.message, reason="manual")
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/push")
def trigger_push():
    result = run_push()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/unlock")
def unlock_repo():
    """Remove any stale git lock files immediately (no age check)."""
    cfg = get_config()
    removed = []
    for name in git_service._GIT_LOCK_FILES:
        lock = cfg.git_dir / name
        try:
            lock.unlink(missing_ok=True)
            removed.append(name)
        except OSError as exc:
            log_bus.warning(f"Could not remove lock {name}: {exc}")
    if removed:
        log_bus.warning(f"Manual unlock: removed {', '.join(removed)}.")
    return {"ok": True, "removed": removed}


@router.post("/fetch")
def trigger_fetch(session: Session = Depends(get_session)):
    git_service.fetch(get_settings(session))
    return {"ok": True}


# ----- history --------------------------------------------------------------
@router.get("/history")
def history(limit: int = Query(100, le=500), session: Session = Depends(get_session)):
    settings = get_settings(session)
    return [asdict(c) for c in git_service.log(settings, limit=limit)]


@router.get("/history/{sha}")
def commit_detail(sha: str, session: Session = Depends(get_session)):
    settings = get_settings(session)
    return {"files": git_service.commit_files(settings, sha)}


@router.get("/diff/{sha}")
def commit_diff(
    sha: str,
    path: str | None = None,
    session: Session = Depends(get_session),
):
    settings = get_settings(session)
    return {"diff": git_service.diff(settings, sha, path)}


# ----- services & exclusions ------------------------------------------------
@router.get("/services")
def list_services(session: Session = Depends(get_session)):
    settings = get_settings(session)
    discovered = discover_services(settings.services_dir)

    svc_rows = {s.name: s for s in session.exec(select(ServiceSetting)).all()}
    excl_rows = {e.path: e for e in session.exec(select(ExcludeRule)).all()}

    out = []
    for svc in discovered:
        enabled = svc_rows[svc.name].enabled if svc.name in svc_rows else True
        subdirs = []
        for sub in svc.subdirs:
            rule = excl_rows.get(sub.rel_path)
            subdirs.append(
                {
                    "name": sub.name,
                    "rel_path": sub.rel_path,
                    "size_bytes": sub.size_bytes,
                    "excluded": bool(rule and rule.enabled),
                }
            )
        out.append(
            {
                "name": svc.name,
                "rel_path": svc.rel_path,
                "compose_file": svc.compose_file,
                "size_bytes": svc.size_bytes,
                "enabled": enabled,
                "subdirs": subdirs,
            }
        )
    return out


@router.post("/services/toggle")
def toggle_service(body: ServiceToggle, session: Session = Depends(get_session)):
    row = session.exec(
        select(ServiceSetting).where(ServiceSetting.name == body.name)
    ).first()
    if row is None:
        row = ServiceSetting(name=body.name, enabled=body.enabled)
    else:
        row.enabled = body.enabled
    session.add(row)
    session.commit()
    apply_excludes(session)
    return {"ok": True}


@router.post("/excludes/toggle")
def toggle_exclude(body: ExcludeToggle, session: Session = Depends(get_session)):
    row = session.exec(
        select(ExcludeRule).where(ExcludeRule.path == body.path)
    ).first()
    if row is None:
        row = ExcludeRule(path=body.path, enabled=body.enabled)
    else:
        row.enabled = body.enabled
    session.add(row)
    session.commit()
    apply_excludes(session)
    return {"ok": True}


# ----- settings -------------------------------------------------------------
@router.get("/settings", response_model=SettingsOut)
def read_settings(session: Session = Depends(get_session)):
    return _settings_out(session)


@router.put("/settings", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session)):
    settings = get_settings(session)
    data = body.model_dump(exclude_unset=True)
    # An empty token string means "leave unchanged".
    if "github_token" in data and (data["github_token"] is None or data["github_token"] == ""):
        data.pop("github_token")
    for key, value in data.items():
        setattr(settings, key, value)
    from datetime import datetime, timezone

    settings.updated_at = datetime.now(timezone.utc)
    session.add(settings)
    session.commit()

    # Reconfigure background workers to honour new mode/interval/excludes.
    from ..core.scheduler import scheduler_manager
    from ..core.watcher import watcher_manager

    if git_service.is_initialized():
        apply_excludes(session)
    scheduler_manager.reload()
    watcher_manager.restart()
    log_bus.info("Settings updated.")
    return _settings_out(session)


@router.post("/init")
def initialize(session: Session = Depends(get_session)):
    settings = get_settings(session)
    if not settings.repo_url.strip():
        raise HTTPException(status_code=400, detail="Repository URL is required.")
    try:
        git_service.init_repo(settings)
        apply_excludes(session)
        settings.initialized = True
        session.add(settings)
        session.commit()
    except GitError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from ..core.scheduler import scheduler_manager
    from ..core.watcher import watcher_manager

    scheduler_manager.reload()
    watcher_manager.restart()
    return {"ok": True}


# ----- restore --------------------------------------------------------------
@router.post("/restore/preview")
def restore_preview(req: RestoreRequest, session: Session = Depends(get_session)):
    settings = get_settings(session)
    return {"diff": git_service.restore_preview(settings, req.sha, req.paths)}


@router.post("/restore")
def restore(req: RestoreRequest):
    result = run_restore(req.sha, req.paths)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


# ----- logs / health --------------------------------------------------------
@router.get("/logs")
def logs(limit: int = Query(200, le=500)):
    return log_bus.recent(limit=limit)


@router.get("/compose-projects")
def compose_projects():
    return docker_client.list_compose_projects()
