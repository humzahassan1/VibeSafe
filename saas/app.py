"""FastAPI application — the VibeSafe SaaS web service."""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from saas.auth import (
    create_session_token,
    generate_api_key,
    get_current_user,
    get_user_by_api_key,
    hash_password,
    verify_password,
)
from saas.billing import (
    BillingError,
    apply_webhook_event,
    create_billing_portal_session,
    create_checkout_session,
    verify_and_parse_webhook,
)
from saas.config import load_settings, stripe_enabled
from saas.database import ApiKey, Scan, User, get_session, init_db
from saas.scans import ScanError, run_scan_from_archive
from saas.usage import can_run_scan, get_usage_status
from saas.web import render_dashboard, render_landing

_settings = load_settings()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Initialize the database on startup.

    Args:
        _app: The FastAPI application (unused).

    Yields:
        Control back to the running application.
    """
    init_db()
    yield


app = FastAPI(title="VibeSafe", version="0.1.0", lifespan=_lifespan)


# ─────────────────────────── Auth ───────────────────────────


@app.post("/auth/signup")
def signup(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Register a new user and start a session.

    Args:
        response: Response object for setting the cookie.
        email: The user's email.
        password: The user's password (min 8 chars).
        session: Database session.

    Returns:
        JSON with the new user's email and plan.
    """
    email = email.strip().lower()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(email=email, password_hash=hash_password(password), plan="free")
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_session_token(user.id)
    resp = JSONResponse({"email": user.email, "plan": user.plan})
    _set_session_cookie(resp, token)
    return resp


@app.post("/auth/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Authenticate a user and start a session.

    Args:
        email: The user's email.
        password: The user's password.
        session: Database session.

    Returns:
        JSON with the user's email and plan.
    """
    email = email.strip().lower()
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_session_token(user.id)
    resp = JSONResponse({"email": user.email, "plan": user.plan})
    _set_session_cookie(resp, token)
    return resp


@app.post("/auth/logout")
def logout() -> JSONResponse:
    """Clear the session cookie.

    Returns:
        JSON confirmation.
    """
    resp = JSONResponse({"status": "logged out"})
    resp.delete_cookie("vibesafe_session")
    return resp


# ─────────────────────────── Account & keys ───────────────────────────


@app.get("/api/me")
def me(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Return the current user's account and usage status.

    Args:
        user: The authenticated user.
        session: Database session.

    Returns:
        Account and usage information.
    """
    usage = get_usage_status(session, user)
    return {
        "email": user.email,
        "plan": usage.plan_key,
        "plan_name": usage.plan_name,
        "usage": {
            "used": usage.used,
            "limit": usage.limit,
            "remaining": usage.remaining,
            "tier3_enabled": usage.tier3_enabled,
        },
    }


@app.post("/api/keys")
def create_key(
    name: str = Form("default"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Create a new API key for the current user.

    Args:
        name: A label for the key.
        user: The authenticated user.
        session: Database session.

    Returns:
        The full API key (shown once) and its metadata.
    """
    full_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name=name
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": full_key,
        "prefix": key_prefix,
        "warning": "Store this key now; it will not be shown again.",
    }


@app.get("/api/keys")
def list_keys(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    """List the current user's API keys (prefixes only).

    Args:
        user: The authenticated user.
        session: Database session.

    Returns:
        A list of key metadata.
    """
    keys = session.execute(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.revoked.is_(False))
    ).scalars().all()
    return [
        {"id": k.id, "name": k.name, "prefix": k.key_prefix, "created_at": k.created_at.isoformat()}
        for k in keys
    ]


@app.delete("/api/keys/{key_id}")
def revoke_key(
    key_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Revoke an API key.

    Args:
        key_id: The key ID.
        user: The authenticated user.
        session: Database session.

    Returns:
        Confirmation.
    """
    api_key = session.get(ApiKey, key_id)
    if api_key is None or api_key.user_id != user.id:
        raise HTTPException(status_code=404, detail="Key not found.")
    api_key.revoked = True
    session.add(api_key)
    session.commit()
    return {"status": "revoked", "id": key_id}


# ─────────────────────────── Scans ───────────────────────────


@app.post("/api/scans")
async def create_scan(
    request: Request,
    project: UploadFile = File(...),
    name: str = Form("project"),
    skip_tier3: bool = Form(True),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Upload a zipped project and scan it.

    Accepts either a session cookie or an API key (Authorization: Bearer).

    Args:
        request: The incoming request.
        project: The uploaded zip archive.
        name: Display name for the scan.
        skip_tier3: Whether to skip LLM analysis.
        session: Database session.

    Returns:
        JSON with the scan ID and summary.
    """
    user = _resolve_user(request, session)

    allowed, reason = can_run_scan(session, user)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=reason)

    max_bytes = _settings.max_upload_mb * 1024 * 1024
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="vibesafe_upload_")
    try:
        size = 0
        with os.fdopen(tmp_fd, "wb") as out:
            while chunk := await project.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds {_settings.max_upload_mb} MB limit.",
                    )
                out.write(chunk)

        try:
            result = run_scan_from_archive(
                session, user, tmp_path, project_name=name, skip_tier3=skip_tier3
            )
        except ScanError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return JSONResponse(
        {
            "scan_id": result.scan_id,
            "summary": result.summary,
            "findings": result.report_json.get("findings", []),
        }
    )


@app.get("/api/scans")
def list_scans(
    request: Request,
    session: Session = Depends(get_session),
) -> list[dict]:
    """List the current user's scans, most recent first.

    Args:
        request: The incoming request.
        session: Database session.

    Returns:
        A list of scan summaries.
    """
    user = _resolve_user(request, session)
    scans = session.execute(
        select(Scan).where(Scan.user_id == user.id).order_by(Scan.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": s.id,
            "project_name": s.project_name,
            "framework": s.framework,
            "total": s.total_findings,
            "critical": s.critical_findings,
            "warning": s.warning_findings,
            "tiers_run": s.tiers_run,
            "created_at": s.created_at.isoformat(),
        }
        for s in scans
    ]


@app.get("/api/scans/{scan_id}")
def get_scan(
    scan_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Return the full report for a scan.

    Args:
        scan_id: The scan ID.
        request: The incoming request.
        session: Database session.

    Returns:
        The scan metadata and full report.
    """
    user = _resolve_user(request, session)
    scan = session.get(Scan, scan_id)
    if scan is None or scan.user_id != user.id:
        raise HTTPException(status_code=404, detail="Scan not found.")
    import json

    return {
        "id": scan.id,
        "project_name": scan.project_name,
        "framework": scan.framework,
        "created_at": scan.created_at.isoformat(),
        "report": json.loads(scan.report_json),
    }


# ─────────────────────────── Billing ───────────────────────────


@app.post("/billing/checkout")
def billing_checkout(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Start a Stripe Checkout session to upgrade to Pro.

    Args:
        user: The authenticated user.
        session: Database session.

    Returns:
        JSON containing the checkout URL.
    """
    try:
        url = create_checkout_session(session, user)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"checkout_url": url}


@app.post("/billing/portal")
def billing_portal(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Open the Stripe billing portal for the current user.

    Args:
        user: The authenticated user.
        session: Database session.

    Returns:
        JSON containing the portal URL.
    """
    try:
        url = create_billing_portal_session(session, user)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"portal_url": url}


@app.post("/billing/webhook")
async def billing_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Handle Stripe webhook events (upgrade/downgrade).

    Args:
        request: The incoming request (raw body needed for verification).
        session: Database session.

    Returns:
        JSON acknowledgment.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = verify_and_parse_webhook(payload, signature)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    apply_webhook_event(session, event)
    return {"received": True}


# ─────────────────────────── Web UI ───────────────────────────


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    """Render the landing page.

    Returns:
        The landing page HTML.
    """
    return HTMLResponse(render_landing(stripe_enabled()))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the dashboard for a logged-in user.

    Args:
        request: The incoming request.
        session: Database session.

    Returns:
        The dashboard HTML, or a redirect to the landing page.
    """
    try:
        user = get_current_user(request, session)
    except HTTPException:
        return HTMLResponse(status_code=302, headers={"Location": "/"})

    usage = get_usage_status(session, user)
    scans = session.execute(
        select(Scan).where(Scan.user_id == user.id).order_by(Scan.created_at.desc())
    ).scalars().all()
    return HTMLResponse(render_dashboard(user, usage, scans, stripe_enabled()))


@app.get("/health")
def health() -> dict:
    """Liveness probe.

    Returns:
        Status JSON.
    """
    return {"status": "ok", "stripe": stripe_enabled()}


# ─────────────────────────── Helpers ───────────────────────────


def _set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie on a response.

    Args:
        response: The response to mutate.
        token: The signed session token.
    """
    secure = _settings.app_base_url.startswith("https")
    response.set_cookie(
        "vibesafe_session",
        token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=60 * 60 * 24 * 7,
    )


def _resolve_user(request: Request, session: Session) -> User:
    """Resolve the user from either a session cookie or an API key.

    Args:
        request: The incoming request.
        session: Database session.

    Returns:
        The authenticated User.

    Raises:
        HTTPException: 401 if neither method authenticates.
    """
    auth_header = request.headers.get("authorization")
    if auth_header:
        return get_user_by_api_key(auth_header, session)
    return get_current_user(request, session)
