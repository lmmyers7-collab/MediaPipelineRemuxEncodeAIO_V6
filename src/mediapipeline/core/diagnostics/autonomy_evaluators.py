"""Autonomy health category evaluation wrappers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mediapipeline.core.diagnostics.autonomy_types import category, issue


def evaluate_category(name: str, evaluator: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return evaluator()
    except Exception as exc:
        return category_evaluation_error(name, exc)


def category_evaluation_error(name: str, exc: Exception) -> dict[str, Any]:
    message = str(exc) or exc.__class__.__name__
    return category(
        name,
        "review",
        metrics={"evaluation_error": message},
        summary_lines=[
            f"{name.replace('_', ' ').title()} health could not be fully evaluated.",
            f"Error: {message}",
        ],
        review_items=[
            issue(
                f"autonomy_{name}_evaluation_error",
                name,
                "medium",
                f"Autonomy health category could not be evaluated: {message}",
                next_action="Inspect diagnostics logs and retry autonomy health after the transient read/stat/JSON issue is resolved.",
            )
        ],
    )


__all__ = [
    "category_evaluation_error",
    "evaluate_category",
]
