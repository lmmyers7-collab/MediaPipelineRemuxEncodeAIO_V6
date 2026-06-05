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

const outputPath = "docs/generated/WEBVIEW_DOM_ID_GAP_REPORT.json";
const webviewStaticPrefix = "apps/desktop/webview/static/";

function parseArgs(argv) {
  return {
    check: argv.includes("--check"),
    write: argv.includes("--write") || !argv.includes("--check"),
  };
}

function likelyDynamicId(id) {
  return /(^row-|^detail-|template|prototype|placeholder|generated|dynamic|modal|drawer)/i.test(id)
    || /-(row|cell|item|template|prototype|dialog|modal|drawer)$/.test(id);
}

function expandIncludes(indexHtml) {
  const includePaths = [];
  const html = indexHtml.replace(/<!--\s*mp-include:\s*([^>]+?)\s*-->/g, (_match, includePath) => {
    const normalized = String(includePath || "").trim().replaceAll("\\", "/");
    includePaths.push(normalized);
    return readText(`${webviewStaticPrefix}${normalized}`);
  });
  return { html, includePaths };
}

function buildReport() {
  const indexHtml = readText(repoRelative(webviewIndexPath));
  const expanded = expandIncludes(indexHtml);
  const htmlIds = collectHtmlIds(expanded.html);
  const htmlIdSet = new Set(htmlIds);
  const scripts = collectScriptTags(indexHtml)
    .map((src) => ({ src, path: scriptSrcToRepoPath(src) }))
    .filter((item) => item.path)
    .map((item) => ({
      ...item,
      dom_ids_touched: analyzeScriptAsset(item.path).dom_ids_touched,
    }));
  const jsIds = sortedUniq(scripts.flatMap((script) => script.dom_ids_touched));
  const missing = jsIds.filter((id) => !htmlIdSet.has(id));
  const dynamic = missing.filter(likelyDynamicId);
  const review = missing.filter((id) => !likelyDynamicId(id));

  return {
    schema_version: "webview_dom_id_gap_report.v1",
    generated_by: "ops/scripts/dev/check-webview-dom-id-gaps.mjs",
    source_index: repoRelative(webviewIndexPath),
    included_partials: expanded.includePaths,
    report_note: "Pre-split report only. IDs are collected from index.html with mp-include partials expanded. Missing IDs can be legitimate when markup is generated at runtime, but every future split should keep this report stable or deliberately update it.",
    counts: {
      html_ids: htmlIds.length,
      js_touched_ids: jsIds.length,
      ids_present_in_index: jsIds.filter((id) => htmlIdSet.has(id)).length,
      ids_missing_from_index: missing.length,
      likely_dynamic_missing_ids: dynamic.length,
      review_missing_ids: review.length,
    },
    ids_present_in_index: jsIds.filter((id) => htmlIdSet.has(id)),
    ids_missing_from_index: missing,
    likely_dynamic_missing_ids: dynamic,
    review_missing_ids: review,
    scripts: scripts.map((script) => ({
      src: script.src,
      path: script.path,
      dom_ids_touched: script.dom_ids_touched,
      missing_from_index: script.dom_ids_touched.filter((id) => !htmlIdSet.has(id)),
    })),
  };
}

const args = parseArgs(process.argv.slice(2));
process.exitCode = writeOrCheckJson(outputPath, buildReport(), args.check);
