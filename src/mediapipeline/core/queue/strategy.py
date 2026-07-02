from __future__ import annotations

# ==============================================================================
# src/mediapipeline/core/queue/strategy.py
# ==============================================================================
# Queue ordering strategy — lets the operator choose one of eight queue sort
# presets from the UI without touching the config file.
#
# The strategy state lives at:   state_root / "queue_strategy.json"
#
# Strategies:
#   Standard       — Priority → Movies → TV  (current default behaviour)
#   FreshestFirst  — Priority → All items sorted by last-modified date desc
#   ShowComplete   — TV: finish all eps of each show before moving to the next
#   RoundRobin     — TV: one episode per show per cycle, round-robin
#   DeadlineAware  — Items with a future wantedBy date sort before normal items
#   SmallFirst     — Within each phase, sort by file size ascending
#   LargeFirst     — Within each phase, sort by file size descending
#   ManualOrder    — Operator-set position field in manifest controls order
#
# Schema (queue_strategy.json):
#   {
#     "version": 1,
#     "strategy": "<StrategyName>",
#     "set_at":   "<ISO-8601 UTC timestamp>"
#   }
#
# The PS1 pipeline reads this file at queue-build time (via QueuePlan.ps1
# Get-EffectiveQueueStrategy).  The DesktopApp API writes it via
# POST /api/queue/strategy.
# ==============================================================================

import json
import os
import uuid
from datetime import datetime, UTC
from pathlib import Path

VALID_STRATEGIES: frozenset[str] = frozenset({
    "Standard",
    "FreshestFirst",
    "ShowComplete",
    "RoundRobin",
    "DeadlineAware",
    "SmallFirst",
    "LargeFirst",
    "ManualOrder",
})

STRATEGY_LABELS: dict[str, str] = {
    "Standard":      "Standard — Priority → Movies → TV",
    "FreshestFirst": "Freshest First — by last-modified date",
    "ShowComplete":  "Show Complete — finish each show before moving on",
    "RoundRobin":    "Round Robin — 1 episode per show per cycle",
    "DeadlineAware": "Deadline Aware — by operator-set due date",
    "SmallFirst":    "Small Files First",
    "LargeFirst":    "Large Files First",
    "ManualOrder":   "Manual Order — drag-to-position",
}

DEFAULT_STRATEGY = "Standard"
STRATEGY_FILE_VERSION = 1


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------

def queue_strategy_path(state_root: Path) -> Path:
    """Return the canonical path to queue_strategy.json."""
    return state_root / "queue_strategy.json"


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_queue_strategy(path: Path) -> dict:
    """
    Load the strategy file.  Returns a default-strategy dict if the file
    does not exist, cannot be parsed, or contains an unrecognised strategy.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        if not isinstance(data, dict):
            return _default_state(source="default")
        if data.get("version") != STRATEGY_FILE_VERSION:
            return _default_state(source="default")
        strategy = str(data.get("strategy", DEFAULT_STRATEGY)).strip()
        if strategy not in VALID_STRATEGIES:
            strategy = DEFAULT_STRATEGY
        return {
            "version":  STRATEGY_FILE_VERSION,
            "strategy": strategy,
            "set_at":   str(data.get("set_at", "")),
            "source":   "state_file",
        }
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _default_state(source="default")


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def set_queue_strategy(path: Path, strategy: str) -> dict:
    """
    Atomically persist the chosen strategy name.

    Raises ``ValueError`` for unrecognised strategy names.
    Returns the updated state dict (including ``source="state_file"``).
    """
    strategy = str(strategy).strip()
    if strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"Invalid strategy {strategy!r}. "
            f"Must be one of: {sorted(VALID_STRATEGIES)}"
        )
    state = {
        "version":  STRATEGY_FILE_VERSION,
        "strategy": strategy,
        "set_at":   datetime.now(UTC).isoformat(),
    }
    _write_atomic(path, state)
    return {**state, "source": "state_file"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _default_state(source: str = "default") -> dict:
    return {
        "version":  STRATEGY_FILE_VERSION,
        "strategy": DEFAULT_STRATEGY,
        "set_at":   "",
        "source":   source,
    }


def _write_atomic(path: Path, data: dict) -> None:
    """Write *data* to *path* using a temp-file + os.replace pattern."""
    path.parent.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    tmp = path.parent / f".{path.name}.{uid}.tmp"
    try:
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# API serialisation helper
# ---------------------------------------------------------------------------

def strategy_to_api_payload(state: dict) -> dict:
    """Convert a strategy state dict to a stable API-safe payload."""
    return {
        "ok":               True,
        "strategy":         state.get("strategy", DEFAULT_STRATEGY),
        "set_at":           state.get("set_at", ""),
        "source":           state.get("source", "default"),
        "default_strategy": DEFAULT_STRATEGY,
        "valid_strategies": sorted(VALID_STRATEGIES),
        "strategy_labels":  STRATEGY_LABELS,
    }
