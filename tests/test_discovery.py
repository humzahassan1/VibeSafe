"""Tests for the discovery module."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config
from scanner.discovery import discover, detect_framework, score_relevance

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_EXPRESS = os.path.join(_FIXTURES, "express_basic")
_NEXTJS = os.path.join(_FIXTURES, "nextjs_basic")
_CLEAN = os.path.join(_FIXTURES, "clean_project")


@pytest.fixture(scope="module")
def frameworks_config() -> dict:
    cfg = load_config()
    return cfg.frameworks


class TestFrameworkDetection:
    def test_detects_express(self, frameworks_config: dict) -> None:
        from utils.files import walk_project
        files = walk_project(_EXPRESS)
        fw, lang = detect_framework(_EXPRESS, files, frameworks_config)
        assert fw == "express"
        assert lang == "javascript"

    def test_detects_nextjs(self, frameworks_config: dict) -> None:
        from utils.files import walk_project
        files = walk_project(_NEXTJS)
        fw, lang = detect_framework(_NEXTJS, files, frameworks_config)
        assert fw == "nextjs"
        assert lang == "javascript"

    def test_generic_fallback(self, frameworks_config: dict, tmp_path) -> None:
        (tmp_path / "app.py").write_text("print('hello')")
        files = [str(tmp_path / "app.py")]
        fw, lang = detect_framework(str(tmp_path), files, frameworks_config)
        assert fw == "generic"

    def test_handles_no_package_json(self, frameworks_config: dict, tmp_path) -> None:
        (tmp_path / "hello.py").write_text("print('hi')")
        files = [str(tmp_path / "hello.py")]
        fw, lang = detect_framework(str(tmp_path), files, frameworks_config)
        assert fw == "generic"
        assert lang == "python"


class TestRelevanceScoring:
    def test_route_files_score_high(self) -> None:
        score = score_relevance("routes/users.js", "users.js", ".js", [])
        assert score >= 0.7

    def test_auth_files_score_high(self) -> None:
        score = score_relevance("lib/auth.js", "auth.js", ".js", [])
        assert score >= 0.7

    def test_config_files_score_high(self) -> None:
        score = score_relevance(".env", ".env", "", [])
        assert score >= 0.8

    def test_test_files_score_low(self) -> None:
        score = score_relevance("tests/test_app.py", "test_app.py", ".py", [])
        assert score <= 0.3

    def test_framework_patterns_boost(self) -> None:
        patterns = ["pages/api/**"]
        score = score_relevance("pages/api/hello.js", "hello.js", ".js", patterns)
        assert score >= 0.9

    def test_generic_file_moderate(self) -> None:
        score = score_relevance("src/utils.js", "utils.js", ".js", [])
        assert 0.1 <= score <= 0.5

    def test_scores_normalized(self) -> None:
        score = score_relevance("routes/api/auth/middleware/login.js", "login.js", ".js",
                                ["routes/api/**"])
        assert 0.0 <= score <= 1.0


class TestDiscover:
    def test_express_project(self, frameworks_config: dict) -> None:
        ctx = discover(_EXPRESS, frameworks_config)
        assert ctx.framework == "express"
        assert ctx.language == "javascript"
        assert len(ctx.file_manifest) > 0
        assert any("server.js" in ep for ep in ctx.entry_points)
        assert ctx.file_manifest[0].relevance_score >= ctx.file_manifest[-1].relevance_score

    def test_nextjs_project(self, frameworks_config: dict) -> None:
        ctx = discover(_NEXTJS, frameworks_config)
        assert ctx.framework == "nextjs"
        assert len(ctx.file_manifest) > 0
        assert any("next.config.js" in cf for cf in ctx.config_files)

    def test_manifest_sorted_by_relevance(self, frameworks_config: dict) -> None:
        ctx = discover(_EXPRESS, frameworks_config)
        scores = [f.relevance_score for f in ctx.file_manifest]
        assert scores == sorted(scores, reverse=True)

    def test_invalid_path_raises(self, frameworks_config: dict) -> None:
        with pytest.raises(FileNotFoundError, match="does not exist"):
            discover("/nonexistent/path/that/does/not/exist", frameworks_config)

    def test_empty_directory(self, frameworks_config: dict, tmp_path) -> None:
        ctx = discover(str(tmp_path), frameworks_config)
        assert ctx.framework == "generic"
        assert len(ctx.file_manifest) == 0

    def test_file_manifest_has_absolute_paths(self, frameworks_config: dict) -> None:
        ctx = discover(_EXPRESS, frameworks_config)
        for fi in ctx.file_manifest:
            assert os.path.isabs(fi.path)
