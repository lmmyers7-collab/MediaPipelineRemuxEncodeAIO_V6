"""Machine-readable file lifecycle contract for generated safety docs."""

from __future__ import annotations

from dataclasses import dataclass


LIFECYCLE_SCHEMA_VERSION = "file_lifecycle.v1"


@dataclass(frozen=True)
class LifecycleState:
    state_id: str
    label: str
    implemented: bool
    owner: str
    description: str
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    artifacts: tuple[str, ...]
    recovery_rule: str
    cleanup_rule: str
    validation_rung: str


@dataclass(frozen=True)
class LifecycleTransition:
    source: str
    target: str
    trigger: str
    guard: str
    evidence: str


LIFECYCLE_STATES: tuple[LifecycleState, ...] = (
    LifecycleState(
        state_id="source_library",
        label="Source library",
        implemented=True,
        owner="Pipeline source discovery and scratch copy",
        description="Operator media roots are treated as immutable inputs.",
        allowed_operations=("read", "probe metadata", "copy to scratch"),
        forbidden_operations=("delete by default", "overwrite", "in-place transcode", "publish from source"),
        artifacts=("source path", "source size", "source mtime", "source identity fields"),
        recovery_rule="Source media must remain available for retry unless an explicit safe-delete policy is intentionally enabled.",
        cleanup_rule="No cleanup is allowed against source roots by default.",
        validation_rung="media-policy-release-real-media",
    ),
    LifecycleState(
        state_id="incoming_candidate",
        label="Incoming candidate",
        implemented=False,
        owner="Not currently implemented as a dedicated folder",
        description="No canonical incoming/ intake_pending folder state exists in V6 today.",
        allowed_operations=("document as absent",),
        forbidden_operations=("treat as a live queue state without adding code and tests",),
        artifacts=("n/a",),
        recovery_rule="Use the existing source discovery and scratch-copy lifecycle until a dedicated intake state is added.",
        cleanup_rule="No cleanup rule because the state is not implemented.",
        validation_rung="docs-and-contract-checks",
    ),
    LifecycleState(
        state_id="scratch_copy",
        label="Scratch copy",
        implemented=True,
        owner="engine scratch-copy and disk modules",
        description="Source media is copied to local scratch before downstream mutation-capable work.",
        allowed_operations=("copy from source", "hash or size verification", "consume for probe/transcode"),
        forbidden_operations=("expose partial copy as ready", "overwrite unrelated scratch files", "delete source on copy failure"),
        artifacts=("local scratch path", "copy telemetry", "sha256 or size evidence"),
        recovery_rule="Failed or partial scratch copies remain retryable and should not affect source media.",
        cleanup_rule="Stale partial scratch artifacts are eligible for guarded cleanup after retention.",
        validation_rung="media-policy-release-real-media",
    ),
    LifecycleState(
        state_id="processing",
        label="Processing",
        implemented=True,
        owner="Pipeline engine, FFmpeg, subtitle, and audio modules",
        description="Scratch media is probed, routed, remuxed, encoded, and sidecars may be produced.",
        allowed_operations=("read scratch", "write temp outputs", "write sidecars", "write logs"),
        forbidden_operations=("publish unverified partial output", "silently drop subtitle/OCR failures", "mutate source"),
        artifacts=("FFmpeg logs", "progress state", "failure markers", "sidecar outputs"),
        recovery_rule="Failures route to failure markers/review and preserve enough evidence for operator recovery.",
        cleanup_rule="Only temp artifacts inside allowed scratch/state roots may be cleaned.",
        validation_rung="media-policy-release-real-media",
    ),
    LifecycleState(
        state_id="local_output",
        label="Local output",
        implemented=True,
        owner="Pipeline publish preparation",
        description="Completed local media output awaits final publish or pending-publish parking.",
        allowed_operations=("verify size/hash evidence", "write sidecar", "copy to final partial", "park pending publish"),
        forbidden_operations=("delete before publish evidence", "overwrite final output without transactional guard"),
        artifacts=("local output", "pipeline sidecar", "publish transaction id"),
        recovery_rule="Local output can be retried, parked, or reconciled with manifest evidence.",
        cleanup_rule="Delete only after validated publish or pending-publish cleanup rules run.",
        validation_rung="settings-pending-publish-diagnostics",
    ),
    LifecycleState(
        state_id="pending_publish",
        label="Pending publish",
        implemented=True,
        owner="engine publish pending-transaction and drain modules",
        description="Output is parked when final-root publish is unsafe or deferred.",
        allowed_operations=("write pending manifest", "move local output into pending store", "drain with manifest evidence"),
        forbidden_operations=("bypass manifest", "drain from source media", "discard parked output before validated publish"),
        artifacts=("*.manifest.json", "parked media", "parked sidecars", "drain summary"),
        recovery_rule="pending_move manifests are repairable; parked manifests remain retryable until drained or operator-reviewed.",
        cleanup_rule="Parked local artifacts are removed only after server copy validates or already-published evidence is confirmed.",
        validation_rung="settings-pending-publish-diagnostics",
    ),
    LifecycleState(
        state_id="final_output",
        label="Final output",
        implemented=True,
        owner="Publish completion and completed manifest modules",
        description="Validated media output is visible in the final library root.",
        allowed_operations=("write completed manifest entry", "write output summary", "preserve sidecar evidence"),
        forbidden_operations=("replace without transactional partial/backup flow", "delete on sidecar write failure"),
        artifacts=("completed manifest", "pipeline sidecar", "output summary"),
        recovery_rule="Completed evidence can reconcile UI state and prevent duplicate processing.",
        cleanup_rule="Final outputs are not cleanup targets for pipeline temp cleanup.",
        validation_rung="settings-pending-publish-diagnostics",
    ),
    LifecycleState(
        state_id="failure_review",
        label="Failure review",
        implemented=True,
        owner="Failure state and desktop failure cleanup services",
        description="Failure markers and reports preserve evidence for operator review.",
        allowed_operations=("write failure marker", "archive cleared marker", "dry-run clear workspace"),
        forbidden_operations=("clear outside failure roots", "clear without manifest evidence"),
        artifacts=("failure marker JSON", "failure reports", "clear manifest"),
        recovery_rule="Operator can inspect markers and reports before guarded cleanup.",
        cleanup_rule="Failure cleanup is limited to allowed failure workspace roots and can run dry-run first.",
        validation_rung="settings-pending-publish-diagnostics",
    ),
    LifecycleState(
        state_id="ready_archive_quarantine_trash",
        label="Ready/archive/quarantine/trash-pending",
        implemented=False,
        owner="Not currently implemented as dedicated folders",
        description="The audit terms exist as desired lifecycle concepts but are not canonical V6 runtime folders today.",
        allowed_operations=("document as absent", "map future work explicitly before adding states"),
        forbidden_operations=("assume these folders exist", "cleanup into these folders without a contract"),
        artifacts=("n/a",),
        recovery_rule="Use pending publish, completed manifests, and failure review until these states are explicitly implemented.",
        cleanup_rule="No cleanup rule because the states are not implemented.",
        validation_rung="docs-and-contract-checks",
    ),
)


LIFECYCLE_TRANSITIONS: tuple[LifecycleTransition, ...] = (
    LifecycleTransition(
        source="source_library",
        target="scratch_copy",
        trigger="source selected for processing",
        guard="source path allowed and stable enough for copy",
        evidence="source identity, size, mtime, scratch path",
    ),
    LifecycleTransition(
        source="scratch_copy",
        target="processing",
        trigger="copy verification succeeds",
        guard="scratch copy is complete and visible only as scratch input",
        evidence="copy telemetry and scratch metadata",
    ),
    LifecycleTransition(
        source="processing",
        target="local_output",
        trigger="remux/encode/subtitle/audio work completes",
        guard="output exists and required sidecar/review policy is satisfied",
        evidence="local output, sidecars, logs, route decision",
    ),
    LifecycleTransition(
        source="local_output",
        target="pending_publish",
        trigger="final publish is unsafe, unavailable, or deferred",
        guard="pending manifest written and validated before park move completes",
        evidence="pending manifest and parked media",
    ),
    LifecycleTransition(
        source="local_output",
        target="final_output",
        trigger="immediate publish succeeds",
        guard="transactional partial/backup publish validates final copy",
        evidence="completed manifest and pipeline sidecar",
    ),
    LifecycleTransition(
        source="pending_publish",
        target="final_output",
        trigger="pending drain succeeds",
        guard="manifest evidence validates parked local copy and server copy",
        evidence="drain summary, completed manifest, output summary",
    ),
    LifecycleTransition(
        source="processing",
        target="failure_review",
        trigger="stage failure or review-required condition",
        guard="failure reason is classified",
        evidence="failure marker, report, logs",
    ),
)


def lifecycle_state_by_id() -> dict[str, LifecycleState]:
    return {state.state_id: state for state in LIFECYCLE_STATES}
