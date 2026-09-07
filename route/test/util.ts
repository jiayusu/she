import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { App } from '../src/app.ts';

export interface TestApp {
  app: App;
  dataDir: string;
  configDir: string;
  dispose(): void;
}

export function makeTestApp(opts: { storeFaults?: ConstructorParameters<typeof App>[0]['storeFaults'] } = {}): TestApp {
  const root = mkdtempSync(join(tmpdir(), 'route-test-'));
  const dataDir = join(root, 'data');
  const configDir = join(root, 'config');
  mkdirSync(configDir, { recursive: true });
  const app = new App({ dataDir, configDir, storeFaults: opts.storeFaults });
  return {
    app,
    dataDir,
    configDir,
    dispose() {
      app.shutdown();
      rmSync(root, { recursive: true, force: true });
    },
  };
}

export async function waitFor(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms));
}
