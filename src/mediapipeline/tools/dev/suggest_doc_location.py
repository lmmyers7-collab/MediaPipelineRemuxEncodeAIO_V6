"""Suggest an active docs/ location for a proposed Markdown document.

This helper is advisory. It does not create, move, or edit files. When the
classification is uncertain, it exits with status 2 so a human can decide.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
import re
import sys


REPO_ROOT = find_repo_root(Path(__file__))


@dataclass(frozen=True)
class Rule:
    folder: str
    reason: str
    keywords: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule(
        "docs/operator",
        "operator-facing runbook, glossary, worksheet, or manual procedure",
        ("operator", "runbook", "manual", "playbook", "worksheet", "glossary"),
    ),
    Rule(
        "docs/testing",
        "validation, smoke, gate, test, or prerequisite guidance",
        ("validation", "smoke", "test", "gate", "prereq", "coverage"),
    ),
    Rule(
        "docs/sample-validation",
        "real-media sample validation or sample evidence guidance",
        ("real-media", "sample validation", "sample", "pilot evidence", "worksheet"),
    ),
    Rule(
        "docs/inventories",
        "inventory, matrix, catalog, map, or package inclusion reference",
        ("inventory", "matrix", "catalog", "ownership map", "route map", "package"),
    ),
    Rule(
        "docs/architecture",
        "architecture boundary, ADR-like decision support, contract, or risk record",
        ("architecture", "boundary", "contract", "decision", "risk", "lifecycle"),
    ),
    Rule(
        "docs/change_control",
        "change packet, changelog, release manifest, or release-process guidance",
        ("change", "changelog", "release process", "manifest", "finalization"),
    ),
    Rule(
        "docs/implementation",
        "bounded implementation plan for future agent execution",
        ("phase", "implementation", "execution", "plan", "foundation"),
    ),
    Rule(
        "docs/ui",
        "active UI workflow or interface planning",
        ("ui", "ux", "tab", "workflow", "layout", "webview"),
    ),
)


TOP_LEVEL_STATUS_RE = re.compile(
    r"(^|[_\-\s])(report|fixes|checklist|status|handoff)([_\-\s]|$)",
    re.IGNORECASE,
)


def normalize_text(values: list[str]) -> str:
    return " ".join(value for value in values if value).lower()


def score_rule(rule: Rule, text: str, kind: str) -> int:
    score = 0
    if kind and kind.lower() in rule.folder.lower():
        score += 4
    for keyword in rule.keywords:
        if keyword in text:
            score += 2 if " " in keyword else 1
    return score


def existing_docs_folder(path: str) -> bool:
    candidate = (REPO_ROOT / path).resolve()
    docs_root = (REPO_ROOT / "docs").resolve()
    try:
        candidate.relative_to(docs_root)
    except ValueError:
        return False
    return candidate.is_dir()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Suggest a docs/ folder for a proposed Markdown document."
    )
    parser.add_argument("--title", required=True, help="Proposed document title or filename.")
    parser.add_argument(
        "--kind",
        default="",
        help="Optional hint such as operator, testing, architecture, implementation, or inventory.",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="Optional one-sentence purpose or abstract for better classification.",
    )
    parser.add_argument(
        "--allow-archive",
        action="store_true",
        help="Allow archive suggestions when the title looks historical or completed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = normalize_text([args.title, args.kind, args.summary])
    warnings: list[str] = []

    if TOP_LEVEL_STATUS_RE.search(args.title):
        warnings.append(
            "Title looks like a top-level status/checklist/report/handoff. "
            "Use an existing docs/<topic>/ folder or change-control packet instead."
        )

    if any(word in text for word in ("archive", "historical", "completed", "superseded")):
        if args.allow_archive:
            print("recommendation: docs/archive/<dated-housekeeping-or-topic-folder>")
            print("confidence: manual")
            print("reason: title or summary looks historical/completed")
            return 2
        warnings.append(
            "Title or summary looks historical/completed. Decide whether this belongs under docs/archive/."
        )

    scored = sorted(
        ((score_rule(rule, text, args.kind), rule) for rule in RULES),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_rule = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0

    if best_score < 2 or best_score == second_score:
        warnings.append("No single docs/ topic folder matched with enough confidence.")

    if warnings:
        print("recommendation: manual decision required")
        print("confidence: low")
        for warning in warnings:
            print(f"warning: {warning}")
        print("candidate folders:")
        for score, rule in scored:
            if score > 0 and existing_docs_folder(rule.folder):
                print(f"- {rule.folder}: {rule.reason} (score {score})")
        return 2

    print(f"recommendation: {best_rule.folder}")
    print("confidence: high" if best_score >= 4 else "confidence: medium")
    print(f"reason: {best_rule.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
