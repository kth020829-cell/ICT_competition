import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("shared API client covers supplied student endpoints", async () => {
  const services = await readFile(new URL("lib/api/services.ts", root), "utf8");
  for (const endpoint of ["/auth/student", "/home", "/sessions", "/before", "/after", "/result", "/reward", "/collection", "/missions/today", "/complete?session_id="]) {
    assert.equal(services.includes(endpoint), true, `missing endpoint ${endpoint}`);
  }
  assert.match(services, /studentToken/);
  const client = await readFile(new URL("lib/api/client.ts", root), "utf8");
  assert.match(client, /student-token/);
});

test("shared API client covers teacher login, dashboard, code, and lock", async () => {
  const [services, contracts] = await Promise.all([
    readFile(new URL("lib/api/services.ts", root), "utf8"),
    readFile(new URL("lib/api/contracts.ts", root), "utf8"),
  ]);
  assert.match(services, /apiRequest\("\/teacher"/);
  assert.match(services, /\/teacher\/classes/);
  assert.match(services, /\/code/);
  assert.match(services, /\/lock/);
  assert.match(contracts, /goalCurrent/);
  assert.match(contracts, /studentCount/);
});

test("live analysis includes polling, adapters, and session persistence", async () => {
  const [workflow, adapter, session] = await Promise.all([
    readFile(new URL("lib/api/workflows.ts", root), "utf8"),
    readFile(new URL("lib/api/adapters.ts", root), "utf8"),
    readFile(new URL("lib/api/session.ts", root), "utf8"),
  ]);
  assert.match(workflow, /pollAnalysis/);
  assert.match(workflow, /analysisTimeoutMs/);
  assert.match(adapter, /toScanAnalysis/);
  assert.match(adapter, /REMOVE_LABEL/);
  assert.match(session, /sessionStorage/);
  assert.match(session, /studentToken/);
});
