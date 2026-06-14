from __future__ import annotations

import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..db import get_settings, session_scope
from ..models import SyncMode
from .excludes import build_exclude_lines
from .logbus import log_bus
from .manifest import MANIFEST_JSON, MANIFEST_MD

# Files the service itself writes into the work-tree; ignore to avoid loops.
_SELF_WRITES = {MANIFEST_JSON, MANIFEST_MD}

# Glob suffixes that should never trigger a backup (log files, editor temp
# files, etc.). These are checked against the filename only.
_IGNORE_SUFFIXES = {".log", ".bak", ".tmp", ".swp", ".swx"}
_IGNORE_NAMES = {".DS_Store"}


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, manager: "WatcherManager") -> None:
        self._manager = manager

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        name = path.name
        if name in _SELF_WRITES or name in _IGNORE_NAMES:
            return
        if path.suffix.lower() in _IGNORE_SUFFIXES:
            return
        if self._manager.is_suppressed():
            return
        if self._manager.is_excluded(path):
            return
        self._manager.schedule()


class WatcherManager:
    """Recursively watches the services dir and triggers a debounced backup.

    Excluded directories are skipped both for triggering backups and (best
    effort) to keep the inotify watch count low.
    """

    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._services_dir: str = ""
        self._exclude_prefixes: list[str] = []
        self._debounce: int = 30
        self._backup_cb = None
        self._suppressed: bool = False

    def configure(self, backup_cb) -> None:
        self._backup_cb = backup_cb

    def is_suppressed(self) -> bool:
        return self._suppressed

    def set_suppressed(self, value: bool) -> None:
        self._suppressed = value

    def cancel_pending(self) -> None:
        """Cancel any debounce timer that is waiting to fire."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def is_excluded(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self._services_dir).as_posix()
        except ValueError:
            return False
        return any(
            rel == pref or rel.startswith(pref + "/") for pref in self._exclude_prefixes
        )

    def _load(self) -> None:
        with session_scope() as session:
            settings = get_settings(session)
            self._services_dir = settings.services_dir
            self._debounce = max(2, settings.debounce_seconds)
            lines = build_exclude_lines(session)
        self._exclude_prefixes = [
            ln.strip().strip("/")
            for ln in lines
            if ln and not ln.startswith("#") and "*" not in ln
        ]

    def schedule(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        if self._backup_cb is not None:
            self._backup_cb(reason="watch")

    def restart(self) -> None:
        """(Re)start the observer using the latest settings."""
        self.stop()
        self._load()
        with session_scope() as session:
            mode = get_settings(session).sync_mode
        if mode not in (SyncMode.hybrid, SyncMode.watch):
            log_bus.info("File watcher disabled (sync mode = interval).")
            return
        if not Path(self._services_dir).is_dir():
            log_bus.warning(f"Services dir '{self._services_dir}' not found; watcher idle.")
            return
        observer = Observer()
        observer.schedule(_DebouncedHandler(self), self._services_dir, recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer
        log_bus.info(
            f"File watcher started on {self._services_dir} "
            f"(debounce {self._debounce}s, {len(self._exclude_prefixes)} excluded paths)."
        )

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        if self._observer is not None:
            self._observer.stop()
            try:
                self._observer.join(timeout=5)
            except RuntimeError:
                pass
            self._observer = None


watcher_manager = WatcherManager()
