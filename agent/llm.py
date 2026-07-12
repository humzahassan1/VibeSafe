"""Claude API client — all LLM calls go through here."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import anthropic
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from utils.logger import get_logger

_log = get_logger("llm")

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
BACKOFF_BASE = 1.0
RATE_LIMIT_RPM = 30

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "prompts")

_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    undefined=StrictUndefined,
)


class RateLimiter:
    """Token-bucket rate limiter for API calls.

    Args:
        max_requests: Maximum requests allowed per minute.
    """

    def __init__(self, max_requests: int = RATE_LIMIT_RPM) -> None:
        self._max = max_requests
        self._timestamps: list[float] = []

    def wait_if_needed(self) -> None:
        """Block until a request can be made within the rate limit."""
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 60.0]

        if len(self._timestamps) >= self._max:
            sleep_time = 60.0 - (now - self._timestamps[0])
            if sleep_time > 0:
                _log.debug("Rate limiter: sleeping %.1fs", sleep_time)
                time.sleep(sleep_time)

        self._timestamps.append(time.time())


_rate_limiter = RateLimiter()


def load_api_key() -> str:
    """Load the Anthropic API key from environment.

    Returns:
        The API key string.

    Raises:
        SystemExit: If the key is not set.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit(
            "Error: ANTHROPIC_API_KEY is not set.\n"
            "Set it with: export ANTHROPIC_API_KEY=your_key_here\n"
            "Or create a .env file with ANTHROPIC_API_KEY=your_key_here"
        )
    return key


def call_llm(
    system_prompt: str,
    user_content: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> list[dict[str, Any]]:
    """Make a Claude API call and parse the response into findings.

    Args:
        system_prompt: System prompt text.
        user_content: User message content.
        model: Model identifier.
        max_tokens: Maximum response tokens.

    Returns:
        List of finding dicts parsed from the LLM response.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    api_key = load_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        _rate_limiter.wait_if_needed()

        try:
            _log.debug("LLM call attempt %d/%d (model=%s)", attempt, MAX_RETRIES, model)

            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )

            text = response.content[0].text
            return parse_llm_response(text)

        except anthropic.RateLimitError as e:
            last_error = e
            _log.warning("Rate limited (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
        except anthropic.APIStatusError as e:
            last_error = e
            if e.status_code >= 500:
                _log.warning("Server error (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
            else:
                raise
        except anthropic.APIConnectionError as e:
            last_error = e
            _log.warning("Connection error (attempt %d/%d): %s", attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            backoff = BACKOFF_BASE * (2 ** (attempt - 1))
            _log.debug("Retrying in %.1fs", backoff)
            time.sleep(backoff)

    raise RuntimeError(f"LLM call failed after {MAX_RETRIES} attempts: {last_error}")


def parse_llm_response(text: str) -> list[dict[str, Any]]:
    """Extract a JSON array of findings from LLM output.

    Args:
        text: Raw LLM response text.

    Returns:
        List of finding dicts. Empty list if parsing fails.
    """
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start != -1 and bracket_end != -1:
        text = text[bracket_start:bracket_end + 1]

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        _log.warning("LLM response parsed as %s, expected list", type(data).__name__)
        return []
    except json.JSONDecodeError as e:
        _log.warning("Could not parse LLM response as JSON: %s", e)
        return []


def render_prompt(template_name: str, variables: dict[str, str]) -> str:
    """Load and render a prompt template with variables.

    Args:
        template_name: Template filename (e.g., "auth_analysis.txt").
        variables: Template variables to substitute.

    Returns:
        Rendered prompt string.

    Raises:
        FileNotFoundError: If the template does not exist.
        jinja2.UndefinedError: If a required variable is missing.
    """
    try:
        template = _jinja_env.get_template(template_name)
    except Exception as e:
        raise FileNotFoundError(f"Prompt template not found: {template_name}") from e

    return template.render(**variables)
