(function () {
  "use strict";

  let state;
  let text;
  let humanize;
  let stageLabel;
  let routeDisplay;
  let TERMINAL_ITEM_STATES;
  let PROJECTION_SCHEMA;
  const VERIFIED_DISPLAY_NAME_SOURCE = "plex_destination_plan.v1";

function array(value) {
    return Array.isArray(value) ? value.filter(Boolean) : [];
  }

function object(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

function selectedItem(payload = state.payload) {
    return array(payload?.items).find((item) => text(item?.job_id) === state.selectedJobId) || null;
  }

function currentClaimsAllowed(freshnessState) {
    return freshnessState === "current" || freshnessState === "terminal";
  }

function itemEvidenceAllowed(item, freshnessState) {
    // A stale or unavailable run must not revive live claims. Terminal item
    // artifacts are historical proof, however, and remain useful/selectable
    // after live evidence has aged out.
    return currentClaimsAllowed(text(freshnessState))
      || TERMINAL_ITEM_STATES.has(text(item?.lifecycle_state));
  }

function workerJobIds(payload = state.payload) {
    return new Set(array(payload?.current_workers).map((worker) => text(worker?.job_id)).filter(Boolean));
  }

function selectInitialJob(payload) {
    const items = array(payload?.items);
    if (!items.length) return "";
    if (items.some((item) => text(item.job_id) === state.selectedJobId)) return state.selectedJobId;
    if (text(payload?.freshness?.state) === "current") {
      const currentIds = workerJobIds(payload);
      const workerItem = items.find((item) => currentIds.has(text(item.job_id)));
      if (workerItem) return text(workerItem.job_id);
      const activeItem = items.find((item) => text(item.lifecycle_state) === "active");
      if (activeItem) return text(activeItem.job_id);
    }
    return text(items[0]?.job_id);
  }

function visibleLifecycleState(item, freshnessState) {
    const lifecycleState = text(item?.lifecycle_state, "unknown");
    if (currentClaimsAllowed(text(freshnessState)) || TERMINAL_ITEM_STATES.has(lifecycleState)) return lifecycleState;
    return "unknown";
  }

function currentStageLabel(item, freshnessState) {
    const record = object(item);
    const freshness = text(freshnessState);
    if (!itemEvidenceAllowed(record, freshness)) return `Suppressed · ${humanize(freshness)}`;
    if (freshness === "current") {
      const current = object(record.current_stage);
      if (text(current.stage_id) && text(current.state) === "active") return stageLabel(current.stage_id);
    }
    const stages = array(record.stages);
    const explicit = [...stages].reverse().find((stage) => text(stage.state) !== "not_started");
    if (explicit) return `${stageLabel(explicit.stage_id)} · ${humanize(explicit.state)}`;
    if (text(record.lifecycle_state) === "queued" || text(record.lifecycle_state) === "accepted") return "Not started";
    return "Unknown";
  }

function routeSummary(item, freshnessState) {
    if (!itemEvidenceAllowed(item, freshnessState)) return `Route claims suppressed · ${humanize(freshnessState)}`;
    const record = object(item);
    const finalRoute = routeDisplay(record.final_route, "Final route", "Final reason");
    if (finalRoute.value) return `Final route: ${finalRoute.value}`;
    const executedRoute = routeDisplay(record.executed_route, "Executed route", "Executed reason");
    if (executedRoute.value) return `Executed route: ${executedRoute.value}`;
    const plannedRoute = routeDisplay(record.planned_route, "Planned route", "Planned reason");
    if (plannedRoute.value) return `Planned route: ${plannedRoute.value}`;
    return "Route evidence unknown";
  }

function displayNameBasis(item) {
    const declaredBasis = text(item?.display_name_basis);
    if (["verified_queue_plan", "terminal_output", "legacy_accepted"].includes(declaredBasis)) return declaredBasis;
    const evidence = object(item?.display_name_evidence);
    if (text(evidence.source) === VERIFIED_DISPLAY_NAME_SOURCE && text(evidence.provenance) === "queue_plan") {
      return "verified_queue_plan";
    }
    return "legacy_accepted";
  }

function displayNameAuthorityLabel(item) {
    const basis = displayNameBasis(item);
    if (basis === "verified_queue_plan") {
      return "File name authority: Verified backend production naming plan";
    }
    if (basis === "terminal_output") {
      return "File name authority: Exact job-correlated terminal output evidence";
    }
    return "File name authority: Legacy accepted label; cleaned-name evidence unknown";
  }

function duplicateDisplayNames(items) {
    const counts = new Map();
    items.forEach((item) => {
      const key = text(item.display_name, "Unnamed accepted file").toLocaleLowerCase();
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return new Set(Array.from(counts.entries()).filter(([, count]) => count > 1).map(([key]) => key));
  }

function unavailableItem(item) {
    const record = object(item);
    if (TERMINAL_ITEM_STATES.has(text(record.lifecycle_state))) return record;
    return {
      ...record,
      lifecycle_state: "unknown",
      current_stage: null,
      current_progress: null,
      stages: [],
      audio: { state: "unknown", policy_final: false, tracks: [], evidence: object(record.audio?.evidence) },
      subtitles: { state: "unknown", policy_final: false, tracks: [], evidence: object(record.subtitles?.evidence) },
      output: {
        ...object(record.output),
        state: "unknown",
        scratch_path: "",
        working_output_path: "",
        published_path: "",
        parked_path: "",
        intended_final_path: "",
        size_bytes: null,
        verification_state: "unknown",
        sidecars: [],
      },
    };
  }

function unavailablePayload(reasonCode, detail = "", previousPayload = state.payload) {
    const previous = object(previousPayload);
    const existingLastKnown = object(previous.last_known);
    const previousItems = array(previous.items);
    const historicalItems = array(existingLastKnown.items).length ? array(existingLastKnown.items) : previousItems;
    const historicalWorkers = array(existingLastKnown.current_workers).length
      ? array(existingLastKnown.current_workers)
      : array(previous.current_workers);
    const lastUpdated = text(existingLastKnown.updated_at, text(previous.freshness?.updated_at, text(previous.run?.updated_at)));
    const parsedUpdated = Date.parse(lastUpdated);
    const ageSeconds = Number.isFinite(parsedUpdated)
      ? Math.max(0, (Date.now() - parsedUpdated) / 1000)
      : Number.isFinite(Number(existingLastKnown.age_seconds))
        ? Number(existingLastKnown.age_seconds)
        : Number.isFinite(Number(previous.freshness?.age_seconds))
          ? Number(previous.freshness.age_seconds)
          : null;
    const previousRun = object(previous.run);
    const terminalRun = ["completed", "failed", "blocked", "review", "stopped", "force_stopped"].includes(text(previousRun.lifecycle_state));
    const run = text(previousRun.run_id)
      ? {
          ...previousRun,
          lifecycle_state: terminalRun ? text(previousRun.lifecycle_state) : "unknown",
          stop_after_current: terminalRun
            ? object(previousRun.stop_after_current)
            : { state: "unavailable", requested_at: "", evidence: null },
        }
      : null;
    return {
      schema_version: PROJECTION_SCHEMA,
      run,
      freshness: {
        state: "unavailable",
        reason_code: reasonCode,
        detail,
        updated_at: lastUpdated,
        age_seconds: ageSeconds,
        backend_state: "unavailable",
      },
      items: previousItems.map(unavailableItem),
      current_workers: [],
      last_known: historicalItems.length || historicalWorkers.length
        ? {
            label: "Last known — not current",
            updated_at: lastUpdated,
            age_seconds: ageSeconds,
            items: historicalItems,
            current_workers: historicalWorkers,
          }
        : null,
      compatibility: { legacy_current_work_used: false },
    };
  }

function launchAcceptancePayload(identity) {
    return {
      schema_version: PROJECTION_SCHEMA,
      run: {
        run_id: identity.runId,
        mode: "once",
        scope: "backend_queue",
        display_mode: "Run Once · Backend Queue",
        accepted_queue: {
          schema_version: "queue_plan_fingerprint.v1",
          fingerprint: identity.fingerprint,
          accepted_count: null,
        },
        lifecycle_state: "starting",
        launch_acceptance_state: identity.acceptanceState,
        started_at: "",
        updated_at: "",
        ended_at: "",
        stop_after_current: { state: "unavailable", requested_at: "", evidence: null },
        counts: {},
        outcome: null,
        evidence: {
          source: "pipeline_start_response",
          provenance: "backend_launch_response",
          recorded_at: "",
        },
      },
      freshness: {
        state: "unknown",
        reason_code: identity.acceptanceState,
        detail: "The backend accepted the launch. Current Work is loading the durable run monitor before showing accepted files or current claims.",
        updated_at: "",
        age_seconds: null,
        backend_state: "launch_accepted",
      },
      items: [],
      current_workers: [],
      last_known: null,
      compatibility: { legacy_current_work_used: false },
    };
  }

function launchMonitorIdentity(result) {
    const payload = object(result);
    const data = object(payload.data);
    const monitor = object(data.run_monitor);
    return {
      schema: text(monitor.schema_version),
      runId: text(monitor.run_id, text(data.run_id)),
      route: text(monitor.route),
      acceptanceState: text(monitor.acceptance_state),
      fingerprint: text(monitor.expected_queue?.fingerprint, text(data.accepted_queue_fingerprint)),
    };
  }

  window.__runMonitorNormalizationModule = function createRunMonitorNormalization(deps) {
    ({ state, text, humanize, stageLabel, routeDisplay } = deps);
    TERMINAL_ITEM_STATES = deps.terminalItemStates;
    PROJECTION_SCHEMA = deps.projectionSchema;
    return {
      array,
      object,
      selectedItem,
      currentClaimsAllowed,
      itemEvidenceAllowed,
      workerJobIds,
      selectInitialJob,
      visibleLifecycleState,
      currentStageLabel,
      routeSummary,
      displayNameBasis,
      displayNameAuthorityLabel,
      duplicateDisplayNames,
      unavailableItem,
      unavailablePayload,
      launchAcceptancePayload,
      launchMonitorIdentity
    };
  };
})();
