import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "@babel/parser";
import traverseModule from "@babel/traverse";

export const traverse = traverseModule.default || traverseModule;
export const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
export const webviewStaticRoot = join(repoRoot, "apps", "desktop", "webview", "static");
export const webviewAssetsRoot = join(webviewStaticRoot, "assets");
export const webviewIndexPath = join(webviewStaticRoot, "index.html");

export function repoRelative(path) {
  return relative(repoRoot, resolve(repoRoot, path)).replaceAll("\\", "/");
}

export function readText(path) {
  return readFileSync(resolve(repoRoot, path), "utf-8");
}

export function sortedUniq(values) {
  return [...new Set(values.filter(Boolean))].sort();
}

export function collectJsFiles(dir = webviewAssetsRoot) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectJsFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".js")) {
      files.push(repoRelative(fullPath));
    }
  }
  return files.sort();
}

export function collectScriptTags(indexHtml = readFileSync(webviewIndexPath, "utf-8")) {
  return [...indexHtml.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)]
    .map((match) => match[1])
    .filter(Boolean);
}

export function scriptSrcToRepoPath(src) {
  const normalized = src.split(/[?#]/, 1)[0].replace(/^\//, "");
  if (!normalized.startsWith("assets/")) return "";
  return repoRelative(join(webviewStaticRoot, normalized));
}

export function collectHtmlIds(indexHtml = readFileSync(webviewIndexPath, "utf-8")) {
  return sortedUniq([...indexHtml.matchAll(/\bid=["']([^"']+)["']/gi)].map((match) => match[1]));
}

const interactiveHtmlTags = new Set(["button", "input", "select", "textarea", "summary"]);
const interactiveAriaRoles = new Set([
  "button", "link", "checkbox", "radio", "switch", "tab", "menuitem",
  "menuitemcheckbox", "menuitemradio", "option", "treeitem", "gridcell", "row",
]);
const voidHtmlTags = new Set([
  "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
  "param", "source", "track", "wbr",
]);

export function parseHtmlAttributes(raw) {
  const attrs = {};
  const attrRe = /([A-Za-z_:][-A-Za-z0-9_:.]*)\s*(?:=\s*("[^"]*"|'[^']*'|[^\s"'=<>`]+))?/g;
  for (const match of String(raw || "").matchAll(attrRe)) {
    const name = String(match[1] || "").toLowerCase();
    if (!name) continue;
    const value = match[2] === undefined ? "" : String(match[2]).replace(/^["']|["']$/g, "");
    attrs[name] = value;
  }
  return attrs;
}

export function cleanHtmlText(value) {
  return String(value || "")
    .replace(/<script\b[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

export function isInteractiveHtmlElement(tag, attrs = {}) {
  const normalizedTag = String(tag || "").toLowerCase();
  if (interactiveHtmlTags.has(normalizedTag)) return true;
  if (normalizedTag === "a" && Object.hasOwn(attrs, "href")) return true;
  if (interactiveAriaRoles.has(String(attrs.role || "").toLowerCase())) return true;
  if (!Object.hasOwn(attrs, "tabindex")) return false;
  const tabIndex = Number(attrs.tabindex);
  return Number.isInteger(tabIndex) && tabIndex >= 0;
}

function htmlLineAt(source, offset) {
  return source.slice(0, Math.max(0, offset)).split(/\r?\n/).length;
}

function elementInnerMarkup(source, tag, startOffset) {
  if (voidHtmlTags.has(tag)) return "";
  const close = new RegExp(`<\\/${tag}\\s*>`, "ig");
  close.lastIndex = startOffset;
  const match = close.exec(source);
  return match ? source.slice(startOffset, match.index) : "";
}

function selectOptions(innerMarkup) {
  const options = [];
  for (const match of String(innerMarkup || "").matchAll(/<option\b([^>]*)>([\s\S]*?)<\/option>/gi)) {
    const attrs = parseHtmlAttributes(match[1]);
    options.push({
      value: Object.hasOwn(attrs, "value") ? attrs.value : cleanHtmlText(match[2]),
      label: cleanHtmlText(match[2]),
      disabled: Object.hasOwn(attrs, "disabled"),
      selected: Object.hasOwn(attrs, "selected"),
    });
  }
  return options;
}

export function collectHtmlControls(html, { sourcePath = "", surfaceFallback = "app-shell" } = {}) {
  const source = String(html || "");
  const labelsByFor = new Map();
  for (const match of source.matchAll(/<label\b([^>]*)>([\s\S]*?)<\/label>/gi)) {
    const attrs = parseHtmlAttributes(match[1]);
    if (attrs.for) labelsByFor.set(attrs.for, cleanHtmlText(match[2]));
  }

  const controls = [];
  const stack = [];
  const tokenRe = /<!--[\s\S]*?-->|<\/?[A-Za-z][^>]*>/g;
  for (const match of source.matchAll(tokenRe)) {
    const token = match[0];
    if (token.startsWith("<!--")) continue;
    const closing = /^<\//.test(token);
    const tagMatch = token.match(/^<\/?\s*([A-Za-z][\w:-]*)/);
    if (!tagMatch) continue;
    const tag = tagMatch[1].toLowerCase();
    if (closing) {
      for (let index = stack.length - 1; index >= 0; index -= 1) {
        if (stack[index].tag === tag) {
          stack.length = index;
          break;
        }
      }
      continue;
    }

    const rawAttributes = token
      .replace(/^<\s*[A-Za-z][\w:-]*/, "")
      .replace(/\/?>$/, "");
    const attrs = parseHtmlAttributes(rawAttributes);
    const parent = stack.length ? stack[stack.length - 1] : null;
    const offset = match.index || 0;
    const innerMarkup = elementInnerMarkup(source, tag, offset + token.length);
    const wrappingLabel = tag === "label"
      ? cleanHtmlText(innerMarkup)
      : parent?.wrappingLabel || "";
    const surface = attrs["data-page-panel"] || parent?.surface || surfaceFallback;
    const inheritedConditions = parent?.conditions || [];
    const ownConditions = [
      Object.hasOwn(attrs, "hidden") ? "hidden attribute" : "",
      Object.hasOwn(attrs, "disabled") ? "disabled attribute" : "",
      attrs["aria-hidden"] === "true" ? "aria-hidden" : "",
      attrs["aria-disabled"] === "true" ? "aria-disabled" : "",
      /\badvanced-only\b/.test(attrs.class || "") ? "advanced mode" : "",
      /\bsettings-tab-pane\b/.test(attrs.class || "") && !/\bis-active\b/.test(attrs.class || "") ? "inactive tab panel" : "",
      attrs["data-page-panel"] && !/\bis-visible\b/.test(attrs.class || "") ? "inactive page panel" : "",
    ].filter(Boolean);
    const conditions = sortedUniq([...inheritedConditions, ...ownConditions]);

    if (isInteractiveHtmlElement(tag, attrs)) {
      const associatedLabel = attrs.id ? labelsByFor.get(attrs.id) || "" : "";
      const label = cleanHtmlText(
        attrs["aria-label"]
          || associatedLabel
          || parent?.wrappingLabel
          || attrs.title
          || (tag === "input" ? attrs.value || attrs.placeholder || attrs.name : innerMarkup)
          || attrs.placeholder
          || attrs.name
          || attrs.id
      ).slice(0, 240);
      const type = String(attrs.type || (tag === "select" ? "select" : tag === "textarea" ? "textarea" : "")).toLowerCase();
      const finiteValues = tag === "select"
        ? selectOptions(innerMarkup)
        : type === "checkbox"
          ? [{ value: false, label: "unchecked" }, { value: true, label: "checked" }]
          : type === "radio"
            ? [{ value: attrs.value || "on", label: label || attrs.value || "radio option" }]
            : [];
      controls.push({
        tag,
        type,
        role: attrs.role || "",
        id: attrs.id || "",
        source_path: repoRelative(sourcePath || webviewIndexPath),
        source_line: htmlLineAt(source, offset),
        surface,
        label,
        attrs,
        conditions,
        finite_values: finiteValues,
      });
    }

    const selfClosing = /\/>$/.test(token) || voidHtmlTags.has(tag);
    if (!selfClosing) stack.push({ tag, surface, conditions, wrappingLabel });
  }
  return controls;
}

function memberName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "StringLiteral") return node.value;
  return "";
}

function stringLiteralValue(node) {
  if (node?.type === "StringLiteral") return node.value;
  if (node?.type === "TemplateLiteral" && node.expressions.length === 0) return node.quasis[0]?.value?.cooked || "";
  return "";
}

function assignmentToWindowName(node) {
  if (node?.type !== "AssignmentExpression") return "";
  const left = node.left;
  if (left?.type !== "MemberExpression" || left.object?.type !== "Identifier" || left.object.name !== "window") return "";
  return memberName(left.property);
}

function routeFromCall(path) {
  const callee = path.node.callee;
  let name = "";
  if (callee?.type === "Identifier") name = callee.name;
  if (callee?.type === "MemberExpression") name = memberName(callee.property);
  if (!["apiGet", "apiPost", "fetch"].includes(name)) return "";
  const value = stringLiteralValue(path.node.arguments?.[0]);
  return value.startsWith("/api/") ? value : "";
}

function domIdFromCall(path) {
  const callee = path.node.callee;
  let name = "";
  if (callee?.type === "Identifier") name = callee.name;
  if (callee?.type === "MemberExpression") name = memberName(callee.property);
  if (!["byId", "getElementById", "querySelector", "querySelectorAll"].includes(name)) return "";
  const value = stringLiteralValue(path.node.arguments?.[0]);
  if (!value) return "";
  if (name === "querySelector" || name === "querySelectorAll") {
    const match = value.match(/^#([A-Za-z][\w:-]*)$/);
    return match ? match[1] : "";
  }
  return value;
}

function eventFromCall(path) {
  const callee = path.node.callee;
  if (callee?.type !== "MemberExpression" || memberName(callee.property) !== "addEventListener") return "";
  return stringLiteralValue(path.node.arguments?.[0]);
}

export function declarationName(path) {
  const node = path.node;
  if (node.type === "FunctionDeclaration") return node.id?.name || "";
  if (node.type === "VariableDeclaration" && node.declarations.length === 1) {
    const declaration = node.declarations[0];
    if (declaration.id?.type === "Identifier") return declaration.id.name;
  }
  return "";
}

export function isScriptLevelDeclaration(path) {
  if (path.parentPath?.isProgram()) return true;
  return Boolean(
    path.parentPath?.isBlockStatement()
      && path.parentPath.parentPath?.isFunctionExpression()
      && path.parentPath.parentPath.parentPath?.isCallExpression()
      && path.parentPath.parentPath.parentPath.parentPath?.isExpressionStatement()
  );
}

export function parseScript(source, pathForErrors = "script.js") {
  const ast = parse(source, {
    sourceFilename: pathForErrors,
    sourceType: "script",
    errorRecovery: true,
    plugins: ["optionalChaining", "nullishCoalescingOperator"],
  });
  const recoverableErrors = ast.errors || [];
  if (recoverableErrors.length) {
    const details = recoverableErrors
      .map((error) => {
        const location = error.loc ? `${error.loc.line}:${error.loc.column}` : "unknown";
        return `${location} ${error.message}`;
      })
      .join("; ");
    throw new SyntaxError(`Recoverable parser error in ${pathForErrors}: ${details}`);
  }
  return ast;
}

export function analyzeScriptAsset(relativePath) {
  const source = readText(relativePath);
  const ast = parseScript(source, relativePath);
  const topLevelDeclarations = [];
  const windowExports = [];
  const apiRoutes = [];
  const domIds = [];
  const events = [];

  traverse(ast, {
    FunctionDeclaration(path) {
      if (!isScriptLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (name) topLevelDeclarations.push({ name, line: path.node.loc?.start?.line || 1, kind: "function" });
    },
    VariableDeclaration(path) {
      if (!isScriptLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (name) topLevelDeclarations.push({ name, line: path.node.loc?.start?.line || 1, kind: path.node.kind });
    },
    AssignmentExpression(path) {
      windowExports.push(assignmentToWindowName(path.node));
    },
    CallExpression(path) {
      apiRoutes.push(routeFromCall(path));
      domIds.push(domIdFromCall(path));
      events.push(eventFromCall(path));
    },
  });

  const uniqueWindowExports = sortedUniq(windowExports);
  return {
    path: relativePath,
    top_level_declarations: topLevelDeclarations.sort((left, right) => left.line - right.line || left.name.localeCompare(right.name)),
    namespace_exports: uniqueWindowExports.filter((name) => name.startsWith("mediaPipeline")),
    flat_window_exports: uniqueWindowExports.filter((name) => name && !name.startsWith("mediaPipeline")),
    api_routes: sortedUniq(apiRoutes),
    dom_ids_touched: sortedUniq(domIds),
    event_types: sortedUniq(events),
  };
}

function domTargetFromExpression(node, variables) {
  if (!node) return { kind: "", value: "" };
  if (node.type === "Identifier") {
    if (variables.has(node.name)) return { kind: "dom_id", value: variables.get(node.name) };
    if (["document", "window"].includes(node.name)) return { kind: "global", value: node.name };
    return { kind: "variable", value: node.name };
  }
  if (node.type === "CallExpression") {
    const callee = node.callee;
    const name = callee?.type === "Identifier" ? callee.name : callee?.type === "MemberExpression" ? memberName(callee.property) : "";
    const value = stringLiteralValue(node.arguments?.[0]);
    if (["byId", "getElementById"].includes(name) && value) return { kind: "dom_id", value };
    if (["querySelector", "querySelectorAll"].includes(name) && value) return { kind: "selector", value };
  }
  if (node.type === "MemberExpression") return domTargetFromExpression(node.object, variables);
  return { kind: "", value: "" };
}

function eventHandlerName(node, line) {
  if (!node) return `unknown@${line}`;
  if (node.type === "Identifier") return node.name;
  if (node.type === "MemberExpression") return memberName(node.property) || `member@${line}`;
  if (node.type === "CallExpression") {
    const callee = node.callee;
    return callee?.type === "Identifier" ? `${callee.name}()` : `${memberName(callee?.property)}()`;
  }
  if (["ArrowFunctionExpression", "FunctionExpression"].includes(node.type)) return `inline@${line}`;
  return `${node.type || "unknown"}@${line}`;
}

export function collectEventBindings(relativePath) {
  const source = readText(relativePath);
  const ast = parseScript(source, relativePath);
  const variables = new Map();
  traverse(ast, {
    VariableDeclarator(path) {
      const name = path.node.id?.type === "Identifier" ? path.node.id.name : "";
      if (!name) return;
      const target = domTargetFromExpression(path.node.init, variables);
      if (target.kind === "dom_id") variables.set(name, target.value);
    },
  });
  const bindings = [];
  traverse(ast, {
    CallExpression(path) {
      const callee = path.node.callee;
      if (callee?.type !== "MemberExpression" || memberName(callee.property) !== "addEventListener") return;
      const event = stringLiteralValue(path.node.arguments?.[0]);
      if (!event) return;
      const line = path.node.loc?.start?.line || 1;
      bindings.push({
        target: domTargetFromExpression(callee.object, variables),
        event,
        handler: eventHandlerName(path.node.arguments?.[1], line),
        line,
      });
    },
  });
  return bindings.sort((left, right) => left.line - right.line || left.event.localeCompare(right.event));
}

export function writeOrCheckText(outputPath, content, check) {
  const absolute = resolve(repoRoot, outputPath);
  if (check) {
    const current = existsSync(absolute) ? readFileSync(absolute, "utf-8") : "";
    const normalizeLineEndings = (text) => text.replace(/\r\n?/g, "\n");
    if (normalizeLineEndings(current) === normalizeLineEndings(content)) {
      console.log(`${repoRelative(outputPath)} is current`);
      return 0;
    }
    console.error(`${repoRelative(outputPath)} is stale`);
    return 1;
  }
  mkdirSync(dirname(absolute), { recursive: true });
  writeFileSync(absolute, content, "utf-8");
  console.log(`Wrote ${repoRelative(outputPath)}`);
  return 0;
}

export function writeOrCheckJson(outputPath, value, check) {
  return writeOrCheckText(outputPath, `${JSON.stringify(value, null, 2)}\n`, check);
}
