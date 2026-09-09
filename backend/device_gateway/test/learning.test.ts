import assert from "node:assert/strict";
import { test } from "node:test";

import { service } from "../src/learning.js";

test("service omits RequestInit.body for GET requests", async () => {
  const originalFetch = globalThis.fetch;
  let receivedInit: RequestInit | undefined;
  globalThis.fetch = async (_input, init) => {
    receivedInit = init;
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
  };

  try {
    await service("http://learning.test/state");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(receivedInit?.method, "GET");
  assert.equal(Object.hasOwn(receivedInit ?? {}, "body"), false);
});

test("service serializes supplied bodies for POST requests", async () => {
  const originalFetch = globalThis.fetch;
  let receivedInit: RequestInit | undefined;
  globalThis.fetch = async (_input, init) => {
    receivedInit = init;
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
  };

  try {
    await service("http://learning.test/direct", { turn_id: "turn-1" });
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(receivedInit?.method, "POST");
  assert.equal(receivedInit?.body, '{"turn_id":"turn-1"}');
});
