from __future__ import annotations

from typing import Any


def issue_details(
    category: str,
    *,
    evidence: str,
    impact: str,
    next_step: str,
) -> dict[str, Any]:
    """Describe why a hardware-facing operation cannot produce reliable evidence."""
    return {
        "category": category,
        "evidence": evidence,
        "impact": impact,
        "next_step": next_step,
    }
