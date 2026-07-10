"""Network-page settings field definitions."""

from __future__ import annotations

from ..metadata_network import (
    KEY_COORDINATOR_ALSO_ENCODE_LOCALLY,
    KEY_COORDINATOR_AUTH_TOKEN,
    KEY_COORDINATOR_BIND_ADDRESS,
    KEY_COORDINATOR_HEARTBEAT_TIMEOUT_MINS,
    KEY_COORDINATOR_MAX_JOB_RETRIES,
    KEY_COORDINATOR_PORT,
    KEY_NETWORK_RERUN_HANDOFF_ROOT,
    KEY_NETWORK_ROLE,
    KEY_WORKER_AUTH_TOKEN,
    KEY_WORKER_CONFIG_OVERRIDES,
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
    KEY_WORKER_NAME,
    KEY_WORKER_POLL_INTERVAL_SECS,
    KEY_WORKER_SOURCE_PATH_MAP,
)


NETWORK_CONFIG_FIELD_DEFINITIONS = (
    # ------------------------------------------------------------------
    # Network mode fields (Phase 0 — auto-rendered as plain fields;
    # replaced by a hand-built panel in Phase 1)
    # ------------------------------------------------------------------
    {
        "page": "Network",
        "section": "Role",
        "key": KEY_NETWORK_ROLE,
        "label": "Network Role",
        "kind": "combo",
        "choices": ("standalone", "coordinator", "worker"),
        "help": (
            "standalone: one machine, all files local — current behaviour, no change. "
            "coordinator: this machine manages the queue and hands out work via HTTP. "
            "worker: this machine polls a coordinator for files to encode."
        ),
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_COORDINATOR_PORT,
        "label": "Listen Port",
        "kind": "int",
        "default": 7830,
        "help": "TCP port the coordinator HTTP server listens on (default 7830). Workers must use the same port.",
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_COORDINATOR_BIND_ADDRESS,
        "label": "Bind Address",
        "kind": "string",
        "default": "0.0.0.0",
        "help": "Interface address for the plaintext coordinator HTTP API. Use 0.0.0.0 for trusted LAN workers, or 127.0.0.1 for local-only testing.",
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_COORDINATOR_ALSO_ENCODE_LOCALLY,
        "label": "Also Encode Locally",
        "kind": "bool",
        "help": "When enabled, the coordinator also takes files from its own queue and encodes them (requires a GPU). When disabled it only hands out work to remote workers.",
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_COORDINATOR_HEARTBEAT_TIMEOUT_MINS,
        "label": "Heartbeat Timeout (min)",
        "kind": "int",
        "default": 5,
        "help": "Minutes without a heartbeat before a claimed job is considered stale and re-queued for another worker (default 5).",
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_COORDINATOR_MAX_JOB_RETRIES,
        "label": "Max Same-Reason Retries",
        "kind": "int",
        "default": 3,
        "help": "Consecutive same-reason failures for one worker/source before the coordinator stops handing that source back to that worker (default 3).",
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_COORDINATOR_AUTH_TOKEN,
        "label": "Auth Token",
        "kind": "string",
        "help": "Shared bearer token. Leave blank for auto-generation on first coordinator-mode start. Must match WorkerAuthToken on all workers.",
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_NETWORK_RERUN_HANDOFF_ROOT,
        "label": "Rerun Handoff Root",
        "kind": "string",
        "default": "",
        "help": (
            "Coordinator-readable, worker-writable root for Network CSV rerun outputs. "
            "Remote workers require a UNC/shared path. The root must stay outside source, "
            "final output, LocalBase, and Pending Publish state."
        ),
    },
    {
        "page": "Network",
        "section": "Worker",
        "key": KEY_WORKER_COORDINATOR_URL,
        "label": "Coordinator URL",
        "kind": "string",
        "help": "Full URL of the coordinator, e.g. http://192.168.1.50:7830. Only used when NetworkRole is 'worker'.",
    },
    {
        "page": "Network",
        "section": "Worker",
        "key": KEY_WORKER_NAME,
        "label": "Worker Name",
        "kind": "string",
        "help": "Human-readable label shown in the coordinator's worker board. Defaults to the machine hostname when left blank.",
    },
    {
        "page": "Network",
        "section": "Worker",
        "key": KEY_WORKER_AUTH_TOKEN,
        "label": "Auth Token",
        "kind": "string",
        "help": "Must match the coordinator's CoordinatorAuthToken. Only used when NetworkRole is 'worker'.",
    },
    {
        "page": "Network",
        "section": "Worker",
        "key": KEY_WORKER_POLL_INTERVAL_SECS,
        "label": "Poll Interval (s)",
        "kind": "int",
        "default": 10,
        "help": "Seconds between coordinator polls when the queue is empty (default 10).",
    },
    {
        "page": "Network",
        "section": "Worker",
        "key": KEY_WORKER_SOURCE_PATH_MAP,
        "label": "Source Path Map",
        "kind": "string",
        "help": (
            'JSON object mapping coordinator paths → locally-accessible paths. '
            'Use when the coordinator hands out paths that this worker cannot reach '
            '(different drive letter, UNC vs local on the server, NFS vs SMB mount). '
            'Each key is matched as a prefix against the incoming source_path; the '
            'first prefix that matches gets rewritten. Backslashes must be escaped. '
            r'Example: {"C:\\Users\\Operator\\Videos\\Encode": "\\\\MEDIA-SERVER\\Share\\Encode"}'
        ),
    },
    {
        "page": "Network",
        "section": "Worker",
        "key": KEY_WORKER_ENCODER_MAP,
        "label": "Worker Encoder Map",
        "kind": "string",
        "default": "",
        "help": (
            "Worker-owned hardware map from coordinator codec families to local encoders. "
            "Coordinator library policy remains cluster-authoritative; this setting only chooses "
            'the local implementation, for example {"hevc":"hevc_nvenc","h264":"h264_nvenc"}. '
            "Missing or unsupported entries fall back to CPU encoders with a worker log warning."
        ),
    },
    {
        "page": "Network",
        "section": "Worker",
        "key": KEY_WORKER_HONOR_COORDINATOR_POLICY,
        "label": "Honor Coordinator Policy",
        "kind": "bool",
        "default": False,
        "help": (
            "When enabled, claimed network jobs use the coordinator's cluster-authoritative "
            "per-library processing policy plus this worker's encoder map. Leave disabled until "
            "real-media validation for the cluster policy rollout is complete."
        ),
    },
    {
        "page": "Network",
        "section": "Coordinator",
        "key": KEY_WORKER_CONFIG_OVERRIDES,
        "label": "Per-Worker Config Overrides",
        "kind": "string",
        "help": (
            'JSON object mapping worker names to partial config overrides. '
            'Applied when the coordinator builds ClaimResponse.encode_config. '
            'Example: {"BEAST-PC": {"VideoPreset": "p4"}, "LAPTOP": {"VideoPreset": "p2"}}'
        ),
    },
)
