from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

COMPOSE_NAMES = ("docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml")

# Size cache: key = absolute path string, value = (size_bytes, computed_at_monotonic)
_size_cache: dict[str, tuple[int, float]] = {}
_size_cache_lock = Lock()
_SIZE_TTL = 300  # seconds — recompute at most every 5 minutes


@dataclass
class SubDir:
    name: str
    rel_path: str
    size_bytes: int


@dataclass
class DiscoveredService:
    name: str
    rel_path: str
    compose_file: str | None
    size_bytes: int
    subdirs: list[SubDir] = field(default_factory=list)


def _dir_size(path: Path) -> int:
    key = str(path)
    now = time.monotonic()
    with _size_cache_lock:
        cached = _size_cache.get(key)
        if cached is not None and (now - cached[1]) < _SIZE_TTL:
            return cached[0]

    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue

    with _size_cache_lock:
        _size_cache[key] = (total, time.monotonic())
    return total


def _dir_size_shallow(path: Path) -> int:
    """Count only immediate children (files + dirs by name only via os.scandir).

    Returns -1 so callers can tell it's an estimate, and triggers a background
    full count only the first time. For the UI we just show the cached value once
    it has been computed.
    """
    key = str(path)
    with _size_cache_lock:
        cached = _size_cache.get(key)
        if cached is not None:
            return cached[0]
    return -1


def find_compose(path: Path) -> str | None:
    for name in COMPOSE_NAMES:
        if (path / name).exists():
            return name
    return None


def discover_services(services_dir: str) -> list[DiscoveredService]:
    """Return all immediate subdirectories of the base dir that contain a compose
    file.  Directory sizes are served from a 5-minute cache so that large trees
    (e.g. a 6 GB audiobookshelf data folder) do not block the API response.
    The first call after a cache miss kicks off a background thread to walk the
    tree; until that completes the reported size is -1 (UI shows "calculating").
    """
    import threading

    base = Path(services_dir)
    services: list[DiscoveredService] = []
    if not base.is_dir():
        return services

    def _bg_size(p: Path) -> None:
        _dir_size(p)

    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        compose = find_compose(entry)
        if compose is None:
            continue

        subdirs = []
        for sub in sorted(entry.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            sz = _dir_size_shallow(sub)
            if sz == -1:
                threading.Thread(target=_bg_size, args=(sub,), daemon=True).start()
            subdirs.append(
                SubDir(name=sub.name, rel_path=f"{entry.name}/{sub.name}", size_bytes=sz)
            )

        svc_sz = _dir_size_shallow(entry)
        if svc_sz == -1:
            threading.Thread(target=_bg_size, args=(entry,), daemon=True).start()

        services.append(
            DiscoveredService(
                name=entry.name,
                rel_path=entry.name,
                compose_file=compose,
                size_bytes=svc_sz,
                subdirs=subdirs,
            )
        )
    return services


def invalidate_size_cache(path: str | None = None) -> None:
    """Evict one path or the whole cache (e.g. after a restore)."""
    with _size_cache_lock:
        if path:
            _size_cache.pop(path, None)
        else:
            _size_cache.clear()
