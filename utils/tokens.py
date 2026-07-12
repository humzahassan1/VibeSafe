"""Token counting and budget management for LLM context."""

from __future__ import annotations

import tiktoken

from utils.logger import get_logger

_log = get_logger("tokens")

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count the number of tokens in a string.

    Args:
        text: Text to count tokens for.

    Returns:
        Number of tokens.
    """
    if not text:
        return 0
    return len(_ENCODING.encode(text))


def fits_in_context(text: str, budget: int) -> bool:
    """Check if text fits within a token budget.

    Args:
        text: Text to check.
        budget: Maximum token count.

    Returns:
        True if the text fits within the budget.
    """
    return count_tokens(text) <= budget


def truncate_to_budget(text: str, budget: int) -> str:
    """Truncate text to fit within a token budget, preserving start and end.

    Args:
        text: Text to truncate.
        budget: Maximum token count.

    Returns:
        Truncated text that fits within the budget.
    """
    tokens = _ENCODING.encode(text)
    if len(tokens) <= budget:
        return text

    if budget <= 0:
        return ""

    marker = "\n\n... [content truncated for context budget] ...\n\n"
    marker_tokens = len(_ENCODING.encode(marker))

    if budget <= marker_tokens:
        return _ENCODING.decode(tokens[:budget])

    available = budget - marker_tokens
    head_size = available // 2
    tail_size = available - head_size

    head = _ENCODING.decode(tokens[:head_size])
    tail = _ENCODING.decode(tokens[-tail_size:])
    return head + marker + tail


class TokenBudget:
    """Tracks token usage against a total budget.

    Args:
        total: Total token budget.
    """

    def __init__(self, total: int) -> None:
        self._total = total
        self._used = 0

    @property
    def total(self) -> int:
        """Total token budget."""
        return self._total

    @property
    def used(self) -> int:
        """Tokens consumed so far."""
        return self._used

    @property
    def remaining(self) -> int:
        """Tokens remaining in the budget."""
        return max(0, self._total - self._used)

    def consume(self, tokens: int) -> None:
        """Record token usage.

        Args:
            tokens: Number of tokens consumed.
        """
        self._used += tokens
        _log.debug("Token budget: %d used / %d total (%d remaining)",
                    self._used, self._total, self.remaining)

    def can_afford(self, tokens: int) -> bool:
        """Check if the budget can afford a given token count.

        Args:
            tokens: Number of tokens needed.

        Returns:
            True if enough budget remains.
        """
        return tokens <= self.remaining
