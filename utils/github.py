"""GitHub repository fetch — download zipballs without the git binary."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator
from urllib.parse import urlparse

import httpx

from utils.archive import archive_root, safe_extract_zip
from utils.logger import get_logger

_log = get_logger("github")

DEFAULT_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
_USER_AGENT = "VibeSafe/0.1.0"


class GitHubError(Exception):
    """Raised when a GitHub repository cannot be fetched."""


@dataclass(frozen=True)
class RepoRef:
    """Parsed GitHub repository reference.

    Args:
        owner: Repository owner or organization.
        repo: Repository name.
        ref: Branch, tag, or commit SHA. None uses the default branch.
    """

    owner: str
    repo: str
    ref: str | None = None


def parse_repo_ref(value: str) -> RepoRef:
    """Parse a repository reference from a slug or URL.

    Accepts ``owner/repo``, ``owner/repo@ref``, HTTPS GitHub URLs (with optional
    ``.git`` suffix), and ``/tree/<branch>`` URL paths.

    Args:
        value: Repository slug or URL.

    Returns:
        Parsed RepoRef.

    Raises:
        GitHubError: If the value cannot be parsed.
    """
    value = value.strip()
    if not value:
        raise GitHubError("Repository reference cannot be empty.")

    at_match = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)@(.+)$", value)
    if at_match:
        return RepoRef(at_match.group(1), at_match.group(2), at_match.group(3))

    slash_match = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$", value)
    if slash_match:
        return RepoRef(slash_match.group(1), slash_match.group(2), None)

    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        host = parsed.netloc.lower().removeprefix("www.")
        if host != "github.com":
            raise GitHubError(
                f"Unsupported host '{parsed.netloc}'. Only github.com URLs are supported."
            )

        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise GitHubError(f"Cannot parse GitHub URL: {value}")

        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]

        ref: str | None = None
        if len(parts) >= 4 and parts[2] == "tree":
            ref = "/".join(parts[3:])

        return RepoRef(owner, repo, ref or None)

    raise GitHubError(
        f"Cannot parse repository reference: {value!r}. "
        "Use owner/repo, owner/repo@ref, or a github.com URL."
    )


def _zipball_url(repo_ref: RepoRef) -> str:
    """Build the GitHub API zipball URL for a repository reference."""
    base = f"https://api.github.com/repos/{repo_ref.owner}/{repo_ref.repo}/zipball"
    if repo_ref.ref:
        return f"{base}/{repo_ref.ref}"
    return base


def download_repo_zip(
    repo_ref: RepoRef,
    token: str | None,
    dest_path: str,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
) -> None:
    """Download a repository zipball from the GitHub API.

    Args:
        repo_ref: Parsed repository reference.
        token: Optional GitHub personal access token for private repos.
        dest_path: File path to write the downloaded zip.
        max_bytes: Maximum download size in bytes.

    Raises:
        GitHubError: On network, auth, or size-limit failures.
    """
    url = _zipball_url(repo_ref)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": _USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    _log.info("Downloading %s/%s (ref=%s)", repo_ref.owner, repo_ref.repo, repo_ref.ref or "default")

    try:
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=120.0) as response:
            if response.status_code == 404:
                raise GitHubError(
                    f"Repository '{repo_ref.owner}/{repo_ref.repo}' not found or is private. "
                    "Provide a token with --token or GITHUB_TOKEN for private repos."
                )
            if response.status_code in (401, 403):
                raise GitHubError(
                    "GitHub authentication failed or rate limit exceeded. "
                    "Check your token and try again."
                )
            if response.status_code != 200:
                raise GitHubError(
                    f"GitHub API returned HTTP {response.status_code} for {repo_ref.owner}/{repo_ref.repo}."
                )

            total = 0
            with open(dest_path, "wb") as out:
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise GitHubError(
                            f"Download exceeds size limit ({max_bytes // (1024 * 1024)} MB)."
                        )
                    out.write(chunk)

    except httpx.HTTPError as exc:
        raise GitHubError(f"Failed to download repository: {exc}") from exc


@contextmanager
def fetch_repo(
    value: str,
    token: str | None = None,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
) -> Generator[str, None, None]:
    """Download and extract a GitHub repository, yielding the scan root path.

    Args:
        value: Repository slug or URL.
        token: Optional GitHub token.
        max_download_bytes: Maximum zip download size.

    Yields:
        Local path to the extracted project root.

    Raises:
        GitHubError: If download or extraction fails.
    """
    repo_ref = parse_repo_ref(value)
    tmp_zip = tempfile.NamedTemporaryFile(suffix=".zip", prefix="vibesafe_gh_", delete=False)
    tmp_zip_path = tmp_zip.name
    tmp_zip.close()
    extract_dir = tempfile.mkdtemp(prefix="vibesafe_gh_extract_")

    try:
        download_repo_zip(repo_ref, token, tmp_zip_path, max_bytes=max_download_bytes)
        safe_extract_zip(tmp_zip_path, extract_dir)
        yield archive_root(extract_dir)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)
        if os.path.exists(tmp_zip_path):
            os.remove(tmp_zip_path)
