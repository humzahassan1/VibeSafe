"""SaaS configuration — plans, limits, and environment settings.

All secrets are read from environment variables. Nothing is hardcoded.
Stripe runs in test mode unless a live key is explicitly provided.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    """A subscription plan tier.

    Args:
        key: Internal identifier (e.g., "free", "pro").
        name: Human-readable name.
        monthly_scan_limit: Max scans per calendar month (-1 = unlimited).
        tier3_enabled: Whether LLM-based Tier 3 analysis is allowed.
        price_cents: Monthly price in cents (0 for free).
    """

    key: str
    name: str
    monthly_scan_limit: int
    tier3_enabled: bool
    price_cents: int


PLANS: dict[str, Plan] = {
    "free": Plan(
        key="free",
        name="Free",
        monthly_scan_limit=10,
        tier3_enabled=False,
        price_cents=0,
    ),
    "pro": Plan(
        key="pro",
        name="Pro",
        monthly_scan_limit=500,
        tier3_enabled=True,
        price_cents=2900,
    ),
}

DEFAULT_PLAN = "free"


def get_plan(key: str | None) -> Plan:
    """Return the plan for a key, falling back to the free plan.

    Args:
        key: Plan key or None.

    Returns:
        The matching Plan, or the free plan if not found.
    """
    return PLANS.get(key or DEFAULT_PLAN, PLANS[DEFAULT_PLAN])


@dataclass
class Settings:
    """Runtime settings loaded from the environment.

    Args:
        database_url: SQLAlchemy database URL.
        secret_key: Signing key for session tokens.
        stripe_secret_key: Stripe API secret (test or live).
        stripe_webhook_secret: Stripe webhook signing secret.
        stripe_price_id: Stripe price ID for the Pro plan.
        app_base_url: Public base URL for building redirect links.
        max_upload_mb: Max size of an uploaded project archive.
    """

    database_url: str
    secret_key: str
    stripe_secret_key: str | None
    stripe_webhook_secret: str | None
    stripe_price_id: str | None
    app_base_url: str
    max_upload_mb: int
    github_token: str | None


def load_settings() -> Settings:
    """Load settings from environment variables with safe defaults.

    Returns:
        Populated Settings instance.
    """
    return Settings(
        database_url=os.environ.get("VIBESAFE_DATABASE_URL", "sqlite:///./vibesafe_saas.db"),
        secret_key=os.environ.get("VIBESAFE_SECRET_KEY", "dev-insecure-change-me"),
        stripe_secret_key=os.environ.get("STRIPE_SECRET_KEY"),
        stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET"),
        stripe_price_id=os.environ.get("STRIPE_PRICE_ID"),
        app_base_url=os.environ.get("VIBESAFE_APP_URL", "http://localhost:8000"),
        max_upload_mb=int(os.environ.get("VIBESAFE_MAX_UPLOAD_MB", "25")),
        github_token=os.environ.get("GITHUB_TOKEN"),
    )


def stripe_enabled() -> bool:
    """Return True if Stripe is configured.

    Returns:
        True when a Stripe secret key is present in the environment.
    """
    return bool(os.environ.get("STRIPE_SECRET_KEY"))
