"""Tests for the Tier 1 scanner."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config
from models.context import FileInfo, ProjectContext
from models.finding import Severity
from scanner.tier1 import scan_tier1, _scan_file_patterns

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_VULN_EXPRESS = os.path.join(_FIXTURES, "express_vulnerable")


@pytest.fixture(scope="module")
def config():
    return load_config()


def _make_temp_file(content: str, suffix: str = ".js") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


def _scan_snippet(content: str, config, suffix: str = ".js") -> list:
    path = _make_temp_file(content, suffix)
    try:
        return _scan_file_patterns(path, config.patterns, config.rules)
    finally:
        os.unlink(path)


class TestSecretDetection:
    def test_catches_aws_key(self, config) -> None:
        findings = _scan_snippet('const key = "AKIAIOSFODNN7EXAMPLE";', config)
        assert any(f.rule_id == "SEC-001" for f in findings)

    def test_catches_stripe_live_key(self, config) -> None:
        # Assembled at runtime so the literal key never appears in the committed
        # file (avoids tripping GitHub push protection on this test fixture).
        stripe_key = "sk_live_" + "abc123def456ghi789jkl012mno"
        findings = _scan_snippet(f'const key = "{stripe_key}";', config)
        assert any(f.rule_id == "SEC-001" for f in findings)

    def test_catches_openai_key(self, config) -> None:
        findings = _scan_snippet('const key = "sk-proj1234567890abcdefghij";', config)
        assert any(f.rule_id == "SEC-001" for f in findings)

    def test_catches_hardcoded_password(self, config) -> None:
        findings = _scan_snippet('password = "supersecret123"', config, suffix=".py")
        assert any(f.rule_id == "SEC-001" for f in findings)

    def test_ignores_env_var_reference(self, config) -> None:
        findings = _scan_snippet('password = os.environ.get("PASSWORD")', config, suffix=".py")
        pw_findings = [f for f in findings if "password" in f.title.lower() or f.rule_id == "SEC-001"]
        has_hardcoded = any("hardcoded" in f.title.lower() or f.category == "secrets" for f in pw_findings)
        assert not has_hardcoded or all(
            any(ep.search('password = os.environ.get("PASSWORD")') for ep in [])
            for f in pw_findings
        )

    def test_catches_connection_string(self, config) -> None:
        findings = _scan_snippet(
            'DB_URL = "postgres://admin:secret@prod-db.internal:5432/mydb"', config, suffix=".py"
        )
        assert any(f.rule_id == "SEC-004" for f in findings)

    def test_ignores_env_connection_string(self, config) -> None:
        findings = _scan_snippet(
            'DB_URL = os.environ.get("DATABASE_URL")', config, suffix=".py"
        )
        assert not any(f.rule_id == "SEC-004" for f in findings)

    def test_catches_google_api_key(self, config) -> None:
        findings = _scan_snippet('const key = "AIzaSyA1234567890abcdefghijklmnopqrstuv";', config)
        assert any(f.rule_id == "SEC-001" for f in findings)

    def test_aws_severity_is_critical(self, config) -> None:
        findings = _scan_snippet('key = "AKIAIOSFODNN7EXAMPLE"', config)
        aws = [f for f in findings if f.rule_id == "SEC-001"]
        assert all(f.severity == Severity.CRITICAL for f in aws)


class TestDangerousCode:
    def test_catches_eval_js(self, config) -> None:
        findings = _scan_snippet('const result = eval(userInput);', config)
        assert any(f.rule_id == "SEC-022" for f in findings)

    def test_catches_exec_python(self, config) -> None:
        findings = _scan_snippet('exec(user_code)', config, suffix=".py")
        assert any(f.rule_id == "SEC-022" for f in findings)

    def test_catches_innerhtml(self, config) -> None:
        findings = _scan_snippet('element.innerHTML = userInput;', config)
        assert any(f.rule_id == "SEC-022" for f in findings)

    def test_catches_sql_concat_js(self, config) -> None:
        findings = _scan_snippet('db.query("SELECT * FROM users WHERE id = " + userId);', config)
        assert any(f.rule_id == "SEC-020" for f in findings)

    def test_catches_sql_fstring_python(self, config) -> None:
        findings = _scan_snippet('cursor.execute(f"SELECT * FROM users WHERE id = {uid}")', config, suffix=".py")
        assert any(f.rule_id == "SEC-020" for f in findings)

    def test_ignores_eval_in_comment(self, config) -> None:
        findings = _scan_snippet('// eval() is dangerous, do not use', config)
        assert not any(f.rule_id == "SEC-022" for f in findings)

    def test_ignores_parameterized_query(self, config) -> None:
        findings = _scan_snippet(
            'cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))', config, suffix=".py"
        )
        sql_findings = [f for f in findings if f.rule_id == "SEC-020"]
        assert len(sql_findings) == 0


class TestConfigChecks:
    def test_catches_cors_wildcard(self, config) -> None:
        findings = _scan_snippet('res.setHeader("Access-Control-Allow-Origin", "*");', config)
        assert any(f.rule_id == "SEC-039" for f in findings)

    def test_catches_cors_no_config(self, config) -> None:
        findings = _scan_snippet('app.use(cors());', config)
        assert any(f.rule_id == "SEC-039" for f in findings)

    def test_catches_default_password(self, config) -> None:
        findings = _scan_snippet('password = "admin"', config)
        assert any(f.rule_id == "SEC-018" for f in findings)

    def test_catches_sensitive_console_log(self, config) -> None:
        findings = _scan_snippet('console.log("token:", token);', config)
        assert any(f.rule_id == "SEC-046" for f in findings)

    def test_ignores_normal_console_log(self, config) -> None:
        findings = _scan_snippet('console.log("Server started on port 3000");', config)
        assert not any(f.rule_id == "SEC-046" for f in findings)


class TestIntegration:
    def test_vulnerable_express_finds_issues(self, config) -> None:
        ctx = ProjectContext(
            project_path=_VULN_EXPRESS,
            framework="express",
            language="javascript",
            file_manifest=[
                FileInfo(
                    path=os.path.join(_VULN_EXPRESS, "server.js"),
                    file_type=".js",
                    size_bytes=500,
                    relevance_score=0.8,
                ),
            ],
        )
        findings = scan_tier1(ctx, config.patterns, config.rules)
        assert len(findings) > 0

        rule_ids = {f.rule_id for f in findings}
        assert "SEC-001" in rule_ids
        assert "SEC-020" in rule_ids
        assert "SEC-039" in rule_ids

    def test_findings_have_code_snippets(self, config) -> None:
        ctx = ProjectContext(
            project_path=_VULN_EXPRESS,
            framework="express",
            language="javascript",
            file_manifest=[
                FileInfo(
                    path=os.path.join(_VULN_EXPRESS, "server.js"),
                    file_type=".js",
                    size_bytes=500,
                    relevance_score=0.8,
                ),
            ],
        )
        findings = scan_tier1(ctx, config.patterns, config.rules)
        for f in findings:
            assert f.code_snippet is not None
            assert len(f.code_snippet) > 0

    def test_findings_have_fix_suggestions(self, config) -> None:
        ctx = ProjectContext(
            project_path=_VULN_EXPRESS,
            framework="express",
            language="javascript",
            file_manifest=[
                FileInfo(
                    path=os.path.join(_VULN_EXPRESS, "server.js"),
                    file_type=".js",
                    size_bytes=500,
                    relevance_score=0.8,
                ),
            ],
        )
        findings = scan_tier1(ctx, config.patterns, config.rules)
        with_fix = [f for f in findings if f.fix is not None]
        assert len(with_fix) > 0

    def test_no_duplicate_findings(self, config) -> None:
        ctx = ProjectContext(
            project_path=_VULN_EXPRESS,
            framework="express",
            language="javascript",
            file_manifest=[
                FileInfo(
                    path=os.path.join(_VULN_EXPRESS, "server.js"),
                    file_type=".js",
                    size_bytes=500,
                    relevance_score=0.8,
                ),
            ],
        )
        findings = scan_tier1(ctx, config.patterns, config.rules)
        keys = [(f.file_path, f.line_start, f.rule_id) for f in findings]
        assert len(keys) == len(set(keys))

    def test_clean_code_no_findings(self, config) -> None:
        clean_content = """
const express = require('express');
const app = express();
const port = process.env.PORT || 3000;
app.get('/', (req, res) => res.json({ status: 'ok' }));
app.listen(port);
"""
        findings = _scan_snippet(clean_content, config)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        assert len(critical) == 0
