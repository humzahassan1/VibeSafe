"""Tests for report generation and formatting."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.finding import Finding, Severity
from models.fix import Fix
from report.generator import generate_report, deduplicate, sort_findings, compute_summary


def _make_finding(
    rule_id: str = "SEC-001",
    severity: Severity = Severity.WARNING,
    category: str = "secrets",
    title: str = "Test finding",
    description: str = "Test description",
    file_path: str = "app.js",
    tier: int = 1,
    line_start: int | None = 10,
    fix: Fix | None = None,
    code_snippet: str | None = "const key = 'abc';",
    confidence: float = 1.0,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        category=category,
        title=title,
        description=description,
        file_path=file_path,
        tier=tier,
        line_start=line_start,
        code_snippet=code_snippet,
        fix=fix,
        confidence=confidence,
    )


_CONTEXT_INFO = {
    "framework": "express",
    "language": "javascript",
    "files_scanned": 20,
    "scan_time": "1.5s",
}


class TestDeduplication:
    def test_removes_exact_duplicates(self) -> None:
        f1 = _make_finding(rule_id="SEC-001", file_path="app.js", line_start=10)
        f2 = _make_finding(rule_id="SEC-001", file_path="app.js", line_start=10)
        result = deduplicate([f1, f2])
        assert len(result) == 1

    def test_keeps_richer_finding(self) -> None:
        f1 = _make_finding(rule_id="SEC-001", file_path="app.js", line_start=10,
                           description="short", tier=1)
        f2 = _make_finding(rule_id="SEC-001", file_path="app.js", line_start=10,
                           description="a much longer and more detailed description of the issue",
                           tier=3, fix=Fix("fix it", "code", "app.js", "replace"))
        result = deduplicate([f1, f2])
        assert len(result) == 1
        assert result[0].tier == 3

    def test_keeps_different_rules_same_line(self) -> None:
        f1 = _make_finding(rule_id="SEC-001", file_path="app.js", line_start=10)
        f2 = _make_finding(rule_id="SEC-020", file_path="app.js", line_start=10)
        result = deduplicate([f1, f2])
        assert len(result) == 2

    def test_keeps_same_rule_different_files(self) -> None:
        f1 = _make_finding(rule_id="SEC-001", file_path="a.js", line_start=10)
        f2 = _make_finding(rule_id="SEC-001", file_path="b.js", line_start=10)
        result = deduplicate([f1, f2])
        assert len(result) == 2


class TestSorting:
    def test_critical_first(self) -> None:
        findings = [
            _make_finding(severity=Severity.INFO),
            _make_finding(severity=Severity.CRITICAL),
            _make_finding(severity=Severity.WARNING),
        ]
        sorted_f = sort_findings(findings)
        assert sorted_f[0].severity == Severity.CRITICAL
        assert sorted_f[1].severity == Severity.WARNING
        assert sorted_f[2].severity == Severity.INFO

    def test_same_severity_sorted_by_category(self) -> None:
        findings = [
            _make_finding(severity=Severity.WARNING, category="secrets"),
            _make_finding(severity=Severity.WARNING, category="auth"),
        ]
        sorted_f = sort_findings(findings)
        assert sorted_f[0].category == "auth"
        assert sorted_f[1].category == "secrets"


class TestSummary:
    def test_counts_by_severity(self) -> None:
        findings = [
            _make_finding(severity=Severity.CRITICAL),
            _make_finding(severity=Severity.CRITICAL, rule_id="SEC-002"),
            _make_finding(severity=Severity.WARNING),
            _make_finding(severity=Severity.INFO),
        ]
        summary = compute_summary(findings)
        assert summary["total"] == 4
        assert summary["critical"] == 2
        assert summary["warning"] == 1
        assert summary["info"] == 1

    def test_empty_findings(self) -> None:
        summary = compute_summary([])
        assert summary["total"] == 0
        assert summary["critical"] == 0

    def test_files_with_issues(self) -> None:
        findings = [
            _make_finding(file_path="a.js"),
            _make_finding(file_path="a.js", rule_id="SEC-002"),
            _make_finding(file_path="b.js"),
        ]
        summary = compute_summary(findings)
        assert summary["files_with_issues"] == 2


class TestMarkdownReport:
    def test_contains_all_sections(self) -> None:
        findings = [
            _make_finding(severity=Severity.CRITICAL, title="Critical issue"),
            _make_finding(severity=Severity.WARNING, title="Warning issue", rule_id="SEC-002"),
            _make_finding(severity=Severity.INFO, title="Info issue", rule_id="SEC-003"),
        ]
        report = generate_report(findings, _CONTEXT_INFO, output_format="markdown")
        assert "# VibeSafe Security Report" in report
        assert "Critical Findings" in report
        assert "Warnings" in report
        assert "Info" in report
        assert "Critical issue" in report
        assert "Warning issue" in report
        assert "Info issue" in report

    def test_contains_file_paths_and_lines(self) -> None:
        findings = [_make_finding(file_path="routes/api.js", line_start=42)]
        report = generate_report(findings, _CONTEXT_INFO)
        assert "routes/api.js" in report
        assert "42" in report

    def test_contains_code_snippet(self) -> None:
        findings = [_make_finding(code_snippet="eval(userInput)")]
        report = generate_report(findings, _CONTEXT_INFO)
        assert "eval(userInput)" in report

    def test_contains_fix_suggestion(self) -> None:
        fix = Fix("Use safer alternative", "JSON.parse(input)", "app.js", "replace")
        findings = [_make_finding(fix=fix)]
        report = generate_report(findings, _CONTEXT_INFO)
        assert "JSON.parse(input)" in report
        assert "Use safer alternative" in report

    def test_clean_report_for_no_findings(self) -> None:
        report = generate_report([], _CONTEXT_INFO)
        assert "No security issues found" in report
        assert "Critical Findings" not in report

    def test_contains_scan_metadata(self) -> None:
        report = generate_report([], _CONTEXT_INFO)
        assert "express" in report
        assert "javascript" in report


class TestJsonReport:
    def test_valid_json(self) -> None:
        findings = [_make_finding()]
        report = generate_report(findings, _CONTEXT_INFO, output_format="json")
        data = json.loads(report)
        assert "summary" in data
        assert "findings" in data
        assert "scan_info" in data

    def test_findings_have_all_fields(self) -> None:
        fix = Fix("fix desc", "fix code", "app.js", "replace")
        findings = [_make_finding(fix=fix)]
        report = generate_report(findings, _CONTEXT_INFO, output_format="json")
        data = json.loads(report)
        f = data["findings"][0]
        assert f["rule_id"] == "SEC-001"
        assert f["severity"] == "warning"
        assert "fix" in f
        assert f["fix"]["code"] == "fix code"

    def test_empty_findings_valid_json(self) -> None:
        report = generate_report([], _CONTEXT_INFO, output_format="json")
        data = json.loads(report)
        assert data["summary"]["total"] == 0
        assert data["findings"] == []
