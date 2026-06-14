from __future__ import annotations

from sqlmodel import Session, select

from ..models import ExcludeRule, ServiceSetting
from .git_service import git_service

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


def build_exclude_lines(session: Session) -> list[str]:
    lines: list[str] = list(DEFAULT_EXCLUDES)

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
            lines.append(f"/{path}/")
    return lines


def apply_excludes(session: Session) -> list[str]:
    lines = build_exclude_lines(session)
    git_service.write_excludes(lines)
    return lines
