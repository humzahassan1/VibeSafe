"""Config loader — loads and validates rules, patterns, and frameworks at startup."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))

VALID_SEVERITIES = {"critical", "warning", "info"}
VALID_TIERS = {1, 2, 3}


@dataclass
class CompiledPattern:
    """A pre-compiled regex pattern with metadata.

    Args:
        name: Pattern identifier.
        regex: The compiled regex.
        rule_id: Linked rule ID from rules.yaml.
        file_extensions: File extensions this pattern applies to. ["*"] means all.
        exclude_patterns: Regex patterns that, if matching the same line, suppress the match.
    """

    name: str
    regex: re.Pattern[str]
    rule_id: str
    file_extensions: list[str]
    exclude_patterns: list[re.Pattern[str]] = field(default_factory=list)


@dataclass
class Config:
    """Loaded and validated configuration.

    Args:
        rules: All 51 rules keyed by rule_id.
        patterns: Pre-compiled regex patterns grouped by category.
        frameworks: Framework detection signatures.
    """

    rules: dict[str, dict[str, Any]]
    patterns: dict[str, list[CompiledPattern]]
    frameworks: dict[str, dict[str, Any]]


def load_config() -> Config:
    """Load and validate all config files.

    Returns:
        Fully loaded Config with compiled patterns.

    Raises:
        FileNotFoundError: If a config file is missing.
        ValueError: If config data is invalid.
    """
    rules = _load_rules()
    patterns = _load_patterns(rules)
    frameworks = _load_frameworks()
    return Config(rules=rules, patterns=patterns, frameworks=frameworks)


def _load_yaml(filename: str) -> Any:
    """Load a YAML file from the config directory.

    Args:
        filename: Name of the YAML file.

    Returns:
        Parsed YAML content.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML is malformed.
    """
    filepath = os.path.join(_CONFIG_DIR, filename)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Config file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Malformed YAML in {filepath}: {e}") from e


def _load_rules() -> dict[str, dict[str, Any]]:
    """Load and validate rules.yaml.

    Returns:
        Rules keyed by rule_id.

    Raises:
        ValueError: If rules are missing required fields or have invalid values.
    """
    raw = _load_yaml("rules.yaml")
    if not isinstance(raw, list):
        raise ValueError("rules.yaml must be a list of rule objects")

    required_fields = {"id", "category", "severity", "tier", "title", "description", "frameworks"}
    rules: dict[str, dict[str, Any]] = {}

    for i, rule in enumerate(raw):
        missing = required_fields - set(rule.keys())
        if missing:
            raise ValueError(f"Rule at index {i} is missing fields: {missing}")

        if rule["severity"] not in VALID_SEVERITIES:
            raise ValueError(
                f"Rule {rule['id']} has invalid severity '{rule['severity']}'. "
                f"Must be one of: {VALID_SEVERITIES}"
            )

        if rule["tier"] not in VALID_TIERS:
            raise ValueError(
                f"Rule {rule['id']} has invalid tier '{rule['tier']}'. "
                f"Must be one of: {VALID_TIERS}"
            )

        rules[rule["id"]] = rule

    if len(rules) != 51:
        raise ValueError(f"Expected 51 rules, found {len(rules)}")

    return rules


def _load_patterns(rules: dict[str, dict[str, Any]]) -> dict[str, list[CompiledPattern]]:
    """Load and compile patterns from patterns.yaml.

    Args:
        rules: Loaded rules to validate pattern rule_id links.

    Returns:
        Compiled patterns grouped by category.

    Raises:
        ValueError: If patterns are invalid or reference non-existent rules.
    """
    raw = _load_yaml("patterns.yaml")
    if not isinstance(raw, dict):
        raise ValueError("patterns.yaml must be a mapping of categories to pattern lists")

    compiled: dict[str, list[CompiledPattern]] = {}

    for category, pattern_list in raw.items():
        if not isinstance(pattern_list, list):
            raise ValueError(f"Pattern category '{category}' must be a list")

        compiled[category] = []
        for p in pattern_list:
            if p.get("rule_id") not in rules:
                raise ValueError(
                    f"Pattern '{p.get('name')}' references unknown rule_id '{p.get('rule_id')}'"
                )

            try:
                regex = re.compile(p["regex"], re.IGNORECASE)
            except re.error as e:
                raise ValueError(
                    f"Invalid regex in pattern '{p.get('name')}': {e}"
                ) from e

            exclude = []
            for ep in p.get("exclude_patterns", []):
                try:
                    exclude.append(re.compile(ep))
                except re.error as e:
                    raise ValueError(
                        f"Invalid exclude regex in pattern '{p.get('name')}': {e}"
                    ) from e

            compiled[category].append(CompiledPattern(
                name=p["name"],
                regex=regex,
                rule_id=p["rule_id"],
                file_extensions=p.get("file_extensions", ["*"]),
                exclude_patterns=exclude,
            ))

    return compiled


def _load_frameworks() -> dict[str, dict[str, Any]]:
    """Load frameworks.yaml.

    Returns:
        Framework configs keyed by framework name.

    Raises:
        ValueError: If the YAML structure is invalid.
    """
    raw = _load_yaml("frameworks.yaml")
    if not isinstance(raw, dict) or "frameworks" not in raw:
        raise ValueError("frameworks.yaml must have a 'frameworks' key")

    return raw["frameworks"]
