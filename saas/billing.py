"""Stripe billing integration.

Runs in Stripe test mode by default. If no Stripe key is configured, billing
endpoints return a clear "not configured" error rather than crashing, so the
rest of the app (auth, scanning, free tier) works without any Stripe setup.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from saas.config import load_settings, stripe_enabled
from saas.database import User
from utils.logger import get_logger

_log = get_logger("saas.billing")
_settings = load_settings()


class BillingError(Exception):
    """Raised when a billing operation cannot be completed."""


def _get_stripe():
    """Import and configure the Stripe SDK.

    Returns:
        The configured stripe module.

    Raises:
        BillingError: If Stripe is not configured or installed.
    """
    if not stripe_enabled():
        raise BillingError(
            "Billing is not configured. Set STRIPE_SECRET_KEY to enable upgrades."
        )
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise BillingError("The 'stripe' package is not installed.") from exc

    stripe.api_key = _settings.stripe_secret_key
    return stripe


def create_checkout_session(session: Session, user: User) -> str:
    """Create a Stripe Checkout session for the Pro plan.

    Args:
        session: Database session.
        user: The user upgrading.

    Returns:
        The Checkout session URL to redirect the user to.

    Raises:
        BillingError: If Stripe or the price ID is not configured.
    """
    stripe = _get_stripe()
    if not _settings.stripe_price_id:
        raise BillingError("STRIPE_PRICE_ID is not set.")

    customer_id = _ensure_customer(session, user, stripe)

    checkout = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": _settings.stripe_price_id, "quantity": 1}],
        success_url=f"{_settings.app_base_url}/dashboard?upgraded=1",
        cancel_url=f"{_settings.app_base_url}/dashboard?canceled=1",
        metadata={"user_id": str(user.id)},
    )
    return checkout.url


def create_billing_portal_session(session: Session, user: User) -> str:
    """Create a Stripe billing portal session for managing a subscription.

    Args:
        session: Database session.
        user: The user.

    Returns:
        The billing portal URL.

    Raises:
        BillingError: If the user has no Stripe customer record.
    """
    stripe = _get_stripe()
    if not user.stripe_customer_id:
        raise BillingError("No active subscription to manage.")

    portal = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{_settings.app_base_url}/dashboard",
    )
    return portal.url


def _ensure_customer(session: Session, user: User, stripe) -> str:
    """Return the user's Stripe customer ID, creating one if needed.

    Args:
        session: Database session.
        user: The user.
        stripe: Configured stripe module.

    Returns:
        The Stripe customer ID.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
    user.stripe_customer_id = customer.id
    session.add(user)
    session.commit()
    return customer.id


def verify_and_parse_webhook(payload: bytes, signature: str | None) -> dict:
    """Verify a Stripe webhook signature and return the event.

    Args:
        payload: The raw request body.
        signature: The Stripe-Signature header.

    Returns:
        The parsed event as a dict.

    Raises:
        BillingError: If verification fails.
    """
    stripe = _get_stripe()
    if not _settings.stripe_webhook_secret:
        raise BillingError("STRIPE_WEBHOOK_SECRET is not set.")

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, _settings.stripe_webhook_secret
        )
    except Exception as exc:  # stripe raises several exception types
        raise BillingError(f"Webhook verification failed: {exc}") from exc

    return event


def apply_webhook_event(session: Session, event: dict) -> None:
    """Update user subscription state based on a Stripe webhook event.

    Handles checkout completion (upgrade) and subscription cancellation
    (downgrade to free).

    Args:
        session: Database session.
        event: The verified Stripe event.
    """
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        user_id = (obj.get("metadata") or {}).get("user_id")
        subscription_id = obj.get("subscription")
        customer_id = obj.get("customer")
        if user_id:
            user = session.get(User, int(user_id))
            if user:
                user.plan = "pro"
                user.stripe_subscription_id = subscription_id
                if customer_id:
                    user.stripe_customer_id = customer_id
                session.add(user)
                session.commit()
                _log.info("User %s upgraded to Pro", user_id)

    elif event_type in ("customer.subscription.deleted", "customer.subscription.canceled"):
        subscription_id = obj.get("id")
        customer_id = obj.get("customer")
        user = None
        if subscription_id:
            user = (
                session.query(User)
                .filter(User.stripe_subscription_id == subscription_id)
                .one_or_none()
            )
        if user is None and customer_id:
            user = (
                session.query(User)
                .filter(User.stripe_customer_id == customer_id)
                .one_or_none()
            )
        if user:
            user.plan = "free"
            user.stripe_subscription_id = None
            session.add(user)
            session.commit()
            _log.info("User %s downgraded to Free", user.id)
