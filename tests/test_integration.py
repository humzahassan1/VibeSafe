"""Integration tests — full scans against realistic fixtures."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import run, ScanOptions

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_VULN_EXPRESS = os.path.join(_FIXTURES, "express_vulnerable")
_VULN_NEXTJS = os.path.join(_FIXTURES, "nextjs_vulnerable")
_CLEAN = os.path.join(_FIXTURES, "clean_project")


class TestExpressVulnerable:
    @pytest.fixture(autouse=True)
    def _scan(self) -> None:
        self.report = run(_VULN_EXPRESS, ScanOptions(skip_tier3=True, output_format="json"))
        self.data = json.loads(self.report)
        self.findings = self.data["findings"]
        self.rule_ids = [f["rule_id"] for f in self.findings]

    def test_finds_hardcoded_api_keys(self) -> None:
        assert "SEC-001" in self.rule_ids

    def test_finds_sql_injection(self) -> None:
        assert "SEC-020" in self.rule_ids

    def test_finds_xss_eval(self) -> None:
        xss = [f for f in self.findings if f["rule_id"] == "SEC-022"]
        assert len(xss) >= 2

    def test_finds_cors_wildcard(self) -> None:
        assert "SEC-039" in self.rule_ids

    def test_finds_default_credentials(self) -> None:
        assert "SEC-018" in self.rule_ids

    def test_finds_sensitive_logging(self) -> None:
        assert "SEC-046" in self.rule_ids

    def test_finds_missing_helmet(self) -> None:
        assert "SEC-038" in self.rule_ids

    def test_finds_db_connection_string(self) -> None:
        assert "SEC-004" in self.rule_ids

    def test_finds_tenant_isolation(self) -> None:
        sec010 = [f for f in self.findings if f["rule_id"] == "SEC-010"]
        assert len(sec010) >= 2

    def test_has_critical_findings(self) -> None:
        assert self.data["summary"]["critical"] >= 5

    def test_exit_code_is_1(self) -> None:
        from click.testing import CliRunner
        from cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", _VULN_EXPRESS, "--skip-tier3"])
        assert result.exit_code == 1


class TestNextjsVulnerable:
    @pytest.fixture(autouse=True)
    def _scan(self) -> None:
        self.report = run(_VULN_NEXTJS, ScanOptions(skip_tier3=True, output_format="json"))
        self.data = json.loads(self.report)
        self.findings = self.data["findings"]
        self.rule_ids = [f["rule_id"] for f in self.findings]

    def test_detects_nextjs_framework(self) -> None:
        assert self.data["scan_info"]["framework"] == "nextjs"

    def test_finds_sql_injection(self) -> None:
        assert "SEC-020" in self.rule_ids

    def test_finds_xss_innerhtml(self) -> None:
        xss = [f for f in self.findings if f["rule_id"] == "SEC-022"]
        assert len(xss) >= 2

    def test_finds_eval(self) -> None:
        eval_findings = [f for f in self.findings
                         if f["rule_id"] == "SEC-022" and "eval" in (f.get("code_snippet") or "")]
        assert len(eval_findings) >= 1

    def test_finds_next_public_secret(self) -> None:
        assert "SEC-033" in self.rule_ids

    def test_finds_source_maps_enabled(self) -> None:
        assert "SEC-034" in self.rule_ids

    def test_finds_missing_security_headers(self) -> None:
        assert "SEC-038" in self.rule_ids

    def test_finds_default_credentials(self) -> None:
        assert "SEC-018" in self.rule_ids

    def test_finds_sensitive_logging(self) -> None:
        assert "SEC-046" in self.rule_ids

    def test_finds_db_connection_string(self) -> None:
        assert "SEC-004" in self.rule_ids

    def test_has_critical_findings(self) -> None:
        assert self.data["summary"]["critical"] >= 5

    def test_total_findings_reasonable(self) -> None:
        assert 10 <= self.data["summary"]["total"] <= 30


class TestCleanProject:
    @pytest.fixture(autouse=True)
    def _scan(self) -> None:
        self.report = run(_CLEAN, ScanOptions(skip_tier3=True, output_format="json"))
        self.data = json.loads(self.report)

    def test_zero_findings(self) -> None:
        assert self.data["summary"]["total"] == 0

    def test_zero_critical(self) -> None:
        assert self.data["summary"]["critical"] == 0

    def test_exit_code_is_0(self) -> None:
        from click.testing import CliRunner
        from cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", _CLEAN, "--skip-tier3"])
        assert result.exit_code == 0

    def test_clean_message_in_markdown(self) -> None:
        report = run(_CLEAN, ScanOptions(skip_tier3=True))
        assert "No security issues found" in report


class TestScanAccuracy:
    def test_no_false_positives_on_clean(self) -> None:
        report = run(_CLEAN, ScanOptions(skip_tier3=True, output_format="json"))
        data = json.loads(report)
        assert data["summary"]["total"] == 0

    def test_express_catches_at_least_10_issues(self) -> None:
        report = run(_VULN_EXPRESS, ScanOptions(skip_tier3=True, output_format="json"))
        data = json.loads(report)
        assert data["summary"]["total"] >= 10

    def test_nextjs_catches_at_least_10_issues(self) -> None:
        report = run(_VULN_NEXTJS, ScanOptions(skip_tier3=True, output_format="json"))
        data = json.loads(report)
        assert data["summary"]["total"] >= 10

    def test_json_and_markdown_agree_on_counts(self) -> None:
        json_report = run(_VULN_EXPRESS, ScanOptions(skip_tier3=True, output_format="json"))
        md_report = run(_VULN_EXPRESS, ScanOptions(skip_tier3=True, output_format="markdown"))
        data = json.loads(json_report)
        for f in data["findings"]:
            assert f["rule_id"] in md_report
