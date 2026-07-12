"""Usage tracking and plan-limit enforcement."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from saas.config import get_plan
from saas.database import Scan, User


@dataclass
class UsageStatus:
    """A user's current usage against their plan limits.

    Args:
        plan_key: The user's plan key.
        plan_name: Human-readable plan name.
        used: Scans used in the current calendar month.
        limit: Monthly scan limit (-1 = unlimited).
        remaining: Scans remaining (-1 = unlimited).
        tier3_enabled: Whether Tier 3 is allowed on this plan.
    """

    plan_key: str
    plan_name: str
    used: int
    limit: int
    remaining: int
    tier3_enabled: bool


def _month_start(now: dt.datetime | None = None) -> dt.datetime:
    """Return the first moment of the current UTC month.

    Args:
        now: Reference time, defaults to current UTC.

    Returns:
        Datetime at midnight on the first of the month.
    """
    now = now or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def scans_this_month(session: Session, user_id: int) -> int:
    """Count a user's scans in the current calendar month.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        Number of scans since the start of the month.
    """
    count = session.execute(
        select(func.count(Scan.id)).where(
            Scan.user_id == user_id,
            Scan.created_at >= _month_start(),
        )
    ).scalar_one()
    return int(count)


def get_usage_status(session: Session, user: User) -> UsageStatus:
    """Compute a user's usage status against their plan.

    Args:
        session: Database session.
        user: The user.

    Returns:
        A populated UsageStatus.
    """
    plan = get_plan(user.plan)
    used = scans_this_month(session, user.id)
    if plan.monthly_scan_limit < 0:
        remaining = -1
    else:
        remaining = max(0, plan.monthly_scan_limit - used)
    return UsageStatus(
        plan_key=plan.key,
        plan_name=plan.name,
        used=used,
        limit=plan.monthly_scan_limit,
        remaining=remaining,
        tier3_enabled=plan.tier3_enabled,
    )


def can_run_scan(session: Session, user: User) -> tuple[bool, str]:
    """Check whether a user may run another scan this month.

    Args:
        session: Database session.
        user: The user.

    Returns:
        A tuple of (allowed, reason). Reason is empty when allowed.
    """
    status = get_usage_status(session, user)
    if status.limit < 0:
        return True, ""
    if status.used >= status.limit:
        return (
            False,
            f"Monthly scan limit reached ({status.limit} on the {status.plan_name} plan). "
            f"Upgrade to Pro for more scans.",
        )
    return True, ""
