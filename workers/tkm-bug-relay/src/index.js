// Bump this on every deploy-affecting change. It has no functional purpose
// other than letting us confirm from the outside (via /health) that a given
// deploy actually reached the edge, since Worker responses otherwise carry no
// build identifier.
const RELAY_BUILD = "tkm-relay-hardening-v4-2026-10-18";

const MAX_BODY_BYTES = 64 * 1024;
// 5/hour turned out too tight even for one person iterating on this feature,
// let alone a studio with several artists behind the same office IP. Local
// client-side dedupe (see TheKeyMachine's controller.py) already keeps a
// single recurring bug from resubmitting more than once per cooldown window,
// so this is a coarser backstop against actual abuse, not the main defense.
const RATE_LIMIT = 20;
const RATE_WINDOW_SECONDS = 60 * 60;
// The client also uses /status to prune deleted reports from its local
// "sent reports" list in the background every time that menu opens (up to
// _SENT_REPORTS_MAX_ENTRIES worth of checks per open), so this needs enough
// headroom above that count, not just above one-off manual checks.
const STATUS_RATE_LIMIT = 60;
const STATUS_RATE_WINDOW_SECONDS = 60 * 60;
const DEDUPE_TTL_SECONDS = 90 * 24 * 60 * 60;
const TOKEN_TTL_SECONDS = 50 * 60; // GitHub installation tokens last 60 minutes.
const LABEL_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60;
const FREQUENT_OCCURRENCE_THRESHOLD = 10;
const MAX_LOCAL_COUNT = 500;
const STATUS_TITLE_CHARS = 160;
const DEFAULT_REPORT_TYPE = "bug";
const REPORT_TYPES = {
  bug: {
    label: "bug",
    labels: ["bug"],
    titlePrefix: "TKM Bug",
    heading: "What happened",
    contextHeading: "Script error",
    fallbackContext: "No script error supplied.",
  },
  suggestion: {
    label: "suggestion",
    labels: ["suggestion", "enhancement"],
    titlePrefix: "TKM Suggestion",
    heading: "Idea",
    contextHeading: "Related context",
    fallbackContext: "No related context supplied.",
  },
};
const ISSUE_LABELS = {
  bug: {
    color: "d73a4a",
    description: "Something in TheKeyMachine is not working as expected.",
  },
  suggestion: {
    color: "a2eeef",
    description: "A feature idea or workflow improvement for TheKeyMachine.",
  },
  enhancement: {
    color: "a2eeef",
    description: "New feature or request",
  },
  "source:auto-detected": {
    color: "fbca04",
    description: "Created from an exception detected by TheKeyMachine.",
  },
  "source:user-reported": {
    color: "0e8a16",
    description: "Submitted manually from TheKeyMachine.",
  },
  frequent: {
    color: "b60205",
    description: "Reported often enough to need extra attention.",
  },
  regression: {
    color: "5319e7",
    description: "A closed issue happened again and was reopened.",
  },
  "status:reported": {
    color: "d4c5f9",
    description: "Received and awaiting work.",
  },
  "status:worked-on": {
    color: "fbca04",
    description: "Fixed or addressed, pending release.",
  },
  "status:completed": {
    color: "0e8a16",
    description: "Released and complete.",
  },
  "status:cancelled": {
    color: "6e7781",
    description: "Cancelled or not planned.",
  },
};
const AREA_LABEL_COLOR = "c5def5";

const TEXT_LIMITS = {
  name: 50,
  explanation: 1200,
  script_error: 12000,
};

const SYSTEM_FIELDS = [
  "tkm_version",
  "python_version",
  "python_implementation",
  "python_compiler",
  "python_build",
  "qt_version",
  "maya_version",
  "maya_api_version",
  "maya_product",
  "maya_installed_version",
  "maya_operating_system",
  "maya_operating_system_version",
  "maya_ui_language",
  "maya_batch_mode",
  "maya_64bit",
  "maya_cut_identifier",
  "maya_current_unit_time",
  "maya_current_unit_linear",
  "maya_current_unit_angle",
  "platform_system",
  "platform_release",
  "platform_version",
  "platform_platform",
  "platform_machine",
  "platform_architecture",
];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true, service: "tkm-bug-relay", build: RELAY_BUILD });
    }
    if (request.method === "GET" && url.pathname === "/status") {
      return handleStatus(request, env);
    }
    if (request.method !== "POST" || url.pathname !== "/report") {
      return json({ error: "Not found" }, 404);
    }

    try {
      requireConfiguration(env);
      const contentLength = Number(request.headers.get("content-length") || "0");
      if (contentLength > MAX_BODY_BYTES) {
        return json({ error: "Report is too large" }, 413);
      }

      const raw = await request.text();
      if (!raw || new TextEncoder().encode(raw).length > MAX_BODY_BYTES) {
        return json({ error: "Invalid report size" }, 413);
      }

      let input;
      try {
        input = JSON.parse(raw);
      } catch (_error) {
        return json({ error: "Invalid JSON" }, 400);
      }

      const report = sanitizeReport(input);
      if (!report.public_issue_disclosure_shown) {
        return json({ error: "Update TKM before publishing reports to the public issue tracker" }, 409);
      }
      if (!report.explanation) {
        return json({ error: "Explanation is required" }, 400);
      }
      if (!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(report.installation_id)) {
        return json({ error: "Invalid installation identifier" }, 400);
      }

      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      const ipHash = await sha256(`${env.RATE_LIMIT_SALT}:${ip}`);
      const rateKeys = [`rate:ip:${ipHash}`, `rate:install:${report.installation_id}`];
      for (const key of rateKeys) {
        if (!(await consumeRateLimit(env.REPORTS, key))) {
          return json({ error: "Too many reports. Try again later." }, 429);
        }
      }

      const fingerprintSource = normalizeFingerprintSource(
        report.script_error || report.explanation,
      );
      const fingerprint = await sha256(fingerprintSource);
      const exactKey = reportKey(env, report.report_type, fingerprint);
      const clusterKey = clusterKeyFor(
        env,
        report.report_type,
        await sha256(clusterFingerprintSource(fingerprintSource)),
      );
      const useFuzzyCluster = shouldUseFuzzyCluster(report);

      // Exact hash first (cheap, precise); fall back to the fuzzy cluster key
      // so near-identical tracebacks that differ only in message/identifier
      // text still land on the same issue. The cluster key is coarser and can
      // theoretically collide across unrelated bugs, so it is only ever a
      // fallback, never preferred over an exact hit.
      let existing = await env.REPORTS.get(exactKey, { type: "json" });
      if (!existing && useFuzzyCluster) {
        existing = await env.REPORTS.get(clusterKey, { type: "json" });
      }
      const token = await githubInstallationToken(env);
      const versionKey = reportVersionKey(report);
      const increment = clampLocalCount(report.local_count);

      if (existing && existing.issue_number) {
        try {
          const versions = { ...(existing.versions || {}) };
          versions[versionKey] = (versions[versionKey] || 0) + increment;
          const count = Number(existing.count || 1) + increment;
          const { reopened } = await updateOccurrenceCount(
            env,
            token,
            existing.issue_number,
            count,
            versions,
            report,
          );
          const record = JSON.stringify({
            issue_number: existing.issue_number,
            count,
            versions,
            report_type: report.report_type,
          });
          await env.REPORTS.put(exactKey, record, { expirationTtl: DEDUPE_TTL_SECONDS });
          if (useFuzzyCluster) {
            await env.REPORTS.put(clusterKey, record, { expirationTtl: DEDUPE_TTL_SECONDS });
          }
          return json({
            success: true,
            duplicate: true,
            issue_number: existing.issue_number,
            reopened,
          });
        } catch (error) {
          if (!isDeletedGithubIssue(error)) throw error;
          await env.REPORTS.delete(exactKey);
          if (useFuzzyCluster) await env.REPORTS.delete(clusterKey);
        }
      }

      const versions = { [versionKey]: increment };
      const created = await createGithubIssue(env, token, report, fingerprint, versions);
      const record = JSON.stringify({
        issue_number: created.number,
        count: increment,
        versions,
        report_type: report.report_type,
      });
      await env.REPORTS.put(exactKey, record, { expirationTtl: DEDUPE_TTL_SECONDS });
      if (useFuzzyCluster) {
        await env.REPORTS.put(clusterKey, record, { expirationTtl: DEDUPE_TTL_SECONDS });
      }
      return json({
        success: true,
        duplicate: false,
        issue_number: created.number,
      });
    } catch (error) {
      console.error("Bug report relay failed", error);
      return json({ error: "Report delivery failed" }, 502);
    }
  },
};

async function handleStatus(request, env) {
  try {
    requireConfiguration(env);
    const url = new URL(request.url);
    const fingerprint = (url.searchParams.get("fingerprint") || "").toLowerCase();
    if (!/^[a-f0-9]{64}$/.test(fingerprint)) {
      return json({ error: "Invalid fingerprint" }, 400);
    }

    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const ipHash = await sha256(`${env.RATE_LIMIT_SALT}:${ip}`);
    const allowed = await consumeRateLimit(
      env.REPORTS,
      `rate:status:ip:${ipHash}`,
      STATUS_RATE_LIMIT,
      STATUS_RATE_WINDOW_SECONDS,
    );
    if (!allowed) {
      return json({ error: "Too many status checks. Try again later." }, 429);
    }

    const reportType = normalizeReportType(url.searchParams.get("report_type"));
    const exactKey = reportKey(env, reportType, fingerprint);
    const record = await env.REPORTS.get(exactKey, { type: "json" });
    if (!record || !record.issue_number) {
      return json({ found: false });
    }

    const token = await githubInstallationToken(env);
    let issue;
    try {
      issue = await githubFetch(env, token, `/issues/${record.issue_number}`);
    } catch (error) {
      if (isDeletedGithubIssue(error)) {
        // The issue was deleted on GitHub -- stop pointing future duplicates
        // of this exact fingerprint at a dead issue number. (The fuzzy
        // cluster key, if any, is left to expire on its own TTL: its hash
        // isn't derivable from the fingerprint we were given here.)
        await env.REPORTS.delete(exactKey);
        return json({ found: false, deleted: true });
      }
      throw error;
    }
    return json(
      buildStatusResponse(record, issue),
    );
  } catch (error) {
    console.error("Bug report status check failed", error);
    return json({ error: "Status check failed" }, 502);
  }
}

// Pure so it's unit-testable without a live KV/GitHub round trip: given the
// KV record for a fingerprint and the issue's current state from GitHub,
// shape the response the client actually consumes.
export function buildStatusResponse(record, issue) {
  issue = issue && typeof issue === "object" ? issue : { state: issue };
  return {
    found: true,
    issue_number: record.issue_number,
    count: Number(record.count || 1),
    // GitHub's comment count is monotonic for ordinary ticket discussion and
    // lets the Maya client persist a tiny per-ticket cursor instead of
    // downloading comment contents.
    update_count: Math.max(0, Number(issue.comments || 0)),
    issue_title: String(issue.title || "").slice(0, STATUS_TITLE_CHARS),
    ticket_status: ticketStatus(issue),
    versions: record.versions || {},
    report_type: normalizeReportType(record.report_type),
    state: issue.state === "closed" ? "closed" : "open",
  };
}

export function ticketStatus(issue) {
  issue = issue && typeof issue === "object" ? issue : {};
  if (issue.state === "closed") {
    return issue.state_reason === "not_planned" ? "cancelled" : "completed";
  }
  const labels = (issue.labels || []).map((label) =>
    String(typeof label === "string" ? label : label && label.name || "").toLowerCase(),
  );
  const workingLabels = new Set([
    "in progress",
    "in-progress",
    "status:in progress",
    "status:in-progress",
    "working on it",
    "status:worked-on",
  ]);
  if (labels.includes("status:cancelled")) return "cancelled";
  if (labels.includes("status:completed")) return "completed";
  if ((issue.assignees || []).length || labels.some((label) => workingLabels.has(label))) {
    return "being_worked_on";
  }
  return "open";
}

function requireConfiguration(env) {
  const required = [
    "GITHUB_APP_ID",
    "GITHUB_INSTALLATION_ID",
    "GITHUB_PRIVATE_KEY",
    "GITHUB_OWNER",
    "GITHUB_REPO",
    "RATE_LIMIT_SALT",
    "REPORTS",
  ];
  for (const key of required) {
    if (!env[key]) throw new Error(`Missing ${key}`);
  }
}

export function sanitizeReport(input) {
  input = input && typeof input === "object" ? input : {};
  const report = {
    installation_id: cleanText(input.installation_id, 40),
    public_issue_disclosure_shown: input.public_issue_disclosure_shown === true,
    name: cleanText(input.name, TEXT_LIMITS.name),
    explanation: cleanText(input.explanation, TEXT_LIMITS.explanation),
    script_error: cleanText(input.script_error, TEXT_LIMITS.script_error),
    report_type: normalizeReportType(input.report_type),
    local_count: clampLocalCount(input && input.local_count),
    system: {},
  };
  const system = input.system && typeof input.system === "object" ? input.system : {};
  for (const key of SYSTEM_FIELDS) {
    const value = cleanText(system[key], 500);
    if (value) report.system[key] = value;
  }
  return report;
}

export function normalizeReportType(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return Object.prototype.hasOwnProperty.call(REPORT_TYPES, normalized)
    ? normalized
    : DEFAULT_REPORT_TYPE;
}

function reportTypeMeta(reportOrType) {
  const reportType = typeof reportOrType === "string"
    ? normalizeReportType(reportOrType)
    : normalizeReportType(reportOrType && reportOrType.report_type);
  return REPORT_TYPES[reportType];
}

export function clampLocalCount(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.min(Math.floor(n), MAX_LOCAL_COUNT);
}

function cleanText(value, limit) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
    .replace(/@/g, "@\u200b")
    .slice(0, limit)
    .trim();
}

export function normalizeFingerprintSource(value) {
  return String(value || "unknown")
    .toLowerCase()
    .replace(/(?:[a-z]:)?[\\/](?:[^\s:\n]+[\\/])+[^\s:\n]+/gi, "<path>")
    .replace(/line \d+/gi, "line <n>")
    .replace(/0x[0-9a-f]+/gi, "<address>")
    .replace(/\b\d+\b/g, "<n>")
    .replace(/\s+/g, " ")
    .slice(0, 8000);
}

// A coarser, fuzzier key than the exact fingerprint: strips quoted literals
// (identifier/message text that legitimately varies between otherwise
// identical errors) and keeps only the leading significant tokens. Two
// tracebacks that differ solely in a variable name or message string collapse
// onto the same cluster key even though their exact fingerprints differ.
export function clusterFingerprintSource(normalizedValue) {
  return String(normalizedValue || "")
    .replace(/["'`][^"'`]*["'`]/g, " ")
    .split(/[^a-z0-9<>]+/)
    .filter((token) => token.length > 2)
    .slice(0, 16)
    .join(" ");
}

export function reportVersionKey(report) {
  const system = (report && report.system) || {};
  const tkm = versionKeyPart(system.tkm_version);
  const maya = versionKeyPart(system.maya_version);
  return `${tkm}|${maya}`;
}

function versionKeyPart(value) {
  return String(value || "unknown").replace(/[|\r\n]+/g, " ").trim().slice(0, 100) || "unknown";
}

function escapeMarkdown(value) {
  return String(value || "").replace(/([\\`*_{}\[\]()<>#+!|>~])/g, "\\$1");
}

export function shouldUseFuzzyCluster(report) {
  return report.report_type === "bug" && Boolean(report.script_error);
}

export function versionsBlock(versions) {
  const entries = Object.entries(versions || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return "_No version data yet._";
  const lines = entries.map(([key, count]) => {
    const [tkm, maya] = key.split("|");
    return `- TKM ${escapeMarkdown(tkm)} / Maya ${escapeMarkdown(maya)}: **${count}**`;
  });
  return ["**Seen on:**", ...lines].join("\n");
}

export function guessComponentLabel(scriptError) {
  const match = /TheKeyMachine[\\/](tools|core|ui)[\\/]([a-zA-Z0-9_]+)/i.exec(scriptError || "");
  if (!match) return null;
  return `area:${match[2].toLowerCase()}`;
}

export function isAutoDetected(explanation) {
  return /auto-detected exception/i.test(explanation || "");
}

async function consumeRateLimit(kv, key, limit = RATE_LIMIT, windowSeconds = RATE_WINDOW_SECONDS) {
  const current = Number((await kv.get(key)) || "0");
  if (current >= limit) return false;
  await kv.put(key, String(current + 1), { expirationTtl: windowSeconds });
  return true;
}

async function createGithubIssue(env, token, report, fingerprint, versions) {
  const labels = issueLabels(report);
  await ensureGithubLabels(env, token, labels);

  const response = await githubFetch(env, token, "/issues", {
    method: "POST",
    body: JSON.stringify({
      title: issueTitle(report),
      body: issueBody(report, fingerprint, versions),
      labels,
    }),
  });
  return response;
}

export function issueLabels(report) {
  const labels = [];
  const component = guessComponentLabel(report.script_error);
  if (component) labels.push(component);
  labels.push(...reportTypeMeta(report).labels);
  labels.push(isAutoDetected(report.explanation) ? "source:auto-detected" : "source:user-reported");
  labels.push("status:reported");
  return labels;
}

async function updateOccurrenceCount(env, token, issueNumber, count, versions, report) {
  const issue = await githubFetch(env, token, `/issues/${issueNumber}`);
  let body = String(issue.body || "").replace(
    /Occurrences: \*\*\d+\*\*/,
    `Occurrences: **${count}**`,
  );
  const block = `<!-- tkm-versions:start -->\n${versionsBlock(versions)}\n<!-- tkm-versions:end -->`;
  if (/<!-- tkm-versions:start -->[\s\S]*?<!-- tkm-versions:end -->/.test(body)) {
    body = body.replace(/<!-- tkm-versions:start -->[\s\S]*?<!-- tkm-versions:end -->/, block);
  } else {
    // Older issues created before version tracking existed: append the block.
    body = body.replace(/(Occurrences: \*\*\d+\*\*)/, `$1\n\n${block}`);
  }

  const wasClosed = issue.state === "closed";
  const labels = new Set(
    (issue.labels || []).map((label) => (typeof label === "string" ? label : label.name)),
  );
  for (const label of reportTypeMeta(report).labels) labels.add(label);
  if (wasClosed) labels.add("regression");
  if (count >= FREQUENT_OCCURRENCE_THRESHOLD) labels.add("frequent");
  await ensureGithubLabels(env, token, Array.from(labels));

  // Don't touch the title here: this runs on every duplicate/occurrence,
  // and a fuzzy cluster match can carry a different first line than the
  // original report. Overwriting the title would rename the original issue
  // to whatever the newest duplicate happens to say.
  const patch = { body, labels: Array.from(labels) };
  if (wasClosed) {
    patch.state = "open";
    patch.state_reason = "reopened";
  }
  await githubFetch(env, token, `/issues/${issueNumber}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

  if (wasClosed) {
    const [tkm, maya] = reportVersionKey(report).split("|");
    await githubFetch(env, token, `/issues/${issueNumber}/comments`, {
      method: "POST",
      body: JSON.stringify({
        body: `Recurred on TKM ${escapeMarkdown(tkm)} / Maya ${escapeMarkdown(maya)} after this was closed (occurrence ${count}). Reopening as a regression.`,
      }),
    });
  }

  return { reopened: wasClosed };
}

export function issueTitle(report) {
  const firstLine = report.explanation.split(/\r?\n/, 1)[0].replace(/^#+\s*/, "");
  return `[${reportTypeMeta(report).titlePrefix}] ${(firstLine || "Unnamed report").slice(0, 100)}`;
}

export function issueBody(report, fingerprint, versions) {
  const systemLines = Object.entries(report.system)
    .map(([key, value]) => `- **${key}:** ${escapeMarkdown(value.replace(/\n/g, " "))}`)
    .join("\n");
  const meta = reportTypeMeta(report);
  const safeError = (report.script_error || meta.fallbackContext).replace(/```/g, "''' ");
  const totalOccurrences =
    Object.values(versions || {}).reduce((sum, n) => sum + n, 0) || 1;
  return [
    "<!-- tkm-toolbar-bug-report -->",
    `<!-- fingerprint:${fingerprint} -->`,
    `Occurrences: **${totalOccurrences}**`,
    "",
    "<!-- tkm-versions:start -->",
    versionsBlock(versions),
    "<!-- tkm-versions:end -->",
    "",
    "## Reporter",
    escapeMarkdown(report.name || "Anonymous"),
    "",
    `Type: **${meta.titlePrefix}**`,
    "",
    `## ${meta.heading}`,
    escapeMarkdown(report.explanation),
    "",
    `## ${meta.contextHeading}`,
    "```text",
    safeError,
    "```",
    "",
    "## System details",
    systemLines || "No system details supplied.",
  ].join("\n");
}

function repositoryKeyPrefix(env) {
  return `repo:${String(env.GITHUB_OWNER).toLowerCase()}/${String(env.GITHUB_REPO).toLowerCase()}`;
}

function reportKey(env, reportType, fingerprint) {
  return `${repositoryKeyPrefix(env)}:report:${normalizeReportType(reportType)}:${fingerprint}`;
}

function clusterKeyFor(env, reportType, clusterFingerprint) {
  return `${repositoryKeyPrefix(env)}:cluster:${normalizeReportType(reportType)}:${clusterFingerprint}`;
}

function isDeletedGithubIssue(error) {
  return error && (error.status === 404 || error.status === 410);
}

export async function ensureGithubLabels(env, token, labels) {
  const uniqueLabels = Array.from(new Set(labels || [])).filter(Boolean);
  for (const name of uniqueLabels) {
    const definition = ISSUE_LABELS[name] || (
      name.startsWith("area:")
        ? {
            color: AREA_LABEL_COLOR,
            description: `Reports related to ${name.slice("area:".length)}.`,
          }
        : null
    );
    if (!definition) continue;
    await ensureGithubLabel(env, token, name, definition);
  }
}

async function ensureGithubLabel(env, token, name, definition) {
  const cacheKey = `${repositoryKeyPrefix(env)}:gh:label:${name}`;
  if (await env.REPORTS.get(cacheKey)) return;
  try {
    await githubFetch(env, token, "/labels", {
      method: "POST",
      body: JSON.stringify({
        name,
        color: definition.color,
        description: definition.description,
      }),
    });
    await env.REPORTS.put(cacheKey, "1", { expirationTtl: LABEL_CACHE_TTL_SECONDS });
  } catch (error) {
    if (error && error.status === 422) {
      await env.REPORTS.put(cacheKey, "1", { expirationTtl: LABEL_CACHE_TTL_SECONDS });
      return;
    }
    throw error;
  }
}

async function githubFetch(env, token, path, options = {}) {
  const response = await fetch(
    `https://api.github.com/repos/${encodeURIComponent(env.GITHUB_OWNER)}/${encodeURIComponent(env.GITHUB_REPO)}${path}`,
    {
      ...options,
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": "tkm-bug-relay",
        "X-GitHub-Api-Version": "2022-11-28",
        ...(options.headers || {}),
      },
    },
  );
  if (!response.ok) {
    const error = new Error(`GitHub API ${response.status}: ${await response.text()}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function githubInstallationToken(env) {
  // Installation tokens are valid for an hour; caching avoids a JWT sign plus
  // a GitHub API round trip on every single request, including duplicates
  // (the common case once a bug has an open issue).
  const cacheKey = `${repositoryKeyPrefix(env)}:gh:installation-token:${env.GITHUB_INSTALLATION_ID}`;
  const cached = await env.REPORTS.get(cacheKey, { type: "json" });
  if (cached && cached.token && Number(cached.expires_at) > Date.now()) {
    return cached.token;
  }

  const jwt = await githubAppJwt(env.GITHUB_APP_ID, env.GITHUB_PRIVATE_KEY);
  const response = await fetch(
    `https://api.github.com/app/installations/${env.GITHUB_INSTALLATION_ID}/access_tokens`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${jwt}`,
        "User-Agent": "tkm-bug-relay",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    },
  );
  if (!response.ok) {
    throw new Error(`GitHub token ${response.status}: ${await response.text()}`);
  }
  const body = await response.json();
  await env.REPORTS.put(
    cacheKey,
    JSON.stringify({ token: body.token, expires_at: Date.now() + TOKEN_TTL_SECONDS * 1000 }),
    { expirationTtl: TOKEN_TTL_SECONDS },
  );
  return body.token;
}

async function githubAppJwt(appId, pem) {
  const now = Math.floor(Date.now() / 1000);
  const header = base64Url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = base64Url(JSON.stringify({ iat: now - 60, exp: now + 540, iss: appId }));
  const unsigned = `${header}.${payload}`;
  const keyData = pemToBytes(pem);
  const key = await crypto.subtle.importKey(
    "pkcs8",
    keyData,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(unsigned),
  );
  return `${unsigned}.${base64UrlBytes(new Uint8Array(signature))}`;
}

function pemToBytes(pem) {
  const base64 = String(pem)
    .replace(/-----BEGIN PRIVATE KEY-----/, "")
    .replace(/-----END PRIVATE KEY-----/, "")
    .replace(/\s+/g, "");
  const binary = atob(base64);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function base64Url(value) {
  return base64UrlBytes(new TextEncoder().encode(value));
}

function base64UrlBytes(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function json(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
