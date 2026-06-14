from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Literal

Level = Literal["info", "success", "warning", "error"]


class LogBus:
    """In-memory ring buffer of recent activity, surfaced in the UI's Logs view."""

    def __init__(self, capacity: int = 500) -> None:
        self._buf: deque[dict] = deque(maxlen=capacity)
        self._lock = Lock()
        self._logger = logging.getLogger("backup")

    def add(self, level: Level, message: str) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        with self._lock:
            self._buf.append(entry)
        getattr(self._logger, "error" if level == "error" else "info")(message)

    def info(self, message: str) -> None:
        self.add("info", message)

    def success(self, message: str) -> None:
        self.add("success", message)

    def warning(self, message: str) -> None:
        self.add("warning", message)

    def error(self, message: str) -> None:
        self.add("error", message)

    def recent(self, limit: int = 200) -> list[dict]:
        with self._lock:
            items = list(self._buf)
        return items[-limit:][::-1]


log_bus = LogBus()
