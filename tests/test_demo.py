"""Tests for public demo scan endpoints."""

from __future__ import annotations

import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_demo_test.db")
os.environ["VIBESAFE_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["VIBESAFE_SECRET_KEY"] = "test-secret-key"
os.environ.pop("STRIPE_SECRET_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from saas import database  # noqa: E402
from saas.app import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    yield
    database.Base.metadata.drop_all(bind=database.engine)


@pytest.fixture
def client():
    return TestClient(app)


def _make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


_VULN_FILES = {
    "app/server.js": (
        'const express = require("express");\n'
        'const KEY = "sk_live_abc123";\n'
        'app.get("/u", (req, res) => db.query("SELECT * FROM u WHERE id = " + req.params.id));\n'
    ),
    "app/package.json": '{"dependencies": {"express": "*"}}',
}


class TestDemoScan:
    def test_demo_zip_no_auth_required(self, client):
        archive = _make_zip(_VULN_FILES)
        res = client.post(
            "/api/demo/scan",
            files={"project": ("p.zip", archive, "application/zip")},
            data={"name": "demo"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["summary"]["total"] >= 1
        assert "findings" in body

    def test_demo_github_with_mock(self, client, monkeypatch):
        fixture = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures",
            "express_vulnerable",
        )

        from contextlib import contextmanager

        @contextmanager
        def fake_fetch(*_args, **_kwargs):
            yield fixture

        monkeypatch.setattr("saas.demo.fetch_repo", fake_fetch)

        res = client.post(
            "/api/demo/scan/github",
            data={"repo": "acme/widget"},
        )
        assert res.status_code == 200
        assert res.json()["summary"]["total"] >= 1
