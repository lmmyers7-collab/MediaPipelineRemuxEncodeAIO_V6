"""Generated-contract validation helpers for API and stage boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mediapipeline.contracts.api_commands import validate_api_command_payload
from mediapipeline.contracts.stages import (
    StageName,
    StagePayload,
    StageRequest,
    StageResult,
    build_stage_request,
    validate_stage_data,
)


class ValidationFailure(ValueError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class ApiPayload(BaseModel):
    """Compatibility API payload model.

    Existing Local API routes accept route-specific objects in legacy
    handler modules. Phase 4 validates the object boundary
    without rejecting existing route-specific fields.
    """

    model_config = ConfigDict(extra="allow")


class ApiRouteEnvelope(BaseModel):
    route: str = Field(min_length=1)
    payload: ApiPayload


def _validation_failure(prefix: str, exc: ValidationError) -> ValidationFailure:
    first: Any = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = str(first.get("msg") or exc)
    if location:
        message = f"{location}: {message}"
    return ValidationFailure(f"{prefix}: {message}", details={"errors": exc.errors()})


def validate_api_payload(route: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the Local API object boundary without changing route contracts."""

    try:
        envelope = ApiRouteEnvelope.model_validate({"route": route, "payload": dict(payload)})
    except (TypeError, ValueError, ValidationError) as exc:
        if isinstance(exc, ValidationError):
            raise _validation_failure("invalid API payload", exc) from exc
        raise ValidationFailure(f"invalid API payload: {exc}") from exc
    try:
        return validate_api_command_payload(envelope.route, dict(envelope.payload.model_dump(mode="json")))
    except ValidationError as exc:
        raise _validation_failure("invalid API command payload", exc) from exc
    except (TypeError, ValueError) as exc:
        raise ValidationFailure(f"invalid API command payload: {exc}") from exc


def validate_stage_payload(stage: StageName | str, payload: StagePayload | Mapping[str, Any]) -> StagePayload:
    try:
        return build_stage_request(stage, payload).payload
    except ValidationError as exc:
        raise _validation_failure("invalid stage payload", exc) from exc


def validate_stage_result(stage: StageName | str, result: StageResult | Mapping[str, Any]) -> StageResult:
    try:
        typed_result = result if isinstance(result, StageResult) else StageResult.model_validate(result)
        stage_name = StageName(stage)
        if typed_result.stage != stage_name.value:
            raise ValidationFailure(
                f"stage result mismatch: expected {stage_name.value!r}, got {typed_result.stage!r}",
                details={"expected": stage_name.value, "actual": typed_result.stage},
            )
        if typed_result.ok and typed_result.data is not None:
            validate_stage_data(stage_name, typed_result.data)
        return typed_result
    except ValidationError as exc:
        raise _validation_failure("invalid stage result", exc) from exc


__all__ = [
    "ValidationFailure",
    "validate_api_payload",
    "validate_stage_payload",
    "validate_stage_result",
]
