"""Database models and session management for the SaaS layer."""

from __future__ import annotations

import datetime as dt
from typing import Generator

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from saas.config import DEFAULT_PLAN, load_settings

_settings = load_settings()

_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(_settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _utcnow() -> dt.datetime:
    """Return the current UTC time.

    Returns:
        Timezone-naive UTC datetime.
    """
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class User(Base):
    """A registered user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default=DEFAULT_PLAN, nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    scans: Mapped[list["Scan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    """An API key belonging to a user, used for programmatic scans."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="api_keys")


class Scan(Base):
    """A record of a completed scan and its summary results."""

    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), default="project", nullable=False)
    framework: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    total_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tiers_run: Mapped[str] = mapped_column(String(32), default="1, 2", nullable=False)
    report_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="scans")


def init_db() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session (FastAPI dependency).

    Yields:
        An active SQLAlchemy session, closed on completion.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
