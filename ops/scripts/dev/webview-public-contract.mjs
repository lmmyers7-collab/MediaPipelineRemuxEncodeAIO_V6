import {
  analyzeScriptAsset,
  collectHtmlIds,
  collectScriptTags,
  readText,
  repoRelative,
  scriptSrcToRepoPath,
  sortedUniq,
  webviewIndexPath,
  writeOrCheckJson,
} from "./webview-tooling-common.mjs";

const outputPath = "docs/generated/WEBVIEW_PUBLIC_CONTRACT_BASELINE.json";

function parseArgs(argv) {
  return {
    check: argv.includes("--check"),
    write: argv.includes("--write") || !argv.includes("--check"),
  };
}

function aggregate(scripts) {
  return {
    namespace_exports: sortedUniq(scripts.flatMap((script) => script.namespace_exports)),
    flat_window_exports: sortedUniq(scripts.flatMap((script) => script.flat_window_exports)),
    api_routes: sortedUniq(scripts.flatMap((script) => script.api_routes)),
    dom_ids_touched: sortedUniq(scripts.flatMap((script) => script.dom_ids_touched)),
    event_types: sortedUniq(scripts.flatMap((script) => script.event_types)),
    top_level_declaration_count: scripts.reduce((total, script) => total + script.top_level_declarations.length, 0),
  };
}

function buildManifest() {
  const indexHtml = readText(repoRelative(webviewIndexPath));
  const scriptOrder = collectScriptTags(indexHtml)
    .map((src, index) => ({
      index,
      src,
      path: scriptSrcToRepoPath(src),
    }))
    .filter((item) => item.path);
  const scripts = scriptOrder.map((item) => ({
    load_index: item.index,
    src: item.src,
    ...analyzeScriptAsset(item.path),
  }));

  return {
    schema_version: "webview_public_contract_baseline.v1",
    generated_by: "ops/scripts/dev/webview-public-contract.mjs",
    source_index: repoRelative(webviewIndexPath),
    contract_note: "Classic ordered scripts remain the runtime model. This file records the public JS/DOM/API surface before split work.",
    script_order: scriptOrder,
    html_dom_ids: collectHtmlIds(indexHtml),
    aggregate: aggregate(scripts),
    scripts,
  };
}

const args = parseArgs(process.argv.slice(2));
process.exitCode = writeOrCheckJson(outputPath, buildManifest(), args.check);
