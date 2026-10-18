import assert from "node:assert/strict";
import test from "node:test";

import worker, {
  buildStatusResponse,
  clampLocalCount,
  clusterFingerprintSource,
  ensureGithubLabels,
  guessComponentLabel,
  isAutoDetected,
  issueBody,
  issueLabels,
  issueTitle,
  normalizeReportType,
  ticketStatus,
  normalizeFingerprintSource,
  reportVersionKey,
  sanitizeReport,
  versionsBlock,
} from "../src/index.js";

test("health endpoint does not require credentials", async () => {
  const response = await worker.fetch(
    new Request("https://relay.example/health"),
    {},
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.ok, true);
  assert.equal(body.service, "tkm-bug-relay");
  assert.equal(typeof body.build, "string");
});

test("report text is bounded, mentions are neutralized, and unknown fields are dropped", () => {
  const report = sanitizeReport({
    installation_id: "12345678-1234-1234-1234-123456789abc",
    name: "@maintainer",
    explanation: "A".repeat(1400),
    script_error: "trace",
    report_type: "suggestion",
    system: { maya_version: "2026", secret: "do not copy" },
  });

  assert.equal(report.name, "@\u200bmaintainer");
  assert.equal(report.explanation.length, 1200);
  assert.equal(report.report_type, "suggestion");
  assert.equal(report.public_issue_disclosure_shown, false);
  assert.deepEqual(report.system, { maya_version: "2026" });
});

test("report type accepts only the supported ticket types", () => {
  assert.equal(normalizeReportType("bug"), "bug");
  assert.equal(normalizeReportType("Suggestion"), "suggestion");
  assert.equal(normalizeReportType("feature"), "bug");
  assert.equal(normalizeReportType(undefined), "bug");
});

test("report endpoint refuses clients that still describe submissions as private", async () => {
  const response = await worker.fetch(
    new Request("https://relay.example/report", {
      method: "POST",
      body: JSON.stringify({
        installation_id: "12345678-1234-1234-1234-123456789abc",
        explanation: "Should not become public without updated disclosure",
      }),
    }),
    {
      GITHUB_APP_ID: "1",
      GITHUB_INSTALLATION_ID: "1",
      GITHUB_PRIVATE_KEY: "key",
      GITHUB_OWNER: "owner",
      GITHUB_REPO: "repo",
      RATE_LIMIT_SALT: "salt",
      REPORTS: createMockKv(),
    },
  );
  assert.equal(response.status, 409);
  assert.match((await response.json()).error, /public issue tracker/);
});

test("fingerprints ignore volatile paths, line numbers, addresses, and numbers", () => {
  const first = normalizeFingerprintSource(
    "File /Users/alice/TKM/tool.py line 17 at 0xABC123 value 42",
  );
  const second = normalizeFingerprintSource(
    "File /Users/bob/TKM/tool.py line 99 at 0xFFEEDD value 71",
  );
  assert.equal(first, second);
});

test("bug issue formatting includes type prefix and toolbar-report metadata", () => {
  const report = sanitizeReport({
    installation_id: "12345678-1234-1234-1234-123456789abc",
    explanation: "Playback fails\nSecond line",
    script_error: "RuntimeError",
    system: { maya_version: "2026" },
  });
  assert.equal(issueTitle(report), "[TKM Bug] Playback fails");
  const body = issueBody(report, "abc123", { "0.1.99|2026": 1 });
  assert.match(body, /tkm-toolbar-bug-report/);
  assert.match(body, /Occurrences: \*\*1\*\*/);
  assert.match(body, /fingerprint:abc123/);
  assert.match(body, /maya_version/);
  assert.match(body, /TKM 0\.1\.99 \/ Maya 2026/);
  assert.deepEqual(issueLabels(report), ["bug", "source:user-reported", "status:reported"]);
});

test("suggestions get suggestion title prefix, body headings, and type metadata", () => {
  const report = sanitizeReport({
    installation_id: "12345678-1234-1234-1234-123456789abc",
    explanation: "Make onion skin colors configurable",
    script_error: "",
    report_type: "suggestion",
    system: { maya_version: "2026" },
  });
  assert.equal(issueTitle(report), "[TKM Suggestion] Make onion skin colors configurable");
  const body = issueBody(report, "abc123", { "0.1.99|2026": 1 });
  assert.match(body, /Type: \*\*TKM Suggestion\*\*/);
  assert.match(body, /## Idea/);
  assert.match(body, /## Related context/);
  assert.deepEqual(issueLabels(report), [
    "suggestion",
    "enhancement",
    "source:user-reported",
    "status:reported",
  ]);
});

test("auto-detected component labels are included with the type labels", () => {
  const report = sanitizeReport({
    installation_id: "12345678-1234-1234-1234-123456789abc",
    explanation: "Auto-detected exception in Onion Skin",
    script_error: 'File "/Users/alice/TheKeyMachine/tools/onion_skin/controller.py", line 9',
  });
  assert.deepEqual(issueLabels(report), [
    "area:onion_skin",
    "bug",
    "source:auto-detected",
    "status:reported",
  ]);
});

test("label self-healing creates each known label once and caches it", async () => {
  const kv = createMockKv();
  const createdLabels = [];
  const originalFetch = global.fetch;
  global.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    createdLabels.push(body.name);
    return new Response(JSON.stringify({ name: body.name }), { status: 201 });
  };

  try {
    await ensureGithubLabels(
      {
        GITHUB_OWNER: "owner",
        GITHUB_REPO: "repo",
        REPORTS: kv,
      },
      "fake-token",
      ["suggestion", "enhancement", "source:user-reported", "suggestion"],
    );
    await ensureGithubLabels(
      {
        GITHUB_OWNER: "owner",
        GITHUB_REPO: "repo",
        REPORTS: kv,
      },
      "fake-token",
      ["suggestion", "enhancement", "source:user-reported"],
    );
    assert.deepEqual(createdLabels, ["suggestion", "enhancement", "source:user-reported"]);
  } finally {
    global.fetch = originalFetch;
  }
});

test("local_count is clamped to a sane positive range", () => {
  assert.equal(clampLocalCount(undefined), 1);
  assert.equal(clampLocalCount(0), 1);
  assert.equal(clampLocalCount(-5), 1);
  assert.equal(clampLocalCount(12.7), 12);
  assert.equal(clampLocalCount(99999), 500);

  const report = sanitizeReport({
    installation_id: "12345678-1234-1234-1234-123456789abc",
    explanation: "Playback fails",
    local_count: 4.9,
  });
  assert.equal(report.local_count, 4);
});

test("cluster fingerprint drops quoted literals so near-identical errors match", () => {
  const first = clusterFingerprintSource(
    normalizeFingerprintSource("KeyError: 'left_ctrl' not found in namespace 'rig_v2'"),
  );
  const second = clusterFingerprintSource(
    normalizeFingerprintSource("KeyError: 'right_ctrl' not found in namespace 'rig_v3'"),
  );
  assert.equal(first, second);
});

test("cluster fingerprint still differs across unrelated exception types", () => {
  const keyError = clusterFingerprintSource(normalizeFingerprintSource("KeyError: 'foo'"));
  const typeError = clusterFingerprintSource(
    normalizeFingerprintSource("TypeError: expected str, got NoneType"),
  );
  assert.notEqual(keyError, typeError);
});

test("version key groups occurrences by TKM + Maya version", () => {
  const report = sanitizeReport({
    installation_id: "12345678-1234-1234-1234-123456789abc",
    explanation: "x",
    system: { tkm_version: "0.1.99", maya_version: "2026" },
  });
  assert.equal(reportVersionKey(report), "0.1.99|2026");
});

test("versions block renders a sorted, human-readable table", () => {
  const block = versionsBlock({ "0.1.98|2025": 2, "0.1.99|2026": 5 });
  assert.match(block, /\*\*Seen on:\*\*/);
  assert.ok(block.indexOf("0.1.99") < block.indexOf("0.1.98"));
});

test("component label is guessed from a TheKeyMachine source path", () => {
  const scriptError = 'File "/Users/alice/maya/scripts/TheKeyMachine/tools/onion_skin/controller.py", line 12';
  assert.equal(guessComponentLabel(scriptError), "area:onion_skin");
  assert.equal(guessComponentLabel("no path here"), null);
});

test("auto-detected explanations are distinguished from user-written ones", () => {
  assert.equal(isAutoDetected("Auto-detected exception in tool X.\n\nPlease describe..."), true);
  assert.equal(isAutoDetected("The playback range resets when I do this"), false);
});

test("status response normalizes GitHub issue state and carries KV data through", () => {
  const record = { issue_number: 12, count: 4, versions: { "0.1.99|2026": 4 } };
  assert.deepEqual(
    buildStatusResponse(
      record,
      { state: "open", comments: 5, title: "Graph Editor crash" },
    ),
    {
    found: true,
    issue_number: 12,
    count: 4,
    update_count: 5,
    issue_title: "Graph Editor crash",
    ticket_status: "open",
    versions: { "0.1.99|2026": 4 },
    report_type: "bug",
    state: "open",
    },
  );
  assert.equal(buildStatusResponse(record, { state: "closed" }).state, "closed");
  assert.equal(buildStatusResponse(record, { state: "closed" }).update_count, 0);
  // Keep the old helper call shape working for older integrations/tests.
  assert.equal(buildStatusResponse(record, "closed").state, "closed");
});

test("ticket status exposes only useful user-facing workflow states", () => {
  assert.equal(ticketStatus({ state: "open" }), "open");
  assert.equal(ticketStatus({ state: "open", assignees: [{}] }), "being_worked_on");
  assert.equal(ticketStatus({ state: "open", labels: [{ name: "in progress" }] }), "being_worked_on");
  assert.equal(ticketStatus({ state: "open", labels: ["status:worked-on"] }), "being_worked_on");
  assert.equal(ticketStatus({ state: "open", labels: ["status:completed"] }), "completed");
  assert.equal(ticketStatus({ state: "open", labels: ["status:cancelled"] }), "cancelled");
  assert.equal(ticketStatus({ state: "closed", state_reason: "completed" }), "completed");
  assert.equal(ticketStatus({ state: "closed", state_reason: "not_planned" }), "cancelled");
});

test("status endpoint rejects a malformed fingerprint before touching KV", async () => {
  const response = await worker.fetch(
    new Request("https://relay.example/status?fingerprint=not-a-hash"),
    {
      GITHUB_APP_ID: "1",
      GITHUB_INSTALLATION_ID: "1",
      GITHUB_PRIVATE_KEY: "key",
      GITHUB_OWNER: "owner",
      GITHUB_REPO: "repo",
      RATE_LIMIT_SALT: "salt",
      REPORTS: { get: async () => null, put: async () => {} },
    },
  );
  assert.equal(response.status, 400);
});

function createMockKv(initial = {}) {
  const store = new Map(Object.entries(initial));
  return {
    store,
    async get(key, options) {
      if (!store.has(key)) return null;
      const value = store.get(key);
      return options && options.type === "json" ? JSON.parse(value) : value;
    },
    async put(key, value) {
      store.set(key, value);
    },
    async delete(key) {
      store.delete(key);
    },
  };
}

test("status endpoint treats a 404 from GitHub as a deleted issue and clears its KV record", async () => {
  const fingerprint = "a".repeat(64);
  const kv = createMockKv({
    [`repo:owner/repo:report:bug:${fingerprint}`]: JSON.stringify({ issue_number: 99, count: 2, versions: {} }),
    // Pre-seed a still-valid cached installation token so this test only
    // has to mock the GitHub issue lookup, not the JWT-signing token mint.
    "repo:owner/repo:gh:installation-token:1": JSON.stringify({
      token: "fake-token",
      expires_at: Date.now() + 60 * 60 * 1000,
    }),
  });

  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    if (String(url).includes("/issues/99")) {
      return new Response("Not Found", { status: 404 });
    }
    throw new Error("unexpected fetch: " + url);
  };

  try {
    const response = await worker.fetch(
      new Request(`https://relay.example/status?fingerprint=${fingerprint}`),
      {
        GITHUB_APP_ID: "1",
        GITHUB_INSTALLATION_ID: "1",
        GITHUB_PRIVATE_KEY: "-----BEGIN PRIVATE KEY-----\nAA==\n-----END PRIVATE KEY-----",
        GITHUB_OWNER: "owner",
        GITHUB_REPO: "repo",
        RATE_LIMIT_SALT: "salt",
        REPORTS: kv,
      },
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { found: false, deleted: true });
    assert.equal(kv.store.has(`repo:owner/repo:report:bug:${fingerprint}`), false);
  } finally {
    global.fetch = originalFetch;
  }
});

test("status endpoint treats a 410 from GitHub as a deleted issue and clears its KV record", async () => {
  const fingerprint = "b".repeat(64);
  const kv = createMockKv({
    [`repo:owner/repo:report:bug:${fingerprint}`]: JSON.stringify({ issue_number: 77, count: 2, versions: {} }),
    "repo:owner/repo:gh:installation-token:1": JSON.stringify({
      token: "fake-token",
      expires_at: Date.now() + 60 * 60 * 1000,
    }),
  });

  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    if (String(url).includes("/issues/77")) {
      return new Response(JSON.stringify({ message: "This issue was deleted" }), { status: 410 });
    }
    throw new Error("unexpected fetch: " + url);
  };

  try {
    const response = await worker.fetch(
      new Request(`https://relay.example/status?fingerprint=${fingerprint}`),
      {
        GITHUB_APP_ID: "1",
        GITHUB_INSTALLATION_ID: "1",
        GITHUB_PRIVATE_KEY: "-----BEGIN PRIVATE KEY-----\nAA==\n-----END PRIVATE KEY-----",
        GITHUB_OWNER: "owner",
        GITHUB_REPO: "repo",
        RATE_LIMIT_SALT: "salt",
        REPORTS: kv,
      },
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { found: false, deleted: true });
    assert.equal(kv.store.has(`repo:owner/repo:report:bug:${fingerprint}`), false);
  } finally {
    global.fetch = originalFetch;
  }
});

test("report submission recreates an issue when a stale duplicate points to a deleted GitHub issue", async () => {
  const kv = createMockKv({
    "repo:owner/repo:gh:installation-token:1": JSON.stringify({
      token: "fake-token",
      expires_at: Date.now() + 60 * 60 * 1000,
    }),
  });
  const explanation = "Previously deleted report";
  const normalized = normalizeFingerprintSource(explanation);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalized));
  const fingerprint = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  kv.store.set(`repo:owner/repo:report:bug:${fingerprint}`, JSON.stringify({ issue_number: 66, count: 1, versions: {} }));

  const originalFetch = global.fetch;
  global.fetch = async (url, options = {}) => {
    const path = String(url);
    if (path.includes("/issues/66")) {
      return new Response(JSON.stringify({ message: "This issue was deleted" }), { status: 410 });
    }
    if (path.endsWith("/labels")) {
      const body = JSON.parse(options.body);
      return new Response(JSON.stringify({ name: body.name }), { status: 201 });
    }
    if (path.endsWith("/issues") && options.method === "POST") {
      return new Response(JSON.stringify({ number: 67 }), { status: 201 });
    }
    throw new Error("unexpected fetch: " + path);
  };

  try {
    const response = await worker.fetch(
      new Request("https://relay.example/report", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "CF-Connecting-IP": "127.0.0.1",
        },
        body: JSON.stringify({
          installation_id: "12345678-1234-1234-1234-123456789abc",
          public_issue_disclosure_shown: true,
          explanation,
          report_type: "bug",
        }),
      }),
      {
        GITHUB_APP_ID: "1",
        GITHUB_INSTALLATION_ID: "1",
        GITHUB_PRIVATE_KEY: "-----BEGIN PRIVATE KEY-----\nAA==\n-----END PRIVATE KEY-----",
        GITHUB_OWNER: "owner",
        GITHUB_REPO: "repo",
        RATE_LIMIT_SALT: "salt",
        REPORTS: kv,
      },
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      success: true,
      duplicate: false,
      issue_number: 67,
    });
  } finally {
    global.fetch = originalFetch;
  }
});
