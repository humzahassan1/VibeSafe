"""Tests for the SaaS layer — auth, API keys, scans, usage limits, billing."""

from __future__ import annotations

import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use an isolated in-memory-ish test DB before importing any saas module.
_TEST_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_saas_test.db"
)
os.environ["VIBESAFE_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["VIBESAFE_SECRET_KEY"] = "test-secret-key"
os.environ.pop("STRIPE_SECRET_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from saas import database  # noqa: E402
from saas.app import app  # noqa: E402
from saas.billing import apply_webhook_event  # noqa: E402
from saas.database import SessionLocal, User  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """Recreate the database before each test."""
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    yield
    database.Base.metadata.drop_all(bind=database.engine)


@pytest.fixture
def client():
    """Return a test client."""
    return TestClient(app)


def _make_zip(files: dict[str, str]) -> bytes:
    """Build an in-memory zip archive from a path->content mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


# Assembled at runtime so the literal key never appears in the committed file
# (avoids tripping GitHub push protection on this test fixture).
_FAKE_STRIPE_KEY = "sk_live_" + "abc123def456ghi789jkl012mno"

_VULN_FILES = {
    "app/server.js": (
        'const express = require("express");\n'
        'const app = express();\n'
        f'const KEY = "{_FAKE_STRIPE_KEY}";\n'
        'app.get("/u", (req, res) => db.query("SELECT * FROM u WHERE id = " + req.params.id));\n'
        "app.listen(3000);\n"
    ),
    "app/package.json": '{"name": "x", "dependencies": {"express": "*"}}',
}

_CLEAN_FILES = {
    "app/index.js": 'console.log("hello");\n',
}


def _signup(client: TestClient, email="a@b.com", password="password123") -> None:
    """Sign up and set the session cookie on the client."""
    res = client.post("/auth/signup", data={"email": email, "password": password})
    assert res.status_code == 200, res.text


class TestAuth:
    def test_signup_creates_user(self, client):
        res = client.post("/auth/signup", data={"email": "new@x.com", "password": "password123"})
        assert res.status_code == 200
        assert res.json()["email"] == "new@x.com"
        assert res.json()["plan"] == "free"
        assert "vibesafe_session" in res.cookies

    def test_signup_rejects_short_password(self, client):
        res = client.post("/auth/signup", data={"email": "a@x.com", "password": "short"})
        assert res.status_code == 400

    def test_signup_rejects_duplicate(self, client):
        client.post("/auth/signup", data={"email": "dup@x.com", "password": "password123"})
        res = client.post("/auth/signup", data={"email": "dup@x.com", "password": "password123"})
        assert res.status_code == 409

    def test_login_succeeds(self, client):
        client.post("/auth/signup", data={"email": "l@x.com", "password": "password123"})
        client.cookies.clear()
        res = client.post("/auth/login", data={"email": "l@x.com", "password": "password123"})
        assert res.status_code == 200

    def test_login_wrong_password(self, client):
        client.post("/auth/signup", data={"email": "w@x.com", "password": "password123"})
        client.cookies.clear()
        res = client.post("/auth/login", data={"email": "w@x.com", "password": "nope12345"})
        assert res.status_code == 401

    def test_me_requires_auth(self, client):
        client.cookies.clear()
        res = client.get("/api/me")
        assert res.status_code == 401

    def test_me_returns_usage(self, client):
        _signup(client)
        res = client.get("/api/me")
        assert res.status_code == 200
        body = res.json()
        assert body["plan"] == "free"
        assert body["usage"]["limit"] == 10
        assert body["usage"]["used"] == 0


class TestApiKeys:
    def test_create_and_list_key(self, client):
        _signup(client)
        res = client.post("/api/keys", data={"name": "ci"})
        assert res.status_code == 200
        key = res.json()["key"]
        assert key.startswith("vsk_")

        listed = client.get("/api/keys").json()
        assert len(listed) == 1
        assert listed[0]["name"] == "ci"

    def test_revoke_key(self, client):
        _signup(client)
        key_id = client.post("/api/keys", data={"name": "temp"}).json()["id"]
        res = client.delete(f"/api/keys/{key_id}")
        assert res.status_code == 200
        assert client.get("/api/keys").json() == []

    def test_api_key_authenticates_scan(self, client):
        _signup(client)
        key = client.post("/api/keys", data={"name": "ci"}).json()["key"]
        client.cookies.clear()
        archive = _make_zip(_VULN_FILES)
        res = client.post(
            "/api/scans",
            headers={"Authorization": f"Bearer {key}"},
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "viakey", "skip_tier3": "true"},
        )
        assert res.status_code == 200

    def test_bad_api_key_rejected(self, client):
        client.cookies.clear()
        archive = _make_zip(_CLEAN_FILES)
        res = client.post(
            "/api/scans",
            headers={"Authorization": "Bearer vsk_totally_invalid"},
            files={"project": ("p.zip", archive, "application/zip")},
        )
        assert res.status_code == 401


class TestScans:
    def test_scan_finds_vulnerabilities(self, client):
        _signup(client)
        archive = _make_zip(_VULN_FILES)
        res = client.post(
            "/api/scans",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "vuln", "skip_tier3": "true"},
        )
        assert res.status_code == 200
        summary = res.json()["summary"]
        assert summary["total"] >= 2
        assert summary["critical"] >= 1

    def test_scan_clean_project(self, client):
        _signup(client)
        archive = _make_zip(_CLEAN_FILES)
        res = client.post(
            "/api/scans",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "clean", "skip_tier3": "true"},
        )
        assert res.status_code == 200
        assert res.json()["summary"]["total"] == 0

    def test_scan_persists_to_history(self, client):
        _signup(client)
        archive = _make_zip(_VULN_FILES)
        client.post(
            "/api/scans",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "hist", "skip_tier3": "true"},
        )
        history = client.get("/api/scans").json()
        assert len(history) == 1
        assert history[0]["project_name"] == "hist"

    def test_scan_detail_returns_report(self, client):
        _signup(client)
        archive = _make_zip(_VULN_FILES)
        scan_id = client.post(
            "/api/scans",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "detail", "skip_tier3": "true"},
        ).json()["scan_id"]
        detail = client.get(f"/api/scans/{scan_id}").json()
        assert detail["report"]["summary"]["total"] >= 2

    def test_rejects_non_zip(self, client):
        _signup(client)
        res = client.post(
            "/api/scans",
            files={"project": ("p.zip", b"not a zip", "application/zip")},
            data={"name": "bad", "skip_tier3": "true"},
        )
        assert res.status_code == 400

    def test_free_plan_cannot_use_tier3(self, client):
        _signup(client)
        archive = _make_zip(_CLEAN_FILES)
        res = client.post(
            "/api/scans",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "t3", "skip_tier3": "false"},
        )
        assert res.status_code == 400
        assert "Pro" in res.json()["detail"]

    def test_scans_isolated_between_users(self, client):
        _signup(client, email="u1@x.com")
        archive = _make_zip(_VULN_FILES)
        client.post(
            "/api/scans",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "u1scan", "skip_tier3": "true"},
        )
        client.cookies.clear()
        _signup(client, email="u2@x.com")
        assert client.get("/api/scans").json() == []


class TestUsageLimits:
    def test_free_plan_blocks_after_limit(self, client):
        _signup(client, email="heavy@x.com")
        # Seed 10 scans directly to hit the free limit.
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "heavy@x.com").one()
            for _ in range(10):
                db.add(database.Scan(user_id=user.id, project_name="seed"))
            db.commit()

        archive = _make_zip(_CLEAN_FILES)
        res = client.post(
            "/api/scans",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "over", "skip_tier3": "true"},
        )
        assert res.status_code == 402
        assert "limit" in res.json()["detail"].lower()

    def test_pro_plan_higher_limit(self, client):
        _signup(client, email="pro@x.com")
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "pro@x.com").one()
            user.plan = "pro"
            for _ in range(10):
                db.add(database.Scan(user_id=user.id, project_name="seed"))
            db.commit()

        res = client.get("/api/me").json()
        assert res["plan"] == "pro"
        assert res["usage"]["limit"] == 500
        assert res["usage"]["remaining"] == 490


class TestBilling:
    def test_checkout_without_stripe_returns_error(self, client):
        _signup(client)
        res = client.post("/billing/checkout")
        assert res.status_code == 400
        assert "not configured" in res.json()["detail"].lower()

    def test_webhook_upgrade_event(self, client):
        _signup(client, email="upgrade@x.com")
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "upgrade@x.com").one()
            uid = user.id
            event = {
                "type": "checkout.session.completed",
                "data": {"object": {
                    "metadata": {"user_id": str(uid)},
                    "subscription": "sub_123",
                    "customer": "cus_123",
                }},
            }
            apply_webhook_event(db, event)

        with SessionLocal() as db:
            user = db.get(User, uid)
            assert user.plan == "pro"
            assert user.stripe_subscription_id == "sub_123"

    def test_webhook_downgrade_event(self, client):
        _signup(client, email="downgrade@x.com")
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "downgrade@x.com").one()
            user.plan = "pro"
            user.stripe_subscription_id = "sub_456"
            user.stripe_customer_id = "cus_456"
            db.commit()
            uid = user.id

        with SessionLocal() as db:
            event = {
                "type": "customer.subscription.deleted",
                "data": {"object": {"id": "sub_456", "customer": "cus_456"}},
            }
            apply_webhook_event(db, event)

        with SessionLocal() as db:
            assert db.get(User, uid).plan == "free"


class TestWebUI:
    def test_landing_page_renders(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "VibeSafe" in res.text

    def test_dashboard_redirects_when_logged_out(self, client):
        client.cookies.clear()
        res = client.get("/dashboard", follow_redirects=False)
        assert res.status_code == 302

    def test_dashboard_renders_when_logged_in(self, client):
        _signup(client, email="dash@x.com")
        res = client.get("/dashboard")
        assert res.status_code == 200
        assert "dash@x.com" in res.text

    def test_health(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
