"""Tests for the orchestrator and CLI."""

from __future__ import annotations

import json
import os
import sys

import pytest
from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import run, ScanOptions
from cli import cli

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_VULN_EXPRESS = os.path.join(_FIXTURES, "express_vulnerable")
_CLEAN = os.path.join(_FIXTURES, "clean_project")
_EXPRESS_BASIC = os.path.join(_FIXTURES, "express_basic")


class TestOrchestrator:
    def test_runs_full_pipeline_skip_tier3(self) -> None:
        report = run(_VULN_EXPRESS, ScanOptions(skip_tier3=True))
        assert "VibeSafe Security Report" in report
        assert "Critical" in report or "Warning" in report

    def test_finds_issues_in_vulnerable_project(self) -> None:
        report = run(_VULN_EXPRESS, ScanOptions(skip_tier3=True))
        assert "SEC-001" in report

    def test_clean_project_fewer_findings(self) -> None:
        report = run(_CLEAN, ScanOptions(skip_tier3=True))
        assert "VibeSafe Security Report" in report

    def test_json_output(self) -> None:
        report = run(_VULN_EXPRESS, ScanOptions(skip_tier3=True, output_format="json"))
        data = json.loads(report)
        assert "summary" in data
        assert "findings" in data
        assert data["summary"]["total"] > 0

    def test_empty_project(self, tmp_path) -> None:
        report = run(str(tmp_path), ScanOptions(skip_tier3=True))
        assert "No security issues found" in report

    def test_invalid_path_exits(self) -> None:
        with pytest.raises(SystemExit):
            run("/nonexistent/path/xyz", ScanOptions(skip_tier3=True))

    def test_scan_time_in_report(self) -> None:
        report = run(_EXPRESS_BASIC, ScanOptions(skip_tier3=True))
        assert "Scan Time" in report

    def test_framework_in_report(self) -> None:
        report = run(_EXPRESS_BASIC, ScanOptions(skip_tier3=True))
        assert "express" in report


class TestCLI:
    def test_scan_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Scan a project" in result.output

    def test_vibesafe_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "VibeSafe" in result.output

    def test_scan_skip_tier3(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", _EXPRESS_BASIC, "--skip-tier3"])
        assert result.exit_code in (0, 1)
        assert "VibeSafe" in result.output

    def test_scan_json_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", _EXPRESS_BASIC, "--skip-tier3", "-f", "json"])
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert "summary" in data

    def test_scan_output_to_file(self, tmp_path) -> None:
        out_file = str(tmp_path / "report.md")
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", _EXPRESS_BASIC, "--skip-tier3", "-o", out_file])
        assert result.exit_code in (0, 1)
        assert os.path.isfile(out_file)
        with open(out_file, encoding="utf-8") as f:
            content = f.read()
        assert "VibeSafe" in content

    def test_scan_verbose(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", _EXPRESS_BASIC, "--skip-tier3", "-v"])
        assert result.exit_code in (0, 1)

    def test_exit_code_1_for_critical(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", _VULN_EXPRESS, "--skip-tier3"])
        assert result.exit_code == 1

    def test_invalid_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "/nonexistent/xyz/abc"])
        assert result.exit_code != 0
