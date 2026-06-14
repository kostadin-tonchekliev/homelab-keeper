from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from ..db import get_settings, session_scope
from ..models import SyncMode
from .git_service import git_service
from .logbus import log_bus

_INTERVAL_JOB = "interval_backup"
_GC_JOB = "git_gc"


class SchedulerManager:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(daemon=True)
        self._backup_cb = None

    def configure(self, backup_cb) -> None:
        self._backup_cb = backup_cb

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
        self.reload()
        # Periodic housekeeping, independent of sync mode.
        self._scheduler.add_job(
            self._gc, "interval", hours=24, id=_GC_JOB, replace_existing=True
        )

    def _gc(self) -> None:
        with session_scope() as session:
            git_service.gc(get_settings(session))

    def _interval_fire(self) -> None:
        if self._backup_cb is not None:
            self._backup_cb(reason="interval")

    def reload(self) -> None:
        """Re-read settings and (re)configure the interval safety job."""
        with session_scope() as session:
            settings = get_settings(session)
            mode = settings.sync_mode
            interval = max(30, settings.interval_seconds)

        try:
            self._scheduler.remove_job(_INTERVAL_JOB)
        except Exception:
            pass

        if mode in (SyncMode.hybrid, SyncMode.interval):
            self._scheduler.add_job(
                self._interval_fire,
                "interval",
                seconds=interval,
                id=_INTERVAL_JOB,
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            log_bus.info(f"Interval backup scheduled every {interval}s ({mode.value}).")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)


scheduler_manager = SchedulerManager()
