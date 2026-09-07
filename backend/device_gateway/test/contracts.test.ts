import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { ContractValidators } from "../src/contracts.js";


const contractRoot = path.resolve(import.meta.dirname, "../../../shared/contracts/v1");

test("gateway validates canonical device fixtures", async () => {
  const validators = await ContractValidators.load(contractRoot);
  const valid = JSON.parse(await readFile(path.join(contractRoot, "fixtures/valid/device-event.json"), "utf8"));
  const invalid = JSON.parse(await readFile(path.join(contractRoot, "fixtures/invalid/device-event-unknown-type.json"), "utf8"));

  assert.equal(validators.deviceEvent(valid).ok, true);
  assert.equal(validators.deviceEvent(invalid).ok, false);
});
