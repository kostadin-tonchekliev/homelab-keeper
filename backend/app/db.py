from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from .config import get_config
from .models import Settings

_config = get_config()
_engine = create_engine(
    f"sqlite:///{_config.db_path}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(_engine)
    with Session(_engine) as session:
        existing = session.get(Settings, 1)
        if existing is None:
            session.add(Settings(id=1, services_dir=_config.services_dir))
            session.commit()


def get_session() -> Iterator[Session]:
    with Session(_engine) as session:
        yield session


def session_scope() -> Session:
    """Standalone session for use outside request handlers (watcher/scheduler)."""
    return Session(_engine)


def get_settings(session: Session) -> Settings:
    settings = session.get(Settings, 1)
    if settings is None:
        settings = Settings(id=1, services_dir=_config.services_dir)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


__all__ = [
    "init_db",
    "get_session",
    "session_scope",
    "get_settings",
    "select",
]
