"""Safe zip extraction helpers shared by CLI and SaaS."""

from __future__ import annotations

import os
import zipfile

DEFAULT_MAX_FILES = 5000
DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024


class ArchiveError(Exception):
    """Raised when an archive cannot be safely extracted."""


def safe_extract_zip(
    archive_path: str,
    dest_dir: str,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> None:
    """Extract a zip archive, guarding against path traversal and zip bombs.

    Args:
        archive_path: Path to the zip file.
        dest_dir: Directory to extract into.
        max_files: Maximum number of files allowed in the archive.
        max_file_bytes: Maximum uncompressed size per file.

    Raises:
        ArchiveError: If the archive is malformed or unsafe.
    """
    try:
        with zipfile.ZipFile(archive_path) as zf:
            members = zf.infolist()
            if len(members) > max_files:
                raise ArchiveError(f"Archive has too many files (>{max_files}).")

            dest_root = os.path.realpath(dest_dir)
            for member in members:
                if member.file_size > max_file_bytes:
                    raise ArchiveError(f"File '{member.filename}' exceeds size limit.")
                target = os.path.realpath(os.path.join(dest_dir, member.filename))
                if not target.startswith(dest_root + os.sep) and target != dest_root:
                    raise ArchiveError("Archive contains an unsafe path (traversal).")

            zf.extractall(dest_dir)
    except zipfile.BadZipFile as exc:
        raise ArchiveError("Uploaded file is not a valid zip archive.") from exc


def archive_root(extract_dir: str) -> str:
    """Return the effective project root inside an extracted archive.

    If the archive contains a single top-level directory, use it as the root
    (matches GitHub zipball layout: ``owner-repo-<sha>/``).

    Args:
        extract_dir: The extraction directory.

    Returns:
        The path to scan.
    """
    entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
    if len(entries) == 1:
        candidate = os.path.join(extract_dir, entries[0])
        if os.path.isdir(candidate):
            return candidate
    return extract_dir
