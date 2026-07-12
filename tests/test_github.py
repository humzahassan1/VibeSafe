"""Tests for GitHub repository scanning."""

from __future__ import annotations

import io
import os
import sys
import zipfile
from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest
from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli import cli
from orchestrator import ScanOptions, run_github
from utils.github import (
    GitHubError,
    RepoRef,
    download_repo_zip,
    fetch_repo,
    parse_repo_ref,
)

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_VULN_EXPRESS = os.path.join(_FIXTURES, "express_vulnerable")

# SaaS test setup (isolated DB) — imported only for SaaS endpoint tests.
_TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_github_saas_test.db")
os.environ["VIBESAFE_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["VIBESAFE_SECRET_KEY"] = "test-secret-key"
os.environ.pop("STRIPE_SECRET_KEY", None)


def _make_zip(files: dict[str, str], root_prefix: str = "owner-repo-abc123/") -> bytes:
    """Build an in-memory zip archive mimicking a GitHub zipball."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(f"{root_prefix}{path}", content)
    return buf.getvalue()


_VULN_ZIP_FILES = {
    "server.js": (
        'const express = require("express");\n'
        'const app = express();\n'
        'const KEY = "sk_live_abc123def456";\n'
        'app.get("/u", (req, res) => db.query("SELECT * FROM u WHERE id = " + req.params.id));\n'
        "app.listen(3000);\n"
    ),
    "package.json": '{"name": "x", "dependencies": {"express": "*"}}',
}


class TestParseRepoRef:
    def test_owner_repo_slug(self) -> None:
        ref = parse_repo_ref("acme/widget")
        assert ref == RepoRef("acme", "widget", None)

    def test_owner_repo_at_ref(self) -> None:
        ref = parse_repo_ref("acme/widget@develop")
        assert ref == RepoRef("acme", "widget", "develop")

    def test_https_url(self) -> None:
        ref = parse_repo_ref("https://github.com/acme/widget")
        assert ref == RepoRef("acme", "widget", None)

    def test_https_url_git_suffix(self) -> None:
        ref = parse_repo_ref("https://github.com/acme/widget.git")
        assert ref == RepoRef("acme", "widget", None)

    def test_tree_branch_url(self) -> None:
        ref = parse_repo_ref("https://github.com/acme/widget/tree/main")
        assert ref == RepoRef("acme", "widget", "main")

    def test_tree_nested_branch_url(self) -> None:
        ref = parse_repo_ref("https://github.com/acme/widget/tree/feature/my-branch")
        assert ref == RepoRef("acme", "widget", "feature/my-branch")

    def test_empty_raises(self) -> None:
        with pytest.raises(GitHubError):
            parse_repo_ref("  ")

    def test_invalid_raises(self) -> None:
        with pytest.raises(GitHubError):
            parse_repo_ref("not-a-valid-ref")


class TestDownloadRepoZip:
    def test_download_writes_zip(self, tmp_path) -> None:
        zip_bytes = _make_zip(_VULN_ZIP_FILES)
        dest = str(tmp_path / "repo.zip")
        repo_ref = RepoRef("acme", "widget", "main")

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/repos/acme/widget/zipball/main" in str(request.url)
            return httpx.Response(200, content=zip_bytes)

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            with patch("utils.github.httpx.stream", wraps=httpx.stream) as mock_stream:
                def stream(method, url, **kwargs):
                    return client.stream(method, url, **kwargs)

                mock_stream.side_effect = stream
                download_repo_zip(repo_ref, None, dest)

        assert os.path.isfile(dest)
        assert os.path.getsize(dest) > 0

    def test_404_raises_github_error(self, tmp_path) -> None:
        dest = str(tmp_path / "repo.zip")
        repo_ref = RepoRef("missing", "repo", None)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            with patch("utils.github.httpx.stream", wraps=httpx.stream) as mock_stream:
                def stream(method, url, **kwargs):
                    return client.stream(method, url, **kwargs)

                mock_stream.side_effect = stream
                with pytest.raises(GitHubError, match="not found or is private"):
                    download_repo_zip(repo_ref, None, dest)


class TestFetchRepo:
    def test_yields_scan_root_with_findings(self, tmp_path) -> None:
        zip_bytes = _make_zip(_VULN_ZIP_FILES)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes)

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            with patch("utils.github.httpx.stream", wraps=httpx.stream) as mock_stream:
                def stream(method, url, **kwargs):
                    return client.stream(method, url, **kwargs)

                mock_stream.side_effect = stream
                with fetch_repo("acme/widget") as root:
                    assert os.path.isdir(root)
                    assert os.path.isfile(os.path.join(root, "server.js"))

                    from orchestrator import run

                    report = run(root, ScanOptions(skip_tier3=True, output_format="json"))
                    import json

                    data = json.loads(report)
                    assert data["summary"]["total"] >= 1


@contextmanager
def _mock_fetch_to_fixture():
    """Monkeypatch fetch_repo to yield a local fixture path."""
    @contextmanager
    def fake_fetch(value, token=None, max_download_bytes=25 * 1024 * 1024):
        yield _VULN_EXPRESS

    with patch("utils.github.fetch_repo", fake_fetch):
        yield


class TestRunGithubOrchestrator:
    def test_run_github_scans_fixture(self) -> None:
        with _mock_fetch_to_fixture():
            report = run_github("acme/widget", ScanOptions(skip_tier3=True))
        assert "VibeSafe" in report or "SEC-" in report


class TestScanGithubCLI:
    def test_scan_github_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scan-github", "--help"])
        assert result.exit_code == 0
        assert "GitHub" in result.output

    def test_scan_github_with_mocked_fetch(self) -> None:
        runner = CliRunner()
        with _mock_fetch_to_fixture():
            result = runner.invoke(cli, ["scan-github", "acme/widget", "--skip-tier3"])
        assert result.exit_code == 1
        assert "SEC-" in result.output or "critical" in result.output.lower()

    def test_scan_github_json_format(self) -> None:
        runner = CliRunner()
        with _mock_fetch_to_fixture():
            result = runner.invoke(
                cli, ["scan-github", "acme/widget", "--skip-tier3", "-f", "json"]
            )
        assert result.exit_code == 1
        import json

        data = json.loads(result.output)
        assert data["summary"]["total"] > 0


class TestSaasGithubEndpoint:
    @pytest.fixture(autouse=True)
    def _fresh_db(self):
        from saas import database

        database.Base.metadata.drop_all(bind=database.engine)
        database.Base.metadata.create_all(bind=database.engine)
        yield
        database.Base.metadata.drop_all(bind=database.engine)

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from saas.app import app

        return TestClient(app)

    def _signup(self, client, email="gh@x.com") -> None:
        res = client.post(
            "/auth/signup", data={"email": email, "password": "password123"}
        )
        assert res.status_code == 200, res.text

    def test_github_scan_persists(self, client) -> None:
        self._signup(client)
        with patch("saas.scans.fetch_repo") as mock_fetch:
            @contextmanager
            def fake_fetch(*_args, **_kwargs):
                yield _VULN_EXPRESS

            mock_fetch.side_effect = fake_fetch
            res = client.post(
                "/api/scans/github",
                data={"repo": "acme/widget", "name": "gh-scan", "skip_tier3": "true"},
            )
        assert res.status_code == 200
        assert res.json()["summary"]["total"] > 0
        history = client.get("/api/scans").json()
        assert len(history) == 1
        assert history[0]["project_name"] == "gh-scan"

    def test_github_scan_usage_limit(self, client) -> None:
        from saas import database
        from saas.database import SessionLocal, User

        self._signup(client, email="limit@x.com")
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "limit@x.com").one()
            for _ in range(10):
                db.add(database.Scan(user_id=user.id, project_name="seed"))
            db.commit()

        with patch("saas.scans.fetch_repo") as mock_fetch:
            @contextmanager
            def fake_fetch(*_args, **_kwargs):
                yield _VULN_EXPRESS

            mock_fetch.side_effect = fake_fetch
            res = client.post(
                "/api/scans/github",
                data={"repo": "acme/widget", "skip_tier3": "true"},
            )
        assert res.status_code == 402

    def test_github_scan_tier3_gated_on_free(self, client) -> None:
        self._signup(client, email="tier3@x.com")
        res = client.post(
            "/api/scans/github",
            data={"repo": "acme/widget", "skip_tier3": "false"},
        )
        assert res.status_code == 400
        assert "Pro" in res.json()["detail"]
