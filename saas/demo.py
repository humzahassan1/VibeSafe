"""Stateless demo scans for the public landing page — no auth or persistence."""

from __future__ import annotations

import json
import tempfile

from orchestrator import ScanOptions, run
from utils.archive import ArchiveError, archive_root, safe_extract_zip
from utils.github import GitHubError, fetch_repo
from utils.logger import get_logger

_log = get_logger("saas.demo")


class DemoScanError(Exception):
    """Raised when a demo scan cannot be completed."""


def run_demo_scan(project_path: str) -> dict:
    """Run Tier 1 + 2 scan and return the parsed JSON report.

    Args:
        project_path: Local path to the project root.

    Returns:
        Full report dict with summary, scan_info, and findings.
    """
    report_str = run(project_path, ScanOptions(output_format="json", skip_tier3=True))
    try:
        return json.loads(report_str)
    except json.JSONDecodeError as exc:
        raise DemoScanError("Scanner produced an invalid report.") from exc


def run_demo_scan_archive(archive_path: str) -> dict:
    """Extract a zip archive and run a demo scan.

    Args:
        archive_path: Path to the uploaded zip file.

    Returns:
        Full report dict.
    """
    with tempfile.TemporaryDirectory(prefix="vibesafe_demo_") as work_dir:
        try:
            safe_extract_zip(archive_path, work_dir)
        except ArchiveError as exc:
            raise DemoScanError(str(exc)) from exc
        scan_root = archive_root(work_dir)
        _log.info("Demo zip scan on %s", scan_root)
        return run_demo_scan(scan_root)


def run_demo_scan_github(repo: str, token: str | None = None) -> dict:
    """Fetch a GitHub repository and run a demo scan.

    Args:
        repo: Repository slug or URL.
        token: Optional GitHub token for private repos.

    Returns:
        Full report dict.
    """
    try:
        with fetch_repo(repo, token=token) as scan_root:
            _log.info("Demo GitHub scan on %s", repo)
            return run_demo_scan(scan_root)
    except GitHubError as exc:
        raise DemoScanError(str(exc)) from exc
