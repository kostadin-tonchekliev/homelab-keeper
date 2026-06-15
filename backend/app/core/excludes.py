from __future__ import annotations

from pathlib import Path
from sqlmodel import Session, select

from ..config import get_config
from ..models import ExcludeRule, ServiceSetting
from .git_service import git_service
from .logbus import log_bus

# Always-on noise excludes (safe defaults; the rest is opt-in per your "back up
# as-is" choice). These avoid committing volatile runtime cruft.
DEFAULT_EXCLUDES = [
    "*.pid",
    "*.sock",
    "*.lock",
    "*.log",
    "*.bak",
    "*.tmp",
    "**/.DS_Store",
]


def _data_dir_exclude(services_dir: str) -> str | None:
    """Return a gitignore-style path if the app's data directory sits inside
    the services directory (i.e. the user bind-mounted /data to a path under
    /services on the host).

    If the data dir is inside the work-tree and not excluded, every backup
    would stage the git object store, causing a runaway commit spiral and
    potential history corruption.
    """
    cfg = get_config()
    try:
        data = Path(cfg.data_dir).resolve()
        services = Path(services_dir).resolve()
        rel = data.relative_to(services)   # raises ValueError if not inside
        rel_str = str(rel)
        log_bus.warning(
            f"Data directory ({cfg.data_dir}) is inside the services directory "
            f"({services_dir}). It has been automatically excluded from backups "
            "to prevent circular git history. "
            "For a cleaner setup, use a named Docker volume for /data instead of "
            "a bind-mount inside your services tree."
        )
        return rel_str
    except ValueError:
        return None


def build_exclude_lines(session: Session) -> list[str]:
    lines: list[str] = list(DEFAULT_EXCLUDES)

    # Guard against the data dir being inside the services tree.
    from ..db import get_settings
    settings = get_settings(session)
    data_rel = _data_dir_exclude(settings.services_dir)
    if data_rel:
        lines.append(f"/{data_rel}")

    disabled_services = session.exec(
        select(ServiceSetting).where(ServiceSetting.enabled == False)  # noqa: E712
    ).all()
    for svc in disabled_services:
        lines.append(f"/{svc.name.strip('/')}/")

    rules = session.exec(
        select(ExcludeRule).where(ExcludeRule.enabled == True)  # noqa: E712
    ).all()
    for rule in rules:
        path = rule.path.strip().strip("/")
        if path:
            # No trailing slash — matches both files and directories at this
            # exact path (trailing slash would silently skip plain files).
            lines.append(f"/{path}")
    return lines


def apply_excludes(session: Session) -> list[str]:
    lines = build_exclude_lines(session)
    git_service.write_excludes(lines)
    return lines
