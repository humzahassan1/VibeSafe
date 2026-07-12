"""Tests for the Tier 2 scanner."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config
from models.context import FileInfo, ProjectContext
from models.finding import Severity
from scanner.tier2 import scan_tier2


@pytest.fixture(scope="module")
def rules():
    return load_config().rules


def _make_project(tmp_path, files: dict[str, str], framework: str = "generic",
                  language: str = "javascript") -> ProjectContext:
    for rel_path, content in files.items():
        fp = tmp_path / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")

    manifest = []
    config_files = []
    env_files = []
    for rel_path in files:
        abs_path = str(tmp_path / rel_path)
        ext = os.path.splitext(rel_path)[1]
        manifest.append(FileInfo(path=abs_path, file_type=ext, size_bytes=100, relevance_score=0.5))
        if rel_path.startswith(".env"):
            env_files.append(abs_path)
        if rel_path in ("next.config.js", "next.config.ts", "app.js", "server.js"):
            config_files.append(abs_path)

    return ProjectContext(
        project_path=str(tmp_path),
        framework=framework,
        language=language,
        file_manifest=manifest,
        config_files=config_files,
        env_files=env_files,
    )


class TestNextjsConfig:
    def test_detects_source_maps_enabled(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "next.config.js": "module.exports = { productionBrowserSourceMaps: true };"
        }, framework="nextjs")
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-034" for f in findings)

    def test_detects_missing_headers(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "next.config.js": "module.exports = { reactStrictMode: true };"
        }, framework="nextjs")
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-038" for f in findings)

    def test_detects_nextpublic_secret(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "next.config.js": "module.exports = {};",
            ".env.local": "NEXT_PUBLIC_SECRET_KEY=abc123",
        }, framework="nextjs")
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-033" for f in findings)

    def test_no_findings_for_good_config(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "next.config.js": """
module.exports = {
  productionBrowserSourceMaps: false,
  async headers() { return [{ source: "/(.*)", headers: [] }]; },
};"""
        }, framework="nextjs")
        findings = scan_tier2(ctx, rules)
        source_map = [f for f in findings if f.rule_id == "SEC-034"]
        assert len(source_map) == 0

    def test_handles_missing_config(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {}, framework="nextjs")
        findings = scan_tier2(ctx, rules)
        nextjs_findings = [f for f in findings if f.rule_id in ("SEC-034", "SEC-038", "SEC-033")]
        assert len(nextjs_findings) == 0


class TestExpressMiddleware:
    def test_detects_missing_helmet(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "server.js": 'const app = require("express")();\napp.listen(3000);'
        }, framework="express")
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-038" for f in findings)

    def test_detects_permissive_cors(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "app.js": 'const app = require("express")();\napp.use(cors());\napp.listen(3000);'
        }, framework="express")
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-039" for f in findings)

    def test_detects_missing_rate_limit(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "server.js": 'const app = require("express")();\napp.listen(3000);'
        }, framework="express")
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-028" for f in findings)

    def test_detects_insecure_session(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "app.js": 'const app = require("express")();\napp.use(session({ secret: "x" }));\napp.listen(3000);'
        }, framework="express")
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-016" for f in findings)

    def test_no_cors_finding_when_restricted(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "app.js": 'app.use(cors({ origin: "https://mysite.com" }));\napp.use(helmet());\napp.use(rateLimit({}));\napp.listen(3000);'
        }, framework="express")
        findings = scan_tier2(ctx, rules)
        assert not any(f.rule_id == "SEC-039" for f in findings)


class TestDatabaseConfig:
    def test_detects_firebase_open_rules(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "firebase.rules": '{ "rules": { ".read": true, ".write": true } }'
        })
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-009" for f in findings)

    def test_no_finding_for_restricted_firebase(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "firebase.rules": '{ "rules": { ".read": "auth != null", ".write": "auth != null" } }'
        })
        findings = scan_tier2(ctx, rules)
        assert not any(f.rule_id == "SEC-009" for f in findings)


class TestDependencies:
    def test_detects_missing_audit_script(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "package.json": json.dumps({"scripts": {"start": "node server.js"}})
        })
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-047" for f in findings)

    def test_detects_unpinned_dependency(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "package.json": json.dumps({"dependencies": {"express": "*"}})
        })
        findings = scan_tier2(ctx, rules)
        assert any(f.rule_id == "SEC-049" for f in findings)

    def test_no_finding_for_pinned_deps(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "package.json": json.dumps({
                "dependencies": {"express": "^4.18.2"},
                "scripts": {"audit": "npm audit"}
            })
        })
        findings = scan_tier2(ctx, rules)
        assert not any(f.rule_id == "SEC-049" for f in findings)
        assert not any(f.rule_id == "SEC-047" for f in findings)

    def test_handles_malformed_package_json(self, tmp_path, rules) -> None:
        ctx = _make_project(tmp_path, {
            "package.json": "{ invalid json"
        })
        findings = scan_tier2(ctx, rules)
        # Should not crash
