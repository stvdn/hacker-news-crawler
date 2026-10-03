import assert from "node:assert/strict";
import { test } from "node:test";

import {
  categorizeFailure,
  failureMessage,
  logEntriesFailure,
  requestIdFrom,
} from "../src/features/hacker-news/entry-errors.ts";

test("classifies failures at the server fetch boundary", () => {
  assert.equal(categorizeFailure("request", new DOMException("expired", "TimeoutError")), "timeout");
  assert.equal(categorizeFailure("request", new TypeError("connection refused")), "network");
  assert.equal(categorizeFailure("configuration", new TypeError("invalid URL")), "configuration");
  assert.equal(categorizeFailure("response", new SyntaxError("invalid JSON")), "invalid_response");
  assert.equal(categorizeFailure("request", new Error("unexpected")), "unexpected");

  assert.match(failureMessage("timeout"), /too long/);
  assert.match(failureMessage("invalid_response"), /unexpected response/);
});

test("logs a failure category and safe request ID without response contents", () => {
  const id = "b737af75-681b-4597-b84f-e359e396d3c2";
  const response = new Response(null, { headers: { "X-Request-ID": id } });
  assert.equal(requestIdFrom(response), id);
  assert.equal(requestIdFrom(new Response(null, { headers: { "X-Request-ID": "invalid" } })), undefined);

  const entries = [];
  const original = console.error;
  console.error = (value) => { entries.push(value); };
  try {
    logEntriesFailure("short", "api_error", id, 503);
    logEntriesFailure("all", "network");
  } finally {
    console.error = original;
  }
  assert.deepEqual(entries.map((entry) => JSON.parse(entry)), [
    {
      event: "entries_fetch_failed", category: "api_error", filter: "short",
      request_id: id, status_code: 503,
    },
    { event: "entries_fetch_failed", category: "network", filter: "all" },
  ]);
});
