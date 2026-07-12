"""Fix data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Fix:
    """A suggested fix for a security finding.

    Args:
        description: What the fix does.
        code: The actual code to replace or add.
        file_path: Where to apply the fix.
        fix_type: How to apply it — "replace", "insert", or "create_file".
    """

    description: str
    code: str
    file_path: str
    fix_type: str
