"""Subtitle QA evidence contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


SUBTITLE_QA_RESULT_SCHEMA_VERSION: Literal["subtitle_qa_result.v1"] = "subtitle_qa_result.v1"
SUBTITLE_TRACK_INVENTORY_SCHEMA_VERSION: Literal["subtitle_track_inventory.v1"] = "subtitle_track_inventory.v1"
SUBTITLE_SYNC_REVIEW_SCHEMA_VERSION: Literal["subtitle_sync_review.v1"] = "subtitle_sync_review.v1"


class SubtitleContractModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    def to_wire_payload(self) -> dict[str, Any]:
        return dict(self.model_dump(mode="json", exclude_unset=True))


class SubtitleTrackInventory(SubtitleContractModel):
    schema_version: Literal["subtitle_track_inventory.v1"] = SUBTITLE_TRACK_INVENTORY_SCHEMA_VERSION
    status: str = ""
    track_metadata_available: bool | None = None
    embedded_subtitle_count: int | None = None
    external_sidecar_count: int | None = None
    subtitle_languages: list[str] = Field(default_factory=list)
    has_forced_subtitles: bool | None = None


class SubtitleSyncReview(SubtitleContractModel):
    schema_version: Literal["subtitle_sync_review.v1"] = SUBTITLE_SYNC_REVIEW_SCHEMA_VERSION
    status: str = "heuristic_only"
    risk: str = "unknown"
    failures: list[str] = Field(default_factory=list)
    reason: str = ""


class SubtitleQaResult(SubtitleContractModel):
    schema_version: Literal["subtitle_qa_result.v1"] = SUBTITLE_QA_RESULT_SCHEMA_VERSION
    evidence_authority: str = "backend"
    scope: str = ""
    posture: str = "unknown"
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    safe_next_action: str = ""
    inventory: SubtitleTrackInventory | dict[str, Any] = Field(default_factory=dict)
    policy_match: dict[str, Any] = Field(default_factory=dict)
    srt_validity: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    conversion_evidence: dict[str, Any] = Field(default_factory=dict)
    sync_review: SubtitleSyncReview | dict[str, Any] = Field(default_factory=dict)
    guardrail: str = ""


def validate_subtitle_qa_result(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return SubtitleQaResult.model_validate(payload).to_wire_payload()
    except ValidationError:
        raise


__all__ = [
    "SUBTITLE_QA_RESULT_SCHEMA_VERSION",
    "SUBTITLE_TRACK_INVENTORY_SCHEMA_VERSION",
    "SUBTITLE_SYNC_REVIEW_SCHEMA_VERSION",
    "SubtitleQaResult",
    "SubtitleSyncReview",
    "SubtitleTrackInventory",
    "validate_subtitle_qa_result",
]
