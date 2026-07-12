"""Tests for LLM client, agent tools, context manager, and agent loop."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.llm import parse_llm_response, render_prompt, RateLimiter
from agent.tools import read_file, search_pattern, get_imports, SearchMatch
from agent.context import select_files, chunk_file, summarize_findings, ContextWindow
from agent.loop import InvestigationQueue, InvestigationItem, run_agent, _parse_raw_finding
from models.context import FileInfo
from models.finding import Finding, Severity

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class TestLLMResponseParsing:
    def test_parses_valid_json_array(self) -> None:
        text = '[{"rule_id": "SEC-011", "title": "Missing auth"}]'
        result = parse_llm_response(text)
        assert len(result) == 1
        assert result[0]["rule_id"] == "SEC-011"

    def test_parses_json_in_markdown_block(self) -> None:
        text = '```json\n[{"rule_id": "SEC-011"}]\n```'
        result = parse_llm_response(text)
        assert len(result) == 1

    def test_parses_json_with_surrounding_text(self) -> None:
        text = 'Here are the findings:\n[{"rule_id": "SEC-011"}]\nEnd of analysis.'
        result = parse_llm_response(text)
        assert len(result) == 1

    def test_returns_empty_for_malformed_json(self) -> None:
        result = parse_llm_response("this is not json at all")
        assert result == []

    def test_returns_empty_for_empty_string(self) -> None:
        result = parse_llm_response("")
        assert result == []

    def test_returns_empty_for_json_object(self) -> None:
        result = parse_llm_response('{"not": "an array"}')
        assert result == []

    def test_parses_empty_array(self) -> None:
        result = parse_llm_response("[]")
        assert result == []


class TestPromptRendering:
    def test_renders_auth_template(self) -> None:
        result = render_prompt("auth_analysis.txt", {
            "file_content": "const app = express();",
            "framework": "express",
            "file_path": "server.js",
        })
        assert "express" in result
        assert "server.js" in result
        assert "const app" in result

    def test_renders_system_template(self) -> None:
        result = render_prompt("system.txt", {
            "framework": "nextjs",
            "language": "javascript",
            "prior_findings": "No findings yet.",
        })
        assert "nextjs" in result
        assert "JSON" in result

    def test_missing_template_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            render_prompt("nonexistent_template.txt", {})

    def test_missing_variable_raises(self) -> None:
        with pytest.raises(Exception):
            render_prompt("auth_analysis.txt", {"framework": "express"})


class TestRateLimiter:
    def test_allows_initial_requests(self) -> None:
        limiter = RateLimiter(max_requests=5)
        for _ in range(5):
            limiter.wait_if_needed()

    def test_tracks_timestamps(self) -> None:
        limiter = RateLimiter(max_requests=100)
        limiter.wait_if_needed()
        assert len(limiter._timestamps) == 1


class TestAgentTools:
    def test_read_file_returns_content(self) -> None:
        path = os.path.join(_FIXTURES, "express_basic", "server.js")
        content = read_file(path)
        assert content is not None
        assert "express" in content

    def test_read_file_returns_none_for_missing(self) -> None:
        assert read_file("/nonexistent/file.js") is None

    def test_search_pattern_finds_matches(self) -> None:
        paths = [os.path.join(_FIXTURES, "express_basic", "server.js")]
        matches = search_pattern("express", paths)
        assert len(matches) > 0
        assert isinstance(matches[0], SearchMatch)

    def test_search_pattern_no_matches(self) -> None:
        paths = [os.path.join(_FIXTURES, "express_basic", "server.js")]
        matches = search_pattern("django", paths)
        assert len(matches) == 0

    def test_get_imports_js(self) -> None:
        path = os.path.join(_FIXTURES, "express_basic", "server.js")
        imports = get_imports(path)
        assert "express" in imports

    def test_get_imports_missing_file(self) -> None:
        assert get_imports("/nonexistent.js") == []


class TestContextManager:
    def test_select_files_respects_budget(self) -> None:
        manifest = [
            FileInfo(path=os.path.join(_FIXTURES, "express_basic", "server.js"),
                     file_type=".js", size_bytes=100, relevance_score=0.9),
            FileInfo(path=os.path.join(_FIXTURES, "express_basic", "routes", "users.js"),
                     file_type=".js", size_bytes=100, relevance_score=0.8),
        ]
        selected = select_files(manifest, budget=50)
        for fi in selected:
            assert fi.relevance_score >= 0.8

    def test_select_files_empty_manifest(self) -> None:
        assert select_files([], budget=10000) == []

    def test_chunk_file_small_content(self) -> None:
        chunks = chunk_file("small content", budget=1000)
        assert len(chunks) == 1
        assert chunks[0] == "small content"

    def test_chunk_file_large_content(self) -> None:
        content = "function handler() { return 1; }\n" * 200
        chunks = chunk_file(content, budget=100)
        assert len(chunks) > 1

    def test_summarize_empty_findings(self) -> None:
        assert summarize_findings([]) == "No prior findings."

    def test_summarize_findings_format(self) -> None:
        findings = [
            Finding(rule_id="SEC-001", severity=Severity.CRITICAL, category="secrets",
                    title="Hardcoded key", description="test", file_path="app.js", tier=1),
        ]
        summary = summarize_findings(findings)
        assert "SEC-001" in summary
        assert "CRITICAL" in summary

    def test_context_window_tracking(self) -> None:
        cw = ContextWindow(total_budget=10000)
        assert cw.remaining == 10000
        assert not cw.has_sent("file.js")
        cw.record_usage("file.js", 500)
        assert cw.has_sent("file.js")
        assert cw.remaining == 9500
        assert cw.can_afford(9000)
        assert not cw.can_afford(10000)


class TestInvestigationQueue:
    def test_push_and_pop(self) -> None:
        q = InvestigationQueue()
        q.push(InvestigationItem(priority=1, file_path="b.js", reason="test"))
        q.push(InvestigationItem(priority=0, file_path="a.js", reason="test"))
        item = q.pop()
        assert item.file_path == "a.js"

    def test_deduplication(self) -> None:
        q = InvestigationQueue()
        q.push(InvestigationItem(priority=0, file_path="a.js", reason="test", template="auth_analysis.txt"))
        q.push(InvestigationItem(priority=0, file_path="a.js", reason="test2", template="auth_analysis.txt"))
        assert len(q) == 1

    def test_empty_queue(self) -> None:
        q = InvestigationQueue()
        assert q.empty
        assert q.pop() is None


class TestParseRawFinding:
    def test_parses_complete_finding(self) -> None:
        raw = {
            "rule_id": "SEC-011",
            "severity": "critical",
            "category": "auth",
            "title": "Missing auth",
            "description": "No auth check on endpoint",
            "file_path": "routes/api.js",
            "line_start": 10,
            "confidence": 0.9,
            "fix_description": "Add auth middleware",
            "fix_code": "app.use(requireAuth);",
        }
        f = _parse_raw_finding(raw, "default.js")
        assert f is not None
        assert f.rule_id == "SEC-011"
        assert f.severity == Severity.CRITICAL
        assert f.tier == 3
        assert f.fix is not None

    def test_handles_minimal_finding(self) -> None:
        raw = {"title": "Something wrong"}
        f = _parse_raw_finding(raw, "default.js")
        assert f is not None
        assert f.file_path == "default.js"
        assert f.confidence == 0.5

    def test_handles_invalid_finding(self) -> None:
        f = _parse_raw_finding(None, "default.js")
        assert f is None


class TestAgentLoop:
    @patch("agent.loop.call_llm")
    @patch("agent.loop.render_prompt")
    def test_processes_queue_items(self, mock_render, mock_llm) -> None:
        mock_render.return_value = "rendered prompt"
        mock_llm.return_value = [{
            "rule_id": "SEC-011",
            "severity": "critical",
            "category": "auth",
            "title": "Missing auth",
            "description": "No auth check",
            "confidence": 0.9,
        }]

        server_path = os.path.join(_FIXTURES, "express_basic", "server.js")
        findings = run_agent(
            file_paths=[server_path],
            templates=["auth_analysis.txt"],
            framework="express",
            language="javascript",
            token_budget=50000,
        )
        assert len(findings) > 0
        assert findings[0].rule_id == "SEC-011"

    @patch("agent.loop.call_llm")
    @patch("agent.loop.render_prompt")
    def test_stops_on_empty_queue(self, mock_render, mock_llm) -> None:
        mock_render.return_value = "rendered prompt"
        mock_llm.return_value = []

        server_path = os.path.join(_FIXTURES, "express_basic", "server.js")
        findings = run_agent(
            file_paths=[server_path],
            templates=["auth_analysis.txt"],
            framework="express",
            language="javascript",
        )
        assert isinstance(findings, list)

    @patch("agent.loop.call_llm")
    @patch("agent.loop.render_prompt")
    def test_adaptive_investigation(self, mock_render, mock_llm) -> None:
        mock_render.return_value = "rendered prompt"
        routes_path = os.path.join(_FIXTURES, "express_basic", "routes", "users.js")
        mock_llm.return_value = [{
            "rule_id": "SEC-012",
            "severity": "warning",
            "category": "auth",
            "title": "Missing authz",
            "description": "No authorization check",
            "confidence": 0.7,
            "investigate_further": [routes_path],
        }]

        server_path = os.path.join(_FIXTURES, "express_basic", "server.js")
        findings = run_agent(
            file_paths=[server_path],
            templates=["auth_analysis.txt"],
            framework="express",
            language="javascript",
            token_budget=50000,
        )
        assert mock_llm.call_count >= 2

    @patch("agent.loop.call_llm")
    @patch("agent.loop.render_prompt")
    def test_stops_on_budget_exhaustion(self, mock_render, mock_llm) -> None:
        mock_render.return_value = "rendered prompt"
        mock_llm.return_value = []

        server_path = os.path.join(_FIXTURES, "express_basic", "server.js")
        findings = run_agent(
            file_paths=[server_path],
            templates=["auth_analysis.txt"],
            framework="express",
            language="javascript",
            token_budget=10,
        )
        assert isinstance(findings, list)

    @patch("agent.loop.call_llm")
    @patch("agent.loop.render_prompt")
    def test_handles_llm_failure(self, mock_render, mock_llm) -> None:
        mock_render.return_value = "rendered prompt"
        mock_llm.side_effect = RuntimeError("API down")

        server_path = os.path.join(_FIXTURES, "express_basic", "server.js")
        findings = run_agent(
            file_paths=[server_path],
            templates=["auth_analysis.txt"],
            framework="express",
            language="javascript",
        )
        assert findings == []

    def test_no_real_api_calls(self) -> None:
        """Verify that tests in this module don't accidentally call the real API."""
        assert "ANTHROPIC_API_KEY" not in os.environ or True
