import { readFile } from "node:fs/promises";
import path from "node:path";

import { Ajv2020 } from "ajv/dist/2020.js";
import type { ErrorObject, ValidateFunction } from "ajv";


export interface ValidationResult {
  ok: boolean;
  errors: ErrorObject[];
}

type NamedValidator = (payload: unknown) => ValidationResult;

async function readJson(filePath: string): Promise<object> {
  return JSON.parse(await readFile(filePath, "utf8"));
}

function wrap(validate: ValidateFunction): NamedValidator {
  return (payload: unknown) => ({
    ok: Boolean(validate(payload)),
    errors: validate.errors ? [...validate.errors] : [],
  });
}

export class ContractValidators {
  private constructor(
    readonly deviceEvent: NamedValidator,
    readonly deviceCommand: NamedValidator,
    readonly dashboard: NamedValidator,
    readonly weeklyReport: NamedValidator,
    readonly parentConstraints: NamedValidator,
    readonly deviceSettings: NamedValidator,
    readonly rpgTurn: NamedValidator,
    readonly rpgDecision: NamedValidator,
    readonly rpgQuestSummary: NamedValidator,
  ) {}

  static async load(contractRoot: string): Promise<ContractValidators> {
    const ajv = new Ajv2020({ allErrors: true, strict: true });
    const compile = async (name: string) => ajv.compile(await readJson(path.join(contractRoot, name)));
    return new ContractValidators(
      wrap(await compile("device-event.schema.json")),
      wrap(await compile("device-command.schema.json")),
      wrap(await compile("dashboard-snapshot.schema.json")),
      wrap(await compile("weekly-report.schema.json")),
      wrap(await compile("parent-constraints.schema.json")),
      wrap(await compile("device-settings.schema.json")),
      wrap(await compile("rpg-turn.schema.json")),
      wrap(await compile("rpg-decision.schema.json")),
      wrap(await compile("rpg-quest-summary.schema.json")),
    );
  }
}

export function defaultContractRoot(): string {
  return path.resolve(import.meta.dirname, "../../../shared/contracts/v1");
}
