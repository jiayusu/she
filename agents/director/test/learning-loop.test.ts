import { test } from "node:test";
import assert from "node:assert/strict";
import { LearningDirector } from "../src/learning-director.ts";

test("assesses the preceding target with the help actually used, before selecting the next target", () => {
  const director = new LearningDirector();
  const first = director.direct({
    session_id: "loop-synthetic",
    utterance: "",
    detected_object: "milk",
    asr: 1,
  });
  const next = director.direct({
    session_id: "loop-synthetic",
    utterance: "I want milk.",
    detected_object: "apple",
    asr: 1,
  });
  assert.equal(next.assessment.target_reached, true);
  assert.equal(next.assessment.prompt_level_used, first.scaffold_level);
  assert.equal(next.assessment.spontaneous, false);
  assert.equal(next.target_expression, "I like apples.");
  assert.equal(next.learning_loop.assessed_target, first.target_expression);
});
test("first contact does not score a response against an unissued task", () => {
  const result = new LearningDirector().direct({
    session_id: "first",
    utterance: "I want milk.",
    detected_object: "milk",
    asr: 1,
  });
  assert.equal(result.assessment.target_reached, false);
  assert.equal(result.teaching_action.memory_policy, "no_write");
});
test("two unsuccessful replies stop repeated demands and switch to listening", () => {
  const director = new LearningDirector();
  const request = {
    session_id: "bounded",
    utterance: "",
    detected_object: "milk",
    asr: 1,
  };
  director.direct(request);
  assert.equal(
    director.direct(request).teaching_action.teaching_action,
    "prompt",
  );
  const result = director.direct(request);
  assert.equal(result.teaching_action.teaching_action, "pause");
  assert.equal(result.scaffold_level, 6);
  assert.equal(result.learning_loop.reason, "attempt_limit");
});
test("uncertain ASR neither counts as failure nor promotes evidence", () => {
  const director = new LearningDirector();
  director.direct({
    session_id: "uncertain",
    utterance: "",
    detected_object: "milk",
    asr: 1,
  });
  const result = director.direct({
    session_id: "uncertain",
    utterance: "I want milk.",
    asr: 0.2,
  });
  assert.equal(result.teaching_action.memory_policy, "no_write");
  assert.equal(result.learning_loop.failed_attempts, 0);
  assert.equal(result.learning_loop.reason, "uncertain_input");
});
test("session boundaries isolate prior targets", () => {
  const director = new LearningDirector();
  director.direct({
    session_id: "one",
    utterance: "",
    detected_object: "milk",
  });
  assert.equal(
    director.direct({ session_id: "two", utterance: "I want milk." })
      .learning_loop.assessed_target,
    null,
  );
});

import { existsSync } from "node:fs";
import { join } from "node:path";
import { makeTestApp } from "./util.ts";
import { listen } from "../src/server.ts";
import { LearningLoopHooks, LEARNING_STAGES } from "../src/learning-loop.ts";

test("paused sessions wait for voluntary clear input and never assess listening as a failed answer", () => {
  const director = new LearningDirector();
  const req = {
    session_id: "resume",
    utterance: "",
    detected_object: "milk",
    asr: 1,
  };
  director.direct(req);
  director.direct(req);
  director.direct(req);
  const listening = director.direct(req);
  assert.equal(listening.learning_loop.reason, "listening");
  assert.equal(listening.learning_loop.assessed_target, null);
  const resumed = director.direct({
    ...req,
    utterance: "water",
    detected_object: "water",
  });
  assert.equal(resumed.learning_loop.reason, "voluntary_resume");
  assert.equal(resumed.learning_loop.failed_attempts, 0);
  assert.equal(resumed.target_expression, "I want water.");
});
test("session expiry and capacity bound temporary state", () => {
  let now = 0;
  const director = new LearningDirector({
    now: () => now,
    sessionTtlMs: 10,
    maxSessions: 1,
  });
  director.direct({ session_id: "a", utterance: "", asr: 1 });
  now = 11;
  assert.equal(
    director.direct({ session_id: "a", utterance: "", asr: 1 }).learning_loop
      .reason,
    "first_contact",
  );
  director.direct({ session_id: "b", utterance: "", asr: 1 });
  assert.equal(
    director.direct({ session_id: "a", utterance: "", asr: 1 }).learning_loop
      .reason,
    "first_contact",
  );
});
test("lifecycle hooks enforce a finite ordered pipeline", () => {
  const hooks = new LearningLoopHooks();
  assert.throws(
    () => hooks.run("decision", () => true),
    /invalid_learning_stage_order/,
  );
  for (const stage of LEARNING_STAGES) hooks.run(stage, () => null);
  assert.throws(
    () => hooks.run("input", () => null),
    /invalid_learning_stage_order/,
  );
  const trace = hooks.finish({
    assessed_target: null,
    failed_attempts: 0,
    reason: "first_contact",
  });
  assert.deepEqual(trace.stages, LEARNING_STAGES);
  assert.equal(trace.memory_write, "not_performed");
});
test("emotion pause takes precedence and does not alter the supplied learner profile", () => {
  const director = new LearningDirector();
  const learner = { language_level: 3, mastery: { "I want milk.": "HEARD" } };
  director.direct({
    session_id: "emotion",
    utterance: "",
    detected_object: "milk",
    asr: 1,
  });
  const result = director.direct({
    session_id: "emotion",
    utterance: "I want milk.",
    emotion: -0.9,
    learner_state: learner,
    asr: 1,
  });
  assert.equal(result.teaching_action.teaching_action, "pause");
  assert.equal(result.teaching_action.memory_policy, "no_write");
  assert.deepEqual(result.ctx_bundle.learner_state, learner);
});
test("HTTP direct uses the loop, records only trace metadata and skips legacy raw learning files", async () => {
  const fixture = makeTestApp();
  const server = await listen(fixture.app, 0);
  try {
    const request = {
      session_id: "http-loop-synthetic",
      utterance: "",
      detected_object: "milk",
      asr: 1,
    };
    const response = await fetch(
      `http://127.0.0.1:${server.port}/agent/direct`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      },
    );
    assert.equal(response.status, 200);
    const body =
      (await response.json()) as import("../src/types.ts").DirectResponse;
    assert.deepEqual(body.learning_loop.stages, LEARNING_STAGES);
    assert.equal(body.learning_event_id, undefined);
    assert.equal(
      existsSync(join(fixture.dataDir, "learning-events.jsonl")),
      false,
    );
    const audit = fixture.app.audit.query({ type: "learning_loop" });
    assert.equal(audit.at(-1)?.detail?.operation, "learning_loop");
    assert.equal(JSON.stringify(audit).includes("utterance"), false);
  } finally {
    await server.close();
    fixture.dispose();
  }
});
