"""Context window management and file chunking for LLM calls."""

from __future__ import annotations

import re

from models.context import FileInfo
from models.finding import Finding
from utils.files import read_file_safe
from utils.logger import get_logger
from utils.tokens import TokenBudget, count_tokens

_log = get_logger("context")

_SPLIT_PATTERNS = [
    re.compile(r'^(?:def |class |async def |function |export (?:default )?(?:function |class |const |async function ))', re.MULTILINE),
    re.compile(r'^(?:const |let |var |module\.exports)', re.MULTILINE),
]


def select_files(manifest: list[FileInfo], budget: int) -> list[FileInfo]:
    """Select files that fit within the token budget, prioritized by relevance.

    Args:
        manifest: File manifest sorted by relevance (highest first).
        budget: Maximum token budget for file content.

    Returns:
        Files selected to fit within budget.
    """
    selected: list[FileInfo] = []
    remaining = budget

    for fi in manifest:
        content = read_file_safe(fi.path)
        if content is None:
            continue

        tokens = count_tokens(content)
        if tokens <= remaining:
            selected.append(fi)
            remaining -= tokens
        elif remaining > 200:
            continue

    _log.debug("Selected %d/%d files within %d token budget", len(selected), len(manifest), budget)
    return selected


def chunk_file(content: str, budget: int) -> list[str]:
    """Split file content into chunks at logical boundaries.

    Args:
        content: Full file content.
        budget: Maximum tokens per chunk.

    Returns:
        List of content chunks.
    """
    if count_tokens(content) <= budget:
        return [content]

    boundaries: list[int] = [0]
    for pattern in _SPLIT_PATTERNS:
        for match in pattern.finditer(content):
            boundaries.append(match.start())

    boundaries = sorted(set(boundaries))
    if not boundaries or boundaries[0] != 0:
        boundaries.insert(0, 0)

    chunks: list[str] = []
    current_start = 0

    for i in range(1, len(boundaries)):
        segment = content[current_start:boundaries[i]]
        if count_tokens(segment) > budget:
            if current_start != boundaries[i - 1]:
                chunks.append(content[current_start:boundaries[i - 1]])
                current_start = boundaries[i - 1]
            if count_tokens(content[current_start:boundaries[i]]) > budget:
                chunk_text = content[current_start:boundaries[i]]
                lines = chunk_text.splitlines(keepends=True)
                sub_chunk = ""
                for line in lines:
                    if count_tokens(sub_chunk + line) > budget:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = line
                    else:
                        sub_chunk += line
                if sub_chunk:
                    current_start = boundaries[i]
                    chunks.append(sub_chunk)

    remaining = content[current_start:]
    if remaining.strip():
        if count_tokens(remaining) <= budget:
            chunks.append(remaining)
        else:
            lines = remaining.splitlines(keepends=True)
            sub_chunk = ""
            for line in lines:
                if count_tokens(sub_chunk + line) > budget:
                    if sub_chunk:
                        chunks.append(sub_chunk)
                    sub_chunk = line
                else:
                    sub_chunk += line
            if sub_chunk:
                chunks.append(sub_chunk)

    return chunks if chunks else [content]


def summarize_findings(findings: list[Finding], max_tokens: int = 500) -> str:
    """Create a condensed summary of findings for LLM context.

    Args:
        findings: List of findings to summarize.
        max_tokens: Maximum tokens for the summary.

    Returns:
        Condensed summary string.
    """
    if not findings:
        return "No prior findings."

    lines: list[str] = []
    for f in findings:
        line = f"- [{f.severity.value.upper()}] {f.rule_id}: {f.title} in {f.file_path}"
        if f.line_start:
            line += f" (line {f.line_start})"
        lines.append(line)

        if count_tokens("\n".join(lines)) > max_tokens:
            lines.pop()
            lines.append(f"... and {len(findings) - len(lines)} more findings")
            break

    return "\n".join(lines)


class ContextWindow:
    """Tracks what's been sent to the LLM and remaining budget.

    Args:
        total_budget: Total token budget for the session.
    """

    def __init__(self, total_budget: int) -> None:
        self._budget = TokenBudget(total_budget)
        self._sent_files: set[str] = set()

    @property
    def remaining(self) -> int:
        """Remaining tokens in the budget."""
        return self._budget.remaining

    def has_sent(self, file_path: str) -> bool:
        """Check if a file has already been sent to the LLM.

        Args:
            file_path: Path to check.

        Returns:
            True if already sent.
        """
        return file_path in self._sent_files

    def record_usage(self, file_path: str, tokens: int) -> None:
        """Record that a file was sent to the LLM.

        Args:
            file_path: Path that was sent.
            tokens: Tokens consumed.
        """
        self._sent_files.add(file_path)
        self._budget.consume(tokens)

    def can_afford(self, tokens: int) -> bool:
        """Check if the budget can afford a given cost.

        Args:
            tokens: Tokens needed.

        Returns:
            True if affordable.
        """
        return self._budget.can_afford(tokens)
