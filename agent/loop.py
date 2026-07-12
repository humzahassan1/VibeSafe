"""Core agent loop — observe, think, act, repeat."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any

from agent.context import ContextWindow, chunk_file, summarize_findings
from agent.llm import call_llm, render_prompt
from agent.tools import read_file
from models.finding import Finding, Severity
from models.fix import Fix
from utils.logger import get_logger
from utils.tokens import count_tokens

_log = get_logger("loop")

MAX_ITERATIONS = 20
DEFAULT_TOKEN_BUDGET = 100_000

_SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "warning": Severity.WARNING,
    "info": Severity.INFO,
}


@dataclass(order=True)
class InvestigationItem:
    """An item in the investigation queue.

    Args:
        priority: Lower number = higher priority (0 = highest).
        file_path: Path to investigate.
        reason: Why this file should be checked.
        template: Prompt template to use for analysis.
    """

    priority: int
    file_path: str = field(compare=False)
    reason: str = field(compare=False)
    template: str = field(compare=False, default="auth_analysis.txt")


class InvestigationQueue:
    """Priority queue of files to investigate."""

    def __init__(self) -> None:
        self._heap: list[InvestigationItem] = []
        self._seen: set[str] = set()

    def push(self, item: InvestigationItem) -> None:
        """Add an item to the queue if not already seen.

        Args:
            item: Investigation item to add.
        """
        key = f"{item.file_path}:{item.template}"
        if key not in self._seen:
            self._seen.add(key)
            heapq.heappush(self._heap, item)

    def pop(self) -> InvestigationItem | None:
        """Pop the highest-priority item.

        Returns:
            Next item, or None if empty.
        """
        if self._heap:
            return heapq.heappop(self._heap)
        return None

    @property
    def empty(self) -> bool:
        """True if the queue has no items."""
        return len(self._heap) == 0

    def __len__(self) -> int:
        return len(self._heap)


def run_agent(
    file_paths: list[str],
    templates: list[str],
    framework: str,
    language: str,
    prior_findings: list[Finding] | None = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    model: str | None = None,
) -> list[Finding]:
    """Run the adaptive investigation agent loop.

    Args:
        file_paths: Initial files to investigate.
        templates: Prompt templates to use for each file.
        framework: Detected framework name.
        language: Detected language.
        prior_findings: Findings from Tier 1/2 to provide as context.
        token_budget: Maximum tokens for the entire agent session.
        model: LLM model override.

    Returns:
        List of findings from the agent investigation.
    """
    if prior_findings is None:
        prior_findings = []

    context_window = ContextWindow(token_budget)
    queue = InvestigationQueue()
    all_findings: list[Finding] = list(prior_findings)
    new_findings: list[Finding] = []

    for fp in file_paths:
        for template in templates:
            queue.push(InvestigationItem(
                priority=0,
                file_path=fp,
                reason="Initial high-risk file",
                template=template,
            ))

    iteration = 0
    while not queue.empty and iteration < MAX_ITERATIONS:
        item = queue.pop()
        if item is None:
            break

        iteration += 1
        _log.info(
            "Agent iteration %d/%d: investigating %s (%s)",
            iteration, MAX_ITERATIONS, item.file_path, item.reason,
        )

        content = read_file(item.file_path)
        if content is None:
            _log.warning("Could not read file: %s", item.file_path)
            continue

        content_tokens = count_tokens(content)
        if not context_window.can_afford(content_tokens + 1000):
            _log.info("Token budget exhausted at iteration %d", iteration)
            break

        try:
            system_prompt = render_prompt("system.txt", {
                "framework": framework,
                "language": language,
                "prior_findings": summarize_findings(all_findings),
            })
        except Exception as e:
            _log.warning("Could not render system prompt: %s", e)
            continue

        try:
            user_prompt = render_prompt(item.template, {
                "file_content": content,
                "framework": framework,
                "file_path": item.file_path,
            })
        except Exception as e:
            _log.warning("Could not render template %s: %s", item.template, e)
            continue

        prompt_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
        if not context_window.can_afford(prompt_tokens + 2000):
            _log.info("Not enough budget for this call, skipping")
            continue

        try:
            kwargs: dict[str, Any] = {}
            if model:
                kwargs["model"] = model
            raw_findings = call_llm(system_prompt, user_prompt, **kwargs)
        except Exception as e:
            _log.error("LLM call failed for %s: %s", item.file_path, e)
            continue

        context_window.record_usage(item.file_path, prompt_tokens + 2000)

        for raw in raw_findings:
            finding = _parse_raw_finding(raw, item.file_path)
            if finding:
                new_findings.append(finding)
                all_findings.append(finding)

            for path_hint in raw.get("investigate_further", []):
                queue.push(InvestigationItem(
                    priority=1,
                    file_path=path_hint,
                    reason=f"Follow-up from {item.file_path}: {raw.get('title', 'related issue')}",
                    template=item.template,
                ))

    _log.info(
        "Agent loop complete: %d iterations, %d new findings, %d tokens remaining",
        iteration, len(new_findings), context_window.remaining,
    )
    return new_findings


def _parse_raw_finding(raw: dict[str, Any], default_path: str) -> Finding | None:
    """Convert a raw LLM finding dict into a Finding dataclass.

    Args:
        raw: Raw finding dict from LLM response.
        default_path: Default file path if not specified in finding.

    Returns:
        Finding instance, or None if parsing fails.
    """
    try:
        severity_str = raw.get("severity", "warning").lower()
        severity = _SEVERITY_MAP.get(severity_str, Severity.WARNING)

        fix = None
        if raw.get("fix_description") and raw.get("fix_code"):
            fix = Fix(
                description=raw["fix_description"],
                code=raw["fix_code"],
                file_path=raw.get("file_path", default_path),
                fix_type="replace",
            )

        return Finding(
            rule_id=raw.get("rule_id", "SEC-000"),
            severity=severity,
            category=raw.get("category", "unknown"),
            title=raw.get("title", "Untitled finding"),
            description=raw.get("description", ""),
            file_path=raw.get("file_path", default_path),
            tier=3,
            line_start=raw.get("line_start"),
            line_end=raw.get("line_end"),
            code_snippet=raw.get("code_snippet"),
            fix=fix,
            confidence=raw.get("confidence", 0.5),
        )
    except Exception as e:
        _log.warning("Could not parse finding: %s — %s", raw, e)
        return None
