"""Integration tests for Python framework scanning."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import run, ScanOptions

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_VULN_DJANGO = os.path.join(_FIXTURES, "django_vulnerable")
_VULN_FLASK = os.path.join(_FIXTURES, "flask_vulnerable")


class TestDjangoVulnerable:
    @pytest.fixture(autouse=True)
    def _scan(self) -> None:
        self.report = run(_VULN_DJANGO, ScanOptions(skip_tier3=True, output_format="json"))
        self.data = json.loads(self.report)
        self.findings = self.data["findings"]
        self.rule_ids = [f["rule_id"] for f in self.findings]

    def test_detects_django_framework(self) -> None:
        assert self.data["scan_info"]["framework"] == "django"

    def test_detects_python_language(self) -> None:
        assert self.data["scan_info"]["language"] == "python"

    def test_finds_hardcoded_secret_key(self) -> None:
        assert "SEC-017" in self.rule_ids

    def test_finds_debug_true(self) -> None:
        assert "SEC-036" in self.rule_ids

    def test_finds_allowed_hosts_wildcard(self) -> None:
        assert "SEC-039" in self.rule_ids

    def test_finds_missing_csrf_middleware(self) -> None:
        assert "SEC-023" in self.rule_ids

    def test_finds_missing_security_middleware(self) -> None:
        sec038 = [f for f in self.findings if f["rule_id"] == "SEC-038"]
        assert len(sec038) >= 1

    def test_finds_sql_injection(self) -> None:
        assert "SEC-020" in self.rule_ids

    def test_finds_eval(self) -> None:
        assert "SEC-022" in self.rule_ids

    def test_finds_pickle_loads(self) -> None:
        pickle_findings = [f for f in self.findings
                          if "pickle" in (f.get("code_snippet") or "")]
        assert len(pickle_findings) >= 1

    def test_finds_os_system(self) -> None:
        os_findings = [f for f in self.findings
                      if "os.system" in (f.get("code_snippet") or "")]
        assert len(os_findings) >= 1

    def test_finds_shell_true(self) -> None:
        shell_findings = [f for f in self.findings
                         if "shell=True" in (f.get("code_snippet") or "")]
        assert len(shell_findings) >= 1

    def test_finds_default_credentials(self) -> None:
        assert "SEC-018" in self.rule_ids

    def test_finds_sensitive_logging(self) -> None:
        assert "SEC-046" in self.rule_ids

    def test_finds_unpinned_deps(self) -> None:
        assert "SEC-049" in self.rule_ids

    def test_finds_session_cookies_not_secure(self) -> None:
        assert "SEC-016" in self.rule_ids

    def test_finds_tenant_isolation(self) -> None:
        sec010 = [f for f in self.findings if f["rule_id"] == "SEC-010"]
        assert len(sec010) >= 2

    def test_has_critical_findings(self) -> None:
        assert self.data["summary"]["critical"] >= 5

    def test_total_findings_reasonable(self) -> None:
        assert 10 <= self.data["summary"]["total"] <= 35


class TestFlaskVulnerable:
    @pytest.fixture(autouse=True)
    def _scan(self) -> None:
        self.report = run(_VULN_FLASK, ScanOptions(skip_tier3=True, output_format="json"))
        self.data = json.loads(self.report)
        self.findings = self.data["findings"]
        self.rule_ids = [f["rule_id"] for f in self.findings]

    def test_detects_flask_framework(self) -> None:
        assert self.data["scan_info"]["framework"] == "flask"

    def test_finds_hardcoded_secret_key(self) -> None:
        assert "SEC-017" in self.rule_ids

    def test_finds_debug_mode(self) -> None:
        assert "SEC-036" in self.rule_ids

    def test_finds_sql_injection(self) -> None:
        assert "SEC-020" in self.rule_ids

    def test_finds_eval(self) -> None:
        assert "SEC-022" in self.rule_ids

    def test_finds_pickle_loads(self) -> None:
        pickle_findings = [f for f in self.findings
                          if "pickle" in (f.get("code_snippet") or "")]
        assert len(pickle_findings) >= 1

    def test_finds_os_system(self) -> None:
        os_findings = [f for f in self.findings
                      if "os.system" in (f.get("code_snippet") or "")]
        assert len(os_findings) >= 1

    def test_finds_no_csrf(self) -> None:
        assert "SEC-023" in self.rule_ids

    def test_finds_default_credentials(self) -> None:
        assert "SEC-018" in self.rule_ids

    def test_finds_unpinned_deps(self) -> None:
        assert "SEC-049" in self.rule_ids

    def test_has_critical_findings(self) -> None:
        assert self.data["summary"]["critical"] >= 3
