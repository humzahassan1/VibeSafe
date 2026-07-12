"""Centralized logging with sensitive data sanitization."""

from __future__ import annotations

import logging
import os
import re
import sys

_SENSITIVE_PATTERNS = [
    re.compile(r'((?:api[_-]?key|token|secret|password|passwd|pwd)\s*[=:]\s*)[^\s,;\"\']+', re.IGNORECASE),
    re.compile(r'((?:sk-|pk_live_|sk_live_|AKIA)[a-zA-Z0-9]+)'),
    re.compile(r'((?:postgres|mysql|mongodb|redis)://[^\s]+)', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[^\s]+', re.IGNORECASE),
]

_REDACTION = "***REDACTED***"


def sanitize(text: str) -> str:
    """Redact sensitive data from text before logging.

    Args:
        text: Raw text that may contain secrets.

    Returns:
        Text with sensitive values replaced by ***REDACTED***.
    """
    result = text
    result = _SENSITIVE_PATTERNS[0].sub(rf'\1{_REDACTION}', result)
    result = _SENSITIVE_PATTERNS[1].sub(_REDACTION, result)
    result = _SENSITIVE_PATTERNS[2].sub(_REDACTION, result)
    result = _SENSITIVE_PATTERNS[3].sub(rf'\1{_REDACTION}', result)
    return result


class _SanitizingFormatter(logging.Formatter):
    """Log formatter that sanitizes sensitive data in messages."""

    def format(self, record: logging.LogRecord) -> str:
        record.msg = sanitize(str(record.msg))
        if record.args:
            record.args = tuple(
                sanitize(str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """Create a configured logger that outputs to stderr.

    Args:
        name: Logger name, typically the module name.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(f"vibesafe.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = _SanitizingFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    level_name = os.environ.get("VIBESAFE_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))

    return logger
