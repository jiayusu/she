import assert from "node:assert/strict";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { createGateway } from "../src/app.js";


const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const smokeScript = path.join(repositoryRoot, "clients", "hardware-rx5", "scripts", "gateway_smoke.py");
const contractRoot = path.join(repositoryRoot, "shared", "contracts", "v1");

async function waitFor(predicate: () => boolean, timeoutMs = 8_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error("smoke_timeout");
}

test("Python RX5 simulator completes the ordered gateway flow", { timeout: 10_000 }, async () => {
  const gateway = await createGateway({ host: "127.0.0.1", port: 0 });
  let child: ChildProcessWithoutNullStreams | undefined;
  let output = "";
  let errors = "";
  try {
    const processChild = spawn(process.env.PYTHON ?? "python", [
      smokeScript,
      "--url", `${gateway.wsUrl}/v1/device/session`,
      "--device-id", "rx5-e2e-001",
    ], {
      env: { ...process.env, SHE_CONTRACT_ROOT: contractRoot },
      stdio: ["pipe", "pipe", "pipe"],
    });
    child = processChild;
    processChild.stdin.end();
    processChild.stdout.on("data", (chunk) => { output += chunk.toString(); });
    processChild.stderr.on("data", (chunk) => { errors += chunk.toString(); });

    await waitFor(() => gateway.sessions.snapshot("rx5-e2e-001")?.online === true);
    gateway.sessions.sendCommand("rx5-e2e-001", { type: "capture", payload: { window_ms: 300 } });
    gateway.sessions.sendCommand("rx5-e2e-001", { type: "speak", payload: { text: "Open!" } });

    await waitFor(() => {
      const snapshot = gateway.sessions.snapshot("rx5-e2e-001");
      return snapshot?.acceptedEvents === 5 && snapshot.pendingCommands === 0;
    });
    const exitCode = await new Promise<number | null>((resolve) => processChild.once("exit", resolve));

    assert.equal(exitCode, 0, errors);
    assert.deepEqual(gateway.sessions.snapshot("rx5-e2e-001")?.acceptedEventTypes, [
      "hello", "wake", "pointing", "command_ack", "command_ack",
    ]);
    assert.match(output, /"type": "command_ack"/);
    assert.doesNotMatch(output + errors, /Open!|utterance|audio|image|token/);
  } finally {
    if (child && child.exitCode === null) child.kill();
    await gateway.close();
  }
});
