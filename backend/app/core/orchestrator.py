from __future__ import annotations

from threading import Lock

from ..db import get_settings, session_scope
from .docker_client import compose_down, compose_up, list_compose_projects
from .excludes import apply_excludes
from .git_service import BackupResult, GitError, git_service
from .logbus import log_bus
from .manifest import write_manifest
from .notify import notify

# Serialises backup/restore so they never overlap with each other or themselves.
_op_lock = Lock()

# Lightweight status surfaced to the dashboard.
state: dict = {"status": "idle", "last_error": None, "last_backup_at": None}


def run_backup(message: str | None = None, reason: str = "manual") -> dict:
    # Import here to avoid a circular import (watcher imports from orchestrator
    # indirectly via the backup callback).
    from .watcher import watcher_manager

    if not _op_lock.acquire(blocking=False):
        return {"ok": False, "skipped": True, "reason": "another operation in progress"}
    try:
        state["status"] = "syncing"
        # Suppress the file watcher for the duration of the backup so that the
        # manifest write (and any service log activity during the run) does not
        # schedule a new backup while we are still finishing this one.
        watcher_manager.set_suppressed(True)
        with session_scope() as session:
            settings = get_settings(session)
            if not settings.initialized or not settings.repo_url.strip():
                state["status"] = "idle"
                return {"ok": False, "reason": "not configured"}

            apply_excludes(session)
            write_manifest(settings.services_dir)
            try:
                result: BackupResult = git_service.backup(settings, message=message)
            except GitError as exc:
                state["status"] = "error"
                state["last_error"] = str(exc)
                notify(settings, "Backup failed", str(exc), success=False)
                return {"ok": False, "error": str(exc)}

            state["status"] = "idle"
            state["last_error"] = None
            if result.commit is None:
                log_bus.info(f"No changes to back up ({reason}).")
                return {
                    "ok": True,
                    "changed": False,
                    "skipped_files": result.skipped_large_files,
                }

            from datetime import datetime, timezone

            state["last_backup_at"] = datetime.now(timezone.utc).isoformat()
            notify(
                settings,
                "Backup complete",
                f"{result.commit.short_sha} {result.commit.subject}",
                success=True,
            )
            return {
                "ok": True,
                "changed": True,
                "commit": result.commit.short_sha,
                "skipped_files": result.skipped_large_files,
            }
    finally:
        # Re-enable the watcher and discard any debounce timer that was
        # scheduled before suppression took effect (e.g. from events that
        # arrived in the brief window before the lock was acquired).
        watcher_manager.set_suppressed(False)
        watcher_manager.cancel_pending()
        if _op_lock.locked():
            _op_lock.release()


def run_push() -> dict:
    with session_scope() as session:
        settings = get_settings(session)
        try:
            git_service.push(settings)
            return {"ok": True}
        except GitError as exc:
            return {"ok": False, "error": str(exc)}


def run_restore(sha: str, paths: list[str]) -> dict:
    if not _op_lock.acquire(blocking=False):
        return {"ok": False, "skipped": True, "reason": "another operation in progress"}
    try:
        state["status"] = "restoring"
        with session_scope() as session:
            settings = get_settings(session)
            stopped: list[str] = []
            if settings.stop_containers_on_restore:
                stopped = _stop_affected(settings.services_dir, paths)
            try:
                git_service.restore(settings, sha, paths)
            except GitError as exc:
                state["status"] = "error"
                state["last_error"] = str(exc)
                return {"ok": False, "error": str(exc)}
            finally:
                for wd in stopped:
                    compose_up(wd)
            state["status"] = "idle"
            notify(
                settings,
                "Restore complete",
                f"Restored {', '.join(paths) or 'all'} from {sha[:8]}",
                success=True,
            )
            return {"ok": True, "restarted": stopped}
    finally:
        if _op_lock.locked():
            _op_lock.release()


def _stop_affected(services_dir: str, paths: list[str]) -> list[str]:
    """Stop compose projects whose working dir is affected by the restore."""
    affected_services = {p.strip("/").split("/")[0] for p in paths if p.strip("/")}
    stopped: list[str] = []
    for proj in list_compose_projects():
        wd = proj.get("working_dir", "")
        if not wd:
            continue
        service_name = wd.rstrip("/").split("/")[-1]
        if not affected_services or service_name in affected_services:
            if compose_down(wd):
                stopped.append(wd)
    return stopped
